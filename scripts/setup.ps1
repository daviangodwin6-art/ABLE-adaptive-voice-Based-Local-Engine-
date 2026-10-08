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

# --- B1 environment: venv inside the Lumo folder, exact versions from the lock file ---
# Only vosk/gpt4all/sounddevice/numpy are needed for English voice mode (torch/transformers are Bangla-only).
if (-not (Test-Path "baselines\lumo\.venv")) {
    py -3.11 -m venv "baselines\lumo\.venv"   # use "py -3.11" if 3.11 is installed on the target laptop
}
& "baselines\lumo\.venv\Scripts\python.exe" -m pip install --quiet -r "scripts\lumo_requirements.lock.txt"
Copy-Item "scripts\lumo_requirements.lock.txt" "baselines\lumo\requirements.lock.txt" -Force
Write-Host "Next: scripts\download_models.ps1"
