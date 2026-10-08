r"""Run the real voice loop on a recording instead of the microphone and print what it heard and answered.

  baselines\lumo\.venv\Scripts\python.exe bench\audio_test.py recording.mp3 [--tuning '{"stt_model": "vosk-model-en-us-0.22-lgraph"}']

mp3/wav/flac/ogg. Uses the tuned demo settings unless --tuning is given. Reply is spoken on the speakers; CPU only.
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO_TUNING = {"n_batch": 128, "n_threads": 5, "history_turns": 3, "max_tokens": 100, "min_conf": 0.5, "end_silence_ms": 700,
               "prompt_style": "tiny", "stream": True, "length_scale": 0.88, "stt_model": "vosk-model-small-en-us-0.15",
               "stt_engine": "whisper", "whisper_model": "whisper-base.en"}

ap = argparse.ArgumentParser()
ap.add_argument("file")
ap.add_argument("--tuning", help="JSON object overriding pipeline.toml (default: the demo settings)")
a = ap.parse_args()
env = dict(os.environ, JARVIS_TEST_FILE=str(Path(a.file).resolve()), PYTHONUTF8="1", CUDA_VISIBLE_DEVICES="-1",
           JARVIS_TUNING=a.tuning or json.dumps(DEMO_TUNING))
t0 = time.perf_counter()
r = subprocess.run([sys.executable, str(ROOT / "pipeline" / "jarvis_v1.py")], env=env, capture_output=True, text=True, encoding="utf-8")
for line in r.stdout.splitlines():
    if line.startswith(("You:", "ABLE:", "[*]")):
        print(line)
print(f"total {time.perf_counter() - t0:.1f} s (includes model load and the file's own length)")
if r.returncode:
    print(r.stderr[-800:])
