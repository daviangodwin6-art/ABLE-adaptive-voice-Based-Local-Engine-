import Back from "./Back.jsx";
import { useSnapshot } from "../api.js";

// Read-only. Pipeline settings come live from /state (settings = PIPE); model name from the benchmark snapshot.
// Wake word (none configured), persona editing, CPU/RAM limits → withheld.
export default function Config({ live, go }) {
  const snap = useSnapshot();
  const p = live.settings ?? {};
  const model = p.llm_model ?? snap?.llm_info?.kwargs?.match(/'model_name': '([^']+)'/)?.[1];
  const rows = [
    ["Model", model?.replace(/\.gguf.*$/, "")],
    ["Quantization", model?.match(/q\d_\w+?(?=\.|$)/i)?.[0].toUpperCase()],
    ["LLM Runtime", p.llm_backend],
    ["Threads", p.n_threads ?? snap?.llm_info?.threads],
    ["Batch Size", p.n_batch],
    ["Max Tokens", p.max_tokens ?? snap?.gen_kwargs?.max_tokens],
    ["History Turns", p.history_turns],
    ["Speech Engine", p.stt_engine && `${p.stt_engine} · ${p.stt_engine === "whisper" ? p.whisper_model : p.stt_model}`],
    ["Streaming", p.stream == null ? null : p.stream ? "On" : "Off"],
    ["Persona", "ABLE"],
  ];
  return (
    <section className="view-container active">
      <Back onClick={() => go("main")} />
      <div className="page-heading"><h2 className="page-title">Configuration</h2><p className="page-subtitle">Current local assistant configuration</p></div>
      <div className="config-grid-card">
        <div className="config-card-header"><span className="config-section-title">Engine Runtime Specifications</span><span className="badge-readonly">READ ONLY</span></div>
        <table className="config-table">
          <tbody>
            {rows.map(([k, v]) => (
              <tr key={k}><td className="config-key">{k}</td><td className="config-val"><span className="config-val-badge">{v ?? "—"}</span></td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
