import { useEffect, useState } from "react";

// Backend /state (demo/web_demo.py):
// {on:[stage names], turns:[{heard,reply,asr_ms,first_token_ms,tts_start_ms,tts_ms,first_audio_ms,tokens,sentences}],
//  settings:{n_threads,...}, running, error, mic}
export function useLiveState() {
  const [s, setS] = useState({ online: false, on: [], turns: [], settings: {} });
  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const d = await (await fetch("/state")).json();
        setS({ ...d, online: true });
      } catch {
        setS((p) => (p.online ? { ...p, online: false } : p));
      }
    }, 100);
    return () => clearInterval(id);
  }, []);
  return s;
}

export const run = () => fetch("/run", { method: "POST" }).catch(() => {});
// Terminate button: cuts the reply being written/spoken; the loop keeps running.
export const skip = () => fetch("/skip", { method: "POST" }).catch(() => {});

// Benchmark snapshot copied from results/raw (static): CPU/RAM/GPU peaks and model info.
export function useSnapshot() {
  const [d, setD] = useState(null);
  useEffect(() => {
    fetch("/snapshot_events.json").then((r) => r.json()).then(setD).catch(() => {});
  }, []);
  return d;
}

export const ms = (v) => (v == null ? "—" : v >= 1000 ? (v / 1000).toFixed(2) + " s" : Math.round(v) + " ms");
export const pct = (a, p) => {
  if (!a.length) return null;
  const s = [...a].sort((x, y) => x - y);
  return s[Math.min(s.length - 1, Math.ceil(p * s.length) - 1)];
};

export function heroState(s) {
  if (!s.online || !s.running) return "IDLE";
  if (s.on.includes("Speaking")) return "SPEAKING";
  if (s.on.some((x) => x !== "Listening")) return "THINKING";
  return "LISTENING";
}

// Real turns only (drops the start-up greeting).
export const realTurns = (s) => (s.turns ?? []).filter((t) => t.heard && !t.heard.startsWith("(start-up"));
