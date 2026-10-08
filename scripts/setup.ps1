# Reproducible setup. Run from the project root:  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# --- B1 baseline: Lumo, pinned commit (never edited, never committed) ---
$LumoUrl    = "https://github.com/mehedinaeem/Lumo.git"
$LumoCommit = "778ed055033ec3b0410349a82b9ea68e9546a4e0"
if (-not (Test-Path "baselines\lumo\.git")) {
    git clone $LumoUrl "baselines\lumo"
}
git -C "baselines\lumo" fetch --quiet origin
git -C "baselines\lumo" checkout --quiet $LumoCommit
Write-Host "Lumo at $(git -C 'baselines\lumo' rev-parse HEAD)"
