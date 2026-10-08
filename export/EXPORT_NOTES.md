# Export notes (owner) - test package for a friend's laptop

Build: `powershell -ExecutionPolicy Bypass -File scripts\make_export.ps1` (`-DryRun` lists files and sizes only,
`-Wheels` adds an offline wheelhouse, `-NoZip` skips the zip). Output: `export\ABLE_test_package\` and
`export\ABLE_test_package.zip` (both git-ignored via `export\.gitignore`). Only `-DryRun` has been run so far.

## What ships (dry run, 2026-10-08)
| Part | Size | Why |
|---|---:|---|
| `baselines\lumo\models\llm\orca-mini-3b-gguf2-q4_0.gguf` | 1888.2 MB | LLM (`jarvis_v1.py` loads it from here) |
| `baselines\lumo\models\stt\vosk-model-small-en-us-0.15\` | 67.6 MB | ASR |
| `baselines\lumo\models\tts\en_US-amy-medium.onnx` + `.json` | 60.3 MB | Piper voice |
| `baselines\lumo\piper\piper\` (piper.exe, DLLs, espeak-ng-data) | 37.0 MB | TTS program (run per sentence) |
| `demo\node_modules\` (React 18.3.1) | 4.7 MB | page works offline; small, so included |
| `pipeline\jarvis_v1.py, sentence_splitter.py, asr_fix.py`, `config\*.toml`, `demo\web_demo.py, package.json`, `bench\mic_check.py`, `baselines\lumo\README.md` | < 0.1 MB | code + Lumo credit |
| `FRIEND_README.md`, `setup.bat`, `start.bat`, `requirements.txt` (= `scripts\lumo_requirements.lock.txt`) | < 0.1 MB | friend-side setup (sources in `scripts\friend\`) |
| **Total** | **2057.9 MB, 477 files** | zip about the same (models do not compress) |
| optional `wheels\` (`-Wheels`) | est. 150-250 MB | offline `setup.bat`; size unverified (not downloaded) |

`asr_fix.py` is shipped because `jarvis_v1.py` and `web_demo.py` import it (it is E4 work, but always active in the code).

## Excluded
- `baselines\lumo\.venv` (334 MB): **not movable**. `pyvenv.cfg` points to `C:\Users\davia\AppData\Local\Programs\Python\Python313`
  and the `Scripts\*.exe` launchers embed absolute paths; it also only contains CUDA DLLs we never use.
- Rest of `baselines\lumo`: `.git`, Lumo scripts (`main.py`, `chat.py`, Bangla files), `tests`, `dataset`, `docs`, PDF paper,
  `output.wav`, `test_output.wav`, eval logs. `jarvis_v1.py` only needs `models\` and `piper\piper\` from there.
- `pipeline\jarvis_v0.py`, `bench\` (except `mic_check.py`), `tests\`, `results\`, `models\_downloads\` (60.7 MB zips),
  `limits\`, `stages\`, root docs, `.git`, `__pycache__`, `*.pyc`, `*.wav`, `results_gpu_tmp.txt`.
  The script refuses to finish if any `.git`, `.venv`, `__pycache__`, `results`, `.pyc`, `.env`, `.wav` or `results_gpu_tmp` path ends up in the package.
- No secrets exist in the shipped files (code, TOML, model files, React).

## Python environment decision
Fresh venv on the friend's laptop: `setup.bat` creates `.venv` inside the package with `py -3.13` (fallback `python`, needs >= 3.11
for `tomllib`) and runs `pip install -r requirements.txt` (the exact lock), `--no-index --find-links wheels` when `wheels\` exists.
`.bat` instead of `.ps1` because a non-dev Windows blocks double-clicked PowerShell scripts (execution policy).
- Default package = **online install** (friend needs internet once). Build with `-Wheels` for a fully offline package
  (the wheels are cp313/win_amd64: then the friend must use Python 3.13 x64).
- `start.bat` pins the **E3 settings** through `JARVIS_TUNING`:
  `n_batch 128, n_threads 5 (or start.bat N), history_turns 3, max_tokens 60, prompt_style "short", stream true, max_first_chunk_words 12, length_scale 1.0`.
  This matters: `demo\web_demo.py` on disk currently defaults to the E4 values (`prompt_style "tiny"`, `length_scale 0.88`);
  a non-empty `JARVIS_TUNING` overrides them, so the package runs E3 without changing any repo file.

## Must be installed on the friend's side
- Python 3.13 x64 (python.org, per-user install, no admin).
- Microsoft Visual C++ 2015-2022 Redistributable x64: `piper.exe`, `onnxruntime.dll`, `llmodel.dll` and the llama DLLs import
  `MSVCP140.dll` (checked in the binaries). Python only brings `vcruntime140*.dll`. Usually already present; installing it needs admin.
- CPU with AVX (gpt4all ships AVX2 and AVX-only builds). About 3 GB RAM for ABLE, ~2.5 GB disk + venv.

## Licences to credit
| Component | Licence | Source of the claim |
|---|---|---|
| Lumo (code our pipeline derives from) | MIT | Lumo README badge + "MIT License" section; repo has no LICENSE file |
| Vosk library | Apache 2.0 | upstream project (not in local files) |
| vosk-model-small-en-us-0.15 | Apache 2.0 (alphacephei.com model list) | local README only says "Copyright 2020 Alpha Cephei Inc" - confirm |
| GPT4All Python bindings 2.8.2 | MIT | wheel METADATA classifier |
| orca-mini-3b (psmathur/orca_mini_3b) | **CC BY-NC-SA 4.0** per its Hugging Face card, as far as I know - **verify**; non-commercial | `models\llm\README.md` only links the HF page |
| Piper 2023.11.14-2 | MIT | upstream (no licence file in the release zip) |
| espeak-ng (bundled `espeak-ng.dll` + data in Piper) | **GPL-3.0** | upstream; redistribution should include/point to its source and licence |
| en_US-amy-medium voice | see the piper-voices MODEL_CARD (dataset "amy") - **verify** | `.onnx.json` names the dataset only |
| React 18.3.1 | MIT | `demo\node_modules\react\LICENSE` (shipped) |
| numpy (BSD-3), sounddevice/PortAudio (MIT), cffi (MIT), requests (Apache 2.0) | as listed | installed by setup.bat |

## Open questions
1. Build timing: the script copies `pipeline\`, `demo\`, `config\` as they are on disk. The E4 work is editing these now; build after E4
   is paused/committed, or at least re-check `jarvis_v1.py` still accepts the E3 key set. Nothing E3 is committed in git (only up to Step A).
2. Offline or online setup? `-Wheels` needs a one-time download (est. 150-250 MB, PyPI) - owner approval required.
3. Bundle the Python 3.13 installer (~27 MB) and/or `vc_redist.x64.exe` (~25 MB) in the zip? Both are downloads; not done.
4. orca-mini-3b and the amy voice licences need a check before sharing beyond a private test (non-commercial / attribution).
5. `results_gpu_tmp.txt` is still in the repo root and tracked in git (RUNBOOK says it was removed); it is not shipped, but should be deleted.
6. Transfer: the zip is ~2 GB (USB stick or a file-sharing link the owner chooses).
