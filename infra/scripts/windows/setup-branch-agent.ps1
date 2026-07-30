<#
.SYNOPSIS
    One-time setup for a branch PC: detects the GSM modem, configures Gammu SMSD
    and branch-agent, and installs both as Windows services.

.DESCRIPTION
    Run this once on each branch's PC, with the GSM modem already plugged in.
    It will:
      1. List available COM ports and let you pick the modem's port (or accept -ComPort).
      2. Probe the port with AT commands (DTR/RTS enabled) to confirm the modem responds.
      3. Write gammu-config\smsdrc and branch-agent\.env for this branch.
      4. Remove any previous copies of both services and kill stray
         gammu-smsd processes (a leftover one holding the COM port makes
         every subsequent start fail with DEVICEBUSY).
      5. Install gammu-smsd and branch-agent as Windows services (auto-start
         on boot), both wrapped with NSSM (downloaded automatically if
         missing). gammu-smsd runs behind gammu-cmee-prewarm.ps1 -- see the
         service-install section for why.
      6. Optionally create the branch's scoped API user via -CreateApiUser.

    Modem quirks this handles automatically, learned from real branch
    installs (all three produce confusing, misleading errors otherwise):
      - "device = comN:" needs the trailing colon on Windows, or the port
        fails to open with bogus "device speed"/"DEVICEBUSY" errors.
      - "connection = at<baud>" pins the speed; bare "at" auto-negotiation
        fails on some USB-to-serial adapters (e.g. Prolific PL2303).
      - Some modems (Wavecom MULTIBAND 900E 1800) reject every SIM-touching
        AT command until AT+CMEE=1 is sent on the connection, surfacing as
        UNKNOWN[27] / "Error getting SMSC" / EMPTYSMSC[31].

.EXAMPLE
    .\setup-branch-agent.ps1 -BranchCode 003 -BranchName "Culasi Branch" `
        -BranchId 37f1b734-81fd-4329-8e79-1d16efbe8439 `
        -ApiBaseUrl https://textkonek.example.com `
        -ApiUsername branch-agent-003 -ApiPassword "Str0ngPass!" `
        -GammuPath "C:\Program Files\Gammu 1.42.0"

.NOTES
    Must be run as Administrator (creates Windows services).
    Each branch PC needs its own copy of the `branch-agent` folder from this repo.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$BranchCode,
    [Parameter(Mandatory = $true)][string]$BranchName,
    [Parameter(Mandatory = $true)][string]$BranchId,
    [Parameter(Mandatory = $true)][string]$ApiBaseUrl,
    [Parameter(Mandatory = $true)][string]$ApiUsername,
    [Parameter(Mandatory = $true)][string]$ApiPassword,

    [string]$ComPort,
    [int]$BaudRate = 115200,
    [string]$ModemName,
    [string]$NodeName,

    [string]$RepoRoot,
    [string]$GammuPath = "C:\Program Files\Gammu 1.42.0",
    [string]$NssmPath,

    [switch]$CreateApiUser,
    [string]$AdminUsername,
    [string]$AdminPassword,
    [string]$ApiUserEmail,
    [string]$ApiUserFullName,

    [switch]$SkipServiceInstall
)

$ErrorActionPreference = "Stop"

function Write-Step($message) {
    Write-Host ""
    Write-Host "==> $message" -ForegroundColor Cyan
}

function Set-ContentNoBom([string]$Path, [string]$Content) {
    # Windows PowerShell 5.1's `Set-Content -Encoding UTF8` always writes a
    # BOM, which breaks tools that read these files as plain UTF-8 (e.g.
    # pydantic-settings sees a "﻿API_BASE_URL" key instead of
    # "API_BASE_URL" and rejects it as an unknown field).
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "This script must be run as Administrator (needed to install Windows services)."
    }
}

function Get-CandidateComPorts {
    Get-PnpDevice -Class Ports -Status OK -ErrorAction SilentlyContinue |
        Where-Object { $_.FriendlyName -match "\(COM\d+\)" } |
        ForEach-Object {
            if ($_.FriendlyName -match "\((COM\d+)\)") {
                [PSCustomObject]@{ Port = $Matches[1]; Description = $_.FriendlyName }
            }
        }
}

function Test-ModemPort([string]$Port, [int]$Baud) {
    $serial = New-Object System.IO.Ports.SerialPort $Port, $Baud, ([System.IO.Ports.Parity]::None), 8, ([System.IO.Ports.StopBits]::One)
    try {
        $serial.ReadTimeout = 3000
        $serial.WriteTimeout = 3000
        $serial.NewLine = "`r`n"
        $serial.Handshake = [System.IO.Ports.Handshake]::None
        $serial.DtrEnable = $true
        $serial.RtsEnable = $true
        $serial.Open()
        Start-Sleep -Milliseconds 300
        $serial.DiscardInBuffer()
        $serial.Write("ATI`r`n")
        Start-Sleep -Milliseconds 800
        $response = $serial.ReadExisting()
        return $response
    } catch {
        return $null
    } finally {
        if ($serial.IsOpen) { $serial.Close() }
    }
}

function Get-Nssm([string]$ExplicitPath, [string]$InstallRoot) {
    if ($ExplicitPath -and (Test-Path $ExplicitPath)) {
        return $ExplicitPath
    }

    $existing = Get-Command nssm.exe -ErrorAction SilentlyContinue
    if ($existing) {
        return $existing.Source
    }

    $arch = if ([Environment]::Is64BitOperatingSystem) { "win64" } else { "win32" }
    $nssmDir = Join-Path $InstallRoot "nssm-2.24"
    $nssmExe = Join-Path $nssmDir "$arch\nssm.exe"
    if (Test-Path $nssmExe) {
        return $nssmExe
    }

    Write-Host "NSSM not found locally; downloading from nssm.cc ..." -ForegroundColor Yellow
    $zipPath = Join-Path $InstallRoot "nssm-2.24.zip"
    New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
    Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile $zipPath -UseBasicParsing
    Expand-Archive -Path $zipPath -DestinationPath $InstallRoot -Force
    Remove-Item $zipPath -Force

    if (-not (Test-Path $nssmExe)) {
        throw "NSSM download/extract failed; expected $nssmExe. Download manually from https://nssm.cc/download and pass -NssmPath."
    }
    return $nssmExe
}

# ---------------------------------------------------------------------------
Assert-Admin

if (-not $RepoRoot) {
    $scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
    $RepoRoot = (Resolve-Path (Join-Path $scriptDir "..\..\..")).Path
}

Write-Step "Branch: $BranchCode - $BranchName ($BranchId)"
Write-Host "Repo root: $RepoRoot"

if (-not $NodeName) { $NodeName = "branch-$($BranchCode.ToLower())-node-01" }
if (-not $ModemName) { $ModemName = "modem-$($BranchCode.ToLower())" }

# ---------------------------------------------------------------------------
Write-Step "Detecting candidate COM ports"

$candidates = Get-CandidateComPorts
if ($candidates) {
    $candidates | Format-Table -AutoSize | Out-String | Write-Host
} else {
    Write-Host "No serial COM ports detected via Get-PnpDevice." -ForegroundColor Yellow
}

if (-not $ComPort) {
    if ($candidates.Count -eq 1) {
        $ComPort = $candidates[0].Port
        Write-Host "Auto-selected the only candidate port: $ComPort"
    } else {
        $ComPort = Read-Host "Enter the modem's COM port (e.g. COM11)"
    }
}

# ---------------------------------------------------------------------------
Write-Step "Probing $ComPort at $BaudRate baud (AT command)"

$response = Test-ModemPort -Port $ComPort -Baud $BaudRate
if (-not $response -or $response -notmatch "OK") {
    Write-Host "No valid AT response from $ComPort at $BaudRate baud." -ForegroundColor Red
    Write-Host "Response received: [$response]"
    Write-Host "Check: modem power, SIM inserted, antenna attached, correct port, correct baud rate." -ForegroundColor Yellow
    $proceed = Read-Host "Continue setup anyway? (y/N)"
    if ($proceed -ne "y") { throw "Aborted: modem did not respond." }
} else {
    Write-Host "Modem responded on $ComPort." -ForegroundColor Green
    Write-Host ($response.Trim())
}

# ---------------------------------------------------------------------------
Write-Step "Reading modem identity via Gammu"

$gammuExe = Join-Path $GammuPath "bin\gammu.exe"
$smsdExe = Join-Path $GammuPath "bin\gammu-smsd.exe"
if (-not (Test-Path $gammuExe)) {
    throw "gammu.exe not found at $gammuExe. Install Gammu or pass -GammuPath."
}

$brandDir = Join-Path $RepoRoot "branch-agent\gammu-config-$BranchCode"
New-Item -ItemType Directory -Force -Path $brandDir | Out-Null
$spoolRoot = Join-Path $brandDir "spool"
foreach ($sub in "inbox", "outbox", "sent", "error") {
    New-Item -ItemType Directory -Force -Path (Join-Path $spoolRoot $sub) | Out-Null
}

# Gammu's Windows serial backend needs the trailing colon ("com3:", as in
# Gammu's own documented examples). Without it, opening the port fails in a
# way that surfaces as misleading "Error setting device speed" /
# "already opened by another app (DEVICEBUSY)" errors even when the port is
# free and the modem is healthy. Also pin the baud rate explicitly: bare
# "connection = at" makes Gammu auto-negotiate, which fails on some
# USB-to-serial adapters (e.g. Prolific PL2303) that a fixed
# "at<baud>" handles fine.
$devicePath = ($ComPort.TrimEnd(':')).ToLower() + ':'
$connection = "at$BaudRate"

$gammurcPath = Join-Path $brandDir "gammurc"
$gammurcContent = @"
[gammu]
device = $devicePath
connection = $connection
"@
Set-ContentNoBom -Path $gammurcPath -Content $gammurcContent

$identity = & $gammuExe -c $gammurcPath identify 2>&1
Write-Host $identity

# ---------------------------------------------------------------------------
Write-Step "Writing gammu-smsd config (smsdrc)"

$smsdLogPath = Join-Path $brandDir "smsd.log"
$smsdrcPath = Join-Path $brandDir "smsdrc"
$smsdrcContent = @"
[gammu]
device = $devicePath
connection = $connection

[smsd]
service = files
logfile = $smsdLogPath
debuglevel = 1
commtimeout = 30
sendtimeout = 30
outboxformat = standard
transmitformat = auto

inboxpath = $spoolRoot\inbox\
outboxpath = $spoolRoot\outbox\
sentsmspath = $spoolRoot\sent\
errorsmspath = $spoolRoot\error\
"@
Set-ContentNoBom -Path $smsdrcPath -Content $smsdrcContent

Write-Host "Wrote $smsdrcPath"

# ---------------------------------------------------------------------------
Write-Step "Writing branch-agent\.env"

$branchAgentDir = Join-Path $RepoRoot "branch-agent"
if (-not (Test-Path (Join-Path $branchAgentDir "agent\main.py"))) {
    throw "branch-agent\agent\main.py not found under $RepoRoot. Pass -RepoRoot to the correct location."
}

# Each branch PC has its own checkout of this repo, so .env here always
# belongs to exactly one branch -- no per-branch suffix needed.
$envPath = Join-Path $branchAgentDir ".env"
if (Test-Path $envPath) {
    $backupPath = Join-Path $branchAgentDir (".env.bak-{0}" -f (Get-Date -Format "yyyyMMddHHmmss"))
    Copy-Item -Path $envPath -Destination $backupPath
    Write-Host "Existing .env backed up to $backupPath" -ForegroundColor Yellow
}
$envContent = @"
API_BASE_URL=$ApiBaseUrl
API_USERNAME=$ApiUsername
API_PASSWORD=$ApiPassword
BRANCH_ID=$BranchId
NODE_NAME=$NodeName
MODEM_NAME=$ModemName
MODEM_PORT=$ComPort
POLL_INTERVAL_SECONDS=10
HEARTBEAT_INTERVAL_SECONDS=30
GAMMU_OUTBOX_PATH=$spoolRoot\outbox
GAMMU_SENT_PATH=$spoolRoot\sent
GAMMU_ERROR_PATH=$spoolRoot\error
GAMMU_INBOX_PATH=$spoolRoot\inbox
GAMMU_CURSOR_DB_PATH=$brandDir\agent-cursor.sqlite
SMSD_LOG_PATH=$smsdLogPath
MODEM_CHECK_INTERVAL_SECONDS=60
SMSD_LOG_STALE_AFTER_SECONDS=120
"@
Set-ContentNoBom -Path $envPath -Content $envContent

Write-Host "Wrote $envPath"

# ---------------------------------------------------------------------------
if ($CreateApiUser) {
    Write-Step "Creating scoped API user for this branch"
    if (-not $AdminUsername -or -not $AdminPassword) {
        throw "-CreateApiUser requires -AdminUsername and -AdminPassword (a superuser account)."
    }
    $loginBody = @{ username = $AdminUsername; password = $AdminPassword } | ConvertTo-Json
    $login = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/api/auth/login" -ContentType "application/json" -Body $loginBody
    $headers = @{ Authorization = "Bearer $($login.access_token)" }

    $userBody = @{
        email     = if ($ApiUserEmail) { $ApiUserEmail } else { "$ApiUsername@barbazampc.coop" }
        username  = $ApiUsername
        full_name = if ($ApiUserFullName) { $ApiUserFullName } else { "Branch Agent - $BranchName" }
        password  = $ApiPassword
        is_superuser = $false
        branch_id = $BranchId
    } | ConvertTo-Json
    # Re-running setup on an already-onboarded PC is the normal way to apply
    # config fixes, so an existing user must not abort the run before the
    # services are (re)installed. The agent keeps using the password already
    # in .env; this step only matters on a first install.
    try {
        $newUser = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/api/auth/users" -ContentType "application/json" -Headers $headers -Body $userBody
        Write-Host "Created user $($newUser.username) ($($newUser.id)), assigned to branch $BranchId"
    } catch {
        $detail = ""
        if ($_.Exception.Response) {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $detail = $reader.ReadToEnd()
            $reader.Close()
        }
        if ($detail -match "already exists") {
            Write-Host "User $ApiUsername already exists; keeping it and continuing." -ForegroundColor Yellow
            Write-Host "  If its password differs from what you just entered, reset it in Administration -> Users." -ForegroundColor Yellow
        } else {
            throw
        }
    }
}

# ---------------------------------------------------------------------------
if (-not $SkipServiceInstall) {
    $smsdServiceName = "GammuSMSD-$BranchCode"
    $agentServiceName = "TextKonekBranchAgent-$BranchCode"

    # A plain Python process does not implement the Windows Service Control
    # API, so `sc create` cannot manage it directly (it would fail to start
    # with error 1053). NSSM wraps any console app as a proper service --
    # used for both services here (see the gammu-smsd note below).
    $nssmExe = Get-Nssm -ExplicitPath $NssmPath -InstallRoot (Join-Path $RepoRoot "infra\scripts\windows\tools")

    Write-Step "Removing any previous services and stray processes"

    # Stop/remove both services regardless of how they were registered
    # before (gammu-smsd's own -i registration, or NSSM), then kill leftover
    # processes. A gammu-smsd left holding the COM port makes every
    # subsequent start fail with DEVICEBUSY, and orphans accumulate quickly
    # across repeated setup attempts.
    foreach ($svc in @($smsdServiceName, $agentServiceName)) {
        try { Stop-Service $svc -Force -ErrorAction Stop } catch { }
        try { & $nssmExe stop $svc 2>&1 | Out-Null } catch { }
        try { & $nssmExe remove $svc confirm 2>&1 | Out-Null } catch { }
    }
    # gammu-smsd's own service registration, if this PC was set up before
    # this script switched to the NSSM wrapper. Expected to "fail" with
    # error 1060 (no such service) on a first-time run.
    try { & $smsdExe -u -n $smsdServiceName 2>&1 | Out-Null } catch { }
    Get-Process -Name "gammu-smsd" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2

    Write-Step "Installing gammu-smsd as a Windows service (via NSSM + CMEE pre-warm)"

    # gammu-smsd is deliberately NOT registered with its own `-i` flag.
    # Some modems (confirmed: Wavecom MULTIBAND 900E 1800) reject every
    # SIM-touching AT command until AT+CMEE=1 has been sent on the
    # connection, which gammu-smsd cannot be configured to do -- so it runs
    # behind gammu-cmee-prewarm.ps1, which sends that first and then execs
    # gammu-smsd in the foreground. Harmless on modems that don't need it.
    #
    # NSSM's CLI re-tokenises AppParameters and mangles quoted paths
    # containing spaces (e.g. "C:\Program Files\Gammu 1.42.0\..."), so the
    # arguments are baked into a .cmd shim and AppParameters is left empty.
    # Sits next to this script in the downloadable branch-agent package
    # (scripts\), or under infra\scripts\windows\ in a full repo checkout.
    $prewarmScript = $null
    foreach ($candidate in @(
        (Join-Path $PSScriptRoot "gammu-cmee-prewarm.ps1"),
        (Join-Path $RepoRoot "scripts\gammu-cmee-prewarm.ps1"),
        (Join-Path $RepoRoot "infra\scripts\windows\gammu-cmee-prewarm.ps1")
    )) {
        if ($candidate -and (Test-Path $candidate)) { $prewarmScript = (Resolve-Path $candidate).Path; break }
    }
    if (-not $prewarmScript) {
        throw "gammu-cmee-prewarm.ps1 not found next to this script, or under scripts\ / infra\scripts\windows\ in $RepoRoot."
    }
    $smsdShimPath = Join-Path $brandDir "start-gammu-smsd.cmd"
    $smsdShimContent = @"
@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$prewarmScript" -ComPort $ComPort -BaudRate $BaudRate -GammuSmsdExe "$smsdExe" -SmsdrcPath "$smsdrcPath"
"@
    Set-ContentNoBom -Path $smsdShimPath -Content $smsdShimContent

    & $nssmExe install $smsdServiceName $smsdShimPath
    & $nssmExe set $smsdServiceName DisplayName "Gammu SMSD ($BranchCode)"
    & $nssmExe set $smsdServiceName Start SERVICE_AUTO_START
    & $nssmExe set $smsdServiceName AppExit Default Restart
    & $nssmExe set $smsdServiceName AppRestartDelay 10000
    & $nssmExe set $smsdServiceName AppStdout (Join-Path $brandDir "gammu-smsd.out.log")
    & $nssmExe set $smsdServiceName AppStderr (Join-Path $brandDir "gammu-smsd.err.log")
    & $nssmExe start $smsdServiceName
    Write-Host "Installed and started service: $smsdServiceName" -ForegroundColor Green

    Write-Step "Installing branch-agent as a Windows service (via NSSM)"

    $pythonExe = Join-Path $branchAgentDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $pythonExe)) {
        throw "branch-agent virtualenv not found at $pythonExe. Run 'python -m venv .venv; pip install -r requirements.txt' in $branchAgentDir first."
    }
    & $nssmExe install $agentServiceName $pythonExe "-m agent.main"
    & $nssmExe set $agentServiceName AppDirectory $branchAgentDir
    & $nssmExe set $agentServiceName DisplayName "TextKonek Branch Agent ($BranchCode)"
    & $nssmExe set $agentServiceName Start SERVICE_AUTO_START
    & $nssmExe set $agentServiceName AppExit Default Restart
    & $nssmExe set $agentServiceName AppRestartDelay 10000
    & $nssmExe set $agentServiceName AppStdout (Join-Path $brandDir "branch-agent.out.log")
    & $nssmExe set $agentServiceName AppStderr (Join-Path $brandDir "branch-agent.err.log")
    & $nssmExe start $agentServiceName

    Write-Host "Installed and started service: $agentServiceName" -ForegroundColor Green
} else {
    Write-Step "Skipped service install (-SkipServiceInstall)"
}

Write-Step "Setup complete for branch $BranchCode"
Write-Host "Config folder: $brandDir"
Write-Host "Env file:      $envPath  (copy to branch-agent\.env, then start the services)"
