$ErrorActionPreference = "Continue"

Write-Host "AI Git Assistant prerequisites" -ForegroundColor Cyan

$commands = @("git", "node", "npm", "python", "rustc", "cargo")

foreach ($command in $commands) {
    $resolved = Get-Command $command -ErrorAction SilentlyContinue

    if ($null -ne $resolved) {
        $version = & $command --version 2>$null | Select-Object -First 1
        Write-Host "[OK] $command  $version" -ForegroundColor Green
    }
    else {
        Write-Host "[MISSING] $command not found on PATH" -ForegroundColor Yellow
    }
}
