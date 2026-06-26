[CmdletBinding()]
param([string]$Python = "python")

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Push-Location (Join-Path $ProjectRoot "sidecar")
try {
    & $Python -m pip install ".[dev]"
    # Keep pytest temporary files inside the project because the default Windows
    # Temp location is inaccessible on this machine. Disable pytest's cache plugin
    # as the current cache directory has a stale/invalid structure.
    & $Python -m pytest --basetemp ".pytest-tmp" -p no:cacheprovider
}
finally {
    Pop-Location
}
