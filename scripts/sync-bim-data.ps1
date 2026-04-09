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

if (-not (Test-Path $dataGatewayScript)) {
    Write-Host "[Sync] data_gateway.py not found. Skipping BIM data sync." -ForegroundColor Yellow
    exit 0
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
    Write-Host "[Sync] No usable Python interpreter was found. Skipping BIM data sync." -ForegroundColor Yellow
    exit 1
}

& $pythonCommand.File @($pythonCommand.Prefix + @("-c", "import requests")) *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[Sync] Installing missing dependency: requests" -ForegroundColor Cyan
    & $pythonCommand.File @($pythonCommand.Prefix + @("-m", "pip", "install", "requests"))
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[Sync] Failed to install requests. Skipping BIM data sync." -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "[Sync] Running data_gateway.py and pushing snapshot to FastAPI..." -ForegroundColor Cyan
$env:DATA_GATEWAY_SYNC_URL = $projectSyncUrl
& $pythonCommand.File @($pythonCommand.Prefix + @($dataGatewayScript))
$exitCode = $LASTEXITCODE
Remove-Item Env:DATA_GATEWAY_SYNC_URL -ErrorAction SilentlyContinue

if ($exitCode -ne 0) {
    Write-Host "[Sync] data_gateway.py failed. Frontend may show stale/demo data." -ForegroundColor Yellow
    exit $exitCode
}

try {
    $project = Invoke-RestMethod -Uri $projectSyncUrl -Method Get -TimeoutSec 5
    $obstacleCount = @($project.obstacles).Count
    $craneCount = @($project.working_cranes).Count
    Write-Host "[Sync] BIM snapshot ready. Cranes: $craneCount, obstacles: $obstacleCount" -ForegroundColor Green
} catch {
    Write-Host "[Sync] Snapshot push finished, but verification GET failed." -ForegroundColor Yellow
    exit 1
}
