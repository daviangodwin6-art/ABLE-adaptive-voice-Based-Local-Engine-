"""Does Vosk hear "where" as "there"? Synthesizes phrases with Piper, feeds them to the Vosk model, prints what it hears.

Run: baselines\\lumo\\.venv\\Scripts\\python.exe bench\\asr_check.py      (synthetic speech: tells model problems from mic problems)
Shows the raw text and the text after pipeline/asr_fix.py.
"""
import json, subprocess, sys, tempfile, wave
from pathlib import Path
from vosk import Model, KaldiRecognizer, SetLogLevel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from asr_fix import fix_asr

LUMO = ROOT / "baselines" / "lumo"
PIPER, VOICE = LUMO / "piper" / "piper" / "piper.exe", LUMO / "models" / "tts" / "en_US-amy-medium.onnx"
PHRASES = ["where is the library", "where are my keys", "where can I buy bread", "where do you live",
           "where was Einstein born", "where does rain come from", "where should I go on holiday",
           "is there a bank nearby", "is there a pharmacy near here"]  # statements "there is ..." would be rewritten: known cost of fix_asr

SetLogLevel(-1)
import time
MODEL = sys.argv[1] if len(sys.argv) > 1 else "vosk-model-small-en-us-0.15"  # or vosk-model-en-us-0.22-lgraph
t0 = time.perf_counter()
model = Model(str(LUMO / "models/stt" / MODEL))
print(f"{MODEL}: loaded in {time.perf_counter() - t0:.1f} s")
bad = 0
with tempfile.TemporaryDirectory() as tmp:
    for p in PHRASES:
        wav = Path(tmp) / "p.wav"
        subprocess.run([str(PIPER), "--model", str(VOICE), "--output_file", str(wav), "--quiet"],
                       input=p.encode(), check=True, capture_output=True)
        with wave.open(str(wav)) as w:
            rec = KaldiRecognizer(model, w.getframerate())
            rec.AcceptWaveform(w.readframes(w.getnframes()))
            heard = json.loads(rec.FinalResult()).get("text", "")
        fixed = fix_asr(heard)
        bad += fixed != p.lower()
        print(f"{'ok ' if fixed == p.lower() else 'BAD'} said={p!r:40} heard={heard!r:40} fixed={fixed!r}")
print(f"{bad} of {len(PHRASES)} still wrong after the fix")
