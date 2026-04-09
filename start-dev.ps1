$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$batchFile = Join-Path $rootDir "start-dev.bat"

if (-not (Test-Path $batchFile)) {
    throw "start-dev.bat not found."
}

& cmd.exe /c "`"$batchFile`""
