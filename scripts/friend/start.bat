@echo off
rem Starts the ABLE demo page with the E3 settings (E1 + E2 + E3, streaming on).
rem Optional: number of LLM threads, e.g.  start.bat 4   (default 5, tuned on the dev laptop)
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run setup.bat first.
  pause
  exit /b 1
)
set T=%~1
if "%T%"=="" set T=5
set CUDA_VISIBLE_DEVICES=-1
set PYTHONUTF8=1
set "JARVIS_TUNING={"n_batch": 128, "n_threads": %T%, "history_turns": 3, "max_tokens": 60, "prompt_style": "short", "stream": true, "max_first_chunk_words": 12, "length_scale": 1.0}"
rem open the page 2 s later, when the server is up
start "" /min cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8765"
.venv\Scripts\python.exe demo\web_demo.py
pause
