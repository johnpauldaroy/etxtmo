<#
.SYNOPSIS
    Packages branch-agent's source into a standalone zip for distribution
    to branch PCs that should not need a full git clone of this repo.

.DESCRIPTION
    Includes only: agent/*.py, requirements.txt, README.md, and the two
    onboarding scripts from infra/scripts/windows. Excludes .venv, .env,
    gammu-config-*/, logs, and __pycache__.

.EXAMPLE
    .\build-branch-agent-package.ps1
    # then: gh release create branch-agent-latest branch-agent.zip --title "branch-agent" --notes "..." --repo johnpauldaroy/etxtmo
#>

[CmdletBinding()]
param(
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..\..")).Path
$branchAgentDir = Join-Path $repoRoot "branch-agent"

if (-not $OutputPath) {
    $OutputPath = Join-Path $repoRoot "branch-agent.zip"
}

if (Test-Path $OutputPath) {
    Remove-Item $OutputPath -Force
}

$stagingDir = Join-Path $env:TEMP "branch-agent-package-staging"
if (Test-Path $stagingDir) {
    Remove-Item $stagingDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $stagingDir | Out-Null

Write-Host "Staging branch-agent source..." -ForegroundColor Cyan
$agentStaging = Join-Path $stagingDir "branch-agent\agent"
New-Item -ItemType Directory -Force -Path $agentStaging | Out-Null
Copy-Item -Path (Join-Path $branchAgentDir "agent\*.py") -Destination $agentStaging
Copy-Item -Path (Join-Path $branchAgentDir "requirements.txt") -Destination (Join-Path $stagingDir "branch-agent")
Copy-Item -Path (Join-Path $branchAgentDir "README.md") -Destination (Join-Path $stagingDir "branch-agent") -ErrorAction SilentlyContinue

Write-Host "Staging onboarding scripts..." -ForegroundColor Cyan
$scriptsStaging = Join-Path $stagingDir "scripts"
New-Item -ItemType Directory -Force -Path $scriptsStaging | Out-Null
Copy-Item -Path (Join-Path $scriptDir "setup-branch-agent.ps1") -Destination $scriptsStaging
Copy-Item -Path (Join-Path $scriptDir "bootstrap-branch.ps1") -Destination $scriptsStaging -ErrorAction SilentlyContinue

Write-Host "Compressing to $OutputPath ..." -ForegroundColor Cyan
Compress-Archive -Path (Join-Path $stagingDir "*") -DestinationPath $OutputPath -Force

Remove-Item $stagingDir -Recurse -Force

Write-Host ""
Write-Host "Built: $OutputPath" -ForegroundColor Green
Write-Host ""
Write-Host "To publish (one-time: run 'gh auth login' first if not already):" -ForegroundColor Yellow
Write-Host "  gh release create branch-agent-latest `"$OutputPath`" --repo johnpauldaroy/etxtmo --title `"branch-agent`" --notes `"Standalone branch-agent package for branch PC onboarding.`""
Write-Host ""
Write-Host "To republish after changes (delete + recreate, since assets can't be overwritten in place):" -ForegroundColor Yellow
Write-Host "  gh release delete branch-agent-latest --repo johnpauldaroy/etxtmo --yes"
Write-Host "  gh release create branch-agent-latest `"$OutputPath`" --repo johnpauldaroy/etxtmo --title `"branch-agent`" --notes `"Standalone branch-agent package for branch PC onboarding.`""
