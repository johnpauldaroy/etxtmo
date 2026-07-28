<#
.SYNOPSIS
    One-off onboarding for Branch 001 (Barbaza Main) against production.

.DESCRIPTION
    Looks up the branch by code "001" via the production API, then delegates
    to setup-branch-agent.ps1 to detect the modem, configure Gammu SMSD,
    create the branch-agent API user, and install both as Windows services.

    Run this once, as Administrator, with the modem plugged into COM11
    (or let it auto-detect).

.NOTES
    Prompts for the admin password interactively -- it is not hard-coded
    here since this file may end up committed to the repo.
#>

[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "https://etxtmo.barbazampc.cloud",
    [string]$AdminUsername = "jp",
    [string]$BranchCode = "001",
    [string]$AgentApiUsername = "branch-agent-001",
    [string]$ComPort = "COM11"
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
    throw "No branch found with code '$BranchCode'. Existing codes: $(($branches | ForEach-Object { $_.code }) -join ', ')"
}
Write-Host "Found branch: $($branch.code) - $($branch.name) ($($branch.id))" -ForegroundColor Green

Write-Host "==> Setting a password for the branch-agent API user" -ForegroundColor Cyan
$AgentPassword = Read-Host "New password for $AgentApiUsername" -AsSecureString
$AgentPasswordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($AgentPassword)
)

& (Join-Path $scriptDir "setup-branch-agent.ps1") `
    -BranchCode $BranchCode `
    -BranchName $branch.name `
    -BranchId $branch.id `
    -ApiBaseUrl $ApiBaseUrl `
    -ApiUsername $AgentApiUsername `
    -ApiPassword $AgentPasswordPlain `
    -ComPort $ComPort `
    -CreateApiUser `
    -AdminUsername $AdminUsername `
    -AdminPassword $AdminPasswordPlain
