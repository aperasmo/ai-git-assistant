[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$InstallDependencies
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BaseTempRoot = Join-Path $ProjectRoot ".local\pytest-tmp"
$RunTemp = Join-Path $BaseTempRoot ("run-" + [Guid]::NewGuid().ToString("N"))
$env:GIT_CEILING_DIRECTORIES = $ProjectRoot

Push-Location (Join-Path $ProjectRoot "sidecar")
try {
    if ($InstallDependencies) {
        & $Python -m pip install ".[dev]"
        if ($LASTEXITCODE -ne 0) {
            throw "Dependency installation failed with exit code $LASTEXITCODE."
        }
    }

    New-Item -ItemType Directory -Force -Path $BaseTempRoot | Out-Null

    # Use a unique temp directory per run because pytest removes --basetemp
    # before starting, and stale Windows handles can make fixed paths fail.
    # The cache plugin is disabled so no state is written to sidecar/.pytest_cache.
    & $Python -m pytest --basetemp $RunTemp -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) {
        throw "Sidecar tests failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
