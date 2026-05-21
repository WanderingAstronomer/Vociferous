[CmdletBinding()]
param(
    [string]$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"

$ProjectDir = $ProjectDir.Trim().Trim('"')
if ($ProjectDir.Length -gt 3) {
    $ProjectDir = $ProjectDir.TrimEnd("\\/")
}
$ProjectDir = (Resolve-Path $ProjectDir).Path
$FrontendDir = Join-Path $ProjectDir "frontend"
$FrontendDistDir = Join-Path $FrontendDir "dist"
$FrontendBuildStamp = Join-Path $FrontendDistDir ".vociferous-build-stamp"

function Get-CommandPath([string]$Name, [string]$FallbackPath) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    if (Test-Path $FallbackPath) {
        $nodeDir = Split-Path $FallbackPath -Parent
        $env:PATH = "$nodeDir;$env:PATH"
        return $FallbackPath
    }
    return $null
}

function Get-BuildBaseline {
    if (Test-Path $FrontendBuildStamp) {
        return (Get-Item $FrontendBuildStamp).LastWriteTimeUtc
    }

    $indexHtml = Join-Path $FrontendDistDir "index.html"
    if (Test-Path $indexHtml) {
        return (Get-Item $indexHtml).LastWriteTimeUtc
    }

    return $null
}

function Test-FrontendNeedsBuild {
    $packageJson = Join-Path $FrontendDir "package.json"
    if (-not (Test-Path $packageJson)) {
        return $false
    }

    if (-not (Test-Path $FrontendDistDir)) {
        return $true
    }

    $baseline = Get-BuildBaseline
    if ($null -eq $baseline) {
        return $true
    }

    $sourcePaths = @(
        (Join-Path $FrontendDir "src"),
        (Join-Path $FrontendDir "index.html"),
        (Join-Path $FrontendDir "package.json"),
        (Join-Path $FrontendDir "package-lock.json"),
        (Join-Path $FrontendDir "svelte.config.js"),
        (Join-Path $FrontendDir "tsconfig.json"),
        (Join-Path $FrontendDir "tsconfig.app.json"),
        (Join-Path $FrontendDir "tsconfig.node.json"),
        (Join-Path $FrontendDir "vite.config.js"),
        (Join-Path $FrontendDir "vite.config.ts")
    )

    foreach ($path in $sourcePaths) {
        if (-not (Test-Path $path)) {
            continue
        }

        $item = Get-Item $path
        if ($item.PSIsContainer) {
            $newerFile = Get-ChildItem $path -File -Recurse | Where-Object { $_.LastWriteTimeUtc -gt $baseline } | Select-Object -First 1
            if ($newerFile) {
                return $true
            }
        } elseif ($item.LastWriteTimeUtc -gt $baseline) {
            return $true
        }
    }

    return $false
}

function Build-Frontend {
    $npmExe = Get-CommandPath "npm.cmd" (Join-Path $env:ProgramFiles "nodejs\npm.cmd")
    $npxExe = Get-CommandPath "npx.cmd" (Join-Path $env:ProgramFiles "nodejs\npx.cmd")

    if (-not $npmExe -or -not $npxExe) {
        throw "Frontend is missing or stale, but npm/npx was not found. Install Node.js 18+ and run the launcher again."
    }

    Write-Host "Building frontend..."
    Push-Location $FrontendDir
    try {
        & $npmExe install --silent
        if ($LASTEXITCODE -ne 0) {
            throw "npm install failed with exit code $LASTEXITCODE"
        }

        & $npxExe vite build
        if ($LASTEXITCODE -ne 0) {
            throw "vite build failed with exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }

    New-Item -ItemType Directory -Force -Path $FrontendDistDir | Out-Null
    Set-Content -Path $FrontendBuildStamp -Value (Get-Date).ToUniversalTime().ToString("o") -Encoding utf8
}

if (-not (Test-Path (Join-Path $FrontendDir "package.json"))) {
    Write-Host "Frontend package not found; skipping frontend build check."
    exit 0
}

if (Test-FrontendNeedsBuild) {
    Build-Frontend
} else {
    Write-Host "Frontend already current."
    if (-not (Test-Path $FrontendBuildStamp)) {
        New-Item -ItemType Directory -Force -Path $FrontendDistDir | Out-Null
        Set-Content -Path $FrontendBuildStamp -Value (Get-Date).ToUniversalTime().ToString("o") -Encoding utf8
    }
}