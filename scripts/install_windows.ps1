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
$Readiness = [ordered]@{
    Python = $false
    Venv = $false
    Dependencies = $false
    Frontend = $false
    CriticalImports = $false
    Cuda = $false
    WebView2 = $false
    Models = $false
    Shortcuts = $false
}

function Write-Section {
    param([string]$Title)

    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host $Title -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$Command,
        [Parameter(Mandatory = $true)][string]$FailureMessage
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$FailureMessage (exit code $LASTEXITCODE)"
    }
}

function Get-CudaRuntimeStatus {
    param([string]$PythonExe, [string]$ProjectRoot)

    $probe = @'
import json
import sys

sys.path.insert(0, r"__PROJECT_ROOT__")

from src.main import _register_nvidia_dll_dirs
from src.core.cuda_runtime import detect_cuda_runtime

if sys.platform == "win32":
    _register_nvidia_dll_dirs()

status = detect_cuda_runtime()
print(
    json.dumps(
        {
            "driver_detected": status.driver_detected,
            "cuda_available": status.cuda_available,
            "cuda_device_count": status.cuda_device_count,
            "gpu_name": status.gpu_name,
            "detail": status.detail,
        }
    )
)
'@

    $probe = $probe.Replace("__PROJECT_ROOT__", $ProjectRoot.Replace("\", "\\"))
    $probeFile = Join-Path ([System.IO.Path]::GetTempPath()) ("vociferous-cuda-probe-" + [guid]::NewGuid().ToString("N") + ".py")
    try {
        [System.IO.File]::WriteAllText($probeFile, $probe)
        $json = & $PythonExe $probeFile 2>$null
        if (-not $json) { return $null }
        try {
            return $json | ConvertFrom-Json
        } catch {
            return $null
        }
    } finally {
        Remove-Item -LiteralPath $probeFile -Force -ErrorAction SilentlyContinue
    }
}

function Install-PinnedWindowsCudaRuntime {
    param([string]$PythonExe, [string]$ProjectRoot)

    $manifest = Join-Path $ProjectRoot "requirements-windows-cuda.txt"
    if (-not (Test-Path $manifest)) {
        Write-Host "[FAIL] Windows CUDA runtime manifest missing: $manifest" -ForegroundColor Red
        return $false
    }

    Write-Host "Installing pinned Windows CUDA runtime wheels..." -ForegroundColor Cyan
    Write-Host "  Manifest: requirements-windows-cuda.txt"
    & $PythonExe -m pip install -r $manifest
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] CUDA runtime wheel installation failed" -ForegroundColor Red
        return $false
    }

    return $true
}

function Test-WebView2Runtime {
    $webview2Keys = @(
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BEE-13A6279D3EBB}",
        "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BEE-13A6279D3EBB}",
        "HKCU:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BEE-13A6279D3EBB}"
    )

    foreach ($webview2Key in $webview2Keys) {
        if (Test-Path $webview2Key) { return $true }
    }

    $webview2Roots = @(
        (Join-Path ${env:ProgramFiles(x86)} "Microsoft\EdgeWebView\Application"),
        (Join-Path $env:ProgramFiles "Microsoft\EdgeWebView\Application"),
        (Join-Path $env:LOCALAPPDATA "Microsoft\EdgeWebView\Application")
    )

    foreach ($root in $webview2Roots) {
        if (-not (Test-Path $root)) { continue }
        $runtime = Get-ChildItem -LiteralPath $root -Recurse -Filter "msedgewebview2.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($runtime) { return $true }
    }

    return $false
}

# --- Check Python ---
# Windows Python detection is notoriously tricky. The Microsoft Store installs
# "app execution alias" stubs (WindowsApps\python.exe) that shadow real Python
# on PATH. The py launcher and real Python installs are often not on PATH at all.
# Strategy: try PATH candidates (filtering out MS Store stubs), then probe
# well-known install locations, then give actionable guidance on failure.

function Test-PythonCandidate {
    param([string]$Exe, [string[]]$ExtraArgs)
    try {
        # Reject Microsoft Store stubs - they never return a real version
        $resolved = (Get-Command $Exe -ErrorAction SilentlyContinue).Source
        if ($resolved -and $resolved -match "Microsoft\\WindowsApps") { return $false }

        $allArgs = @($ExtraArgs) + "--version"
        $ver = & $Exe @allArgs 2>&1
        return ($ver -match "Python (3\.1[23])")
    } catch { return $false }
}

$PythonCmd = $null
$PythonArgs = @()

# Phase 1: PATH-based candidates (filtered for MS Store stubs)
# Specific-version py launcher calls come first - `py -3.12` / `py -3.13`
# are preferred because pythonnet 3.0.5 (Windows .NET interop) requires Python <3.14.
# Generic `py -3` would silently pick up 3.14+ if that is the newest installed.
$pathCandidates = @(
    @{ Cmd = "py";      Args = @("-3.12") },
    @{ Cmd = "py";      Args = @("-3.13") },
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

    # py launcher - winget and python.org both install it here
    $pyLauncher = "$env:LOCALAPPDATA\Programs\Python\Launcher\py.exe"
    if (Test-Path $pyLauncher) {
        $probePaths += @{ Cmd = $pyLauncher; Args = @("-3.12") }
        $probePaths += @{ Cmd = $pyLauncher; Args = @("-3.13") }
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
    Write-Host "Error: Python 3.12 or 3.13 is required." -ForegroundColor Red
    Write-Host ""

    # Detect the MS Store stub specifically - this is by far the most common cause
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
        # Detect if Python 3.14+ is available but 3.12/3.13 are not
        $has314 = $false
        foreach ($cand in @("python3", "python")) {
            try {
                $v = & $cand --version 2>&1
                if ($v -match "Python 3\.1[4-9]") { $has314 = $true; break }
            } catch {}
        }
        try { $v = & py -3 --version 2>&1; if ($v -match "Python 3\.1[4-9]") { $has314 = $true } } catch {}
        if ($has314) {
            Write-Host "DETECTED: Python 3.14+ is installed, but it is not yet supported." -ForegroundColor Yellow
            Write-Host "  The 'pythonnet' dependency (Windows .NET interop) requires Python <3.14." -ForegroundColor Yellow
            Write-Host ""
            Write-Host "Install Python 3.12 or 3.13 alongside your existing installation:" -ForegroundColor White
            Write-Host "  winget install --id Python.Python.3.12 --accept-package-agreements"
            Write-Host "  (then re-run this script - it will prefer 3.12/3.13 automatically)"
        } else {
            Write-Host "Install Python 3.12 or 3.13 from: https://www.python.org/downloads/"
            Write-Host "Make sure to check 'Add Python to PATH' during installation."
        }
    }
    exit 1
}

$PythonVersion = (& $PythonCmd @($PythonArgs + "--version") 2>&1) -replace "Python ", ""
$PythonDisplay = if ($PythonArgs.Count -gt 0) { "$PythonCmd $($PythonArgs -join ' ')" } else { $PythonCmd }
Write-Host "[OK] Python $PythonVersion ($PythonDisplay)" -ForegroundColor Green
$Readiness.Python = $true

# --- Check for Visual C++ Build Tools (needed for some native deps) ---
Write-Section "Checking build prerequisites"

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
Write-Section "Creating virtual environment"

$VenvDir = Join-Path $ProjectDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"

if (Test-Path $VenvDir) {
    $venvOk = $false
    if (Test-Path $VenvPython) {
        try {
            $venvVer = & $VenvPython --version 2>&1
            $venvOk = ($venvVer -match "Python (3\.1[23])")
        } catch {}
    }
    if (-not $venvOk) {
        Write-Host "[WARN] Existing .venv is stale or built with an unsupported Python version. Recreating..." -ForegroundColor Yellow
        Remove-Item -Path $VenvDir -Recurse -Force
    }
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment..."
    Invoke-CheckedCommand -Command { & $PythonCmd @($PythonArgs + "-m", "venv", $VenvDir) } -FailureMessage "Virtual environment creation failed"
    Write-Host "[OK] Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "[OK] Virtual environment already exists" -ForegroundColor Green
}
$Readiness.Venv = $true

# --- Upgrade build tools ---
Write-Section "Upgrading build tools"

Invoke-CheckedCommand -Command { & $VenvPython -m pip install --upgrade pip setuptools wheel } -FailureMessage "Build tool upgrade failed"
Write-Host "[OK] Build tools upgraded" -ForegroundColor Green

# --- Install dependencies ---
Write-Section "Installing dependencies"

Push-Location $ProjectDir
try {
    Invoke-CheckedCommand -Command { & $VenvPython -m pip install -r requirements.txt } -FailureMessage "Dependency installation failed"
    Write-Host "[OK] Dependencies installed" -ForegroundColor Green
    $Readiness.Dependencies = $true
} finally {
    Pop-Location
}

# --- Build frontend if needed ---
Write-Section "Building frontend"

$FrontendDir = Join-Path $ProjectDir "frontend"
$FrontendDistDir = Join-Path $FrontendDir "dist"

if (Test-Path $FrontendDistDir) {
    Write-Host "[OK] Frontend already built (frontend/dist exists)" -ForegroundColor Green
    $Readiness.Frontend = $true
} else {
    # Find npm - same approach as Python: check PATH first, then well-known locations
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
            # Add to session PATH - postinstall scripts (esbuild etc.) spawn
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
            Invoke-CheckedCommand -Command { & $npmExe install --silent } -FailureMessage "npm install failed"
            Invoke-CheckedCommand -Command { & $npxExe vite build } -FailureMessage "vite build failed"

            Write-Host "[OK] Frontend built" -ForegroundColor Green
            $Readiness.Frontend = $true
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
Write-Section "Verifying critical dependencies"

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
$Readiness.CriticalImports = $true

# --- GPU Detection ---
Write-Section "GPU Detection"

$nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($nvidiaSmi) {
    try {
        $gpuInfo = & nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>$null
        if ($gpuInfo) {
            Write-Host "[OK] NVIDIA GPU detected: $gpuInfo" -ForegroundColor Green
            $cudaStatus = Get-CudaRuntimeStatus -PythonExe $VenvPython -ProjectRoot $ProjectDir
            if ($cudaStatus -and $cudaStatus.cuda_available) {
                Write-Host "  CTranslate2 CUDA runtime is usable ($($cudaStatus.cuda_device_count) device(s))" -ForegroundColor Green
                $Readiness.Cuda = $true
            } else {
                Write-Host "[WARN] NVIDIA driver detected, but CUDA inference is NOT ready." -ForegroundColor Yellow
                if ($cudaStatus) {
                    Write-Host "  Probe detail: $($cudaStatus.detail)"
                } else {
                    Write-Host "  Probe detail: CUDA runtime probe did not return usable results."
                }
                Write-Host ""
                Write-Host "  Recommended fix: install pinned CUDA runtime wheels inside the app venv." -ForegroundColor White
                Write-Host "  This avoids system-wide CUDA Toolkit changes."
                Write-Host ""
                $installCudaRuntime = Read-Host "Install pinned Windows CUDA runtime now? (Y/n)"
                if ($installCudaRuntime -notmatch "^(?i:n|no)$") {
                    if (Install-PinnedWindowsCudaRuntime -PythonExe $VenvPython -ProjectRoot $ProjectDir) {
                        $cudaStatus = Get-CudaRuntimeStatus -PythonExe $VenvPython -ProjectRoot $ProjectDir
                        if ($cudaStatus -and $cudaStatus.cuda_available) {
                            Write-Host "[OK] CUDA runtime verified after install ($($cudaStatus.cuda_device_count) device(s))" -ForegroundColor Green
                            Write-Host "  Probe detail: $($cudaStatus.detail)"
                            $Readiness.Cuda = $true
                        } else {
                            Write-Host "[WARN] CUDA runtime wheels installed, but CTranslate2 still cannot use CUDA." -ForegroundColor Yellow
                            if ($cudaStatus) { Write-Host "  Probe detail: $($cudaStatus.detail)" }
                        }
                    }
                }

                if (-not $Readiness.Cuda) {
                    Write-Host ""
                    Write-Host "  Vociferous will run on CPU until this is fixed." -ForegroundColor Yellow
                    $continueGpu = Read-Host "Continue installation with CPU fallback? (Y/n)"
                    if ($continueGpu -match "^(?i:n|no)$") { exit 1 }
                }
            }
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
$hasWebView2 = Test-WebView2Runtime

if ($hasWebView2) {
    Write-Host "[OK] Microsoft Edge WebView2 Runtime installed" -ForegroundColor Green
    $Readiness.WebView2 = $true
} else {
    Write-Host "[WARN] Microsoft Edge WebView2 Runtime not detected." -ForegroundColor Yellow
    Write-Host "  pywebview requires WebView2 on Windows."
    Write-Host "  Download: https://developer.microsoft.com/en-us/microsoft-edge/webview2/"
}

# --- Model Provisioning ---
Write-Section "Model Provisioning"

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
        Invoke-CheckedCommand -Command { & $VenvPython $ProvisionScript install silero_vad } -FailureMessage "Silero VAD provisioning failed"

        Write-Host ""
        Write-Host "Downloading ASR model (faster-whisper-large-v3-turbo-int8)..." -ForegroundColor Cyan
        Invoke-CheckedCommand -Command { & $VenvPython $ProvisionScript install large-v3-turbo-int8 } -FailureMessage "ASR model provisioning failed"

        Write-Host ""
        Write-Host "Downloading SLM model (Qwen3 4B CT2 INT8)..." -ForegroundColor Cyan
        Invoke-CheckedCommand -Command { & $VenvPython $ProvisionScript install qwen4b } -FailureMessage "SLM model provisioning failed"

        Write-Host "[OK] Models downloaded" -ForegroundColor Green
        $Readiness.Models = $true
    } else {
        Write-Host "Skipped. You can download models later from Settings in the app," -ForegroundColor Yellow
        Write-Host "or run:  .venv\Scripts\python.exe scripts\provision_models.py install <model_id>" -ForegroundColor Yellow
    }
} else {
    Write-Host "[OK] All default models already present" -ForegroundColor Green
    $Readiness.Models = $true
}

# --- Desktop Shortcut ---
Write-Section "Desktop Shortcut"

$ShortcutScript = Join-Path $ScriptDir "install_windows_shortcut.ps1"
$doShortcut = Read-Host "Create Desktop and Start Menu shortcuts? (Y/n)"
if ($doShortcut -eq "" -or $doShortcut -match "^(?i:y|yes)$") {
    Invoke-CheckedCommand -Command { & powershell -ExecutionPolicy Bypass -File $ShortcutScript } -FailureMessage "Shortcut installation failed"
    $Readiness.Shortcuts = $true
} else {
    Write-Host "Skipped. Run later:  .\scripts\install_windows_shortcut.ps1" -ForegroundColor Yellow
}

# --- Readiness Summary ---
Write-Section "Readiness Summary"
foreach ($item in $Readiness.GetEnumerator()) {
    if ($item.Value) {
        Write-Host ("[OK]   {0}" -f $item.Key) -ForegroundColor Green
    } else {
        Write-Host ("[WARN] {0}" -f $item.Key) -ForegroundColor Yellow
    }
}

if (-not $Readiness.Models) {
    Write-Host ""
    Write-Host "Vociferous is launchable, but transcription/refinement will not be ready until models are provisioned." -ForegroundColor Yellow
}
if (-not $Readiness.Cuda) {
    Write-Host "Vociferous is configured for CPU fallback unless CUDA readiness is fixed later." -ForegroundColor Yellow
}

# --- Done ---
Write-Section "Installation complete!"
Write-Host ""
Write-Host "To run the application:"
Write-Host "  cd $ProjectDir"
Write-Host "  .\vociferous.bat"
Write-Host ""
Write-Host "Or directly:"
Write-Host "  .venv\Scripts\python.exe -m src.main"
Write-Host ""
