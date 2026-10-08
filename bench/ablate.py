"""Run several configurations over N passes (interleaved) with bench/snapshot_harness.py and aggregate them.

Run with Lumo's venv (the workers need vosk/gpt4all):
  baselines\\lumo\\.venv\\Scripts\\python.exe bench\\ablate.py --passes 3 --md results\\gate_a.md ^
      --cfg lumo|lumo|  --cfg v0|v0|
  --cfg takes  label|target|tuning-json   (tuning is only used by the v1 target)
  --aggregate-only  re-reads results/raw/passes/<label>_p<N>.json without running anything.
Interleaving (cfg1 pass1, cfg2 pass1, cfg1 pass2, ...) spreads thermal / background drift over all configs.
Each pass = fresh process (fresh history, models loaded once) = greeting + the same 5 questions.
"""
import argparse, json, statistics as st, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASSES = ROOT / "results" / "raw" / "passes"
HARNESS = ROOT / "bench" / "snapshot_harness.py"


def run_pass(label, target, tuning, n):
    out = PASSES / f"{label}_p{n}.json"
    cmd = [sys.executable, "-u", str(HARNESS), "--target", target, "--label", label, "--out", str(out)]
    if tuning:
        cmd += ["--tuning", tuning]
    print(f"== {label} pass {n}", flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**__import__("os").environ, "PYTHONUTF8": "1"})
    for line in r.stdout.splitlines():
        if line.startswith(("Q", "threads:")):
            print("  " + line, flush=True)
    if r.returncode != 0 or not out.exists():
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit(f"pass failed: {label} p{n}")


def load(label):
    return [json.loads(p.read_text()) for p in sorted(PASSES.glob(f"{label}_p*.json"))]


def mw(v):
    return f"{st.median(v):.0f} / {max(v):.0f}"


def table(labels):
    hdr = ["Config", "n", "A end-of-speech->text", "B text->1st token", "C LLM total", "D text->1st audio",
           "**E end-of-speech->1st audio**", "tok/s", "prompt tokens", "B ms per prompt token", "peak CPU cores", "peak RAM MB",
           "replies cut off"]
    L = ["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    per_pass = ["| Config | per-pass median of E (ms) | per-pass median of B (ms) |", "|---|---|---|"]
    for lab in labels:
        runs = load(lab)
        if not runs:
            continue
        rows = [r for run in runs for r in run["rows"]]
        g = lambda k: [r[k] for r in rows]
        bpt = [r["text_to_first_token_ms"] / r["prompt_tokens"] for r in rows]
        thr = runs[0]["llm_info"].get("threads")
        L.append("| " + " | ".join([
            f"`{lab}` ({thr} thr)", str(len(rows)), mw(g("speech_end_to_text_ms")), mw(g("text_to_first_token_ms")),
            mw(g("llm_total_ms")), mw(g("text_to_first_audio_ms")), "**" + mw(g("speech_end_to_first_audio_ms")) + "**",
            f"{st.median(g('decode_tok_s')):.1f}", f"{st.median(g('prompt_tokens')):.0f}", f"{st.median(bpt):.0f}",
            f"{max(g('peak_proc_cores')):.1f}", f"{max(g('peak_ws_mb')):.0f}",
            f"{sum(1 for r in rows if not r['ends_sentence'])}/{len(rows)}"]) + " |")
        per_pass.append(f"| `{lab}` | " + ", ".join(f"{st.median(r['speech_end_to_first_audio_ms'] for r in run['rows']):.0f}" for run in runs)
                        + " | " + ", ".join(f"{st.median(r['text_to_first_token_ms'] for r in run['rows']):.0f}" for run in runs) + " |")
    return L, per_pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", action="append", default=[], help="label|target|tuning-json")
    ap.add_argument("--passes", type=int, default=3)
    ap.add_argument("--md", default=None)
    ap.add_argument("--title", default="Ablation")
    ap.add_argument("--aggregate-only", action="store_true")
    ap.add_argument("--labels", default=None, help="comma list for aggregate-only (default: labels in --cfg)")
    a = ap.parse_args()
    cfgs = [c.split("|", 2) + [""] * (3 - len(c.split("|", 2))) for c in a.cfg]
    PASSES.mkdir(parents=True, exist_ok=True)
    if not a.aggregate_only:
        for n in range(1, a.passes + 1):
            for label, target, tuning in cfgs:
                if not (PASSES / f"{label}_p{n}.json").exists():
                    run_pass(label, target, tuning, n)
    labels = a.labels.split(",") if a.labels else [c[0] for c in cfgs]
    L, pp = table(labels)
    md = [f"# {a.title}", "", "**DEVELOPMENT LAPTOP - NOT FINAL NUMBERS.** Synthetic Piper speech, fake real-time mic, audio not played "
          "(first audio = `PlaySound` call). Each cell is `median / worst` in ms over all questions of all passes "
          "(n = 5 questions x passes). Peaks are the maximum over all replies.", ""] + L + [""] + pp
    print("\n".join(md))
    if a.md:
        Path(a.md).write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
