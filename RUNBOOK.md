# RUNBOOK

Exact working commands and problems solved. Updated continuously.

## Environment
- Dev laptop: see env_report.md. Python 3.13 approved (3.11 not installed).
- Project path contains spaces: always quote paths.

## Phase 0
- Created repo, .gitignore, CLAUDE.md, env_report.md, folder structure.

## Phase 1 - Lumo baseline (B1)
- Cloned https://github.com/mehedinaeem/Lumo.git into `baselines/lumo` (1.8 MB).
- **Pinned commit: `778ed055033ec3b0410349a82b9ea68e9546a4e0`** (branch HEAD, "Updated"). `scripts/setup.ps1` clones and checks out this commit.
- Code reviewed (Gate 1 summary given in chat). No binaries are committed in the Lumo repo (`piper.exe` is NOT included; README expects `piper\piper\piper.exe`).

### Setup commands (from project root)
```
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1            # clone Lumo @ pinned commit, venv, pip install (locked)
powershell -ExecutionPolicy Bypass -File scripts\download_models.ps1  # ~2 GB, checksums -> scripts\model_checksums.txt
```
- Installed only `vosk gpt4all sounddevice numpy` (+deps) in `baselines/lumo/.venv` (Python 3.13). Lock: `scripts/lumo_requirements.lock.txt` (copy at `baselines/lumo/requirements.lock.txt`).
- Models: orca-mini 1,979,946,720 B (1888 MB); vosk-small-en-us-0.15 zip; Piper release 2023.11.14-2 `piper_windows_amd64.zip`; en_US-amy-medium.onnx (60 MB). Total in `models/`: 2016 MB. All as README expects. SHA256 in `scripts/model_checksums.txt` (no publisher checksums available to compare).
- Official Piper zip extracts to `piper/` containing `piper.exe` + DLLs, so it goes to `baselines/lumo/piper/piper/piper.exe` (the path Lumo expects). No Piper binary is committed.

### Test runs on the dev laptop (all CPU; nvidia-smi: GPU 0 %, 0 MiB throughout)
Run from `baselines/lumo` with `set CUDA_VISIBLE_DEVICES=-1`, `set PYTHONUTF8=1`:
- `tests/test_tts.py`: OK (3.96 s WAV, played on speakers).
- `tests/test_llm.py`: OK (13 s wall incl. load). "Failed to load llamamodel-mainline-cuda*.dll" warnings are harmless (no CUDA runtime = CPU).
- `chat.py` text mode: OK, answer "Paris..." (23 s wall incl. load).
- `bench/lumo_stage_timing.py`: OK -> `results/lumo_dev_timings.md`.

### Problems solved
- Lumo's scripts print emoji; with piped stdout Windows uses cp1252 and crashes (`UnicodeEncodeError`). Fix without editing Lumo: `PYTHONUTF8=1`. (`python -I` ignores that variable; don't use `-I` for Lumo scripts.)
- `curl.exe` progress output floods logs when run in the background; harmless.
- Lumo tests use relative paths: always run them from `baselines/lumo`.
