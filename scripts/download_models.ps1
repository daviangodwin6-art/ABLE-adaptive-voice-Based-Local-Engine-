# Downloads Lumo's models/binaries into the paths its README expects. Idempotent.
# Run from anywhere: powershell -ExecutionPolicy Bypass -File scripts\download_models.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$lumo = Join-Path $root "baselines\lumo"
$cache = Join-Path $root "models\_downloads"   # gitignored
New-Item -ItemType Directory -Force $cache, "$lumo\models\llm", "$lumo\models\stt", "$lumo\models\tts" | Out-Null

function Get-File($url, $dest, $minBytes) {
    if ((Test-Path $dest) -and (Get-Item $dest).Length -ge $minBytes) { Write-Host "have $dest"; return }
    Write-Host "downloading $url"
    curl.exe -L --fail --retry 3 -o $dest $url
    if ($LASTEXITCODE -ne 0) { throw "download failed: $url" }
    $len = (Get-Item $dest).Length
    if ($len -lt $minBytes) { throw "$dest too small ($len bytes)" }
}

# LLM (official GPT4All model host)
Get-File "https://gpt4all.io/models/gguf/orca-mini-3b-gguf2-q4_0.gguf" "$lumo\models\llm\orca-mini-3b-gguf2-q4_0.gguf" 1500000000

# STT: VOSK small English
$vz = "$cache\vosk-model-small-en-us-0.15.zip"
Get-File "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip" $vz 30000000
if (-not (Test-Path "$lumo\models\stt\vosk-model-small-en-us-0.15")) { Expand-Archive $vz "$lumo\models\stt" }

# TTS: official Piper release (zip contains a top-level piper\ folder with piper.exe)
$pz = "$cache\piper_windows_amd64.zip"
Get-File "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip" $pz 20000000
if (-not (Test-Path "$lumo\piper\piper\piper.exe")) { Expand-Archive $pz "$lumo\piper" }

# Voice: en_US-amy-medium
$base = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium"
Get-File "$base/en_US-amy-medium.onnx" "$lumo\models\tts\en_US-amy-medium.onnx" 50000000
Get-File "$base/en_US-amy-medium.onnx.json" "$lumo\models\tts\en_US-amy-medium.onnx.json" 1000

# Record checksums for reproducibility
Get-ChildItem "$lumo\models\llm\*.gguf", "$lumo\models\tts\*.onnx*", $vz, $pz | Get-FileHash -Algorithm SHA256 |
    ForEach-Object { "$($_.Hash)  $(Split-Path -Leaf $_.Path)" } | Set-Content "$root\scripts\model_checksums.txt"
Get-ChildItem "$lumo\models" -Recurse -File | Measure-Object Length -Sum | ForEach-Object { "models total MB: " + [math]::Round($_.Sum/1MB,1) }
