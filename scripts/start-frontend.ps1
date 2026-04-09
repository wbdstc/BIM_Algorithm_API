$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
if (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$rootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$frontendDir = Join-Path $rootDir "frontend"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [Parameter(Mandatory = $true)]
        [string]$ErrorMessage
    )

    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & $Command
    } finally {
        $exitCode = $LASTEXITCODE
        $ErrorActionPreference = $previousPreference
    }

    if ($exitCode -ne 0) {
        Write-Host $ErrorMessage -ForegroundColor Red
        Read-Host "Press Enter to close"
        exit $exitCode
    }
}

$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npmCmd) {
    Write-Host ""
    Write-Host "[Frontend] npm was not found." -ForegroundColor Red
    Write-Host "[Frontend] Install Node.js 20+, then run start-dev.bat or start-dev.ps1 again." -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 1
}

Set-Location $frontendDir

if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Host "[Frontend] Installing dependencies..." -ForegroundColor Cyan
    Invoke-Checked -Command { & $npmCmd.Source install } -ErrorMessage "[Frontend] Failed to install frontend dependencies."
}

Write-Host "[Frontend] Starting Vite: http://127.0.0.1:5176" -ForegroundColor Green
Invoke-Checked -Command { & $npmCmd.Source run dev } -ErrorMessage "[Frontend] Vite failed to start."
