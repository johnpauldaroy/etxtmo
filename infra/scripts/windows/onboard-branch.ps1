<#
.SYNOPSIS
    Onboards any branch's modem PC against production, without needing to
    know the branch's UUID ahead of time.

.DESCRIPTION
    Looks up the branch by code via the production API, then delegates to
    bootstrap-branch.ps1 (downloads the branch-agent package, sets up the
    venv, detects the modem, configures Gammu SMSD, creates the branch's
    API user, and installs both as Windows services).

    Run this once per branch PC, as Administrator, with the modem plugged in.

.EXAMPLE
    .\onboard-branch.ps1 -BranchCode 002 -AgentApiUsername branch-agent-002
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$BranchCode,
    [Parameter(Mandatory = $true)][string]$AgentApiUsername,

    [string]$ApiBaseUrl = "https://etxtmo.barbazampc.cloud",
    [string]$AdminUsername = "jp",
    [string]$ComPort
)

$ErrorActionPreference = "Stop"

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }

Write-Host "==> Logging in as $AdminUsername against $ApiBaseUrl" -ForegroundColor Cyan
$AdminPassword = Read-Host "Admin password for $AdminUsername" -AsSecureString
$AdminPasswordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($AdminPassword)
)

$loginBody = @{ username = $AdminUsername; password = $AdminPasswordPlain } | ConvertTo-Json
$login = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/api/auth/login" -ContentType "application/json" -Body $loginBody
$headers = @{ Authorization = "Bearer $($login.access_token)" }

Write-Host "==> Looking up branch code $BranchCode" -ForegroundColor Cyan
$branches = Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/admin/branches" -Headers $headers
$branch = $branches | Where-Object { $_.code -eq $BranchCode }
if (-not $branch) {
    throw "No branch found with code '$BranchCode'. Existing codes: $(($branches | ForEach-Object { $_.code }) -join ', '). Create it first: Administration -> Branches -> Add branch."
}
Write-Host "Found branch: $($branch.code) - $($branch.name) ($($branch.id))" -ForegroundColor Green

Write-Host "==> Setting a password for $AgentApiUsername" -ForegroundColor Cyan
$AgentPassword = Read-Host "New password for $AgentApiUsername" -AsSecureString
$AgentPasswordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($AgentPassword)
)

$bootstrapArgs = @{
    BranchCode    = $BranchCode
    BranchName    = $branch.name
    BranchId      = $branch.id
    ApiBaseUrl    = $ApiBaseUrl
    ApiUsername   = $AgentApiUsername
    ApiPassword   = $AgentPasswordPlain
    CreateApiUser = $true
    AdminUsername = $AdminUsername
    AdminPassword = $AdminPasswordPlain
}
if ($ComPort) { $bootstrapArgs["ComPort"] = $ComPort }

& (Join-Path $scriptDir "bootstrap-branch.ps1") @bootstrapArgs
