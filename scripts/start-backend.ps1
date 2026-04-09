$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
if (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$rootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$backendDir = Join-Path $rootDir "backend"
$venvPython = Join-Path $backendDir ".venv\\Scripts\\python.exe"
$requirementsFile = Join-Path $backendDir "requirements.txt"

function Get-NativeExitCode {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $true)]
        [string[]]$ArgumentList
    )

    $stdoutFile = [System.IO.Path]::GetTempFileName()
    $stderrFile = [System.IO.Path]::GetTempFileName()

    try {
        $process = Start-Process `
            -FilePath $FilePath `
            -ArgumentList $ArgumentList `
            -Wait `
            -NoNewWindow `
            -PassThru `
            -RedirectStandardOutput $stdoutFile `
            -RedirectStandardError $stderrFile
        return $process.ExitCode
    } catch {
        return 9999
    } finally {
        Remove-Item $stdoutFile, $stderrFile -Force -ErrorAction SilentlyContinue
    }
}

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

function Get-GlobalPython {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        return @{ Type = "exe"; Command = $pythonCmd.Source }
    }

    $pyExitCode = Get-NativeExitCode -FilePath "py" -ArgumentList @("-3.11", "-c", "import sys; print(sys.executable)")
    if ($pyExitCode -eq 0) {
        return @{ Type = "launcher"; Command = "py -3.11" }
    }

    return $null
}

if (-not (Test-Path $venvPython)) {
    $globalPython = Get-GlobalPython
    if (-not $globalPython) {
        Write-Host ""
        Write-Host "[Backend] Python 3.11 was not found." -ForegroundColor Red
        Write-Host "[Backend] Install Python 3.11, then run start-dev.bat or start-dev.ps1 again." -ForegroundColor Yellow
        Read-Host "Press Enter to close"
        exit 1
    }

    Write-Host "[Backend] Creating virtual environment..." -ForegroundColor Cyan
    if ($globalPython.Type -eq "exe") {
        Invoke-Checked -Command { & $globalPython.Command -m venv (Join-Path $backendDir ".venv") } -ErrorMessage "[Backend] Failed to create virtual environment."
    } else {
        Invoke-Checked -Command { & py -3.11 -m venv (Join-Path $backendDir ".venv") } -ErrorMessage "[Backend] Failed to create virtual environment."
    }
}

Write-Host "[Backend] Checking dependencies..." -ForegroundColor Cyan
$dependencyExitCode = Get-NativeExitCode -FilePath $venvPython -ArgumentList @("-c", "import fastapi, uvicorn, sqlalchemy, pydantic")
if ($dependencyExitCode -ne 0) {
    Invoke-Checked -Command { & $venvPython -m pip install --upgrade pip } -ErrorMessage "[Backend] Failed to upgrade pip."
    Invoke-Checked -Command { & $venvPython -m pip install -r $requirementsFile } -ErrorMessage "[Backend] Failed to install backend dependencies."
}

Write-Host "[Backend] Starting FastAPI: http://127.0.0.1:8000/docs" -ForegroundColor Green
Set-Location $backendDir
Invoke-Checked -Command { & $venvPython -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 } -ErrorMessage "[Backend] FastAPI failed to start."
