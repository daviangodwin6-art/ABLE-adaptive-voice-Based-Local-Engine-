"""Live web view of the voice loop for demos (Python stdlib server + a small React page, offline at run time).

Runs pipeline/jarvis_v1.py UNCHANGED with the real microphone and speakers, and wraps the same four calls the
bench wraps (VOSK Result, GPT4All.generate, the Piper subprocess, winsound.PlaySound) to show the current stage,
the reply as it is written, and the timings of every turn. Settings come from config/pipeline.toml as usual.

  once:  cd demo ; npm install          (React 18.3.1, the only download)
  run:   baselines\\lumo\\.venv\\Scripts\\python.exe demo\\web_demo.py      then open http://localhost:8765
"""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"  # never touch the GPU

import json, subprocess, sys, threading, time
# E1 + E2 + E3 winners (results/ablation.md). The demo uses them unless JARVIS_TUNING is set to something non-empty; pipeline.toml keeps the v0 defaults.
if not os.environ.get("JARVIS_TUNING"):
    os.environ["JARVIS_TUNING"] = json.dumps({"n_batch": 128, "n_threads": 5, "history_turns": 3,
                                              "max_tokens": 100, "min_conf": 0.5, "end_silence_ms": 700, "prompt_style": "tiny", "stream": True, "length_scale": 0.88,
                                              "stt_model": "vosk-model-small-en-us-0.15",
                                              "stt_engine": "whisper", "whisper_model": "whisper-base.en"})
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from asr_fix import fix_asr, cut_role_echo, is_confident
TARGET = ROOT / "pipeline" / "jarvis_v1.py"
PORT = 8765

lock = threading.Lock()
READ, WRITE, VOICE, SPEAK = "Reading the prompt", "Writing the reply", "Making the voice", "Speaking"
# "on" holds every stage active right now: with streaming several are lit at once, which is the point.
S = {"on": set(), "turns": [{"heard": "(start-up greeting)", "reply": "", "t": time.perf_counter()}]}
g = {"__name__": "__main__", "__file__": str(TARGET)}


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


def heard_event(name, **kw):
    """Whisper engine: jarvis_v1 reports the recognised phrase here (Vosk is hooked in install())."""
    if name == "heard":
        with lock:
            S["turns"].append({"heard": kw["text"], "reply": "", "t": time.perf_counter()})
            S["on"] = {READ}


def start():
    """Run the voice loop in a thread (button on the page). False if it is already running."""
    with lock:
        if S.get("running"):
            return False
        S["running"] = True
        S["on"] = set()
        g.clear()
        g.update({"__name__": "__main__", "__file__": str(TARGET), "timing_event": heard_event})

    def go():
        try:
            exec(compile(TARGET.read_text(encoding="utf-8"), TARGET.name, "exec"), g)
        except BaseException as e:  # SystemExit from a bad config included: show it instead of dying silently
            S["error"] = repr(e)
        finally:
            S["running"] = False
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
                with lock:
                    S["turns"].append({"heard": text, "reply": "", "t": time.perf_counter()})
                    S["on"] = {READ}
            return r
    vosk.KaldiRecognizer = KR

    import gpt4all
    orig_gen = gpt4all.GPT4All.generate
    def gen(self, prompt, **k):
        n = [0]
        def cb(token_id, response):
            n[0] += 1
            text = S["turns"][-1]["reply"] + response
            cut = cut_role_echo(text, g.get("CFG", {}).get("name", "ABLE"))
            mark(on=[WRITE], off=[READ], first={"first_token_ms": since_turn()}, tokens=n[0], reply=cut)
            return cut == text  # False stops the LLM when it starts writing the next "User:" line
        out = orig_gen(self, prompt, callback=cb, **k)
        if isinstance(out, str):
            mark(off=[READ, WRITE])
            return out
        def stream():  # streaming=True returns a generator: the LLM is done when it is exhausted
            yield from out
            mark(off=[READ, WRITE])
        return stream()
    gpt4all.GPT4All.generate = gen

    orig_run = subprocess.run
    def run(cmd, *a, **k):
        if "piper" not in str(cmd):
            return orig_run(cmd, *a, **k)
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
        mark(on=[SPEAK], first={"first_audio_ms": since_turn()}, sentences=S["turns"][-1].get("sentences", 0) + 1)
        orig_play(path, flags)
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
const STAGES=["Loading models","Listening","Reading the prompt","Writing the reply","Making the voice","Speaking"];
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
  const [mode,setMode]=React.useState("mic");
  const btn={font:"inherit",padding:"8px 18px",borderRadius:6,border:0,color:"#fff"};
  React.useEffect(()=>{
    const id=setInterval(async()=>{try{setS(await(await fetch("/state")).json())}catch(e){}},300);
    return()=>clearInterval(id);
  },[]);
  if(!s)return h("p",null,"Connecting...");
  return h(React.Fragment,null,
    h("h1",null,"ABLE - offline voice assistant"),
    h("div",{style:{margin:"8px 0",display:"flex",gap:8,flexWrap:"wrap",alignItems:"center"}},
      [["mic","Mic"],["file","Recorded audio"]].map(([m,label])=>h("button",{key:m,disabled:s.running,onClick:()=>{setMode(m);if(m==="mic")fetch("/run",{method:"POST"});},
        style:{...btn,background:s.running?"#333":mode===m?"#2e7d32":"#444",cursor:s.running?"default":"pointer"}},label)),
      s.running&&h("span",{className:"dim"},"Running (say exit to stop)"),
      mode==="file"&&!s.running&&h("label",{style:{...btn,background:"#1565c0",cursor:"pointer"}},"Upload audio (mp3/wav) and run",
        h("input",{type:"file",accept:"audio/*",style:{display:"none"},onChange:async e=>{
          const f=e.target.files[0];if(!f)return;
          await fetch("/test",{method:"POST",headers:{"X-Filename":f.name},body:f});e.target.value="";}}))),
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


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/state":
            with lock:
                idle = "Listening" if "llm" in g and not g.get("is_speaking") else "Loading models" if "llm" not in g else ""
                run = bool(S.get("running"))
                state = {"on": sorted(S["on"]) or ([idle] if run else []), "turns": S["turns"], "settings": g.get("PIPE", {}),
                         "running": run, "error": S.get("error", "")}
                body, ctype = json.dumps(state).encode(), "application/json"
        elif self.path in REACT:
            body, ctype = REACT[self.path].read_bytes(), "text/javascript"
        else:
            body, ctype = PAGE.encode(), "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/test":  # recorded audio instead of the microphone (pipeline/jarvis_v1.py test mode)
            n = int(self.headers.get("Content-Length", 0))
            ext = Path(self.headers.get("X-Filename", "a.mp3")).suffix.lower()
            if n > 20_000_000 or ext not in (".mp3", ".wav", ".flac", ".ogg") or S.get("running"):
                self.send_response(400)
                self.end_headers()
                return
            path = ROOT / "results" / "raw" / f"test_upload{ext}"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(self.rfile.read(n))
            S.pop("error", None)
            os.environ["JARVIS_TEST_FILE"] = str(path)
            start()
            self.send_response(204)
            self.end_headers()
            return
        if self.path == "/run":
            S.pop("error", None)
            os.environ.pop("JARVIS_TEST_FILE", None)  # live microphone
            start()
        self.send_response(204)
        self.end_headers()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # the loop prints an emoji
    if not all(p.exists() for p in REACT.values()):
        raise SystemExit("React is not installed. Run once (needs internet):  cd demo ; npm install")
    install()
    print(f"[*] Live view: http://127.0.0.1:{PORT}  (press Start ABLE on the page; Ctrl+C here to quit)")
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
