import { useState } from "react";
import { useLiveState, heroState } from "./api.js";
import Home from "./views/Home.jsx";
import History from "./views/History.jsx";
import Config from "./views/Config.jsx";
import Benchmarks from "./views/Benchmarks.jsx";
import Replay from "./views/Replay.jsx";

const NAV = [["main", "ABLE"], ["history", "History"], ["config", "Config"], ["benchmarks", "Benchmarks"], ["replay", "Replay"]];

export default function App() {
  const [view, setView] = useState("main");
  const live = useLiveState();
  const go = (v) => { setView(v); window.scrollTo(0, 0); };
  const active = view === "detail" ? "history" : view;

  return (
    <div className="app-frame">
      <header className="app-header">
        <button className="brand-group" onClick={() => go("main")} title="Back to Voice Assistant">
          <div className="brand-title"><span className="brand-mark"></span>ABLE</div>
          <div className="brand-subtitle">Adaptive Voice-Based Local Engine</div>
        </button>
        <nav aria-label="Quick Page Navigation" className="header-nav">
          {NAV.map(([id, label]) => (
            <button key={id} className={"nav-link-btn" + (active === id ? " active" : "")} onClick={() => go(id)}>{label}</button>
          ))}
        </nav>
        <div className="header-status-group">
          <div className="status-badge highlight"><span className="dot-pulse"></span><span>{heroState(live)}</span></div>
          <div className="status-badge verified">OFFLINE ✓</div>
        </div>
      </header>
      {view === "main" && <Home live={live} go={go} />}
      {(view === "history" || view === "detail") && <History live={live} go={go} view={view} setView={setView} />}
      {view === "config" && <Config live={live} go={go} />}
      {view === "benchmarks" && <Benchmarks go={go} />}
      {view === "replay" && <Replay go={go} />}
    </div>
  );
}
