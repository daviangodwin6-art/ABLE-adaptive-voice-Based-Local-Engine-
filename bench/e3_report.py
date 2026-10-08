"""Per-question and short/long tables for the streaming comparison (reads results/raw/passes/<label>_p*.json).

  baselines\\lumo\\.venv\\Scripts\\python.exe bench\\e3_report.py e3_off e3_on
Times are medians over the passes, in ms. Short = questions 1-5, long = questions 6-8 (BENCH_LONG=1).
"""
import json, statistics as st, sys
from pathlib import Path

PASSES = Path(__file__).resolve().parent.parent / "results" / "raw" / "passes"
TIMES = [("A", "speech_end_to_text_ms"), ("B", "text_to_first_token_ms"), ("C", "llm_total_ms"),
         ("D", "text_to_first_audio_ms"), ("E", "speech_end_to_first_audio_ms")]


def cells(rows):
    gaps = [g for r in rows for g in r["gaps_ms"]]
    m = lambda k: f"{st.median(r[k] for r in rows):.0f}"
    return [m(k) for _, k in TIMES] + [
        f"{max(r['speech_end_to_first_audio_ms'] for r in rows):.0f}",
        f"{st.median(r['n_sentences'] for r in rows):g}",
        f"{st.median(gaps):.0f} / {max(gaps):.0f} ({sum(g > 300 for g in gaps)} of {len(gaps)} over 300)" if gaps else "-",
        f"{st.median(r['decode_tok_s'] for r in rows):.1f}",
        f"{max(r['peak_proc_cores'] for r in rows):.1f}", f"{max(r['peak_sys_cpu_pct'] for r in rows):.0f}",
        f"{max(r['peak_ws_mb'] for r in rows):.0f}"]


HDR = [n for n, _ in TIMES] + ["E worst", "sentences", "gaps median / worst", "tok/s", "peak cores", "peak machine CPU %", "peak RAM MB"]


def main(labels):
    data = {lab: [r for p in sorted(PASSES.glob(f"{lab}_p*.json")) for r in json.loads(p.read_text())["rows"]] for lab in labels}
    out = ["| Questions | Config | " + " | ".join(HDR) + " |", "|" + "---|" * (len(HDR) + 2)]
    nq = max(r["q"] for rows in data.values() for r in rows)
    groups = [(f"Q{q}", [q]) for q in range(1, nq + 1)] + [("**Short (Q1-5)**", range(1, 6))]
    if nq > 5:
        groups += [("**Long (Q6-%d)**" % nq, range(6, nq + 1)), ("**All**", range(1, nq + 1))]
    for name, qs in groups:
        for lab in labels:
            out.append(f"| {name} | `{lab}` | " + " | ".join(cells([r for r in data[lab] if r["q"] in qs])) + " |")
    out += ["", "| Q | Config | Reply (pass 1) | Reply ends a sentence (passes) |", "|---|---|---|---|"]
    for q in range(1, nq + 1):
        for lab in labels:
            rs = [r for r in data[lab] if r["q"] == q]
            out.append(f"| Q{q} | `{lab}` | {rs[0]['reply']} | {sum(r['ends_sentence'] for r in rs)}/{len(rs)} |")
    print("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1:])
