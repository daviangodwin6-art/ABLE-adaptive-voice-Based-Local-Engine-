"""Real-microphone check: say "where is the library" a few times; prints what Vosk hears plus its runner-up guesses.

Run (stop the demo first, it uses the same microphone):
  baselines\\lumo\\.venv\\Scripts\\python.exe bench\\mic_check.py
If "where ..." shows up only as a lower alternative, the audio is the problem (mic level, noise, distance), not the words.
Ctrl+C to stop.
"""
import json, queue
from pathlib import Path
import sounddevice as sd
from vosk import Model, KaldiRecognizer, SetLogLevel

LUMO = Path(__file__).resolve().parent.parent / "baselines" / "lumo"
SetLogLevel(-1)
rec = KaldiRecognizer(Model(str(LUMO / "models/stt/vosk-model-small-en-us-0.15")), 16000)
rec.SetMaxAlternatives(4)
q = queue.Queue()
print("Say: 'where is the library' ... (Ctrl+C to stop)")
with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype="int16", channels=1, callback=lambda d, *_: q.put(bytes(d))):
    try:
        while True:
            if rec.AcceptWaveform(q.get()):
                for a in json.loads(rec.Result()).get("alternatives", []):
                    if a["text"]:
                        print(f"  {a['confidence']:7.1f}  {a['text']}")
                print()
    except KeyboardInterrupt:
        pass
