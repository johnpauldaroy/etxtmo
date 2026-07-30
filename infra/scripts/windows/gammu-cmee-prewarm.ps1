<#
.SYNOPSIS
    Sends AT+CMEE=1 to a modem before starting its gammu-smsd service.

.DESCRIPTION
    Some modems (confirmed: a Wavecom MULTIBAND 900E 1800, firmware
    652a09gg.Q2406B) answer AT+CGSN and AT+CUSD fine but reject every
    SIM-touching command -- AT+CPIN?, AT+CIMI, AT+CPMS, AT+CSCA -- with a
    bare "ERROR" until AT+CMEE=1 (verbose CME error reporting) has been set
    on the current connection. Gammu's own init sequence does attempt
    AT+CMEE=1, but on this hardware it does not take effect, so gammu-smsd
    then reports a cascade of misleading downstream failures:

        Error getting SMS status: Unknown error. (UNKNOWN[27])
        Error getting SMSC from phone
        Error sending SMS: No SMSC number given ... (EMPTYSMSC[31])

    All three are symptoms of the same cause. Sending AT+CMEE=1 once on a
    fresh connection makes CPIN?/CIMI/CPMS/CSCA all succeed -- verified by
    raw serial probe, where AT+CSCA? then returned the SIM's real, correctly
    stored SMSC. So do NOT "fix" EMPTYSMSC by hardcoding an SMSC= line in
    smsdrc; the SIM's own SMSC is fine and a hardcoded guess would route
    messages through the wrong SMS centre.

    CMEE is a per-connection setting, not stored on the SIM, so it must be
    re-sent every time the service (re)starts -- hence this wrapper rather
    than a one-off manual command.

    Wire it in by pointing NSSM at this script instead of gammu-smsd.exe.
    NSSM's own CLI re-tokenises AppParameters and mangles quoted paths
    containing spaces, so pass a .cmd shim (with the paths baked in) as
    Application and leave AppParameters empty -- see setup-branch-agent.ps1,
    which generates that shim automatically.

.NOTES
    Harmless on modems that don't need it: a modem that already handles
    CMEE correctly just answers OK and nothing changes.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ComPort,
    [Parameter(Mandatory = $true)][string]$GammuSmsdExe,
    [Parameter(Mandatory = $true)][string]$SmsdrcPath,
    [int]$BaudRate = 115200,
    [int]$PortWaitSeconds = 30
)

$ErrorActionPreference = "Stop"

function Send-CmeePrewarm {
    param([string]$Port, [int]$Baud)

    $serial = New-Object System.IO.Ports.SerialPort $Port, $Baud, ([System.IO.Ports.Parity]::None), 8, ([System.IO.Ports.StopBits]::One)
    try {
        $serial.ReadTimeout = 3000
        $serial.WriteTimeout = 3000
        $serial.Handshake = [System.IO.Ports.Handshake]::None
        $serial.DtrEnable = $true
        $serial.RtsEnable = $true
        $serial.Open()
        Start-Sleep -Milliseconds 300
        $serial.DiscardInBuffer()
        $serial.Write("AT+CMEE=1`r`n")
        Start-Sleep -Milliseconds 500
        $response = $serial.ReadExisting()
        return $response -match "OK"
    } catch {
        # "Access to the port is denied" is expected and transient on a
        # service restart: the previous gammu-smsd may still be releasing
        # the port. Report it so the retry loop can wait it out.
        Write-Host "  $ComPort not ready yet: $($_.Exception.Message)"
        return $false
    } finally {
        if ($serial.IsOpen) { $serial.Close() }
    }
}

Write-Host "==> Pre-warming $ComPort with AT+CMEE=1 before starting gammu-smsd"

# Retry rather than giving up on the first failure: on a service restart the
# outgoing gammu-smsd can hold the port for a few seconds, and starting
# gammu-smsd without a successful pre-warm puts this modem straight back
# into the UNKNOWN[27]/EMPTYSMSC[31] failure loop.
$ok = $false
$deadline = (Get-Date).AddSeconds($PortWaitSeconds)
do {
    $ok = Send-CmeePrewarm -Port $ComPort -Baud $BaudRate
    if (-not $ok) { Start-Sleep -Seconds 2 }
} while (-not $ok -and (Get-Date) -lt $deadline)

if ($ok) {
    Write-Host "CMEE pre-warm succeeded." -ForegroundColor Green
} else {
    Write-Warning "CMEE pre-warm did not succeed within $PortWaitSeconds s; starting gammu-smsd anyway."
}

# NSSM manages this script's own process lifetime as the service. Plain
# "gammu-smsd -c <config>" with none of the service flags (-i/-s/-S/-u/-e)
# already blocks in the foreground running the send/receive loop directly
# -- that's exactly what a child of this script should do, so this script's
# exit (if gammu-smsd ever exits) ends the NSSM service too.
& $GammuSmsdExe -c $SmsdrcPath
exit $LASTEXITCODE
