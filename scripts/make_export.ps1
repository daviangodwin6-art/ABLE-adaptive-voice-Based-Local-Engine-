# Builds export\ABLE_test_package\ (+ export\ABLE_test_package.zip) for testing on another Windows laptop.
# Notes for the owner: export\EXPORT_NOTES.md. Run from anywhere:
#   powershell -ExecutionPolicy Bypass -File scripts\make_export.ps1 -DryRun   # only list files and sizes
#   powershell -ExecutionPolicy Bypass -File scripts\make_export.ps1           # copy (~2.1 GB) and zip
#   ... -Wheels   also DOWNLOADS the Python wheels (est. 150-250 MB, internet, owner approval) so setup.bat works offline
param([switch]$DryRun, [switch]$Wheels, [switch]$NoZip)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$out  = Join-Path $root "export\ABLE_test_package"
$L = "baselines\lumo"

# source -> path in the package (only what pipeline\jarvis_v1.py + demo\web_demo.py load)
$items = [ordered]@{
    "scripts\friend\FRIEND_README.md"      = "FRIEND_README.md"
    "scripts\friend\setup.bat"             = "setup.bat"
    "scripts\friend\start.bat"             = "start.bat"
    "scripts\lumo_requirements.lock.txt"   = "requirements.txt"
    "pipeline\jarvis_v1.py"                = ""
    "pipeline\sentence_splitter.py"        = ""
    "pipeline\asr_fix.py"                  = ""
    "config\persona.toml"                  = ""
    "config\pipeline.toml"                 = ""
    "demo\web_demo.py"                     = ""
    "demo\package.json"                    = ""
    "demo\node_modules"                    = ""   # React 18.3.1 UMD files, served offline
    "bench\mic_check.py"                   = ""
    "$L\README.md"                         = ""   # Lumo credit (MIT)
    "$L\models\llm\orca-mini-3b-gguf2-q4_0.gguf"   = ""
    "$L\models\stt\vosk-model-small-en-us-0.15"    = ""
    "$L\models\tts\en_US-amy-medium.onnx"          = ""
    "$L\models\tts\en_US-amy-medium.onnx.json"     = ""
    "$L\piper\piper"                               = ""   # piper.exe + DLLs + espeak-ng-data
}
# never shipped, even if it shows up inside a copied folder
$banned = '\\(\.git|\.venv[^\\]*|__pycache__|results)(\\|$)|\.pyc$|results_gpu_tmp|\.env$|\.wav$'

$total = 0; $files = @()
foreach ($src in $items.Keys) {
    $abs = Join-Path $root $src
    if (-not (Test-Path $abs)) { throw "Missing: $src" }
    $dst = if ($items[$src]) { $items[$src] } else { $src }
    $part = $(if (Test-Path -LiteralPath $abs -PathType Leaf) { Get-Item -LiteralPath $abs }
              else { Get-ChildItem -LiteralPath $abs -Recurse -Force -File }) | Where-Object { $_.FullName.Substring($root.Length) -notmatch $banned }
    $size = ($part | Measure-Object Length -Sum).Sum
    $total += $size
    "{0,10:N1} MB  {1,5} files  {2}" -f ($size / 1MB), @($part).Count, $dst
    foreach ($f in $part) { $files += ,@($f.FullName, (Join-Path $out ($dst + $f.FullName.Substring($abs.Length)))) }
}
"{0,10:N1} MB  {1,5} files  TOTAL (without wheels)" -f ($total / 1MB), $files.Count
if ($DryRun) { return }

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
foreach ($f in $files) {
    New-Item -ItemType Directory -Force (Split-Path $f[1]) | Out-Null
    Copy-Item -LiteralPath $f[0] -Destination $f[1]
}
if ($Wheels) {
    & (Join-Path $root "$L\.venv\Scripts\python.exe") -m pip download --only-binary=:all: `
        -r (Join-Path $root "scripts\lumo_requirements.lock.txt") -d (Join-Path $out "wheels")
    if ($LASTEXITCODE) { throw "pip download failed" }
}
$bad = Get-ChildItem $out -Recurse -Force | Where-Object { $_.FullName.Substring($out.Length) -match $banned }
if ($bad) { throw "Banned files in package: $($bad.FullName -join ', ')" }

if (-not $NoZip) {
    $zip = "$out.zip"
    if (Test-Path $zip) { Remove-Item $zip }
    Add-Type -AssemblyName System.IO.Compression.FileSystem   # .NET zip: no 2 GB limit like Compress-Archive
    [IO.Compression.ZipFile]::CreateFromDirectory($out, $zip, "Fastest", $true)
    "Zip: {0:N1} MB  {1}" -f ((Get-Item $zip).Length / 1MB), $zip
}
"Done: $out"
