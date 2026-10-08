"""jarvis_v0 - our frozen copy of Lumo's voice loop (baseline B2-v0).

Derived from Lumo's main.py: https://github.com/mehedinaeem/Lumo (MIT License),
pinned commit 778ed055033ec3b0410349a82b9ea68e9546a4e0. Credit and thanks to the Lumo authors.

Behaviour is intentionally IDENTICAL to Lumo (same models, same defaults, same blocking loop,
same shell `echo | piper.exe` call, same prompt wording). The only differences:
  * name, greeting, greeting words and exit words come from config/persona.toml;
  * paths are absolute (models are shared with baselines/lumo, not copied);
  * the Piper output WAV goes to results/raw/ instead of Lumo's folder.
Do not optimise this file; later versions (jarvis_v1.py ...) are copies of it.

Run with Lumo's venv:  baselines\\lumo\\.venv\\Scripts\\python.exe pipeline\\jarvis_v0.py
"""
import sounddevice as sd
import queue, json, subprocess, time, winsound, os, tomllib
from pathlib import Path
from vosk import Model, KaldiRecognizer
from gpt4all import GPT4All

ROOT = Path(__file__).resolve().parent.parent
LUMO = ROOT / "baselines" / "lumo"
CFG = tomllib.loads((ROOT / "config" / "persona.toml").read_text(encoding="utf-8"))

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
    allow_download=False      # Prevent internet access
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
        f'--model "{VOICE}" '
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
            text = result.get("text", "").strip()

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

                # Keep only last 4 exchanges for context
                recent_history = conversation_history[-4:]
                context = "\n".join(recent_history)

                # Lumo's exact wording with the name taken from config/persona.toml
                prompt = f"""You are {CFG['name']}, a helpful offline AI assistant.
Answer the user's question directly and helpfully. Be concise (under 50 words).

{context}
{CFG['name']}:"""

                reply = llm.generate(prompt, max_tokens=80)
                reply = reply.strip()

                # Store response in history
                conversation_history.append(f"{CFG['name']}: {reply}")

            print(f"{CFG['name']}: {reply}")
            speak(reply)
