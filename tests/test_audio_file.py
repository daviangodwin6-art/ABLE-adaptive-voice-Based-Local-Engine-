"""Decoder test: a Piper WAV (22.05 kHz) comes out as mono 16 kHz 16-bit PCM of about the same duration."""
import subprocess, sys, tempfile, wave
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from audio_file import load_pcm16k

def test_wav_is_resampled_to_16k_mono():
    piper = ROOT / "baselines/lumo/piper/piper/piper.exe"
    voice = ROOT / "baselines/lumo/models/tts/en_US-amy-medium.onnx"
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "t.wav"
        subprocess.run([str(piper), "--model", str(voice), "--output_file", str(wav), "--quiet"], input=b"what is python", check=True, capture_output=True)
        with wave.open(str(wav)) as w:
            seconds = w.getnframes() / w.getframerate()
        pcm = load_pcm16k(wav)
    assert abs(len(pcm) / 32000 - seconds) < 0.1, (len(pcm), seconds)

if __name__ == "__main__":
    test_wav_is_resampled_to_16k_mono(); print("ok")
