import Back from "./Back.jsx";
import { useSnapshot, ms, pct } from "../api.js";

// B1/B2 baseline rows withheld until baseline results exist.
export default function Benchmarks({ go }) {
  const d = useSnapshot();
  const rows = d?.rows ?? [];
  const lat = rows.map((r) => r.speech_end_to_first_audio_ms);
  const cores = rows.length ? Math.max(...rows.map((r) => r.peak_proc_cores)) : null;
  const ram = d?.overall_peak_ws_mb;
  return (
    <section className="view-container active">
      <Back onClick={() => go("main")} />
      <div className="page-heading"><h2 className="page-title">Benchmark Results</h2><p className="page-subtitle">ABLE performance measurements</p></div>
      <div className="benchmark-hero-stats">
        <div className="bench-stat-card highlight"><div className="bench-stat-label">Median Latency</div><div className="bench-stat-num">{ms(pct(lat, 0.5))}</div><div className="bench-stat-meta">Speech end → first audio</div></div>
        <div className="bench-stat-card"><div className="bench-stat-label">P95 Latency</div><div className="bench-stat-num">{ms(pct(lat, 0.95))}</div><div className="bench-stat-meta">Upper bound threshold</div></div>
        <div className="bench-stat-card">
          <div className="bench-stat-label">Resource Overhead</div>
          <div className="bench-stat-num">{cores == null ? "—" : cores.toFixed(1)} <span style={{ fontSize: 16, fontWeight: 500 }}>cores</span></div>
          <div className="bench-stat-meta">RAM {ram == null ? "—" : (ram / 1024).toFixed(1)} GB · GPU {d?.gpu_all_max_util ?? "—"}%</div>
        </div>
      </div>
      <div className="bench-comparison-card">
        <h3 className="bench-table-heading">Per-Query Results</h3>
        <table className="comparison-table">
          <thead><tr><th>Query</th><th>Latency</th><th>Decode</th><th>CPU</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.q}><td><strong>{r.text}</strong></td><td>{ms(r.speech_end_to_first_audio_ms)}</td><td>{r.decode_tok_s.toFixed(1)} tok/s</td><td>{r.peak_proc_cores.toFixed(1)} cores</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
