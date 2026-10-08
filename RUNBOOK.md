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
- `tests/test_stt.py` (live mic, 30 s): works but accuracy is poor with the laptop mic array ("tell me a joke" -> "and me a joke"; some sentences produced nothing).
- `main.py` voice mode (90 s, `timeout 90`): OK. Greeting spoken; "what are you doing" and "what" answered by voice. GPU not sampled during this run (sampler race); CUDA disabled via env.
- Gotcha: in bash, `cd x && (...) &` backgrounds the cd too. Put `cd` on its own line before background jobs.
- Lumo timings (dev laptop, on battery): see `results/lumo_dev_timings.md`. Median end-of-speech to first audio about 10.7 s; first LLM token about 6.6 s looks slow, re-run plugged in.

## Snapshot (PROJECT_SNAPSHOT.md)
- `baselines/lumo/.venv/Scripts/python.exe bench/snapshot_harness.py` runs the UNMODIFIED main.py with a fake real-time mic + timing hooks; writes `results/snapshot_timings.md` and `results/raw/snapshot_events.json`. Plugged in: median end-of-speech -> first audio 12.6 s, worst 15.2 s.
- Problem solved: ctypes `GetProcessTimes` needs `argtypes` (HANDLE) or it raises OverflowError on the pseudo-handle.
- Mistake fixed: an earlier GPU-sampling loop left `results_gpu_tmp.txt` in the repo; removed.

## Step A - our own copy (jarvis_v0) vs Lumo
- Files: `config/persona.toml` (name ABLE, TOML via stdlib `tomllib`), `pipeline/jarvis_v0.py` (frozen copy of Lumo's loop, credit in header), `bench/snapshot_harness.py` (now ONE pass per call: `--target lumo|v0|v1 --label --tuning --out`), `bench/ablate.py` (runs configs interleaved over N passes and writes the table).
- Commands (project root, Lumo's venv):
  - live demo: `.\baselines\lumo\.venv\Scripts\python.exe pipeline\jarvis_v0.py`
  - Gate A: `.\baselines\lumo\.venv\Scripts\python.exe bench\ablate.py --passes 3 --md results\gate_a.md --cfg "lumo|lumo|" --cfg "v0|v0|"`
- Prompt tokens are counted exactly: a wrapper on `LLModel._prompt_callback` (called once per prompt token); it equals `context.n_past - generated tokens` on every question.
- Result (`results/gate_a.md`, plugged in): Lumo median E 12.9 s, v0 12.0 s; time per prompt token identical (97 vs 98 ms).
## Step B - jarvis_v1 (config-driven) and ablation
- `pipeline/jarvis_v1.py` = copy of v0 + toggles from `config/pipeline.toml` (TOML, stdlib `tomllib`, because persona.toml has lists; unknown keys are rejected). `jarvis_v0.py` stays frozen.
- One toggle per run without editing the file: `--cfg "label|v1|{\"n_batch\": 128}"` (sent as `JARVIS_TUNING`).
- Regression check (v1 at v0 defaults vs v0, 3 interleaved passes, plugged in): `.\baselines\lumo\.venv\Scripts\python.exe bench\ablate.py --passes 3 --md results\ablation.md --cfg "v0_chk|v0|" --cfg "v1_defaults|v1|"` -> median E 12317 (v0) vs 12435 ms (v1), same prompt tokens.
- Splitter tests (no pytest needed): `.\baselines\lumo\.venv\Scripts\python.exe tests\test_sentence_splitter.py`
- `ablate.py` skips passes whose JSON already exists in `results/raw/passes`; delete them to re-measure.

## Demo page (live view in a browser)
- Once (needs internet, 4.7 MB, React 18.3.1 from the npm registry): `cd demo ; npm install`
- Run from the project root: `.\baselines\lumo\.venv\Scripts\python.exe demo\web_demo.py` then open `http://localhost:8765` and press **Start ABLE** (the voice loop only starts on the button). Say "exit" to stop the loop (the button returns), Ctrl+C to quit the server.
- Speech recognizer: the demo now uses the small model `vosk-model-small-en-us-0.15` (the larger `vosk-model-en-us-0.22-lgraph` is still installed; set `stt_model` in the demo tuning to use it) (130.6 MB zip from alphacephei.com, in `models/_downloads/`, unpacked to `baselines/lumo/models/stt/`); setting `stt_model` in `config/pipeline.toml` (default: the small model). Compare on your voice: `bench\mic_check.py` (edit the model name inside) or `bench\asr_check.py <model folder>`.
- The demo applies the tuned E1 + E2 + E3 settings by default (stream on). A non-empty `JARVIS_TUNING` overrides them; `pipeline.toml` keeps the v0 defaults for benchmarks.
- It runs `jarvis_v1.py` unchanged (real mic and speakers) with the settings in `config/pipeline.toml` (the slow v0 defaults). Do not run it during a benchmark: it uses the same CPU cores.
- Tuned version (E1 + E2 + streaming) without editing the config, PowerShell, same terminal: `$env:JARVIS_TUNING='{"n_batch":128,"n_threads":5,"history_turns":3,"max_tokens":60,"prompt_style":"short","stream":true}'` then the run command. Back to the original: `$env:JARVIS_TUNING=''`.

## E1 / E2 / E3 (results/ablation.md)
- Winners on the dev laptop: `n_batch` 128, 5 threads (re-tune threads on the demo laptop), short prompt, `history_turns` 3, `max_tokens` 60, `stream` true.
- E3 run (8 questions, playback simulated in real time): `$env:BENCH_LONG='1'` then `bench\ablate.py --passes 3 --cfg 'e3_off|v1|{...\"stream\": false}' --cfg 'e3_on|v1|{...\"stream\": true}'`; per-question table: `bench\e3_report.py e3_off e3_on`.
- In Windows PowerShell 5.1 the JSON inside `--cfg` needs `\"`; in VS Code put `--%` right after `python.exe` and use `"...{\"key\": 1}"`.
- Streaming code: `speak_streaming()` in `jarvis_v1.py` (LLM thread -> `pipeline/sentence_splitter.py` -> Piper thread, one WAV per sentence -> playback in the main thread).
- Problem solved: numbered lists ("1. Break down ...") were split after "1." and spoken as a separate clip with a 2 s pause; a number alone before the dot is now treated as a list marker (test added).
- The harness now sleeps for the audio length in its fake `PlaySound`, so passes take longer than before; E (time of the first `PlaySound` call) is not affected.

## Step A notes
- Problem solved: harness `--out` was relative and the harness does `chdir` into baselines/lumo, so a `results/` folder appeared inside Lumo. Fixed by resolving the path first; stray folder deleted.

## Test with a recording (no microphone)
- Once: `baselines\lumo\.venv\Scripts\pip install miniaudio` (pinned in `scripts/lumo_requirements.lock.txt`; decodes mp3/wav/flac/ogg, no ffmpeg).
- CLI: `.\baselines\lumo\.venv\Scripts\python.exe bench\audio_test.py recording.mp3` prints `You:` / `ABLE:` lines; `--tuning '{...}'` overrides the demo settings (e.g. compare the two Vosk models on the same file).
- Demo page: "Test with an audio file" next to Start ABLE (upload is saved as `results/raw/test_upload.<ext>`, max 20 MB). The loop plays the file in real time, answers, then stops by itself.
- Mechanism: env `JARVIS_TEST_FILE` makes `jarvis_v1.py` use `FileStream` instead of the microphone and skip the greeting. Unset = normal live mode.

## Whisper speech recognition (stt_engine)
- `stt_engine = "whisper"` (the demo and `bench/audio_test.py` default) uses faster-whisper `base.en`, int8, CPU; `"vosk"` keeps the old recognizer. Model `whisper-base.en` (141 MB, Systran/faster-whisper-base.en from Hugging Face) is in `baselines/lumo/models/stt/`; packages `faster-whisper` etc. are in the Lumo venv and `scripts/lumo_requirements.lock.txt`.
- Whisper is not streaming: our own end-of-speech detection (`end_silence_ms`, 700 ms default) cuts the phrase, which is then transcribed in one go (Whisper's built-in Silero VAD removes silence inside it). Text is lowercased and stripped of punctuation so exit/greeting matching behaves as with Vosk; `min_conf` uses exp(avg_logprob) of the segments.
- Problem solved: the background-level estimate started at the first audio block; a recording that starts with speech was never detected. It now starts at a typical quiet level (60).
- Check: `bench\audio_test.py bench\test_audio\snap_q1.wav` ... all five snapshot questions are heard correctly with Whisper.
