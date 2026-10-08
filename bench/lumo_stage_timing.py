"""Per-stage timing of the Lumo (B1) models, WITHOUT modifying Lumo.

Mirrors main.py's settings: VOSK small-en (chunks of 4000 frames), GPT4All orca-mini-3b q4_0
(prompt format, max_tokens=80, CPU only), Piper via the same `echo ... | piper.exe` shell call
that Lumo uses (so the whole WAV must be written before anything can play).

Run with Lumo's venv from the project root:
  baselines\\lumo\\.venv\\Scripts\\python.exe bench\\lumo_stage_timing.py [--wav path] [--runs 5]
"""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"  # never touch the GPU

import argparse, json, statistics, subprocess, sys, time, wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
LUMO = ROOT / "baselines" / "lumo"
DEFAULT_WAV = ROOT / "bench" / "test_audio" / "fixed_sentence.wav"
SENTENCE = "What is the capital of France"
OUT_MD = ROOT / "results" / "lumo_dev_timings.md"
PIPER = r"piper\piper\piper.exe"
VOICE = r"models\tts\en_US-amy-medium.onnx"


def ms(t0, t1=None):
    return ((time.perf_counter() if t1 is None else t1) - t0) * 1000


def make_fixed_wav(path):
    """Synthesize the fixed test sentence with Piper, resample 22.05k -> 16k mono 16-bit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.with_suffix(".piper22k.wav")
    subprocess.run([str(LUMO / PIPER), "--model", str(LUMO / VOICE), "--output_file", str(raw), "--quiet"],
                   input=SENTENCE.encode(), check=True, cwd=LUMO)
    with wave.open(str(raw)) as w:
        sr, data = w.getframerate(), np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    n = int(len(data) * 16000 / sr)
    res = np.interp(np.linspace(0, len(data) - 1, n), np.arange(len(data)), data.astype(np.float32))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(res.astype(np.int16).tobytes())
    raw.unlink()


def stt(model, wav_path):
    from vosk import KaldiRecognizer
    with wave.open(str(wav_path)) as wf:
        assert wf.getnchannels() == 1 and wf.getsampwidth() == 2 and wf.getframerate() == 16000
        frames = wf.readframes(wf.getnframes())
    t0 = time.perf_counter()
    rec = KaldiRecognizer(model, 16000)
    for i in range(0, len(frames), 8000):  # 4000 samples, same chunk size as Lumo
        rec.AcceptWaveform(frames[i:i + 8000])
    text = json.loads(rec.FinalResult()).get("text", "").strip()
    return text, ms(t0)


def llm_stream(llm, text):
    prompt = (f"You are Lumo, a helpful offline AI assistant. \n"
              f"Answer the user's question directly and helpfully. Be concise (under 50 words).\n\n"
              f"User: {text}\nLumo:")
    t0 = time.perf_counter()
    first, parts = None, []
    for tok in llm.generate(prompt, max_tokens=80, streaming=True):
        if first is None:
            first = ms(t0)
        parts.append(tok)
    return "".join(parts).strip(), first, ms(t0)


def tts(reply):
    """Same call as Lumo.speak(): shell echo | piper.exe -> WAV. First audio = WAV finished."""
    safe = reply.replace('"', '').replace("'", "").replace('\n', ' ').replace('&', 'and')
    out = ROOT / "results" / "raw" / "lumo_timing_out.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    r = subprocess.run(f'echo {safe} | {PIPER} --model {VOICE} --output_file "{out}" --quiet',
                       shell=True, capture_output=True, cwd=LUMO)
    t = ms(t0)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(r.stderr.decode(errors="replace"))
    return t


def stats(v):
    return statistics.median(v), max(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", type=Path, default=DEFAULT_WAV)
    ap.add_argument("--runs", type=int, default=5)
    a = ap.parse_args()

    if not a.wav.exists():
        print("creating fixed test WAV with Piper:", a.wav)
        make_fixed_wav(a.wav)
    with wave.open(str(a.wav)) as w:
        dur = w.getnframes() / w.getframerate()

    from vosk import Model, SetLogLevel
    from gpt4all import GPT4All
    SetLogLevel(-1)
    t0 = time.perf_counter()
    vm = Model(str(LUMO / "models/stt/vosk-model-small-en-us-0.15"))
    load_stt = ms(t0)
    t0 = time.perf_counter()
    llm = GPT4All("orca-mini-3b-gguf2-q4_0.gguf", model_path=str(LUMO / "models/llm"),
                  allow_download=False, device="cpu")
    load_llm = ms(t0)

    rows = []
    for i in range(a.runs + 1):  # run 0 is a warm-up and is discarded
        text, t_stt = stt(vm, a.wav)
        reply, t_first, t_llm = llm_stream(llm, text)
        t_tts = tts(reply)
        tag = "warm-up (discarded)" if i == 0 else f"run {i}"
        print(f"{tag}: stt={t_stt:.0f} ms  llm_first_token={t_first:.0f} ms  llm_total={t_llm:.0f} ms  "
              f"tts={t_tts:.0f} ms  text={text!r} reply_words={len(reply.split())}")
        if i:
            rows.append((text, reply, t_stt, t_first, t_llm, t_tts))

    cols = [("Speech-to-text (VOSK)", 2), ("LLM time to first token", 3),
            ("LLM total (max 80 tokens)", 4), ("TTS time to first audio (full WAV written)", 5)]
    e2e = [r[2] + r[4] + r[5] for r in rows]  # Lumo is sequential: STT, then whole LLM reply, then whole TTS
    lines = ["# Lumo (B1) per-stage timings", "",
             "**DEVELOPMENT LAPTOP - NOT FINAL NUMBERS**", "",
             f"- Machine: i7-9750H, 6C/12T, CPU only (CUDA_VISIBLE_DEVICES=-1, GPT4All device=cpu); on battery, Balanced power plan",
             f"- Input: `{a.wav.name}` ({dur:.2f} s, 16 kHz mono). Expected text: \"{SENTENCE.lower()}\"",
             "  (synthetic Piper speech, cleaner than a real voice; pass `--wav` to use a real recording)",
             f"- {len(rows)} measured runs after 1 discarded warm-up. Model load (once): VOSK {load_stt:.0f} ms, LLM {load_llm:.0f} ms",
             f"- Recognised text: {sorted({r[0] for r in rows})}", "",
             "| Stage | Median (ms) | Worst (ms) |", "|---|---:|---:|"]
    for name, idx in cols:
        med, worst = stats([r[idx] for r in rows])
        lines.append(f"| {name} | {med:.0f} | {worst:.0f} |")
    med, worst = stats(e2e)
    lines += [f"| **STT + full LLM + TTS (Lumo end-of-speech to first audio, sequential)** | **{med:.0f}** | **{worst:.0f}** |", "",
              "Notes: Lumo generates the full reply (blocking), then Piper writes the whole WAV, then plays it, so first audio",
              "= STT + total LLM + TTS. VOSK time here is decoding of the whole file; in live mode part of it overlaps with speech.",
              "Playback start-up and Lumo's 0.5 s mic chunking / endpoint wait are not included."]
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
