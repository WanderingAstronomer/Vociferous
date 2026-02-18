# Remove Windows shortcuts for Vociferous.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$DesktopShortcut = Join-Path $env:USERPROFILE "Desktop\Vociferous.lnk"
$StartMenuShortcut = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Vociferous.lnk"

foreach ($Path in @($DesktopShortcut, $StartMenuShortcut)) {
    if (Test-Path $Path) {
        Remove-Item -Path $Path -Force
    }
}

Write-Host "Removed Windows shortcuts" -ForegroundColor Green
