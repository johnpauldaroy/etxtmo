<#
.SYNOPSIS
    Sets up a branch PC's GSM modem end-to-end with no git clone required.

.DESCRIPTION
    Downloads the standalone branch-agent package from this repo's GitHub
    Release, extracts it, creates the Python virtualenv, then runs
    setup-branch-agent.ps1 to detect the modem, configure Gammu SMSD,
    create the branch's API user, and install both as Windows services.

    Prerequisites on this PC: Python 3.12+ on PATH, Gammu installed, the
    GSM modem plugged in.

.EXAMPLE
    .\bootstrap-branch.ps1 -BranchCode 002 -BranchName "Culasi Branch" `
        -BranchId 37f1b734-81fd-4329-8e79-1d16efbe8439 `
        -ApiBaseUrl https://etxtmo.barbazampc.cloud `
        -ApiUsername branch-agent-002 -ApiPassword "Str0ngPass!" `
        -CreateApiUser -AdminUsername jp -AdminPassword "..."
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
    [string]$GammuPath = "C:\Program Files\Gammu 1.42.0",

    [switch]$CreateApiUser,
    [string]$AdminUsername,
    [string]$AdminPassword,

    [string]$InstallRoot = "C:\etxtmo-branch-agent",
    [string]$PackageUrl = "https://etxtmo.barbazampc.cloud/downloads/branch-agent.zip"
)

$ErrorActionPreference = "Stop"

function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "This script must be run as Administrator (needed to install Windows services)."
    }
}

function Assert-Command([string]$Name, [string]$Hint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name not found on PATH. $Hint"
    }
}

Assert-Admin
Assert-Command "python" "Install Python 3.12+ from python.org and ensure it's added to PATH."

Write-Host "==> Downloading branch-agent package" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
$zipPath = Join-Path $InstallRoot "branch-agent.zip"
Invoke-WebRequest -Uri $PackageUrl -OutFile $zipPath -UseBasicParsing
Expand-Archive -Path $zipPath -DestinationPath $InstallRoot -Force
Remove-Item $zipPath -Force
Write-Host "Extracted to $InstallRoot" -ForegroundColor Green

$branchAgentDir = Join-Path $InstallRoot "branch-agent"
if (-not (Test-Path (Join-Path $branchAgentDir "agent\main.py"))) {
    throw "Package extraction looks wrong: agent\main.py not found under $branchAgentDir."
}

Write-Host "==> Setting up Python virtualenv" -ForegroundColor Cyan
& python -m venv (Join-Path $branchAgentDir ".venv")
& (Join-Path $branchAgentDir ".venv\Scripts\pip.exe") install --quiet -r (Join-Path $branchAgentDir "requirements.txt")
Write-Host "Virtualenv ready." -ForegroundColor Green

Write-Host "==> Running branch setup" -ForegroundColor Cyan
$setupScript = Join-Path $InstallRoot "scripts\setup-branch-agent.ps1"
if (-not (Test-Path $setupScript)) {
    throw "setup-branch-agent.ps1 not found in the downloaded package at $setupScript."
}

$setupArgs = @{
    BranchCode  = $BranchCode
    BranchName  = $BranchName
    BranchId    = $BranchId
    ApiBaseUrl  = $ApiBaseUrl
    ApiUsername = $ApiUsername
    ApiPassword = $ApiPassword
    BaudRate    = $BaudRate
    GammuPath   = $GammuPath
    RepoRoot    = $InstallRoot
}
if ($ComPort) { $setupArgs["ComPort"] = $ComPort }
if ($CreateApiUser) {
    $setupArgs["CreateApiUser"] = $true
    $setupArgs["AdminUsername"] = $AdminUsername
    $setupArgs["AdminPassword"] = $AdminPassword
}

& $setupScript @setupArgs
