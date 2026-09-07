[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$TargetTriple = $env:TM_TARGET_TRIPLE
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SidecarRoot = Join-Path $ProjectRoot "sidecar"
$BinaryDirectory = Join-Path $ProjectRoot "src-tauri\binaries"
$BuildDirectory = Join-Path $ProjectRoot ".build\sidecar"
$DistDirectory = Join-Path $BuildDirectory "dist"

if (-not $TargetTriple) {
    $HostLine = (& rustc -vV | Select-String "^host:").ToString()
    if (-not $HostLine) {
        throw "Rust is required to determine the Tauri target triple. Install Rust, then rerun."
    }
    $TargetTriple = ($HostLine -replace "^host:\s*", "").Trim()
}

Push-Location $SidecarRoot
try {
    & $Python -m pip install ".[build]"
    & $Python -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --name "ai-git-sidecar" `
        --paths $SidecarRoot `
        --distpath $DistDirectory `
        --workpath (Join-Path $BuildDirectory "work") `
        --specpath $BuildDirectory `
        run.py

    New-Item -ItemType Directory -Force -Path $BinaryDirectory | Out-Null
    $Source = Join-Path $DistDirectory "ai-git-sidecar.exe"
    $Destination = Join-Path $BinaryDirectory "ai-git-sidecar-$TargetTriple.exe"
    Copy-Item -Force $Source $Destination
    Write-Host "Sidecar bundled at $Destination"
}
finally {
    Pop-Location
}
