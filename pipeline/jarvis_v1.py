"""jarvis_v1 - jarvis_v0 plus experiment toggles from config/pipeline.toml.

Derived from Lumo's main.py: https://github.com/mehedinaeem/Lumo (MIT License),
pinned commit 778ed055033ec3b0410349a82b9ea68e9546a4e0. Credit and thanks to the Lumo authors.

A copy of pipeline/jarvis_v0.py (the frozen reference). With every toggle at its v0 default this file
behaves exactly like v0; every ablation row is a config change on THIS file, not a new copy.
Toggles: n_batch, n_threads, max_tokens, history_turns, prompt_style, stream, max_first_chunk_words, length_scale.
The bench overrides single toggles with the JARVIS_TUNING env variable (JSON object).

Run with Lumo's venv:  baselines\\lumo\\.venv\\Scripts\\python.exe pipeline\\jarvis_v1.py
"""
import sounddevice as sd
import queue, json, subprocess, time, winsound, os, tomllib, sys, threading
from pathlib import Path
from vosk import Model, KaldiRecognizer
from gpt4all import GPT4All

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sentence_splitter import SentenceSplitter
from asr_fix import fix_asr

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
_KEYS = {"n_batch", "n_threads", "max_tokens", "history_turns", "prompt_style", "stream", "max_first_chunk_words", "length_scale"}
if set(PIPE) != _KEYS:
    raise SystemExit(f"config/pipeline.toml: unknown or missing keys: {sorted(set(PIPE) ^ _KEYS)}")
if PIPE["prompt_style"] not in ("v0", "short", "tiny"):
    raise SystemExit(f"prompt_style must be 'v0', 'short' or 'tiny', got {PIPE['prompt_style']!r}")

RATE = 16000
audio_q = queue.Queue()
is_speaking = False  # Flag to prevent feedback loop

def audio_callback(indata, frames, time_info, status):
    if not is_speaking:  # Only capture audio when not speaking
        audio_q.put(bytes(indata))

# STT
model = Model(str(LUMO / "models/stt/vosk-model-small-en-us-0.15"))
rec = KaldiRecognizer(model, RATE)

# LLM - using local GGUF model for offline operation
llm = GPT4All(
    model_name="orca-mini-3b-gguf2-q4_0.gguf",
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
            for sentence in splitter.flush():  # also covers a reply cut off by max_tokens
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
    return "".join(parts).strip()

print(f"[*] {CFG['name']} is starting...")
print(f"🤖 {GREETING_MESSAGE}")

# Speak the startup greeting
speak(GREETING_MESSAGE)

print(f"[*] {CFG['name']} is listening... (say 'exit' or 'quit' to stop)")

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
            text = fix_asr(result.get("text", "").strip())

            if not text:
                continue

            # Skip if the text is too short (likely noise)
            if len(text) < 3:
                continue

            # Exit command
            if text.lower() in EXIT_WORDS:
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
                    prompt = f"""You are {CFG['name']}. Answer in one short sentence.
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
                    reply = speak_streaming(llm.generate(
                        prompt, max_tokens=PIPE["max_tokens"], n_batch=PIPE["n_batch"], streaming=True))
                    conversation_history.append(f"{CFG['name']}: {reply}")
                    print(f"{CFG['name']}: {reply}")
                    continue

                reply = llm.generate(prompt, max_tokens=PIPE["max_tokens"], n_batch=PIPE["n_batch"])
                reply = reply.strip()

                # Store response in history
                conversation_history.append(f"{CFG['name']}: {reply}")

            print(f"{CFG['name']}: {reply}")
            speak(reply)
