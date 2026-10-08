import { useState } from "react";
import Back from "./Back.jsx";
import { realTurns } from "../api.js";

// Session history only: built from the live /state turns (no persistence yet).
export default function History({ live, go, view, setView }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(null);
  const turns = realTurns(live).map((t, i) => ({ ...t, n: i + 1 }));
  const shown = turns.filter((t) => (t.heard + " " + t.reply).toLowerCase().includes(q.toLowerCase())).reverse();

  if (view === "detail" && open) {
    return (
      <section className="view-container active">
        <Back onClick={() => setView("history")}>← Back to Chat History</Back>
        <div className="detail-header-card">
          <div className="detail-title-group"><h2>{open.heard}</h2><p>Voice conversation transcript</p></div>
          <div className="detail-badge-pill"><span>THIS SESSION · TURN {open.n}</span></div>
        </div>
        <div className="transcript-container-card">
          <div className="transcript-section-title">CHRONOLOGICAL VOICE TRANSCRIPT</div>
          <div className="transcript-flow-list">
            <Row who="USER" text={open.heard} />
            <Row who="ABLE" text={open.reply} />
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="view-container active">
      <Back onClick={() => go("main")} />
      <div className="page-heading"><h2 className="page-title">Chat History</h2><p className="page-subtitle">Conversations from this session</p></div>
      <div className="history-controls-row">
        <div className="search-wrapper">
          <svg className="search-icon" viewBox="0 0 24 24"><circle cx="11" cy="11" fill="none" r="8" stroke="currentColor" strokeWidth="2"></circle><line stroke="currentColor" strokeWidth="2" x1="21" x2="16.65" y1="21" y2="16.65"></line></svg>
          <input aria-label="Search conversations" className="search-input" placeholder="Search conversations..." value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      {shown.length ? (
        <div className="history-group-section">
          <div className="history-group-title">THIS SESSION</div>
          <div className="conversation-card-list">
            {shown.map((t) => (
              <button key={t.n} className="conversation-row" onClick={() => { setOpen(t); setView("detail"); }}>
                <div className="row-meta-left">
                  <h3 className="row-title">{t.heard}</h3>
                  <div className="row-subtext"><span>Turn {t.n}</span>{t.first_audio_ms != null && <><span className="row-subtext-divider">·</span><span>{(t.first_audio_ms / 1000).toFixed(1)} s to first sound</span></>}</div>
                </div>
                <span aria-hidden="true" className="row-chevron">→</span>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="empty-state-box">
          <div className="empty-title">{turns.length ? "No conversations found" : "No conversations yet"}</div>
          <p>{turns.length ? "Try a different search." : "Start talking with ABLE to create your first conversation."}</p>
        </div>
      )}
    </section>
  );
}

function Row({ who, text }) {
  return (
    <div className="transcript-row-entry">
      {who === "ABLE" ? <div className="speaker-badge-row able"><span className="speaker-accent-dot"></span><span>ABLE</span></div> : <div className="speaker-badge-row user">USER</div>}
      <div className="transcript-utterance-text">{text}</div>
    </div>
  );
}
