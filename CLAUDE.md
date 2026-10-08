# ABLE - Adaptive voice - Based Local Engine (hackathon EPS08)

CPU-only, fully offline voice assistant on Windows:
mic -> VAD + wake word -> ASR -> small local LLM -> TTS -> speaker.
Goal: minimize time from END of user speech to FIRST reply audio, at low CPU/RAM.

## Standing rules
- Windows + Python 3.11. Use 3.10+ only if 3.11 is unavailable (dev laptop: 3.13 approved by user).
- CPU only. Never use the GPU (no CUDA; set `CUDA_VISIBLE_DEVICES=-1`, Ollama `num_gpu 0`).
- Offline after setup. No cloud calls at runtime.
- Every pipeline stage writes timestamps to ONE shared log (CSV: run id, stage, event, monotonic ms).
- Small commits. Never commit models, audio or binaries.
- Never edit `baselines/lumo` (baseline B1, pinned commit, not committed).
- Python packages only inside virtual environments in the project folder.
- Everything must be reproducible from the repo plus scripts (a teammate clones it on another laptop).
- Third-party code is read BEFORE it is run. No admin rights or system-setting changes without asking.
- Downloads: only user-approved, official sources, size stated first.
- Stop and ask if a step fails twice, needs admin, or looks suspicious.
- Do NOT start optimizations (streaming, caching, thread tuning) until the user says so.
- Keep RUNBOOK.md updated with exact working commands and problems solved.
- The folder `..\Problem Statement` (outside the repo) holds the hackathon documents; read-only reference.
