<#
.SYNOPSIS
    Sends AT+CMEE=1 to a modem before starting its gammu-smsd service.

.DESCRIPTION
    Some modems (confirmed: a Wavecom MULTIBAND 900E 1800) reject CIMI/CPIN/
    CPMS/CSCA -- and therefore fail SIM reads, SMS storage negotiation, and
    SMSC lookup -- unless AT+CMEE=1 (verbose CME error reporting) has been
    set on the current connection first. Gammu's own init sequence already
    attempts this, but on this hardware the attempt does not take effect
    reliably, and CMEE mode does not persist across a service restart or
    reboot (this is a per-connection modem setting, not stored on the SIM).

    Wire this in front of gammu-smsd by pointing NSSM at this script instead
    of gammu-smsd.exe directly:

        nssm set GammuSMSD-<code> Application powershell.exe
        nssm set GammuSMSD-<code> AppParameters '-NoProfile -ExecutionPolicy Bypass -File "C:\path\to\gammu-cmee-prewarm.ps1" -ComPort COM3 -GammuSmsdExe "C:\Program Files\Gammu 1.42.0\bin\gammu-smsd.exe" -SmsdrcPath "C:\etxtmo-branch-agent\branch-agent\gammu-config-008\smsdrc"'

.NOTES
    Only needed for modems that show "Error getting SMS status. Unknown
    error. (UNKNOWN[27])" or "No SMSC number given (EMPTYSMSC[31])" despite
    a healthy port/baud connection. Most branches do not need this.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ComPort,
    [Parameter(Mandatory = $true)][string]$GammuSmsdExe,
    [Parameter(Mandatory = $true)][string]$SmsdrcPath,
    [int]$BaudRate = 115200
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
        Write-Warning "CMEE pre-warm failed to open $Port at $Baud baud: $_"
        return $false
    } finally {
        if ($serial.IsOpen) { $serial.Close() }
    }
}

Write-Host "==> Pre-warming $ComPort with AT+CMEE=1 before starting gammu-smsd"
$ok = Send-CmeePrewarm -Port $ComPort -Baud $BaudRate
if ($ok) {
    Write-Host "CMEE pre-warm succeeded." -ForegroundColor Green
} else {
    Write-Warning "CMEE pre-warm did not get an OK response; starting gammu-smsd anyway."
}

# NSSM manages this script's own process lifetime as the service. Plain
# "gammu-smsd -c <config>" with none of the service flags (-i/-s/-S/-u/-e)
# already blocks in the foreground running the send/receive loop directly
# -- that's exactly what a child of this script should do, so this script's
# exit (if gammu-smsd ever exits) ends the NSSM service too.
& $GammuSmsdExe -c $SmsdrcPath
exit $LASTEXITCODE
