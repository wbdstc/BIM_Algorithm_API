@echo off
chcp 65001 >nul
setlocal
title BIM Backend

for %%I in ("%~dp0..") do set "ROOT_DIR=%%~fI"
set "BACKEND_DIR=%ROOT_DIR%\backend"
set "VENV_DIR=%BACKEND_DIR%\.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "REQUIREMENTS_FILE=%BACKEND_DIR%\requirements.txt"

if not exist "%BACKEND_DIR%\app\main.py" (
    echo [Backend] backend\app\main.py not found.
    goto :wait_exit
)

if not exist "%REQUIREMENTS_FILE%" (
    echo [Backend] backend\requirements.txt not found.
    goto :wait_exit
)

if not exist "%VENV_PY%" (
    echo [Backend] Virtual environment not found. Creating...
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3.11 -m venv "%VENV_DIR%" >nul 2>nul
    )

    if not exist "%VENV_PY%" (
        where python >nul 2>nul
        if errorlevel 1 (
            echo [Backend] Python 3.11 was not found.
            echo [Backend] Install Python 3.11 and run start-dev.bat again.
            goto :wait_exit
        )
        python -m venv "%VENV_DIR%"
        if errorlevel 1 goto :failed
    )
)

echo [Backend] Validating virtual environment...
"%VENV_PY%" -c "import sys; print(sys.executable)" >nul 2>nul
if errorlevel 1 (
    echo [Backend] The virtual environment exists, but its base Python runtime is missing.
    echo [Backend] Expected Python 3.11 home: C:\Users\20909\AppData\Local\Programs\Python\Python311
    echo [Backend] Reinstall Python 3.11 to that path or recreate backend\.venv with a valid Python 3.11 interpreter.
    goto :wait_exit
)

echo [Backend] Checking dependencies...
"%VENV_PY%" -c "import fastapi, uvicorn, sqlalchemy, pydantic" >nul 2>nul
if errorlevel 1 (
    echo [Backend] Installing backend dependencies...
    "%VENV_PY%" -m pip install --upgrade pip
    if errorlevel 1 goto :failed
    "%VENV_PY%" -m pip install -r "%REQUIREMENTS_FILE%"
    if errorlevel 1 goto :failed
)

echo [Backend] Starting FastAPI: http://127.0.0.1:8000/docs
cd /d "%BACKEND_DIR%"
"%VENV_PY%" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
if errorlevel 1 goto :failed

echo.
echo [Backend] Service stopped.
goto :wait_exit

:failed
echo.
echo [Backend] Startup failed with exit code %ERRORLEVEL%.

:wait_exit
pause
endlocal
