$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
if (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$rootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$backendDir = Join-Path $rootDir "backend"
$venvPython = Join-Path $backendDir ".venv\\Scripts\\python.exe"
$dataGatewayScript = Join-Path $rootDir "data_gateway.py"
$healthUrl = "http://127.0.0.1:8000/health"
$projectSyncUrl = "http://127.0.0.1:8000/api/v1/projects/demo-smart-site"
$projectStatusUrl = "http://127.0.0.1:8000/api/v1/projects/demo-smart-site/bim-data-status"
$deadline = (Get-Date).AddSeconds(90)
$pythonCommand = $null

function Test-PythonCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [string[]]$Arguments = @()
    )

    try {
        & $Command @Arguments -c "import sys; print(sys.executable)" *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Update-BimDataStatus {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("syncing", "live", "demo")]
        [string]$State,
        [Parameter(Mandatory = $true)]
        [string]$Message,
        [string]$Detail = "",
        [string]$LastSyncError = $null,
        [string]$Source = $(if ($State -eq "demo") { "demo_data" } else { "realtime_snapshot" })
    )

    try {
        $payload = @{
            state = $State
            source = $Source
            message = $Message
            detail = if ($Detail) { $Detail } else { $null }
            last_sync_error = if ($LastSyncError) { $LastSyncError } else { $null }
        } | ConvertTo-Json -Depth 4

        Invoke-RestMethod `
            -Uri $projectStatusUrl `
            -Method Put `
            -ContentType "application/json" `
            -Body $payload `
            -TimeoutSec 5 *> $null
    } catch {
        Write-Host "[Sync] Failed to update BIM status endpoint: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

Write-Host "[Sync] Waiting for backend health check..." -ForegroundColor Cyan
while ((Get-Date) -lt $deadline) {
    try {
        $health = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 3
        if ($health.status -eq "ok") {
            break
        }
    } catch {
        Start-Sleep -Milliseconds 800
        continue
    }

    Start-Sleep -Milliseconds 800
}

if ((Get-Date) -ge $deadline) {
    Write-Host "[Sync] Backend did not become ready in time. Skipping BIM data sync." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $dataGatewayScript)) {
    $detail = "data_gateway.py not found. Frontend will continue using demo data."
    Write-Host "[Sync] $detail" -ForegroundColor Yellow
    Update-BimDataStatus -State "demo" -Message "Using demo BIM data" -Detail $detail -LastSyncError $detail
    exit 1
}

Update-BimDataStatus `
    -State "syncing" `
    -Message "Syncing realtime BIM snapshot" `
    -Detail "Backend is ready and the startup chain is fetching BIMFACE data into the project snapshot."

if (-not (Test-Path $venvPython)) {
    Write-Host "[Sync] Backend virtual environment was not found. Trying system Python..." -ForegroundColor Yellow
}

if ((Test-Path $venvPython) -and (Test-PythonCommand -Command $venvPython)) {
    $pythonCommand = @{ File = $venvPython; Prefix = @() }
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCommand = @{ File = "python"; Prefix = @() }
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCommand = @{ File = "py"; Prefix = @("-3.11") }
} else {
    $detail = "No usable Python interpreter was found. Frontend will continue using demo data."
    Write-Host "[Sync] $detail" -ForegroundColor Yellow
    Update-BimDataStatus -State "demo" -Message "Using demo BIM data" -Detail $detail -LastSyncError $detail
    exit 1
}

& $pythonCommand.File @($pythonCommand.Prefix + @("-c", "import requests")) *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[Sync] Installing missing dependency: requests" -ForegroundColor Cyan
    & $pythonCommand.File @($pythonCommand.Prefix + @("-m", "pip", "install", "requests"))
    if ($LASTEXITCODE -ne 0) {
        $detail = "Failed to install requests. Frontend will continue using demo data."
        Write-Host "[Sync] $detail" -ForegroundColor Yellow
        Update-BimDataStatus -State "demo" -Message "Using demo BIM data" -Detail $detail -LastSyncError $detail
        exit 1
    }
}

Write-Host "[Sync] Running data_gateway.py and pushing snapshot to FastAPI..." -ForegroundColor Cyan
$env:DATA_GATEWAY_SYNC_URL = $projectSyncUrl
& $pythonCommand.File @($pythonCommand.Prefix + @($dataGatewayScript))
$exitCode = $LASTEXITCODE
Remove-Item Env:DATA_GATEWAY_SYNC_URL -ErrorAction SilentlyContinue

if ($exitCode -ne 0) {
    $detail = "data_gateway.py failed. Frontend will continue using demo data."
    Write-Host "[Sync] $detail" -ForegroundColor Yellow
    Update-BimDataStatus -State "demo" -Message "Using demo BIM data" -Detail $detail -LastSyncError $detail
    exit $exitCode
}

try {
    $project = Invoke-RestMethod -Uri $projectSyncUrl -Method Get -TimeoutSec 5
    $obstacleCount = @($project.obstacles).Count
    $craneCount = @($project.working_cranes).Count
    Write-Host "[Sync] BIM snapshot ready. Cranes: $craneCount, obstacles: $obstacleCount" -ForegroundColor Green
    Update-BimDataStatus `
        -State "live" `
        -Message "Realtime snapshot loaded" `
        -Detail "Synced $craneCount cranes and $obstacleCount obstacles into the backend project snapshot."
} catch {
    $detail = "Snapshot push finished, but verification GET failed. Frontend will continue using demo data."
    Write-Host "[Sync] $detail" -ForegroundColor Yellow
    Update-BimDataStatus -State "demo" -Message "Using demo BIM data" -Detail $detail -LastSyncError $detail
    exit 1
}
