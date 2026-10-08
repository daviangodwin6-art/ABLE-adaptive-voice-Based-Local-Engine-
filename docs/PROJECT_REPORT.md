# ABLE - Adaptive voice-Based Local Engine: Project Report

HackNex EPS08, Low-Latency On-Device Voice Stack. Report written 2026-10-09 from the code and the result files in this repository.

## 1. Summary

ABLE is a voice assistant that runs entirely on a Windows laptop CPU, with no GPU and no internet at run time. You speak, it transcribes, a small local language model writes a reply, and a local voice speaks it.

The one number the project optimises is the **time from the end of your speech to the first sound of the reply**, at low CPU and RAM cost.

- **Starting point:** the open-source Lumo assistant (MIT, pinned commit `778ed05`), measured at a median of **12.9 s** to first sound on the development laptop.
- **Best benchmarked configuration:** **7.6 s** median (same LLM, tuned settings, streaming speech; `results/e5_stt.md`).
- **Current demo configuration:** a smaller LLM (Gemma 3 1B) and Whisper for recognition. It has not been through the benchmark harness yet. One live turn observed on 2026-10-09 took 2.6 s from end-of-speech detection to first sound (about 3.3 s including the 0.7 s silence wait). Treat that as a single observation, not a result.

All numbers are from the development laptop (Intel i7-9750H, 6 cores, 31.7 GB RAM, plugged in) and are marked "not final" in the result files.

## 2. The three models

| Stage | Demo configuration | Baseline (v0 defaults in `config/pipeline.toml`) |
|---|---|---|
| **ASR** (speech to text) | **faster-whisper `base.en`**, CTranslate2, int8, CPU, 141 MB | **Vosk `small-en-us-0.15`** (Kaldi), streaming |
| **LLM** (reply) | **Gemma 3 1B instruct, Q4_0 GGUF**, 722 MB, via `llama-cpp-python` | **Orca Mini 3B, Q4_0 GGUF**, 1.98 GB, via `gpt4all` 2.8.2 |
| **TTS** (text to speech) | **Piper `en_US-amy-medium`** (ONNX, 60 MB, 22 050 Hz), speed 0.88 | Same voice, speed 1.0 |

### ASR
- **Whisper** is not a streaming recogniser. The loop does its own end-of-speech detection, then transcribes the whole phrase in one call (`beam_size=1`, Whisper's built-in Silero VAD removes silence inside the phrase, no conditioning on earlier text).
- The Whisper output is lowercased and stripped of punctuation so that it looks like Vosk output. That keeps exit-word and greeting matching identical for both engines.
- **Vosk** stays available as a switch (`stt_engine = "vosk"`). The larger `vosk-model-en-us-0.22-lgraph` was tested and rejected for the demo: it added about 0.9 s to first sound and about 240 MB of RAM (`results/e5_stt.md`).
- A confidence filter (`min_conf = 0.5` in the demo) drops low-confidence phrases such as background TV. A small text fix corrects a known Vosk mistake ("there is the library" becomes "where is the library").

### LLM
- Two back ends sit behind one small interface (`pipeline/llm_backend.py`): `gpt4all` for the original model and `llama-cpp-python` for Gemma 3, which the llama.cpp bundled in gpt4all cannot load.
- Both run CPU-only (`n_gpu_layers=0`, `CUDA_VISIBLE_DEVICES=-1`). Gemma is wrapped in its own turn format (`<start_of_turn>user ... <start_of_turn>model`).
- Demo settings: 5 threads, prompt batch 128, at most 100 new tokens, context 1024.

### TTS
- Piper runs as a separate process (`piper.exe`) and writes a WAV file, which Windows plays through `winsound`.
- With streaming on, there is one Piper run and one WAV per sentence.

## 3. Pipeline and code architecture

### Flow of one turn

```
microphone (16 kHz, mono, 0.2 s blocks)
   -> noise gate (optional) -> audio queue
   -> end-of-speech detector (own energy-based, adaptive background level)
   -> ASR  (Whisper: whole phrase / Vosk: streaming)
   -> text fix, confidence filter, exit and greeting check
   -> prompt builder (persona + recent history, style v0 / short / tiny)
   -> LLM, streamed token by token
        -> role-echo guard -> sentence splitter -> sentence queue      (LLM thread)
             -> Piper, one WAV per sentence -> WAV queue               (TTS thread)
                  -> playback in order, mic muted while speaking       (main thread)
   -> history updated, back to listening
```

### What each part does
- **Audio in** (`audio_callback`): `sounddevice` delivers 0.2 s blocks into a queue. While ABLE speaks, blocks are dropped so it does not hear itself.
- **End-of-speech detection** (main loop in `pipeline/jarvis_v1.py`): tracks the background level from the quietest recent block and treats a block as speech when it is clearly above it. A phrase ends after 700 ms of quiet. For Whisper, the 0.6 s before the first loud block is kept, because speech starts softly.
- **Prompt builder**: three styles. The demo uses `tiny`: one instruction line ("Reply in one short sentence") plus the last exchange only if it was short, otherwise just the question.
- **Streaming speech** (`speak_streaming`): three threads connected by two queues. The LLM thread feeds tokens to the sentence splitter; the TTS thread turns each finished sentence into a WAV; the main thread plays them in order. Sentence N+1 is synthesised while sentence N is playing.
- **Sentence splitter** (`pipeline/sentence_splitter.py`): splits on `. ! ?` and knows abbreviations, initials, ellipses, decimals and list markers ("1."). Only the very first chunk of a reply may also be cut at a comma once it is longer than 12 words.
- **Role-echo guard** (`pipeline/asr_fix.py`): small models often continue the chat by writing the next "User:" line. The guard stops the stream there and never speaks half a marker.

### Repository layout
| Path | Purpose |
|---|---|
| `pipeline/jarvis_v0.py` | Frozen copy of Lumo's loop, the reference |
| `pipeline/jarvis_v1.py` | The working loop: v0 plus every optimisation as a switch |
| `pipeline/llm_backend.py`, `sentence_splitter.py`, `asr_fix.py` | LLM adapter, splitter, text fixes |
| `config/pipeline.toml`, `config/persona.toml` | All 17 switches (v0 defaults) and the persona, greeting, exit words |
| `bench/` | Harness with a fake real-time microphone, ablation runner, reports |
| `results/` | Measurement tables for each experiment |
| `demo/web_demo.py`, `demo/ui/` | Live web view (section 5) |
| `tests/` | Plain-assert tests for the splitter, text fixes and demo state |
| `scripts/` | Reproducible setup: pinned clone, locked packages, model downloads with checksums |

### Configuration design
- Every optimisation is a key in `config/pipeline.toml`. With all keys at their defaults, `jarvis_v1.py` behaves exactly like the frozen `jarvis_v0.py` (checked: 12 435 vs 12 317 ms median).
- A single run can override keys through the `JARVIS_TUNING` environment variable. Unknown keys or wrong types stop the program, so a typo cannot silently run the wrong experiment.

## 4. What made it faster

### Where the time went in the baseline
The first step was measuring the unmodified baseline (`PROJECT_SNAPSHOT.md`). Median 12.6 s to first sound, split roughly as:

| Part | Time | Cause |
|---|---|---|
| Reading the prompt before the first token | 7.8 s (about 60 %) | About 100 ms per prompt token; whole prompt re-read every turn; history grows |
| Writing the reply | 1.3-4.4 s | 5.4 tokens/s; nothing spoken until the whole reply exists |
| Waiting for end of speech | 1.2 s | 0.5 s silence rule plus 0.5 s audio blocks; the decode itself is 13 ms |
| Piper | 0.8 s | New process and model load for every reply |

### Experiments, one change at a time
Each row was measured with the same harness: synthetic spoken questions fed through a fake microphone in real time, three interleaved passes, median and worst case reported.

| Step | Change | Median to first sound | Source |
|---|---|---|---|
| Baseline | Lumo unmodified | 12.9 s | `results/gate_a.md` |
| v0 | Own copy, same behaviour | 12.0 s | `results/gate_a.md` |
| E1 | Prompt batch 8 to 128, threads 4 to 5 | about 11.0 s | `results/ablation.md` |
| E2 | Short prompt, last exchange only | 12.2 to 9.6 s (-22 %) | `results/ablation.md` |
| E3 | Streaming speech, sentence by sentence | Long replies 18.4 to 13.9 s (-25 %); one-sentence replies unchanged | `results/ablation.md` |
| E4 | `tiny` prompt and faster speech (0.88) | 10.1 to 9.5 s | `results/e4.md` |
| E5 | Recogniser choice (small Vosk kept) | 7.6 s vs 8.5 s for the larger model | `results/e5_stt.md` |

### The optimisations, by effect
1. **Fewer prompt tokens.** Reading the prompt costs about 90-100 ms per token on this CPU, and that cost did not change with any setting. The gain came from sending less: 81 tokens down to 56, then 48.
2. **Runtime settings.** Prompt batch 128 cut the per-token cost by 7-11 %. Five threads beat four; six was no better on the median and worse in the worst case, and leaving one physical core free helps Piper.
3. **Overlapping the stages.** With streaming, the first sentence is spoken while the model is still writing the rest. Of 21 gaps between sentences, the median was 0 ms and two were over 300 ms.
4. **Early first chunk.** The first chunk is the one that decides time to first sound, so only that one may be cut at a comma.
5. **Own end-of-speech detection** with 0.2 s blocks, instead of Vosk's rule on 0.5 s blocks, which also merged two questions in a noisy room.
6. **Smaller model.** Gemma 3 1B at 722 MB replaces the 1.98 GB Orca Mini 3B in the demo. This is the largest remaining lever and the one not yet benchmarked.
7. **Faster speech** (Piper length scale 0.88, about 14 % shorter audio).

### Resource use (benchmarked configuration, Orca Mini 3B)
- Peak RAM about 2.7 GB working set, most of it the memory-mapped model file.
- About 5 cores busy while generating.
- GPU: 0 % utilisation and 0 MiB in all 91 samples of the snapshot run.

### What is and is not novel
Stated plainly, the components are existing open-source models, and the techniques (prompt shortening, sentence-level streaming TTS, quantised models) are known. The project's own contribution is:

- **Measurement before optimisation.** A harness that runs the *unmodified* assistant behind a fake real-time microphone and timestamps the same four calls every time, so the baseline and every variant are measured identically.
- **One file, one switch per idea.** Every experiment is a configuration change on the same code, with a frozen reference to prove nothing else moved.
- **First-chunk-only early cut** in the sentence splitter, aimed specifically at the first-sound metric without chopping the rest of the reply into fragments.
- **Stream-safe role-echo guard** that holds back a partial "User" marker until it is known not to be one.
- **Engine-independent ASR contract.** Whisper is made to return Vosk-shaped results so the rest of the loop, the filters and the demo do not care which recogniser is running.
- **A live view that does not touch the pipeline** (section 5).

One caveat: the README describes ABLE as continuously adapting model size and precision to the available CPU and memory. The current code does not do that automatically. Adaptation today is manual, through the configuration switches. Automatic adaptation and response caching are not implemented.

## 5. The web app

### What it is
A local page at `http://localhost:8765` that shows the voice loop working in real time: which stage is active, the reply as it is written, and the timing of every turn. It is meant for demos and for testing.

### How it works
- **Server** (`demo/web_demo.py`): Python standard library only (`http.server`). It runs `pipeline/jarvis_v1.py` in a thread with the real microphone and speakers.
- **No instrumentation in the pipeline.** The server wraps five existing calls from the outside: the recogniser result, Whisper's transcribe, the LLM's generate, the Piper process, and sound playback. Each wrapper switches a stage on or off and records a timestamp.
- **Front end** (`demo/ui`): React 18 built with Vite, served as static files by the same server. It polls `/state` every 100 ms. It works offline once built.

| Endpoint | Function |
|---|---|
| `GET /state` | Active stages, all turns with timings, current settings, running flag, error, microphone name |
| `POST /run` | Start the voice loop (re-reads the Windows default microphone first) |
| `POST /skip` | Terminate the reply in progress |

### Pages
- **Home**
  - Microphone button starts the loop; the label shows Listening, Thinking or Speaking, and the name of the microphone in use.
  - Conversation box with the last question and the reply as it streams in.
  - **Terminate** button in the top-right corner of the reply box and the "currently speaking" box. It stops the LLM, cancels remaining voice clips and cuts the sound; the loop returns to listening in under a second.
  - **Time to First Sound** for the last turn, with session median and 95th percentile.
  - **Runtime Pipeline Execution**: five stages (Transcribing, Reading the prompt, Writing the reply, Making the voice, Speaking), each lit while active and ticked with its time when done.
  - Resource bars (CPU, RAM, GPU). These show the peaks from the last benchmark run, not live readings.
- **History**: the turns of the current session with time to first sound. Not saved between sessions.
- **Config**: read-only table of the live settings (model, quantisation, runtime, threads, batch, max tokens, history, speech engine, streaming).
- **Benchmarks**: per-question table from the benchmark snapshot (first-sound time, tokens per second, peak cores).
- **Replay**: placeholder. Playback needs per-turn audio capture, which does not exist yet.

### Behaviour worth knowing
- The microphone is selected at each Start. If you change device while the loop runs, say "exit" and press Start again.
- "Time to First Sound" on the page starts when end-of-speech is detected and includes transcription. It does not include the 700 ms of silence used to decide the phrase has ended.
- Terminate ends the current reply only. Saying "exit" ends the loop.

## 6. Limits and open items

- The demo configuration (Gemma 3 1B with Whisper) has no benchmark table yet; the measured results are for Orca Mini 3B with Vosk.
- All numbers are from the development laptop with synthetic speech, not a human voice, and exclude speaker latency.
- Piper is still started once per sentence (0.7-1.1 s each); keeping it loaded is not done.
- The prompt is re-read in full every turn; there is no reuse of the model's cache between turns.
- There is no wake word.
- Recognition with the laptop microphone array is noticeably worse than with clean audio.
- Automatic adaptation to CPU and memory budget, and response caching, are described in the README but not implemented.
