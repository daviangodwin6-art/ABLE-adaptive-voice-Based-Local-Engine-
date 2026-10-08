"""jarvis_v1 - jarvis_v0 plus experiment toggles from config/pipeline.toml.

Derived from Lumo's main.py: https://github.com/mehedinaeem/Lumo (MIT License),
pinned commit 778ed055033ec3b0410349a82b9ea68e9546a4e0. Credit and thanks to the Lumo authors.

A copy of pipeline/jarvis_v0.py (the frozen reference). With every toggle at its v0 default this file
behaves exactly like v0; every ablation row is a config change on THIS file, not a new copy.
Toggles: n_batch, n_threads, max_tokens, history_turns, prompt_style, stream, max_first_chunk_words, length_scale, stt_model.
The bench overrides single toggles with the JARVIS_TUNING env variable (JSON object).

Run with Lumo's venv:  baselines\\lumo\\.venv\\Scripts\\python.exe pipeline\\jarvis_v1.py
"""
import sounddevice as sd
import numpy as np
import collections, queue, json, subprocess, time, winsound, os, tomllib, sys, threading
from pathlib import Path
from vosk import Model, KaldiRecognizer
from gpt4all import GPT4All

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sentence_splitter import SentenceSplitter, trim_to_sentence
from asr_fix import fix_asr, is_exit, cut_role_echo, stop_at_role_echo, is_confident

# The bench passes in a function to timestamp events; in normal use it does nothing.
timing_event = globals().get("timing_event") or (lambda name, **kw: None)

ROOT = Path(__file__).resolve().parent.parent
LUMO = ROOT / "baselines" / "lumo"
CFG = tomllib.loads((ROOT / "config" / "persona.toml").read_text(encoding="utf-8"))

# Experiment toggles. pipeline.toml lists every valid key; anything else is a typo and must not run.
PIPE = tomllib.loads((ROOT / "config" / "pipeline.toml").read_text(encoding="utf-8"))
_tuning = json.loads(os.environ.get("JARVIS_TUNING") or "{}")
for _k, _v in _tuning.items():
    if _k not in PIPE:
        raise SystemExit(f"Unknown pipeline setting {_k!r}. Valid keys: {', '.join(PIPE)}")
    if type(_v) is not type(PIPE[_k]):
        raise SystemExit(f"Pipeline setting {_k!r} must be {type(PIPE[_k]).__name__}, got {_v!r}")
PIPE.update(_tuning)
_KEYS = {"n_batch", "n_threads", "max_tokens", "history_turns", "prompt_style", "stream", "max_first_chunk_words", "length_scale", "stt_model", "min_conf", "noise_gate", "mic_device", "end_silence_ms", "stt_engine", "whisper_model", "llm_backend", "llm_model"}
if set(PIPE) != _KEYS:
    raise SystemExit(f"config/pipeline.toml: unknown or missing keys: {sorted(set(PIPE) ^ _KEYS)}")
if PIPE["stt_engine"] not in ("vosk", "whisper"):
    raise SystemExit(f"stt_engine must be 'vosk' or 'whisper', got {PIPE['stt_engine']!r}")
if PIPE["llm_backend"] not in ("gpt4all", "llama_cpp"):
    raise SystemExit(f"llm_backend must be 'gpt4all' or 'llama_cpp', got {PIPE['llm_backend']!r}")
if PIPE["prompt_style"] not in ("v0", "short", "tiny"):
    raise SystemExit(f"prompt_style must be 'v0', 'short' or 'tiny', got {PIPE['prompt_style']!r}")

RATE = 16000
audio_q = queue.Queue()
is_speaking = False  # Flag to prevent feedback loop

def audio_callback(indata, frames, time_info, status):
    if not is_speaking:  # Only capture audio when not speaking
        data = bytes(indata)
        if PIPE["noise_gate"] and np.sqrt(np.mean(np.frombuffer(data, np.int16).astype(np.float64) ** 2)) < PIPE["noise_gate"]:
            data = bytes(len(data))  # silence, not dropped: the recognizer needs the pauses to end a phrase
        audio_q.put(data)

# STT
WHISPER = PIPE["stt_engine"] == "whisper"
if WHISPER:
    # Whisper (faster-whisper, CTranslate2, int8, CPU): transcribes a whole phrase after our end-of-speech detection.
    from faster_whisper import WhisperModel
    import math, re
    wmodel = WhisperModel(str(LUMO / "models/stt" / PIPE["whisper_model"]), device="cpu", compute_type="int8",
                          cpu_threads=PIPE["n_threads"])

    def whisper_transcribe(pcm):
        """-> Vosk-shaped result: lowercase text without punctuation (exit/greeting matching), per-segment confidence."""
        audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
        segs, _ = wmodel.transcribe(audio, language="en", beam_size=1, vad_filter=True, condition_on_previous_text=False)
        segs = [s for s in segs if s.no_speech_prob < 0.6]
        text = re.sub(r"[^\w\s']", "", " ".join(s.text for s in segs)).lower().strip()
        return {"text": " ".join(text.split()), "result": [{"conf": math.exp(s.avg_logprob)} for s in segs]}

    class _NoRec:  # speak() resets the recognizer; Whisper keeps no state between phrases
        def Reset(self): pass
    rec = _NoRec()
else:
    model = Model(str(LUMO / "models/stt" / PIPE["stt_model"]))
    rec = KaldiRecognizer(model, RATE)
    rec.SetWords(True)  # word confidences for min_conf

# LLM - using local GGUF model for offline operation
if PIPE["llm_backend"] == "llama_cpp":  # newer architectures (Gemma 3) that gpt4all's llama.cpp cannot load
    from llm_backend import LlamaCppLLM
    llm = LlamaCppLLM(PIPE["llm_model"], str(LUMO / "models/llm"), n_threads=PIPE["n_threads"], n_batch=PIPE["n_batch"])
else:
    llm = GPT4All(
        model_name=PIPE["llm_model"],
        model_path=str(LUMO / "models/llm"),  # Local path to model
        allow_download=False,     # Prevent internet access
        n_threads=PIPE["n_threads"]
    )

# Conversation history for context
conversation_history = []

GREETING_MESSAGE = CFG["greeting"]
GREETING_WORDS = CFG["greeting_words"]
EXIT_WORDS = CFG["exit_words"]

def is_greeting(text):
    """Check if the text is a greeting"""
    text_lower = text.lower().strip()
    for greeting in GREETING_WORDS:
        if text_lower == greeting or text_lower.startswith(greeting + " "):
            return True
    return False

PIPER = LUMO / "piper" / "piper" / "piper.exe"
VOICE = LUMO / "models" / "tts" / "en_US-amy-medium.onnx"

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

    out_dir = ROOT / "results" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(out_dir / "jarvis_output.wav")

    result = subprocess.run(
        f'echo {safe_text} | "{PIPER}" '
        f'--model "{VOICE}" --length_scale {PIPE["length_scale"]} '
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

    # Clear the audio queue again before resuming listening
    while not audio_q.empty():
        try:
            audio_q.get_nowait()
        except:
            pass

    # Reset the recognizer to clear any buffered audio
    rec.Reset()

    is_speaking = False

END = object()  # queue sentinel: end of reply

def speak_streaming(tokens):
    """Speak a reply sentence by sentence while the LLM is still writing it. Returns the full reply text.

    LLM thread: tokens -> sentence splitter -> `sentences` queue.
    TTS thread: one Piper process and one WAV per sentence -> `wavs` queue (so sentence N+1 is made while N plays).
    This thread: plays the WAVs in order, then does the same clean-up as speak().
    A worker that fails logs the error and ends its queue, so what already exists is still spoken.
    """
    global is_speaking
    sentences, wavs, parts = queue.Queue(), queue.Queue(), []
    out_dir = ROOT / "results" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)

    def llm_worker():
        splitter = SentenceSplitter(PIPE["max_first_chunk_words"])
        try:
            for token in tokens:
                parts.append(token)
                for sentence in splitter.feed(token):
                    timing_event("sentence")
                    sentences.put(sentence)
        except Exception as e:
            print(f"[!] LLM worker failed: {e!r}")
        finally:
            tail = splitter.flush()  # also covers a reply cut off by max_tokens
            if splitter.emitted > 1 and tail and tail[-1].rstrip("\"')]")[-1:] not in (".", "!", "?"):
                tail.pop()  # unfinished last sentence of a cut-off reply: do not speak half of it
            for sentence in tail:
                timing_event("sentence")
                sentences.put(sentence)
            sentences.put(END)

    def tts_worker():
        n = 0
        try:
            while (sentence := sentences.get()) is not END:
                # Same escaping and same Piper call as speak(), one WAV per sentence
                safe_text = sentence.replace('"', '').replace("'", "").replace('\n', ' ').replace('&', 'and')
                output_path = str(out_dir / f"jarvis_output_{n}.wav")
                result = subprocess.run(
                    f'echo {safe_text} | "{PIPER}" '
                    f'--model "{VOICE}" --length_scale {PIPE["length_scale"]} '
                    f'--output_file "{output_path}" --quiet',
                    shell=True,
                    capture_output=True
                )
                if result.returncode != 0:  # otherwise the WAV of an earlier reply would be played
                    raise RuntimeError(result.stderr.decode(errors="replace")[-300:])
                wavs.put(output_path)
                n += 1
        except Exception as e:
            print(f"[!] TTS worker failed: {e!r}")
        finally:
            wavs.put(END)

    threading.Thread(target=llm_worker, daemon=True).start()
    threading.Thread(target=tts_worker, daemon=True).start()

    try:
        while (path := wavs.get()) is not END:
            if not is_speaking:  # mute the microphone from the first sentence on
                is_speaking = True
                while not audio_q.empty():
                    try:
                        audio_q.get_nowait()
                    except:
                        pass
            try:
                winsound.PlaySound(path, winsound.SND_FILENAME)
            except:
                pass
    finally:
        # Same clean-up as speak()
        time.sleep(0.8)
        while not audio_q.empty():
            try:
                audio_q.get_nowait()
            except:
                pass
        rec.Reset()
        is_speaking = False
    return trim_to_sentence("".join(parts))

print(f"[*] {CFG['name']} is starting...")
print(f"🤖 {GREETING_MESSAGE}")

# Speak the startup greeting
speak(GREETING_MESSAGE)

print(f"[*] {CFG['name']} is listening... (say 'exit' or 'quit' to stop)")

floor, voiced, quiet_ms = 60.0, False, 0
utter, prebuf = [], collections.deque(maxlen=3)
with sd.RawInputStream(
    samplerate=RATE, blocksize=3200,  # 0.2 s: fine enough for our own end-of-speech detection
    dtype='int16', channels=1, callback=audio_callback,
    device=PIPE["mic_device"] or None
):
    while True:
        if is_speaking:
            time.sleep(0.1)
            voiced, quiet_ms = False, 0
            continue

        try:
            data = audio_q.get(timeout=0.5)
        except queue.Empty:
            continue
        # Own end-of-speech detection: Vosk waits too long for silence in a noisy room and merges two questions.
        level = float(np.sqrt(np.mean(np.frombuffer(data, np.int16).astype(np.float64) ** 2)))
        floor = min(level, floor * 1.02 + 0.5)  # background level: follows the quietest recent block (starts at a typical quiet room, not at the first block, which may already be speech)
        if level > floor * 2.5 + 50:
            if WHISPER and not voiced:
                utter = list(prebuf)  # keep the 0.6 s before the first loud block: speech starts softly
            voiced, quiet_ms = True, 0
        elif voiced:
            quiet_ms += len(data) // 32  # 16 kHz int16 = 32 bytes per ms
        if WHISPER:
            if not voiced:
                prebuf.append(data)
                continue
            utter.append(data)
            if quiet_ms < (PIPE["end_silence_ms"] or 700) and len(utter) < 100:  # 100 blocks = 20 s cap
                continue
            result = whisper_transcribe(b"".join(utter))
            voiced, quiet_ms, utter = False, 0, []
            prebuf.clear()
        elif rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            voiced, quiet_ms = False, 0
        elif PIPE["end_silence_ms"] and voiced and quiet_ms >= PIPE["end_silence_ms"]:
            result = json.loads(rec.FinalResult())
            rec.Reset()
            voiced, quiet_ms = False, 0
        else:
            continue
        if True:
            text = fix_asr(result.get("text", "").strip())

            if not text or not is_confident(result, PIPE["min_conf"]):
                continue
            if WHISPER:
                timing_event("heard", text=text)  # the demo page lists the turn (Vosk is hooked in web_demo.py instead)

            # Skip if the text is too short (likely noise)
            if len(text) < 3:
                continue

            # Exit command
            if is_exit(text, EXIT_WORDS):
                print("Goodbye!")
                break

            print(f"You: {text}")

            # Check if it's a greeting
            if is_greeting(text):
                reply = GREETING_MESSAGE
            else:
                # Build prompt with conversation context
                conversation_history.append(f"User: {text}")

                # Keep only the last history lines for context (v0: 4, including this question)
                recent_history = conversation_history[-PIPE["history_turns"]:]
                context = "\n".join(recent_history)

                if PIPE["prompt_style"] == "tiny":
                    # Fewest prompt tokens (reading the prompt costs ~87 ms per token): the last exchange only while it is short
                    if len(conversation_history) >= 3 and len(conversation_history[-2].split()) <= 16:
                        context = "\n".join(conversation_history[-3:])
                    else:
                        context = conversation_history[-1]
                    prompt = f"""You are {CFG['name']}, a helpful voice assistant. Reply in one short sentence.
{context}
{CFG['name']}:"""
                elif PIPE["prompt_style"] == "short":
                    prompt = f"""You are {CFG['name']}, a concise voice assistant. Reply in one or two short sentences.
{context}
{CFG['name']}:"""
                else:
                    # Lumo's exact wording with the name taken from config/persona.toml
                    prompt = f"""You are {CFG['name']}, a helpful offline AI assistant.
Answer the user's question directly and helpfully. Be concise (under 50 words).

{context}
{CFG['name']}:"""

                if PIPE["stream"]:
                    reply = speak_streaming(stop_at_role_echo(llm.generate(
                        prompt, max_tokens=PIPE["max_tokens"], n_batch=PIPE["n_batch"], streaming=True), CFG["name"]))
                    conversation_history.append(f"{CFG['name']}: {reply}")
                    print(f"{CFG['name']}: {reply}")
                    continue

                reply = llm.generate(prompt, max_tokens=PIPE["max_tokens"], n_batch=PIPE["n_batch"])
                reply = trim_to_sentence(cut_role_echo(reply.strip(), CFG["name"]))

                # Store response in history
                conversation_history.append(f"{CFG['name']}: {reply}")

            print(f"{CFG['name']}: {reply}")
            speak(reply)
