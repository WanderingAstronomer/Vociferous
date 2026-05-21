@echo off
REM Vociferous v4.0 Launcher (Windows)
REM Runs the application using the project virtual environment.

setlocal

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR:~0,-1%"
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

REM Build frontend if dist\ is missing or stale
if exist "%SCRIPT_DIR%scripts\build_frontend_if_needed.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%scripts\build_frontend_if_needed.ps1" -ProjectDir "%PROJECT_DIR%"
    if errorlevel 1 exit /b %errorlevel%
)

"%PYTHON%" -m src.main %*
