# ABLE - test package

ABLE is an offline voice assistant: you speak, it answers with a voice. Everything runs on the
laptop's CPU; no internet is needed once setup is done. This package is the **E3 version**
(tuned settings, replies spoken sentence by sentence while they are still being written).

## What you need
- Windows 10 or 11, 64-bit, about **5 GB free disk** and **8 GB RAM** (ABLE itself uses about 3 GB).
- A microphone and speakers (a headset works best).
- **Python 3.13 (64-bit)** from https://www.python.org/downloads/ - in the installer tick
  "Add python.exe to PATH". No admin rights are needed for a per-user install.
- The **Microsoft Visual C++ Redistributable (x64)** - most laptops already have it. Only if
  ABLE never speaks or says a DLL is missing: install `vc_redist.x64.exe` from
  https://aka.ms/vs/17/release/vc_redist.x64.exe (needs admin).

## Setup (once)
1. Right-click the .zip > **Properties** > tick **Unblock** > OK. Then **Extract All** to a short
   folder, e.g. `C:\ABLE` (do not run it from inside the zip).
2. Install Python 3.13 (see above).
3. Double-click **`setup.bat`**. It creates a `.venv` folder and installs the Python packages
   (from the bundled `wheels` folder if present, otherwise from the internet, roughly 150-250 MB).
   Wait for "Setup OK".

## Start
1. Double-click **`start.bat`**. A black window opens and the browser shows
   http://localhost:8765 (if not, open that address yourself; `http://127.0.0.1:8765` also works).
2. Press **Start ABLE**. Loading the models takes 10-30 s, then ABLE says hello.
3. Speak a question after the greeting, e.g. "what is the capital of France". Wait for the answer
   before speaking again (the microphone is muted while ABLE talks).
4. Say **"exit"** to stop listening (the button comes back). Close the black window to quit.

## What to expect
- On the developer's laptop (Intel i7-9750H, 6 cores) ABLE needs about **5 s to read the prompt**
  and the **first sound comes about 7-10 s after you stop speaking** (longer for long answers).
  Your numbers will be different; that is exactly what we want to learn.
- The page shows which stage is running and, for every turn, a bar: red = reading the prompt,
  orange = writing before the voice starts, blue = making the first voice clip.
- The small speech recogniser makes mistakes, especially with a far-away laptop microphone.
  Short, clear questions work best. Answers are short (one or two sentences, max 60 tokens).

## Thread tuning (optional)
The LLM uses **5 threads** (`n_threads`), the best value on the developer's 6-core laptop.
On your CPU another value may be faster. Open a terminal in the folder and try e.g.
`start.bat 4` or `start.bat 6` (good values: from half to all of your *physical* cores), ask the
same 3 questions each time and note the "first sound after" times. Do not use more threads than
your CPU has cores, and close other heavy programs while testing.

## Microphone tips
- Windows Settings > Privacy & security > **Microphone**: turn on "Microphone access" and
  "Let desktop apps access your microphone".
- ABLE uses the **default** recording device: Settings > System > Sound > Input. Pick the right
  microphone there and check its level moves when you speak.
- Mic test without the LLM (close start.bat first):
  `.venv\Scripts\python.exe bench\mic_check.py` - say "where is the library", it prints what it
  hears. Ctrl+C to stop.

## Troubleshooting
| Problem | Fix |
|---|---|
| setup.bat: "Python 3.13 was not found" | Install Python 3.13 64-bit with "Add to PATH", open a new window, run setup.bat again. |
| setup.bat: pip errors without internet | The package has no `wheels` folder: connect to the internet once, or ask for the offline package. |
| Page says "Stopped: ... PortAudio / Invalid device / no default input" | No microphone found: plug it in, set it as default input, allow mic access (above), press Start ABLE again. |
| ABLE hears nothing / wrong words | Check the mic level in Sound settings, speak closer, run `bench\mic_check.py`. |
| "address already in use" / page does not open | Port 8765 is busy: close the other start.bat window (or restart the laptop) and try again. |
| "Stopped: ... No such file" / model not found | Models are missing: the folder `baselines\lumo\models` must hold the `.gguf`, the `vosk-model-small-en-us-0.15` folder and `en_US-amy-medium.onnx`; re-extract the zip. |
| Text answers appear but no sound | Check the speakers; if it still fails install the Visual C++ Redistributable (above). |
| Very slow or the laptop freezes | Close other programs, plug in the charger, set Windows power mode to "Best performance", try `start.bat 4`. |
| Windows Defender/SmartScreen warning | The zip was not unblocked (Setup step 1); `piper.exe` is the official Piper speech program. |

## Feedback - please send back
- [ ] Laptop model, **CPU model** (Settings > System > About), **RAM**, plugged in or on battery.
- [ ] Microphone used (built-in / headset / USB).
- [ ] For 5 questions: what you said, what ABLE heard (the "You:" line), the answer, and the
      **"first sound after" time** shown on the page.
- [ ] **Wrong words**: anything ABLE misheard or answered strangely.
- [ ] Thread test (if you did it): threads tried and the times.
- [ ] Any error text (a screenshot of the page and the black window is perfect).

## Credits
Based on Lumo (https://github.com/mehedinaeem/Lumo, MIT). Speech recognition: Vosk and
vosk-model-small-en-us-0.15 (Alpha Cephei, Apache 2.0). Language model: orca-mini-3b (GGUF via
GPT4All). Voice: Piper (MIT, uses espeak-ng, GPL-3.0) with the en_US-amy-medium voice.
Page: React (MIT).
