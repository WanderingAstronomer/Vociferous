@echo off
REM Vociferous v4.0 Launcher (Windows)
REM Runs the application using the project virtual environment.

setlocal

set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe"

REM Use venv Python if available, otherwise system Python
if exist "%VENV_PYTHON%" (
    set "PYTHON=%VENV_PYTHON%"
) else (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        set "PYTHON=python"
    ) else (
        echo Error: Python not found. Run scripts\install_windows.ps1 first. >&2
        exit /b 1
    )
)

REM Build frontend if dist\ doesn't exist
if not exist "%SCRIPT_DIR%frontend\dist" (
    if exist "%SCRIPT_DIR%frontend\package.json" (
        echo Building frontend...
        pushd "%SCRIPT_DIR%frontend"
        call npm install --silent
        call npx vite build
        popd
    )
)

"%PYTHON%" -m src.main %*
