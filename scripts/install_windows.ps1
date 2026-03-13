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
# Windows Python detection is notoriously tricky. The Microsoft Store installs
# "app execution alias" stubs (WindowsApps\python.exe) that shadow real Python
# on PATH. The py launcher and real Python installs are often not on PATH at all.
# Strategy: try PATH candidates (filtering out MS Store stubs), then probe
# well-known install locations, then give actionable guidance on failure.

function Test-PythonCandidate {
    param([string]$Exe, [string[]]$ExtraArgs)
    try {
        # Reject Microsoft Store stubs — they never return a real version
        $resolved = (Get-Command $Exe -ErrorAction SilentlyContinue).Source
        if ($resolved -and $resolved -match "Microsoft\\WindowsApps") { return $false }

        $allArgs = @($ExtraArgs) + "--version"
        $ver = & $Exe @allArgs 2>&1
        return ($ver -match "Python (3\.1[2-9]|3\.[2-9]\d)")
    } catch { return $false }
}

$PythonCmd = $null
$PythonArgs = @()

# Phase 1: PATH-based candidates (filtered for MS Store stubs)
$pathCandidates = @(
    @{ Cmd = "python3"; Args = @() },
    @{ Cmd = "python";  Args = @() },
    @{ Cmd = "py";      Args = @("-3") },
    @{ Cmd = "py";      Args = @() }
)

foreach ($c in $pathCandidates) {
    if (Test-PythonCandidate -Exe $c.Cmd -ExtraArgs $c.Args) {
        $PythonCmd = $c.Cmd
        $PythonArgs = $c.Args
        break
    }
}

# Phase 2: Well-known install locations (py launcher, per-user, system-wide)
if (-not $PythonCmd) {
    $probePaths = @()

    # py launcher — winget and python.org both install it here
    $pyLauncher = "$env:LOCALAPPDATA\Programs\Python\Launcher\py.exe"
    if (Test-Path $pyLauncher) {
        $probePaths += @{ Cmd = $pyLauncher; Args = @("-3") }
        $probePaths += @{ Cmd = $pyLauncher; Args = @() }
    }

    # Per-user installs (the default for python.org and winget)
    foreach ($minor in @(13, 12)) {
        $perUser = "$env:LOCALAPPDATA\Programs\Python\Python3${minor}\python.exe"
        if (Test-Path $perUser) { $probePaths += @{ Cmd = $perUser; Args = @() } }
    }

    # System-wide installs
    foreach ($minor in @(13, 12)) {
        foreach ($root in @("$env:ProgramFiles\Python3${minor}", "C:\Python3${minor}")) {
            $sysExe = "$root\python.exe"
            if (Test-Path $sysExe) { $probePaths += @{ Cmd = $sysExe; Args = @() } }
        }
    }

    foreach ($c in $probePaths) {
        if (Test-PythonCandidate -Exe $c.Cmd -ExtraArgs $c.Args) {
            $PythonCmd = $c.Cmd
            $PythonArgs = $c.Args
            Write-Host "[INFO] Found Python at $($c.Cmd) (not on PATH)" -ForegroundColor Yellow
            break
        }
    }
}

if (-not $PythonCmd) {
    Write-Host "Error: Python 3.12 or newer is required." -ForegroundColor Red
    Write-Host ""

    # Detect the MS Store stub specifically — this is by far the most common cause
    $storeStub = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($storeStub -and $storeStub -match "Microsoft\\WindowsApps") {
        Write-Host "DETECTED: 'python' on your PATH is the Microsoft Store stub," -ForegroundColor Yellow
        Write-Host "          not a real Python installation." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Fix options:" -ForegroundColor White
        Write-Host "  1. Disable the stub: Settings > Apps > Advanced app settings"
        Write-Host "     > App execution aliases > turn OFF 'python.exe' and 'python3.exe'"
        Write-Host "  2. Reinstall Python from https://www.python.org/downloads/"
        Write-Host "     and CHECK 'Add Python to PATH' during installation."
    } else {
        Write-Host "Download from: https://www.python.org/downloads/"
        Write-Host "Make sure to check 'Add Python to PATH' during installation."
    }
    exit 1
}

$PythonVersion = (& $PythonCmd @($PythonArgs + "--version") 2>&1) -replace "Python ", ""
$PythonDisplay = if ($PythonArgs.Count -gt 0) { "$PythonCmd $($PythonArgs -join ' ')" } else { $PythonCmd }
Write-Host "[OK] Python $PythonVersion ($PythonDisplay)" -ForegroundColor Green

# --- Check for Visual C++ Build Tools (needed for some native deps) ---
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Checking build prerequisites"              -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$hasVCTools = $false
$vsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (Test-Path $vsWhere) {
    try {
        $installations = & $vsWhere -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -format json 2>$null | ConvertFrom-Json
        if ($installations) {
            $hasVCTools = $true
        }
    } catch {
        $hasVCTools = $false
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
    if ($confirm -notmatch "^(?i:y|yes)$") { exit 1 }
}

# --- Create virtual environment ---
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Creating virtual environment"              -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$VenvDir = Join-Path $ProjectDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"

if ((Test-Path $VenvDir) -and (-not (Test-Path $VenvPython))) {
    Write-Host "[WARN] Existing .venv is not usable on Windows. Recreating..." -ForegroundColor Yellow
    Remove-Item -Path $VenvDir -Recurse -Force
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment..."
    & $PythonCmd @($PythonArgs + "-m", "venv", $VenvDir)
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

# --- Build frontend if needed ---
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Building frontend"                        -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$FrontendDir = Join-Path $ProjectDir "frontend"
$FrontendDistDir = Join-Path $FrontendDir "dist"

if (Test-Path $FrontendDistDir) {
    Write-Host "[OK] Frontend already built (frontend/dist exists)" -ForegroundColor Green
} else {
    # Find npm — same approach as Python: check PATH first, then well-known locations
    $npmExe = $null
    $npxExe = $null
    $npmOnPath = Get-Command npm -ErrorAction SilentlyContinue
    if ($npmOnPath) {
        $npmExe = "npm"
        $npxExe = "npx"
    } else {
        # Probe the standard Node.js install location
        $nodeDir = "$env:ProgramFiles\nodejs"
        if (Test-Path "$nodeDir\npm.cmd") {
            # Add to session PATH — postinstall scripts (esbuild etc.) spawn
            # child processes via cmd.exe that need 'node' resolvable on PATH
            $env:PATH = "$nodeDir;$env:PATH"
            $npmExe = "npm"
            $npxExe = "npx"
            Write-Host "[INFO] Found Node.js at $nodeDir (added to session PATH)" -ForegroundColor Yellow
        }
    }

    if ($npmExe) {
        Push-Location $FrontendDir
        try {
            & $npmExe install --silent
            if ($LASTEXITCODE -ne 0) { throw "npm install failed" }

            & $npxExe vite build
            if ($LASTEXITCODE -ne 0) { throw "vite build failed" }

            Write-Host "[OK] Frontend built" -ForegroundColor Green
        } finally {
            Pop-Location
        }
    } else {
        Write-Host "[WARN] npm not found - skipping frontend build." -ForegroundColor Yellow
        Write-Host "  Install Node.js 18+, then run:"
        Write-Host "  cd frontend"
        Write-Host "  npm install"
        Write-Host "  npx vite build"
        Write-Host "  (The launcher will auto-build on first run if npm is available.)"
    }
}

# --- Verify critical dependencies ---
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Verifying critical dependencies"           -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$DepsOk = $true
$modules = @("ctranslate2", "faster_whisper", "tokenizers", "webview", "sounddevice", "pydantic", "litestar")

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
    Write-Host "[INFO] No NVIDIA GPU detected -- CPU inference will be used" -ForegroundColor Yellow
    Write-Host "  If you have an NVIDIA GPU, install the latest drivers from:"
    Write-Host "  https://www.nvidia.com/download/index.aspx"
}

# --- WebView2 Check ---
Write-Host ""
$webview2Keys = @(
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BEE-13A6279D3EBB}",
    "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BEE-13A6279D3EBB}",
    "HKCU:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BEE-13A6279D3EBB}"
)

$hasWebView2 = $false
foreach ($webview2Key in $webview2Keys) {
    if (Test-Path $webview2Key) {
        $hasWebView2 = $true
        break
    }
}

if ($hasWebView2) {
    Write-Host "[OK] Microsoft Edge WebView2 Runtime installed" -ForegroundColor Green
} else {
    Write-Host "[WARN] Microsoft Edge WebView2 Runtime not detected." -ForegroundColor Yellow
    Write-Host "  pywebview requires WebView2 on Windows."
    Write-Host "  Download: https://developer.microsoft.com/en-us/microsoft-edge/webview2/"
}

# --- Model Provisioning ---
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Model Provisioning"                        -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$ProvisionScript = Join-Path $ProjectDir "scripts\provision_models.py"

# Check if any models are missing
$modelsMissing = $false
try {
    $listOutput = & $VenvPython $ProvisionScript list 2>&1
    if ($listOutput -match "MISSING") {
        $modelsMissing = $true
    }
} catch {
    $modelsMissing = $true
}

if ($modelsMissing) {
    Write-Host "Some models need to be downloaded." -ForegroundColor Yellow
    Write-Host ""
    & $VenvPython $ProvisionScript list
    Write-Host ""

    $doProvision = Read-Host "Download default models now? (Y/n)"
    if ($doProvision -eq "" -or $doProvision -match "^(?i:y|yes)$") {
        Write-Host ""
        Write-Host "Downloading Silero VAD..." -ForegroundColor Cyan
        & $VenvPython $ProvisionScript install silero_vad

        Write-Host ""
        Write-Host "Downloading ASR model (faster-whisper-large-v3-turbo-int8)..." -ForegroundColor Cyan
        & $VenvPython $ProvisionScript install large-v3-turbo-int8

        Write-Host ""
        Write-Host "Downloading SLM model (Qwen3-8B-ct2-AWQ)..." -ForegroundColor Cyan
        & $VenvPython $ProvisionScript install qwen4b

        Write-Host "[OK] Models downloaded" -ForegroundColor Green
    } else {
        Write-Host "Skipped. You can download models later from Settings in the app," -ForegroundColor Yellow
        Write-Host "or run:  .venv\Scripts\python.exe scripts\provision_models.py install <model_id>" -ForegroundColor Yellow
    }
} else {
    Write-Host "[OK] All default models already present" -ForegroundColor Green
}

# --- Desktop Shortcut ---
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Desktop Shortcut"                          -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$ShortcutScript = Join-Path $ScriptDir "install_windows_shortcut.ps1"
$doShortcut = Read-Host "Create Desktop and Start Menu shortcuts? (Y/n)"
if ($doShortcut -eq "" -or $doShortcut -match "^(?i:y|yes)$") {
    & powershell -ExecutionPolicy Bypass -File $ShortcutScript
} else {
    Write-Host "Skipped. Run later:  .\scripts\install_windows_shortcut.ps1" -ForegroundColor Yellow
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
