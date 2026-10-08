import { run, skip, ms, heroState, pct, realTurns, useSnapshot } from "../api.js";

// Stages as the backend reports them (s.on). MIC/VAD and SPEECH timings aren't exposed by /state → withheld.
const STAGES = [
  ["HEARING", "Transcribing", (t) => t.asr_ms],
  ["READING", "Reading the prompt", (t) => (t.first_token_ms != null ? t.first_token_ms - (t.asr_ms ?? 0) : null)],
  ["WRITING", "Writing the reply", (t) => (t.tts_start_ms != null && t.first_token_ms != null ? t.tts_start_ms - t.first_token_ms : null)],
  ["VOICE", "Making the voice", (t) => t.tts_ms],
  ["SPEAKING", "Speaking", (t) => t.first_audio_ms],
];
const LABEL = { LISTENING: "Listening", THINKING: "Thinking", SPEAKING: "Speaking", IDLE: "Idle" };
const Icon = ({ d, children }) => (
  <svg fill="none" height="15" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" width="15">{children ?? <path d={d} />}</svg>
);

export default function Home({ live, go }) {
  const snap = useSnapshot();
  const state = heroState(live);
  const turns = realTurns(live);
  const last = turns[turns.length - 1];
  const lat = turns.map((t) => t.first_audio_ms).filter((v) => v != null);
  const cur = last?.first_audio_ms;
  const busy = state === "THINKING" || state === "SPEAKING";
  const stop = busy && <button className="btn-terminate" onClick={skip} title="Stop this reply and listen again">✕ Terminate</button>;
  // While the next phrase is being transcribed its turn does not exist yet: show an empty pipeline, not the last turn's ticks.
  const shown = live.on.includes("Transcribing") ? null : last;
  const [curVal, curUnit] = cur == null ? ["—", ""] : ms(cur).split(" ");
  const h = new Date().getHours();
  // /state has no live resource sampling; show the benchmark run's peaks.
  const rows = snap?.rows ?? [];
  const cores = rows.length ? Math.max(...rows.map((r) => r.peak_proc_cores)) : null;
  const ram = snap?.overall_peak_ws_mb, gpu = snap?.gpu_all_max_util;

  return (
    <main className="view-container active">
      <section className={"voice-hero-card" + (state === "LISTENING" ? " listening" : "")}>
        <span className="greeting-tag">{h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"} 👋</span>
        <h1 className="hero-prompt">“How can I help?”</h1>
        <div className="mic-button-wrapper">
          <div className="mic-button-ring"></div>
          <button aria-label="Start voice loop" className="mic-button" onClick={run} disabled={live.running || !live.online}>
            <svg className="mic-icon-svg" viewBox="0 0 24 24">
              <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.3-3c0 3-2.54 5.1-5.3 5.1S6.7 14 6.7 11H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c3.28-.48 6-3.3 6-6.72h-1.7z"></path>
            </svg>
          </button>
        </div>
        <div className="voice-state-label"><span>{LABEL[state]}</span></div>
        <p className="assistant-state-hint">
          {live.error ? "Stopped: " + live.error : !live.online ? "Backend offline — run demo/web_demo.py" : live.running ? "Running — say “exit” to stop" : "Tap microphone to start the voice loop"}
        </p>
        {live.mic && <p className="assistant-state-hint">Mic: {live.mic}</p>}
        <div className="conversation-preview-box">
          {last?.heard && <div className="transcript-turn"><div className="transcript-speaker">USER</div><div className="transcript-text">{last.heard}</div></div>}
          {last?.reply && <div className="transcript-turn">{stop}<div className="transcript-speaker">ABLE</div><div className="transcript-text">{last.reply}</div></div>}
          {state === "SPEAKING" && last?.reply && (
            <div className="speaking-indicator-box" style={{ display: "flex" }}>
              {stop}
              <div className="speaking-meta">
                <div className="speaking-title"><span>CURRENTLY SPEAKING</span></div>
                <div className="speaking-quote">“{last.reply}”</div>
              </div>
              <div className="waveform-container">{[...Array(6)].map((_, i) => <div key={i} className="wave-bar"></div>)}</div>
            </div>
          )}
        </div>
      </section>

      <div className="metrics-and-pipeline-grid">
        <section className="metric-card-prominent">
          <div>
            <div className="metric-label-caps">Time to First Sound</div>
            <div className="metric-hero-val"><span>{curVal}</span><span className="metric-unit">{curUnit}</span></div>
          </div>
          <div className="metric-substats">
            <span>Median <strong>{ms(pct(lat, 0.5))}</strong></span>
            <span>P95 <strong>{ms(pct(lat, 0.95))}</strong></span>
          </div>
        </section>
        <section className="pipeline-card">
          <div className="pipeline-header">
            <span className="pipeline-title">Runtime Pipeline Execution</span>
            <span className="pipeline-total-time">Total: {ms(cur)}</span>
          </div>
          <div className="pipeline-timeline">
            {STAGES.map(([label, key, time], i) => {
              const v = shown ? time(shown) : null;
              return <Stage key={label} label={label} time={ms(v)} active={live.on.includes(key)} done={v != null} last={i === STAGES.length - 1} />;
            })}
          </div>
        </section>
      </div>

      <section className="resources-row">
        <Res name="CPU (peak)" val={cores == null ? "—" : `${cores.toFixed(1)} cores`} w={cores == null ? 0 : (cores / 8) * 100} />
        <Res name="RAM (peak)" val={ram == null ? "—" : `${(ram / 1024).toFixed(1)} GB`} w={ram == null ? 0 : Math.min(100, (ram / 4096) * 100)} />
        <Res name="GPU" val={gpu == null ? "—" : `${gpu}% ✓`} w={gpu ?? 0} green />
      </section>

      <div className="system-status-row">
        {["LOCAL PROCESSING", "CPU-ONLY", "OFFLINE"].map((t) => <div key={t} className="sys-check-badge"><span className="sys-check-icon">✓</span> {t}</div>)}
      </div>

      <nav aria-label="Application Sections" className="main-nav-actions">
        <button className="btn-nav-tile" onClick={() => go("config")}><Icon><circle cx="12" cy="12" r="3"></circle></Icon> VIEW CONFIG</button>
        <button className="btn-nav-tile" onClick={() => go("history")}><Icon d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /> VIEW HISTORY</button>
        <button className="btn-nav-tile" onClick={() => go("benchmarks")}><Icon d="M18 20V10M12 20V4M6 20v-6" /> RESULTS</button>
        <button className="btn-nav-tile" onClick={() => go("replay")}><Icon><circle cx="12" cy="12" r="10"></circle><polygon points="10 8 16 12 10 16 10 8"></polygon></Icon> REPLAY</button>
      </nav>
    </main>
  );
}

function Stage({ label, time, active, done, last }) {
  return (
    <>
      <div className="pipeline-stage">
        <div className={"stage-node" + (active ? " active" : done ? " done" : "")}>{done && !active ? "✓" : ""}</div>
        <div className="stage-label">{label}</div>
        <div className="stage-time">{time}</div>
      </div>
      {!last && <div className={"pipeline-connector" + (done ? " active" : "")}></div>}
    </>
  );
}

function Res({ name, val, w, green }) {
  return (
    <div className="resource-item">
      <div className="resource-header"><span className="resource-name">{name}</span><span className="resource-val">{val}</span></div>
      <div className="progress-track"><div className={"progress-fill" + (green ? " green" : "")} style={{ width: w + "%" }}></div></div>
    </div>
  );
}
