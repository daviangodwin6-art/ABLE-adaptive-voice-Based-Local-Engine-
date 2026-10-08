"""Live web view of the voice loop for demos (Python stdlib server + a small React page, offline at run time).

Runs pipeline/jarvis_v1.py UNCHANGED with the real microphone and speakers, and wraps the same four calls the
bench wraps (VOSK Result, GPT4All.generate, the Piper subprocess, winsound.PlaySound) to show the current stage,
the reply as it is written, and the timings of every turn. Settings come from config/pipeline.toml as usual.

  once:  cd demo ; npm install          (React 18.3.1, the only download)
  run:   baselines\\lumo\\.venv\\Scripts\\python.exe demo\\web_demo.py      then open http://localhost:8765
"""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"  # never touch the GPU

import json, mimetypes, subprocess, sys, threading, time, wave
# E1 + E2 + E3 winners (results/ablation.md). The demo uses them unless JARVIS_TUNING is set to something non-empty; pipeline.toml keeps the v0 defaults.
if not os.environ.get("JARVIS_TUNING"):
    os.environ["JARVIS_TUNING"] = json.dumps({"n_batch": 128, "n_threads": 5, "history_turns": 3,
                                              "max_tokens": 100, "min_conf": 0.5, "end_silence_ms": 700, "prompt_style": "tiny", "stream": True, "length_scale": 0.88,
                                              "stt_model": "vosk-model-small-en-us-0.15",
                                              "stt_engine": "whisper", "whisper_model": "whisper-base.en",
                                              "llm_backend": "llama_cpp", "llm_model": "gemma-3-1b-it-Q4_0.gguf"})
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from asr_fix import fix_asr, cut_role_echo, is_confident
TARGET = ROOT / "pipeline" / "jarvis_v1.py"
PORT = 8765

lock = threading.Lock()
HEAR, READ, WRITE, VOICE, SPEAK = "Transcribing", "Reading the prompt", "Writing the reply", "Making the voice", "Speaking"
# "on" holds every stage active right now: with streaming several are lit at once, which is the point.
# "skip" is the Terminate button: the reply in progress is cut (no more tokens, voice clips or playback) until the next turn.
S = {"on": set(), "turns": [{"heard": "(start-up greeting)", "reply": "", "t": time.perf_counter()}]}
g = {"__name__": "__main__", "__file__": str(TARGET)}
PLAY_PAD_S = 0.05  # wait this long past the clip length before the next clip: raise it if sentence ends sound clipped on your speakers


def mark(on=(), off=(), first=None, **fields):
    """Switch stages on/off and update the current turn; `first` fields keep their first value (first sentence)."""
    with lock:
        S["on"] = (S["on"] | set(on)) - set(off)
        cur = S["turns"][-1]
        cur.update(fields)
        for k, v in (first or {}).items():
            cur.setdefault(k, v)


def since_turn():
    return round((time.perf_counter() - S["turns"][-1]["t"]) * 1000)


def new_turn(text):
    """A recognised phrase starts a turn. With Whisper the clock starts where transcription started, so it is counted."""
    now = time.perf_counter()
    with lock:
        t0 = S.pop("asr_t0", None)
        turn = {"heard": text, "reply": "", "t": t0 or now}
        if t0:
            turn["asr_ms"] = round((now - t0) * 1000)
        S["turns"].append(turn)
        S["on"] = {READ}
        S["skip"] = False


def heard_event(name, **kw):
    """Whisper engine: jarvis_v1 reports the recognised phrase here (Vosk is hooked in install())."""
    if name == "heard" and len(kw["text"]) >= 3:  # the loop drops shorter phrases right after reporting them
        new_turn(kw["text"])


def state():
    """/state as JSON text. No stage is lit unless the loop runs; with nothing else on, it is loading, speaking (mic muted) or listening."""
    with lock:
        run = bool(S.get("running"))
        idle = "Loading models" if "llm" not in g else "Speaking" if g.get("is_speaking") else "Listening"
        return json.dumps({"on": (sorted(S["on"]) or [idle]) if run else [], "turns": S["turns"], "settings": g.get("PIPE", {}),
                           "running": run, "error": S.get("error", ""),
                           "mic": g.get("PIPE", {}).get("mic_device") or S.get("mic", "")})


def start():
    """Run the voice loop in a thread (button on the page). False if it is already running."""
    with lock:
        if S.get("running"):
            return False
        S["running"] = True
        S["on"] = set()
        S["skip"] = False
        g.clear()
        g.update({"__name__": "__main__", "__file__": str(TARGET), "timing_event": heard_event})
    try:
        # PortAudio reads the device list once: restart it so the loop gets the microphone Windows uses NOW
        # (a headset plugged in after this server started). Safe here: no stream is open between runs.
        import sounddevice as sd
        sd._terminate()
        sd._initialize()
        S["mic"] = sd.query_devices(kind="input")["name"]
    except Exception as e:  # no microphone at all: the loop reports its own error
        S["mic"] = f"(none: {e})"

    def go():
        try:
            exec(compile(TARGET.read_text(encoding="utf-8"), TARGET.name, "exec"), g)
        except BaseException as e:  # SystemExit from a bad config included: show it instead of dying silently
            S["error"] = repr(e)
        finally:
            S["running"] = False
            S["on"] = set()
    threading.Thread(target=go, daemon=True).start()
    return True


def install():
    import vosk
    class KR(vosk.KaldiRecognizer):
        def Result(self):
            return self._shown(super().Result())

        def FinalResult(self):
            return self._shown(super().FinalResult())

        def _shown(self, r):
            res = json.loads(r)
            text = fix_asr(res.get("text", "").strip())
            if len(text) >= 3 and is_confident(res, g.get("PIPE", {}).get("min_conf", 0.0)):  # same noise filter as the loop
                new_turn(text)
            return r
    vosk.KaldiRecognizer = KR

    try:
        import faster_whisper
        orig_tr = faster_whisper.WhisperModel.transcribe
        def transcribe(self, *a, **k):
            S["asr_t0"] = time.perf_counter()
            mark(on=[HEAR])
            segs, info = orig_tr(self, *a, **k)
            def shown():  # the segments are decoded while the loop reads them: done when exhausted
                try:
                    yield from segs
                finally:
                    mark(off=[HEAR])
            return shown(), info
        faster_whisper.WhisperModel.transcribe = transcribe
    except ImportError:  # Vosk-only install
        pass

    import gpt4all
    from llm_backend import LlamaCppLLM
    def wrap(orig_gen):
        def gen(self, prompt, **k):
            n = [0]
            def cb(token_id, response):
                n[0] += 1
                text = S["turns"][-1]["reply"] + response
                cut = cut_role_echo(text, g.get("CFG", {}).get("name", "ABLE"))
                mark(on=[WRITE], off=[READ], first={"first_token_ms": since_turn()}, tokens=n[0], reply=cut)
                return cut == text and not S.get("skip")  # False stops the LLM: it starts the next "User:" line, or Terminate
            out = orig_gen(self, prompt, callback=cb, **k)
            if isinstance(out, str):
                mark(off=[READ, WRITE])
                return out
            def stream():  # streaming=True returns a generator: the LLM is done when it is exhausted, closed early or fails
                try:
                    yield from out
                finally:
                    mark(off=[READ, WRITE])
            return stream()
        return gen
    for cls in (gpt4all.GPT4All, LlamaCppLLM):  # same view whichever LLM backend pipeline.toml picks
        cls.generate = wrap(cls.generate)

    orig_run = subprocess.run
    def run(cmd, *a, **k):
        if "piper" not in str(cmd):
            return orig_run(cmd, *a, **k)
        if S.get("skip"):  # Terminate: no more voice clips (the loop's TTS worker ends on a failed Piper call)
            return subprocess.CompletedProcess(cmd, 1, b"", b"terminated")
        t0 = time.perf_counter()
        fields = {} if S["turns"][-1]["reply"] else {"reply": str(cmd).split(" | ")[0][5:]}  # fixed greeting: no LLM
        if fields:
            S["turns"][-1]["t"] = t0  # greeting: time from now, not from server start / model loading
        mark(on=[VOICE], off=[READ], first={"tts_start_ms": since_turn()}, **fields)
        r = orig_run(cmd, *a, **k)
        mark(off=[VOICE], first={"tts_ms": round((time.perf_counter() - t0) * 1000)})
        return r
    subprocess.run = run

    import winsound
    orig_play = winsound.PlaySound
    def play(path, flags):
        if S.get("skip"):
            return
        mark(on=[SPEAK], first={"first_audio_ms": since_turn()}, sentences=S["turns"][-1].get("sentences", 0) + 1)
        # Played asynchronously and waited for here: a synchronous PlaySound cannot be stopped from another thread
        # (stopping it blocks until the clip ends), so Terminate would not cut the sound.
        with wave.open(path) as w:
            end = time.perf_counter() + w.getnframes() / w.getframerate() + PLAY_PAD_S
        orig_play(path, flags | winsound.SND_ASYNC)
        while time.perf_counter() < end and not S.get("skip"):
            time.sleep(0.02)
        if S.get("skip"):
            orig_play(None, 0)  # stop the clip now
        mark(off=[SPEAK])
    winsound.PlaySound = play


PAGE = """<!doctype html><meta charset=utf-8><title>ABLE live</title>
<meta name=viewport content="width=device-width,initial-scale=1">
<style>
body{font:16px system-ui,sans-serif;background:#111;color:#eee;margin:0;padding:16px;max-width:900px;margin:auto}
h1{font-size:20px;margin:0 0 4px}small,.dim{color:#999}
#stages{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}
.st{padding:8px 14px;border-radius:20px;background:#222;color:#777}
.st.on{background:#2e7d32;color:#fff;font-weight:600}
.turn{background:#1b1b1b;border-radius:8px;padding:12px;margin:10px 0}
.bar{display:flex;height:14px;border-radius:4px;overflow:hidden;margin:8px 0 4px;background:#222}
.b1{background:#c62828}.b2{background:#ef6c00}.b3{background:#1565c0}
.key i{display:inline-block;width:10px;height:10px;border-radius:2px;margin:0 4px 0 12px}
</style>
<div id=root></div>
<script src="/react.js"></script><script src="/react-dom.js"></script>
<script>
// Plain React.createElement (no JSX), so there is no build step.
const h=React.createElement;
const STAGES=["Loading models","Listening","Transcribing","Reading the prompt","Writing the reply","Making the voice","Speaking"];
const sec=ms=>(ms/1000).toFixed(1)+" s";

function Turn({t}){
  // The bar is the wait until the FIRST sound: reading, writing until the voice starts, making the first voice clip.
  const ft=t.first_token_ms||0,ts=t.tts_start_ms||ft,tts=t.tts_ms||0;
  return h("div",{className:"turn"},
    h("div",{className:"dim"},"You: "+t.heard),
    h("div",null,"ABLE: "+t.reply),
    t.first_audio_ms&&h("div",{className:"bar"},
      (ft?[[ft,"b1"],[ts-ft,"b2"],[tts,"b3"]]:[[tts,"b3"]]).map(([w,c])=>h("div",{key:c,className:c,style:{flex:Math.max(w,0)}}))),
    t.first_audio_ms&&h("div",{className:"dim"},
      (t.first_token_ms?"first word written after "+sec(ft)+", ":"")
      +"first sound after "+sec(t.first_audio_ms)
      +(t.tokens?"  ("+t.tokens+" tokens, spoken in "+t.sentences+(t.sentences>1?" parts)":" part)"):"")));
}

function App(){
  const [s,setS]=React.useState(null);
  const btn={font:"inherit",padding:"8px 18px",borderRadius:6,border:0,color:"#fff"};
  React.useEffect(()=>{
    const id=setInterval(async()=>{try{setS(await(await fetch("/state")).json())}catch(e){}},300);
    return()=>clearInterval(id);
  },[]);
  if(!s)return h("p",null,"Connecting...");
  return h(React.Fragment,null,
    h("h1",null,"ABLE - offline voice assistant"),
    h("div",{style:{margin:"8px 0",display:"flex",gap:8,flexWrap:"wrap",alignItems:"center"}},
      h("button",{disabled:s.running,onClick:()=>fetch("/run",{method:"POST"}),
        style:{...btn,background:s.running?"#333":"#2e7d32",cursor:s.running?"default":"pointer"}},"Start ABLE"),
      s.running&&h("span",{className:"dim"},"Running (say exit to stop)"),
      s.running&&h("button",{onClick:()=>fetch("/skip",{method:"POST"}),style:{...btn,background:"#c62828",cursor:"pointer"}},"Terminate reply"),
      s.mic&&h("span",{className:"dim"},"Mic: "+s.mic)),
    s.error&&h("div",{style:{color:"#ef5350"}},"Stopped: "+s.error),
    h("div",null,h("small",null,Object.entries(s.settings).map(([k,v])=>k+"="+v).join("   "))),
    h("div",{id:"stages"},STAGES.map(n=>h("span",{key:n,className:"st"+(s.on.includes(n)?" on":"")},n))),
    h("div",{className:"key dim"},"Wait until the first sound:",h("i",{className:"b1"}),"reading the prompt",
      h("i",{className:"b2"}),"writing before the voice starts",h("i",{className:"b3"}),"making the first voice clip"),
    s.turns.map((t,i)=>h(Turn,{key:i,t})).reverse());
}
ReactDOM.createRoot(document.getElementById("root")).render(h(App));
</script>"""

# React 18 browser builds, installed locally by `npm install` in demo/ (served from disk: no internet at run time).
NPM = Path(__file__).resolve().parent / "node_modules"
REACT = {"/react.js": NPM / "react/umd/react.production.min.js",
         "/react-dom.js": NPM / "react-dom/umd/react-dom.production.min.js"}


UI = (Path(__file__).resolve().parent / "ui" / "dist").resolve()  # built once with: cd demo\ui ; npm install ; npm run build


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/state":
            body, ctype = state().encode(), "application/json"
        elif self.path in REACT:
            body, ctype = REACT[self.path].read_bytes(), "text/javascript"
        elif (UI / "index.html").exists():  # the built React UI (demo/ui); unknown paths get index.html
            f = (UI / self.path.split("?")[0].lstrip("/")).resolve()
            if not (f.is_file() and UI in f.parents):  # also blocks ../ paths
                f = UI / "index.html"
            body, ctype = f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        else:  # UI not built yet: the old single-page view
            body, ctype = PAGE.encode(), "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/run":
            S.pop("error", None)
            start()
        elif self.path == "/skip" and S.get("running"):  # Terminate button: cut the reply in progress, keep the loop
            S["skip"] = True  # the hooks in install() see it: LLM callback, Piper, playback
        self.send_response(204)
        self.end_headers()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # the loop prints an emoji
    if not (UI / "index.html").exists():
        print("[!] New UI is not built, showing the old page. Build once:  cd demo/ui ; npm install ; npm run build")
        if not all(p.exists() for p in REACT.values()):
            raise SystemExit("React is not installed. Run once (needs internet):  cd demo ; npm install")
    install()
    print(f"[*] Live view: http://127.0.0.1:{PORT}  (press Start ABLE on the page; Ctrl+C here to quit)")
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
