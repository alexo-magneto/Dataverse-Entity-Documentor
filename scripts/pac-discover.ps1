# Uses the Power Platform CLI (pac) to help fill config.json (see pac-discover.sh for details).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Get-Command pac -ErrorAction SilentlyContinue)) {
  Write-Error "pac CLI not found. Install: dotnet tool install --global Microsoft.PowerApps.CLI.Tool"
}

$envUrl = $env:DATAVERSE_URL
if (-not $envUrl -and (Test-Path config.json)) {
  $envUrl = (Get-Content config.json -Raw | ConvertFrom-Json).environmentUrl
}

Write-Host "== pac auth profiles =="
pac auth list

if ($env:DATAVERSE_CLIENT_ID -and $env:DATAVERSE_CLIENT_SECRET -and $env:DATAVERSE_TENANT_ID) {
  Write-Host "== creating app-only pac auth profile =="
  $args = @("auth","create","--name","app-documentor","--applicationId",$env:DATAVERSE_CLIENT_ID,"--clientSecret",$env:DATAVERSE_CLIENT_SECRET,"--tenant",$env:DATAVERSE_TENANT_ID)
} else {
  Write-Host "== creating interactive pac auth profile (browser sign-in) =="
  $args = @("auth","create","--name","app-documentor")
}
if ($envUrl) { $args += @("--environment",$envUrl) }
& pac @args

Write-Host "== environments (copy the Environment URL into config.json -> environmentUrl) =="
pac org list
Write-Host "== current org =="
pac org who

Write-Host ""
Write-Host "Next: fill config.json, then run:  .venv\Scripts\python document_app.py --list-apps"
