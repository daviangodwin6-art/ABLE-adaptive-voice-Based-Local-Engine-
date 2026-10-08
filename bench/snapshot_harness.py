"""Time Lumo's UNMODIFIED main.py end to end with a fake, real-time-paced microphone.

How: main.py is exec'd as-is. Before that we swap in
  - a fake `sounddevice.RawInputStream` that delivers 0.5 s chunks (blocksize 8000) in real time:
    speech WAV, then silence, exactly like a live mic;
  - timing wrappers around vosk.KaldiRecognizer, GPT4All.generate (token callback only),
    subprocess.run (Piper call) and winsound.PlaySound (audio is NOT played; the call time is "first audio").
No Lumo file is changed. Run from anywhere with Lumo's venv:
  baselines\\lumo\\.venv\\Scripts\\python.exe bench\\snapshot_harness.py
One invocation = one pass (greeting + 5 questions). Options: --target lumo|v0|v1, --label, --tuning '<json>', --out.
Writes the pass to --out (default results/raw/snapshot_events.json); bench/ablate.py runs many passes and aggregates.
"""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"  # never touch the GPU

import ctypes, json, statistics, subprocess, sys, threading, time, wave
from ctypes import wintypes
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
LUMO = ROOT / "baselines" / "lumo"
AUDIO = ROOT / "bench" / "test_audio"
RATE, BLOCK = 16000, 8000  # main.py: RATE and blocksize
QUESTIONS = ["What is the capital of France", "How many days are there in a week", "Tell me a short joke",
             "Why is the sky blue", "Who wrote the play Romeo and Juliet"]
if os.environ.get("BENCH_LONG"):  # set BENCH_LONG=1 to add three questions that need longer answers
    QUESTIONS += ["Explain how a rainbow forms", "Give me three tips for studying", "What is photosynthesis"]
LEAD_S = 0.3

t_zero = time.perf_counter()
events = []
ev_lock = threading.Lock()
orig_run = subprocess.run


def ev(name, **kw):
    with ev_lock:
        events.append({"name": name, "t": time.perf_counter(), **kw})


# ---------- test audio (synthetic Piper speech, 16 kHz mono) ----------
def make_wav(text, path):
    raw = path.with_suffix(".raw22k.wav")
    orig_run([str(LUMO / r"piper\piper\piper.exe"), "--model", str(LUMO / r"models\tts\en_US-amy-medium.onnx"),
              "--output_file", str(raw), "--quiet"], input=text.encode(), check=True, cwd=LUMO)
    with wave.open(str(raw)) as w:
        sr, d = w.getframerate(), np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    n = int(len(d) * RATE / sr)
    res = np.interp(np.linspace(0, len(d) - 1, n), np.arange(len(d)), d.astype(np.float32))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(res.astype(np.int16).tobytes())
    raw.unlink()


def load_q(i):
    p = AUDIO / f"snap_q{i + 1}.wav"
    if not p.exists():
        make_wav(QUESTIONS[i], p)
    with wave.open(str(p)) as w:
        d = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    loud = np.where(np.abs(d) > 0.02 * np.abs(d).max())[0]
    return d, int(loud[-1])  # samples, index of last audible sample


# ---------- resource sampler (ctypes, no extra packages) ----------
k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
k32.GetCurrentProcess.restype = wintypes.HANDLE
k32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.c_void_p] * 4
k32.GetSystemTimes.argtypes = [ctypes.c_void_p] * 3
psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]


class PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t)]


def ft(f):
    return (f.dwHighDateTime << 32 | f.dwLowDateTime)


res_samples, gpu_samples, stop = [], [], threading.Event()


def res_loop():
    h = k32.GetCurrentProcess()
    while not stop.is_set():
        c, e, kk, u = (wintypes.FILETIME() for _ in range(4))
        k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(kk), ctypes.byref(u))
        i, sk, su = (wintypes.FILETIME() for _ in range(3))
        k32.GetSystemTimes(ctypes.byref(i), ctypes.byref(sk), ctypes.byref(su))
        m = PMC(); m.cb = ctypes.sizeof(m)
        psapi.GetProcessMemoryInfo(h, ctypes.byref(m), m.cb)
        res_samples.append((time.perf_counter(), (ft(kk) + ft(u)) / 1e7, ft(i), ft(sk) + ft(su),
                            m.WorkingSetSize, m.PeakWorkingSetSize, m.PrivateUsage))
        time.sleep(0.1)


def gpu_loop():
    while not stop.is_set():
        try:
            o = orig_run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True, timeout=5).stdout.strip().split(",")
            gpu_samples.append((time.perf_counter(), int(o[0]), int(o[1])))
        except Exception:
            pass
        time.sleep(0.5)


# ---------- fake microphone ----------
g = {"__name__": "__main__", "__file__": str(LUMO / "main.py"),
     "timing_event": lambda name, **kw: ev(name, **kw)}  # jarvis_v1 reports "sentence" events through this
state = {"plays": 0, "q": -1, "counted": False}  # plays = replies whose playback has started (not WAV files)


class FakeStream:
    def __init__(self, samplerate, blocksize, dtype, channels, callback):
        assert (samplerate, blocksize, dtype, channels) == (RATE, BLOCK, "int16", 1)
        self.cb = callback

    def __enter__(self):
        ev("stream_open")
        threading.Thread(target=self.feed, daemon=True).start()
        return self

    def __exit__(self, *a):
        pass

    def feed(self):
        pending, t0, k, next_q_ok_at = [], time.perf_counter(), 0, 0.0
        done_after_play = None
        while True:
            # schedule the next question once the previous reply has been played and the app listens again
            if not pending and state["q"] + 1 <= len(QUESTIONS):
                ready = state["q"] == -1 or (state["plays"] >= state["q"] + 2 and not g.get("is_speaking", True))
                if ready:
                    done_after_play = done_after_play or time.perf_counter()
                    if time.perf_counter() - done_after_play >= 1.0:
                        if state["q"] + 1 == len(QUESTIONS):
                            finish()
                        d, last = load_q(state["q"] + 1)
                        pcm = np.concatenate([np.zeros(int(LEAD_S * RATE), np.int16), d]).astype(np.int16)
                        # distance from chunk boundary k to the last audible sample, in time
                        end_t = t0 + k * BLOCK / RATE + (int(LEAD_S * RATE) + last) / RATE
                        ev("speech_end", t=end_t, q=state["q"] + 1)  # acoustic end of speech (overrides t below)
                        events[-1]["t"] = end_t
                        pcm = np.concatenate([pcm, np.zeros((-len(pcm)) % BLOCK, np.int16)])
                        pending = [pcm[i:i + BLOCK].tobytes() for i in range(0, len(pcm), BLOCK)]
                        state["q"] += 1
                        done_after_play = None
            chunk = pending.pop(0) if pending else bytes(BLOCK * 2)
            k += 1
            wait = t0 + k * BLOCK / RATE - time.perf_counter()  # a block arrives when it has been recorded
            if wait > 0:
                time.sleep(wait)
            self.cb(chunk, BLOCK, None, None)


# ---------- wrappers ----------
def install():
    import types
    fake = types.ModuleType("sounddevice")
    fake.RawInputStream = FakeStream
    sys.modules["sounddevice"] = fake

    import vosk
    class KR(vosk.KaldiRecognizer):
        def AcceptWaveform(self, data):
            t0 = time.perf_counter()
            r = super().AcceptWaveform(data)
            if r:
                ev("accept_true", t0=t0)
            return r

        def Result(self):
            t0 = time.perf_counter()
            r = super().Result()
            ev("result", t0=t0, text=json.loads(r).get("text", ""))
            state["counted"] = False  # the next PlaySound belongs to a new reply
            return r
    vosk.KaldiRecognizer = KR
    orig_model = vosk.Model.__init__
    def model_init(self, *a, **k):
        ev("vosk_load_start"); orig_model(self, *a, **k); ev("vosk_load_end")
    vosk.Model.__init__ = model_init

    import gpt4all
    from gpt4all._pyllmodel import LLModel
    orig_init, orig_gen = gpt4all.GPT4All.__init__, gpt4all.GPT4All.generate
    ptok = [0]
    def prompt_cb(token_id):  # llama.cpp calls this once per prompt token it evaluates
        ptok[0] += 1
        return True
    LLModel._prompt_callback = staticmethod(prompt_cb)
    def init(self, *a, **k):
        ev("llm_load_start"); orig_init(self, *a, **k); ev("llm_load_end")
        ev("llm_info", threads=self.model.thread_count(), device=str(self.device), kwargs=repr(k))
    def gen(self, prompt, **k):
        cnt = [0]
        def cb(token_id, response):
            if cnt[0] == 0:
                ev("first_token")
            cnt[0] += 1
            return True
        k["callback"] = cb
        ptok[0] = 0
        ev("llm_start", prompt_chars=len(prompt))
        def end(reply):
            ev("llm_end", tokens=cnt[0], reply=reply, prompt_tokens=ptok[0], n_past=self.model.context.n_past,
               kwargs=repr({a: b for a, b in k.items() if a != "callback"}))
        out = orig_gen(self, prompt, **k)
        if isinstance(out, str):
            end(out)
            return out
        def stream():  # streaming=True returns a generator: the LLM ends when it is exhausted
            parts = []
            for piece in out:
                parts.append(piece)
                yield piece
            end("".join(parts))
        return stream()
    gpt4all.GPT4All.__init__, gpt4all.GPT4All.generate = init, gen

    def run(*a, **k):
        ev("tts_start"); r = orig_run(*a, **k); ev("tts_end"); return r
    subprocess.run = run

    import winsound
    def play(path, flags):
        with wave.open(path) as w:
            dur = w.getnframes() / w.getframerate(); sr = w.getframerate()
        ev("play", audio_s=dur, sample_rate=sr)
        if not state["counted"]:
            state["plays"] += 1
            state["counted"] = True
        time.sleep(dur)  # audio is not played, but the call blocks for as long as the real one would
        ev("play_end")
    winsound.PlaySound = play


def med_worst(v):
    return statistics.median(v), max(v)


def finish():
    stop.set()
    E = events
    def first(name, after, **match):
        for e in E:
            if e["name"] == name and e["t"] >= after and all(e.get(a) == b for a, b in match.items()):
                return e
    rows = []
    ends = [x for x in E if x["name"] == "speech_end"]
    for i, e in enumerate(ends):
        a = first("accept_true", e["t"] - 0.01)
        r = first("result", a["t"])
        ls, ft_, le = first("llm_start", r["t"]), None, None
        ft_ = first("first_token", ls["t"]); le = first("llm_end", ls["t"])
        ts, te = first("tts_start", ls["t"]), None  # with streaming the first Piper run starts before the LLM ends
        te = first("tts_end", ts["t"]); pl = first("play", te["t"])
        # everything this reply did, up to the next question
        until = ends[i + 1]["t"] if i + 1 < len(ends) else float("inf")
        W = lambda name: [x for x in E if x["name"] == name and ls["t"] <= x["t"] < until]
        plays, play_ends, sents = W("play"), W("play_end"), W("sentence")
        rel = lambda x: (x["t"] - r["t"]) * 1000  # ms after the recognised text
        rows.append({
            "n_sentences": len(plays),
            "first_sentence_ms": rel(sents[0]) if sents else None,  # None when not streaming
            "first_tts_start_ms": rel(ts), "first_tts_end_ms": rel(te),
            "last_play_end_ms": rel(play_ends[-1]),
            "gaps_ms": [(p["t"] - pe["t"]) * 1000 for pe, p in zip(play_ends, plays[1:])],  # silence between sentences
            "reply_audio_s": sum(p["audio_s"] for p in plays),
            "q": e["q"] + 1, "text": r["text"], "reply": le["reply"].strip(), "tokens": le["tokens"],
            "endpoint_wait_ms": (a["t0"] - e["t"]) * 1000,
            "final_accept_ms": (a["t"] - a["t0"]) * 1000,
            "result_ms": (r["t"] - r["t0"]) * 1000,
            "speech_end_to_text_ms": (r["t"] - e["t"]) * 1000,
            "text_to_first_token_ms": (ft_["t"] - r["t"]) * 1000,
            "llm_total_ms": (le["t"] - ls["t"]) * 1000,
            "llm_prefill_ms": (ft_["t"] - ls["t"]) * 1000,
            "decode_tok_s": (le["tokens"] - 1) / max(le["t"] - ft_["t"], 1e-9),
            "tts_ms": (te["t"] - ts["t"]) * 1000,
            "text_to_first_audio_ms": (pl["t"] - r["t"]) * 1000,
            "speech_end_to_first_audio_ms": (pl["t"] - e["t"]) * 1000,
            "win": (a["t0"], play_ends[-1]["t"]), "prompt_chars": ls["prompt_chars"], "audio_s": pl["audio_s"],
            "sample_rate": pl["sample_rate"], "prompt_tokens": le["prompt_tokens"], "n_past": le["n_past"],
            "ends_sentence": le["reply"].strip().endswith((".", "!", "?"))})
    # resources over each reply window (accept_true -> end of the reply's last playback)
    S = res_samples
    for r in rows:
        w = [s for s in S if r["win"][0] <= s[0] <= r["win"][1]]
        cores, sysb = [], []
        for p, q in zip(w, w[1:]):
            dt = q[0] - p[0]
            if dt > 0.05:
                cores.append((q[1] - p[1]) / dt)
                tot = q[3] - p[3]
                sysb.append(100 * (1 - (q[2] - p[2]) / tot) if tot else 0)
        gw = [x for x in gpu_samples if r["win"][0] - 0.5 <= x[0] <= r["win"][1] + 0.5]
        r["peak_proc_cores"] = max(cores) if cores else 0
        r["peak_proc_pct_of_cpu"] = 100 * r["peak_proc_cores"] / (os.cpu_count() or 1)
        r["peak_sys_cpu_pct"] = max(sysb) if sysb else 0
        r["peak_ws_mb"] = max(s[4] for s in w) / 2**20 if w else 0
        r["peak_gpu_util"] = max((x[1] for x in gw), default=None)
        r["peak_gpu_mem_mib"] = max((x[2] for x in gw), default=None)
    out = {"rows": rows,
           "overall_peak_ws_mb": max(s[5] for s in S) / 2**20, "overall_peak_private_mb": max(s[6] for s in S) / 2**20,
           "gpu_all_max_util": max((x[1] for x in gpu_samples), default=None),
           "gpu_all_max_mem_mib": max((x[2] for x in gpu_samples), default=None), "gpu_samples": len(gpu_samples),
           "loads": {n: sum(1 for e in E if e["name"] == n) for n in ("vosk_load_start", "llm_load_start")},
           "llm_info": next(e for e in E if e["name"] == "llm_info"),
           "gen_kwargs": next(e["kwargs"] for e in E if e["name"] == "llm_end"),
           "startup_s": next(e for e in E if e["name"] == "stream_open")["t"] - t_zero,
           "events": [{k: v for k, v in e.items()} for e in E]}
    out["target"], out["label"], out["tuning"] = ARGS.target, ARGS.label, ARGS.tuning
    out["cpu_threads_logical"] = os.cpu_count()
    Path(ARGS.out).parent.mkdir(parents=True, exist_ok=True)
    Path(ARGS.out).write_text(json.dumps(out, indent=1, default=str))
    for r in rows:
        print(f"Q{r['q']} heard={r['text']!r} ptok={r['prompt_tokens']} (n_past={r['n_past']}) tok={r['tokens']} "
              f"A={r['speech_end_to_text_ms']:.0f} B={r['text_to_first_token_ms']:.0f} C={r['llm_total_ms']:.0f} "
              f"D={r['text_to_first_audio_ms']:.0f} E={r['speech_end_to_first_audio_ms']:.0f} | {r['reply']}")
    print("threads:", out["llm_info"].get("threads"), "gen_kwargs:", out["gen_kwargs"],
          "gpu max util/mem:", out["gpu_all_max_util"], out["gpu_all_max_mem_mib"], "->", ARGS.out)
    os._exit(0)


TARGETS = {"lumo": LUMO / "main.py", "v0": ROOT / "pipeline" / "jarvis_v0.py", "v1": ROOT / "pipeline" / "jarvis_v1.py"}

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Time ONE pass (5 questions) of a voice loop with a fake real-time mic.")
    ap.add_argument("--target", choices=TARGETS, default="lumo")
    ap.add_argument("--label", default=None)
    ap.add_argument("--tuning", default="", help="JSON string handed to jarvis_v1 via JARVIS_TUNING")
    ap.add_argument("--out", default=str(ROOT / "results" / "raw" / "snapshot_events.json"))
    ARGS = ap.parse_args()
    ARGS.label = ARGS.label or ARGS.target
    ARGS.out = str(Path(ARGS.out).resolve())  # before chdir below
    if ARGS.tuning:
        os.environ["JARVIS_TUNING"] = ARGS.tuning
    os.chdir(LUMO)  # Lumo uses relative paths; ours uses absolute ones, so this is harmless for v0/v1
    for i in range(len(QUESTIONS)):
        load_q(i)  # make missing question WAVs now, not in the middle of the timed run
    install()
    threading.Thread(target=res_loop, daemon=True).start()
    threading.Thread(target=gpu_loop, daemon=True).start()
    ev("start")
    path = TARGETS[ARGS.target]
    g["__file__"] = str(path)
    exec(compile(path.read_text(encoding="utf-8"), str(path.name), "exec"), g)
