# PROJECT SNAPSHOT - Lumo (B1) as it works today

Read-only snapshot: Lumo's code was **not modified** (`git status` in `baselines/lumo` shows only my untracked `requirements.lock.txt`).
Commit `778ed055033ec3b0410349a82b9ea68e9546a4e0`. Snapshot taken 2026-10-08. **DEVELOPMENT LAPTOP - NOT FINAL NUMBERS.**

## 1. Machine
| Item | Value |
|---|---|
| CPU | Intel Core i7-9750H @ 2.60 GHz |
| Cores / threads | 6 / 12 |
| RAM | 31.7 GB |
| GPU | Intel UHD 630 + NVIDIA Quadro T2000 (4 GB) - not used |
| Power plan | Balanced |
| Plugged in? | **Yes** during the snapshot timing run (AC, battery 85%). Earlier runs in `results/lumo_dev_timings.md` were on battery |
| OS / Python | Windows 11 Enterprise N 10.0.26200 / Python 3.13.0 (Lumo venv) |

## 2. File tree (2 levels) and what each file does
```
baselines/lumo/                      Lumo repo, pinned, NOT committed to our git
  main.py                            voice assistant: mic -> VOSK -> GPT4All -> Piper -> winsound (the file we measure)
  chat.py                            text-only chat with the same LLM (max_tokens=2000, longer prompt)
  debug_main.py                      main.py skeleton with prints; retries with downloads allowed if load fails (unused)
  bangla_tts.py                      Bangla TTS via online Google gTTS (cloud; unused)
  evaluate_english_wer.py            VOSK WER/latency over an external 1000-WAV dataset (not downloaded)
  evaluate_bangla_wer.py             same for Bangla (needs torch/transformers; unused)
  eval_en_results.txt / eval_bn_results.txt   saved outputs of those evaluations (UTF-16 PowerShell logs)
  requirements.txt                   unpinned: vosk gpt4all sounddevice numpy torch transformers
  requirements.lock.txt              (ours) exact versions installed in the venv
  README.md, .gitignore, LUMO_ICEFront_2026 (1).pdf   docs / paper
  tests/test_stt.py                  live-mic VOSK demo      tests/test_llm.py   one GPT4All generation
  tests/test_tts.py                  Piper + winsound demo   tests/test_bangla_*.py  Bangla variants (unused)
  dataset/                           empty placeholders (external dataset repo)
  models/llm|stt|tts/                orca-mini-3b q4_0 gguf, vosk-model-small-en-us-0.15, en_US-amy-medium.onnx(+json)
  piper/piper/piper.exe (+ DLLs)     official Piper release 2023.11.14-2
  .venv/                             vosk 0.3.45, gpt4all 2.8.2, sounddevice 0.5.6, numpy 2.5.3

ABLE project root (our git)
  CLAUDE.md, RUNBOOK.md, env_report.md, PROJECT_SNAPSHOT.md   rules, working commands, machine report, this file
  scripts/setup.ps1                  clone Lumo at pinned commit, venv, locked pip install
  scripts/download_models.ps1        downloads the 5 model files, writes checksums
  scripts/lumo_requirements.lock.txt, model_checksums.txt     pinned versions, SHA256 of downloads
  bench/lumo_stage_timing.py         times STT / LLM / TTS separately on one WAV
  bench/snapshot_harness.py          runs UNMODIFIED main.py with a fake real-time mic and timing hooks (section 7)
  bench/test_audio/                  test WAVs (git-ignored)
  results/lumo_dev_timings.md, results/snapshot_timings.md   measurement tables
  stages/ pipeline/ limits/ baselines/standard_stack/   empty, for Phase 2/3
```

## 3. The main loop (exact code from `baselines/lumo/main.py`)
Audio callback (lines 10-12):
```python
def audio_callback(indata, frames, time_info, status):
    if not is_speaking:  # Only capture audio when not speaking
        audio_q.put(bytes(indata))
```

Model setup, executed once at import time (lines 14-23):
```python
# STT
model = Model("models/stt/vosk-model-small-en-us-0.15")
rec = KaldiRecognizer(model, RATE)

# LLM - using local GGUF model for offline operation
llm = GPT4All(
    model_name="orca-mini-3b-gguf2-q4_0.gguf",
    model_path="models/llm",  # Local path to model
    allow_download=False      # Prevent internet access
)
```

Text-to-speech and playback (lines 42-85):
```python
def speak(text):
    global is_speaking
    is_speaking = True
    
    # Clear the audio queue to prevent feedback
    while not audio_q.empty():
        try:
            audio_q.get_nowait()
        except:
            pass
    
    # Escape special characters for shell safety
    safe_text = text.replace('"', '').replace("'", "").replace('\n', ' ').replace('&', 'and')
    
    output_path = os.path.abspath("output.wav")
    
    result = subprocess.run(
        f'echo {safe_text} | piper\\piper\\piper.exe '
        f'--model models\\tts\\en_US-amy-medium.onnx '
        f'--output_file "{output_path}" --quiet',
        shell=True,
        capture_output=True
    )
    
    # Play audio SYNCHRONOUSLY using winsound (blocks until done)
    try:
        winsound.PlaySound(output_path, winsound.SND_FILENAME)
    except:
        pass
    
    # Wait a bit after speaking ends
    time.sleep(0.8)
    
    # Clear audio queue again before resuming listening
    while not audio_q.empty():
        try:
            audio_q.get_nowait()
        except:
            pass
    
    # Reset the recognizer to clear any buffered audio
    rec.Reset()
    
    is_speaking = False
```

Start-up and the record -> recognise -> LLM -> speak loop (lines 87-147):
```python
print("[*] LUMO is starting...")
print(f"🤖 {GREETING_MESSAGE}")

# Speak the startup greeting
speak(GREETING_MESSAGE)

print("[*] LUMO is listening... (say 'exit' or 'quit' to stop)")

with sd.RawInputStream(
    samplerate=RATE, blocksize=8000,
    dtype='int16', channels=1, callback=audio_callback
):
    while True:
        if is_speaking:
            time.sleep(0.1)
            continue
            
        data = audio_q.get()
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text = result.get("text", "").strip()
            
            if not text:
                continue
            
            # Skip if the text is too short (likely noise)
            if len(text) < 3:
                continue
                
            # Exit command
            if text.lower() in ["exit", "quit", "stop", "goodbye", "bye", "see you","bye bye","farewell", "tata"]:
                print("Goodbye!")
                break
            
            print(f"You: {text}")
            
            # Check if it's a greeting
            if is_greeting(text):
                reply = GREETING_MESSAGE
            else:
                # Build prompt with conversation context
                conversation_history.append(f"User: {text}")
                
                # Keep only last 4 exchanges for context
                recent_history = conversation_history[-4:]
                context = "\n".join(recent_history)
                
                prompt = f"""You are Lumo, a helpful offline AI assistant. 
Answer the user's question directly and helpfully. Be concise (under 50 words).

{context}
Lumo:"""
                
                reply = llm.generate(prompt, max_tokens=80)
                reply = reply.strip()
                
                # Store response in history
                conversation_history.append(f"Lumo: {reply}")
            
            print(f"Lumo: {reply}")
            speak(reply)
```

## 4. Settings that affect speed
Lumo sets almost nothing itself; most values are **library defaults** (read from `gpt4all/gpt4all.py` 2.8.2 and VOSK's `model.conf`, and confirmed at run time by the harness).

| Area | Setting | Value | Source |
|---|---|---|---|
| VOSK | model | `vosk-model-small-en-us-0.15` (small, 16 kHz) | main.py:15 |
| VOSK | endpointing | rule2: 0.5 s trailing silence after speech; rule3: 0.75 s; rule4: 1.0 s (rule1 = 5 s of silence and rule5 = 20 s utterance are Kaldi defaults) | `models/stt/.../conf/model.conf`; Lumo sets none |
| VOSK | result use | only the final result (`AcceptWaveform` returns True at an endpoint); no partial results used | main.py:105 |
| LLM | model file | `orca-mini-3b-gguf2-q4_0.gguf` (1.98 GB) | main.py:20 |
| LLM | threads | **not set**; runtime value **4** (of 12 logical / 6 physical) | `llm.model.thread_count()` in harness |
| LLM | max tokens | 80 | main.py:140 |
| LLM | context size | `n_ctx=2048` (default) | gpt4all `__init__` |
| LLM | device | `device=None` -> CPU backend (we also set CUDA_VISIBLE_DEVICES=-1; the CUDA DLL load fails harmlessly) | harness: `llm.device` = None |
| LLM | sampling | temperature 0.7 (default), top_k 40, top_p 0.4, repeat_penalty 1.18, repeat_last_n 64 | gpt4all `generate` defaults |
| LLM | **prompt batch** | `n_batch=8` (default): the prompt is evaluated 8 tokens at a time | gpt4all `generate` default |
| LLM | streaming | `streaming=False`: `generate()` returns only after the whole reply is done | main.py:140 |
| LLM | memory between turns | no chat session and no KV-cache reuse: the full prompt (persona + last 4 history lines) is re-evaluated every turn | main.py:128-140 |
| Piper | voice | `en_US-amy-medium`, **22050 Hz** output | harness: WAV header |
| Piper | start-up | **a new process for every reply**: `cmd /c echo <text> \| piper.exe --model ... --output_file output.wav` (shell=True); the WAV is then played by winsound | main.py:58-66 |
| Audio in | buffer | `sounddevice.RawInputStream`, 16 kHz, int16, mono, **blocksize 8000 = 0.5 s per chunk**, callback -> `queue.Queue` | main.py:95-97 |
| Audio in | blocking | the main loop blocks on `audio_q.get()`; recognition, LLM and TTS all run in that one thread, so audio keeps queuing while the LLM works (the queue is cleared when speaking starts) | main.py:104 |
| Audio out | playback | `winsound.PlaySound(wav, SND_FILENAME)`: starts only after the full WAV exists, blocks until it ends; then `time.sleep(0.8)` | main.py:68-73 |

## 5. Load behaviour
All three models are loaded **once at start-up**, at module level, before the loop:
- `model = Model("models/stt/vosk-model-small-en-us-0.15")` - main.py:15
- `rec = KaldiRecognizer(model, RATE)` - main.py:16
- `llm = GPT4All(model_name=..., allow_download=False)` - main.py:19-23
- Inside the `while True:` loop (line 99 on) there is only `rec.AcceptWaveform`, `llm.generate(...)` (line 140) and `speak()`; there is no `Model(` or `GPT4All(` call.
- Measured: across the greeting plus 5 questions the harness counted **1** VOSK load and **1** GPT4All load. Start-up to "listening" took 3.05 s including the spoken greeting.
- **Exception: Piper.** It is *not* kept loaded. `speak()` starts `piper.exe` for every reply (main.py:58), which loads the 60 MB ONNX voice again each time (0.67-1.10 s per reply).

## 6. System prompt / persona
There is no separate system prompt: one plain-text prompt is built per question (main.py:134-138), with the last 4 history lines inserted:
```text
You are Lumo, a helpful offline AI assistant. 
Answer the user's question directly and helpfully. Be concise (under 50 words).

<last 4 entries of "User: ..." / "Lumo: ...">
Lumo:
```
Greetings ("hello", "hi", "hey", "good morning/afternoon/evening") skip the LLM and use a fixed greeting string.
The code comment says "last 4 exchanges", but it is really the last 4 *lines* (about 2 exchanges).

## 7. Timing run
**Method.** `bench/snapshot_harness.py` runs the unmodified `main.py` with a fake microphone that delivers 0.5 s chunks in real time: 0.3 s silence, one spoken question, silence until the answer is "played", a 1 s gap, then the next question. Five different questions in one session (so the history grows as in real use). Hooks only timestamp VOSK `AcceptWaveform`/`Result`, `GPT4All.generate` (token callback), the Piper `subprocess.run`, and `winsound.PlaySound`. "First audio" = the moment Lumo calls `PlaySound` (the audio itself is not played during the test).

**Honest limits:** the questions are *synthetic Piper speech* (clean, not a human voice); speaker/driver latency is not included; in the first (crashed-sampler) run VOSK misheard one question ("tell media short joke") that the second run heard correctly, so recognition is not perfectly repeatable; this is one pass of 5 questions, not repeated.

A = end of speech to text. B = text to first LLM token. C = LLM total. D = text to first audio (B + rest of LLM + Piper). E = end of speech to first audio.

| # | Heard (VOSK) | Prompt chars | A (ms) | B (ms) | C (ms) | Tokens | D (ms) | **E (ms)** |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | what is the capital of france | 169 | 1172 | 4928 | 6264 | 8 | 6999 | 8172 |
| 2 | how many days are there in a week | 252 | 968 | 7429 | 8772 | 8 | 9438 | 10406 |
| 3 | tell me a short joke | 281 | 1259 | 8183 | 10489 | 14 | 11323 | 12582 |
| 4 | why is the sky blue | 294 | 1165 | 7847 | 12275 | 28 | 13373 | 14538 |
| 5 | who wrote the play romeo and juliet | 407 | 1449 | 11422 | 12902 | 9 | 13723 | 15172 |
| | **Median** | 281 | 1172 | 7847 | 10489 | 9 | 11323 | **12582** |
| | **Worst** | 407 | 1449 | 11422 | 12902 | 28 | 13723 | **15172** |

- Medians of the parts: wait before the final decode starts 1161 ms; final `AcceptWaveform` call 13 ms; `Result()` 0.6 ms; Piper run 821 ms; decode speed 5.4 tokens/s.
- A is almost all **waiting**: VOSK needs 0.5 s of trailing silence, and the 0.5 s chunking means the endpoint is only noticed at the next chunk boundary. The decode itself is about 13 ms.
- Time to first token vs prompt length (5 points): about 26.8 ms per prompt character + 433 ms.
- Replies: Q1 "The capital city of France is Paris." / Q2 "There are seven days in a week." / Q3 the tomato joke / Q4 a 28-token sky explanation / Q5 "William Shakespeare wrote the play Romeo and Juliet."
- Reply audio lengths 3.1, 2.4, 4.5, 7.9, 3.8 s at 22050 Hz.

## 8. Resource use during a reply
| Metric | Result |
|---|---|
| Peak CPU of the Lumo process | **4.5-4.7 cores busy** (38-39 % of the 12 logical CPUs), matching the 4 LLM threads |
| Peak whole-machine CPU in the reply windows | 54-83 % (includes Piper, my 2 Hz `nvidia-smi` polling and other apps such as VS Code; not Lumo alone) |
| Peak RAM, Lumo process working set | **2.71 GB** (includes the memory-mapped 1.9 GB model file) |
| Peak private (committed) memory | 1.79 GB |
| Piper child process | not included above (short-lived; not measured) |
| **GPU** | **0 % utilisation and 0 MiB memory in all 91 samples** (nvidia-smi every 0.5 s across the whole run) |

CPU and RAM were sampled in-process every 100 ms (Windows `GetProcessTimes` / `GetProcessMemoryInfo`); no extra packages were installed.

## 9. My top 5 guesses for what is slow (ranked, with evidence)
1. **LLM prompt processing (prefill) before the first token: 4.9-11.4 s, median 7.8 s, roughly 60-65 % of the delay.** Time to first token grows linearly with prompt length (about 27 ms per prompt character, i.e. roughly 100 ms per token). Causes in the code: default `n_batch=8`, the whole prompt re-evaluated every turn with no KV-cache reuse (main.py:128-140), and the history growing from 169 to 407 characters over the five questions.
2. **Slow token generation, and waiting for the whole reply: 5.4 tokens/s, only 4 of 12 threads, non-streaming.** Even short replies cost 1.3-4.4 s after the first token (C - B), and an 80-token reply would take about 15 s. Nothing can be spoken until `generate()` returns (main.py:140 then 147).
3. **A strictly sequential, blocking pipeline.** First audio = endpoint wait + STT + entire LLM reply + entire Piper run (D = 7.0-13.7 s). No stage overlaps with the next (no sentence-level TTS, no streaming).
4. **Waiting for end of speech: about 1.2 s median (A), nearly all idle waiting.** The 0.5 s trailing-silence endpoint rule plus 0.5 s audio chunks (main.py:96); the actual decode is about 13 ms.
5. **Piper started fresh for every reply through a shell pipe: 0.67-1.10 s (median 0.82 s).** The 60 MB ONNX voice is loaded each time and the full WAV must be written before playback (main.py:58-68); it grows with longer replies.

Not a latency cause, but worth noting: the 0.8 s sleep after playback (main.py:73) only delays when the next question can be heard.

**Overall (E): median 12.6 s, worst 15.2 s from end of speech to first audio** on this laptop, plugged in, Balanced plan. (The earlier battery-powered run in `results/lumo_dev_timings.md` gave about 10.7 s on a shorter, history-free prompt, so the growing history in the real loop makes it worse.)
