import Back from "./Back.jsx";

// Withheld: playback, speed control and timeline need per-turn audio capture.
export default function Replay({ go }) {
  return (
    <section className="view-container active">
      <Back onClick={() => go("main")} />
      <div className="page-heading"><h2 className="page-title">Replay</h2><p className="page-subtitle">Replay a previous ABLE conversation</p></div>
      <div className="empty-state-box">
        <div className="empty-title">Coming soon</div>
        <p>Conversation replay needs recorded turns and will be added later.</p>
      </div>
    </section>
  );
}
