@echo off
chcp 65001 >nul
cls
setlocal

set "ROOT_DIR=%~dp0"
set "BACKEND_SCRIPT=%ROOT_DIR%scripts\start-backend.bat"
set "FRONTEND_SCRIPT=%ROOT_DIR%scripts\start-frontend.bat"
set "SYNC_SCRIPT=%ROOT_DIR%scripts\sync-bim-data.ps1"

echo =============================================
echo BIM Smart Site AI Layout Startup Script
echo =============================================
echo.

echo 1. Starting backend service...
if exist "%BACKEND_SCRIPT%" (
    start "BIM Backend" "%BACKEND_SCRIPT%"
    echo    Backend window launched.
    echo    Backend:  http://127.0.0.1:8000/docs
) else (
    echo    [ERROR] scripts\start-backend.bat not found.
)
echo.

timeout /t 2 >nul

echo 2. Syncing BIM data to backend...
if exist "%SYNC_SCRIPT%" (
    powershell.exe -ExecutionPolicy Bypass -File "%SYNC_SCRIPT%"
    if errorlevel 1 (
        echo    [WARN] BIM data sync failed or was skipped.
        echo    [WARN] Frontend may show stale/demo data until sync succeeds.
    ) else (
        echo    BIM data synced to FastAPI project snapshot.
    )
) else (
    echo    [WARN] scripts\sync-bim-data.ps1 not found.
)
echo.

echo 3. Starting frontend service...
if exist "%FRONTEND_SCRIPT%" (
    start "BIM Frontend" "%FRONTEND_SCRIPT%"
    echo    Frontend window launched.
    echo    Frontend: http://127.0.0.1:5176
) else (
    echo    [ERROR] scripts\start-frontend.bat not found.
)
echo.

echo =============================================
echo All services are starting in separate windows.
echo =============================================
pause >nul
endlocal
