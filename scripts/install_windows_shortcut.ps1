# Install Windows shortcuts for Vociferous.
# Creates Desktop and Start Menu entries pointing to the virtualenv launcher.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$PythonwTarget = Join-Path $ProjectDir ".venv\Scripts\pythonw.exe"
$PythonTarget = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$Target = if (Test-Path $PythonwTarget) { $PythonwTarget } elseif (Test-Path $PythonTarget) { $PythonTarget } else { $null }
$Arguments = "-m src.main"

if ($null -eq $Target) {
    throw "Python launcher not found in virtual environment: $PythonwTarget"
}

$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Vociferous.lnk"
$StartMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$StartMenuShortcut = Join-Path $StartMenuDir "Vociferous.lnk"
$IconPath = Join-Path $ProjectDir "assets\icons\vociferous_icon.ico"

if (-not (Test-Path $StartMenuDir)) {
    New-Item -Path $StartMenuDir -ItemType Directory -Force | Out-Null
}

$Shell = New-Object -ComObject WScript.Shell

foreach ($Path in @($DesktopShortcut, $StartMenuShortcut)) {
    $Shortcut = $Shell.CreateShortcut($Path)
    $Shortcut.TargetPath = $Target
    $Shortcut.Arguments = $Arguments
    $Shortcut.WorkingDirectory = $ProjectDir
    $Shortcut.Description = "Vociferous - Offline speech-to-text"
    if (Test-Path $IconPath) {
        $Shortcut.IconLocation = $IconPath
    }
    $Shortcut.Save()
}

Write-Host "Installed Windows shortcuts:" -ForegroundColor Green
Write-Host "  $DesktopShortcut"
Write-Host "  $StartMenuShortcut"
