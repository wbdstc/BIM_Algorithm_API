@echo off
chcp 65001 >nul
setlocal
title BIM Frontend

for %%I in ("%~dp0..") do set "ROOT_DIR=%%~fI"
set "FRONTEND_DIR=%ROOT_DIR%\frontend"

if not exist "%FRONTEND_DIR%\package.json" (
    echo [Frontend] frontend\package.json not found.
    goto :wait_exit
)

where npm >nul 2>nul
if errorlevel 1 (
    echo [Frontend] npm was not found.
    echo [Frontend] Install Node.js and run start-dev.bat again.
    goto :wait_exit
)

cd /d "%FRONTEND_DIR%"

if not exist "%FRONTEND_DIR%\node_modules" (
    echo [Frontend] Installing frontend dependencies...
    call npm install
    if errorlevel 1 goto :failed
)

echo [Frontend] Starting Vite: http://127.0.0.1:5176
call npm run dev
if errorlevel 1 goto :failed

echo.
echo [Frontend] Service stopped.
goto :wait_exit

:failed
echo.
echo [Frontend] Startup failed with exit code %ERRORLEVEL%.

:wait_exit
pause
endlocal
