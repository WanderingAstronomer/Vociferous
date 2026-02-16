# Vociferous Installation Script for Windows
# Requires Python 3.12+ installed and on PATH
# Run: powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Vociferous Installation Script (Windows)"  -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

# --- Check Python ---
$PythonCmd = $null
foreach ($cmd in @("python3", "python", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python (3\.1[2-9]|3\.[2-9]\d)") {
            $PythonCmd = $cmd
            break
        }
    } catch {}
}

if (-not $PythonCmd) {
    Write-Host "Error: Python 3.12 or newer is required." -ForegroundColor Red
    Write-Host "Download from: https://www.python.org/downloads/"
    Write-Host "Make sure to check 'Add Python to PATH' during installation."
    exit 1
}

$PythonVersion = (& $PythonCmd --version 2>&1) -replace "Python ", ""
Write-Host "[OK] Python $PythonVersion ($PythonCmd)" -ForegroundColor Green

# --- Check for Visual C++ Build Tools (needed for some native deps) ---
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Checking build prerequisites"              -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$hasVCTools = $false
$vsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (Test-Path $vsWhere) {
    $installations = & $vsWhere -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -format json 2>$null | ConvertFrom-Json
    if ($installations.Count -gt 0) {
        $hasVCTools = $true
    }
}

if ($hasVCTools) {
    Write-Host "[OK] Visual C++ Build Tools found" -ForegroundColor Green
} else {
    Write-Host "[WARN] Visual C++ Build Tools not detected." -ForegroundColor Yellow
    Write-Host "  Some packages with native extensions may fail to build."
    Write-Host "  Install from: https://visualstudio.microsoft.com/visual-cpp-build-tools/"
    Write-Host "  Select 'Desktop development with C++' workload."
    Write-Host ""
    $confirm = Read-Host "Continue anyway? (y/N)"
    if ($confirm -ne "y") { exit 1 }
}

# --- Create virtual environment ---
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Creating virtual environment"              -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$VenvDir = Join-Path $ProjectDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"

if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating virtual environment..."
    & $PythonCmd -m venv $VenvDir
    Write-Host "[OK] Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "[OK] Virtual environment already exists" -ForegroundColor Green
}

# --- Upgrade build tools ---
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Upgrading build tools"                     -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

& $VenvPip install --upgrade pip setuptools wheel
Write-Host "[OK] Build tools upgraded" -ForegroundColor Green

# --- Install dependencies ---
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Installing dependencies"                   -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

Push-Location $ProjectDir
try {
    & $VenvPip install -r requirements.txt
    Write-Host "[OK] Dependencies installed" -ForegroundColor Green
} finally {
    Pop-Location
}

# --- Verify critical dependencies ---
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Verifying critical dependencies"           -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$DepsOk = $true
$modules = @("pywhispercpp", "webview", "sounddevice", "pydantic", "litestar", "llama_cpp")

foreach ($mod in $modules) {
    try {
        & $VenvPython -c "import $mod" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] $mod" -ForegroundColor Green
        } else {
            throw "import failed"
        }
    } catch {
        Write-Host "[FAIL] $mod (MISSING)" -ForegroundColor Red
        $DepsOk = $false
    }
}

if (-not $DepsOk) {
    Write-Host ""
    Write-Host "Error: Some critical dependencies failed to install." -ForegroundColor Red
    Write-Host "Common fixes:"
    Write-Host "  1. Install Visual C++ Build Tools"
    Write-Host "  2. Install Microsoft Edge WebView2 Runtime:"
    Write-Host "     https://developer.microsoft.com/en-us/microsoft-edge/webview2/"
    Write-Host ""
    Write-Host "Then re-run this script."
    exit 1
}

# --- GPU Detection ---
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "GPU Detection"                             -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($nvidiaSmi) {
    try {
        $gpuInfo = & nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>$null
        if ($gpuInfo) {
            Write-Host "[OK] NVIDIA GPU detected: $gpuInfo" -ForegroundColor Green
            Write-Host "  CUDA acceleration will be available for inference"
        }
    } catch {
        Write-Host "[INFO] nvidia-smi found but query failed" -ForegroundColor Yellow
    }
} else {
    Write-Host "[INFO] No NVIDIA GPU detected — CPU inference will be used" -ForegroundColor Yellow
    Write-Host "  If you have an NVIDIA GPU, install the latest drivers from:"
    Write-Host "  https://www.nvidia.com/download/index.aspx"
}

# --- WebView2 Check ---
Write-Host ""
$webview2Key = "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BEE-13A6279D3EBB}"
if (Test-Path $webview2Key) {
    Write-Host "[OK] Microsoft Edge WebView2 Runtime installed" -ForegroundColor Green
} else {
    Write-Host "[WARN] Microsoft Edge WebView2 Runtime not detected." -ForegroundColor Yellow
    Write-Host "  pywebview requires WebView2 on Windows."
    Write-Host "  Download: https://developer.microsoft.com/en-us/microsoft-edge/webview2/"
}

# --- Done ---
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Installation complete!"                    -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To run the application:"
Write-Host "  cd $ProjectDir"
Write-Host "  .\vociferous.bat"
Write-Host ""
Write-Host "Or directly:"
Write-Host "  .venv\Scripts\python.exe -m src.main"
Write-Host ""
