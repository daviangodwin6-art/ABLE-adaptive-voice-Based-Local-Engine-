# Lumo (B1) per-stage timings

**DEVELOPMENT LAPTOP - NOT FINAL NUMBERS**

- Machine: i7-9750H, 6C/12T, CPU only (CUDA_VISIBLE_DEVICES=-1, GPT4All device=cpu); on battery, Balanced power plan
- Input: `fixed_sentence.wav` (2.32 s, 16 kHz mono). Expected text: "what is the capital of france"
  (synthetic Piper speech, cleaner than a real voice; pass `--wav` to use a real recording)
- 5 measured runs after 1 discarded warm-up. Model load (once): VOSK 503 ms, LLM 418 ms
- Recognised text: ['what is the capital of france']

| Stage | Median (ms) | Worst (ms) |
|---|---:|---:|
| Speech-to-text (VOSK) | 1150 | 1232 |
| LLM time to first token | 6648 | 7236 |
| LLM total (max 80 tokens) | 8514 | 9287 |
| TTS time to first audio (full WAV written) | 958 | 1085 |
| **STT + full LLM + TTS (Lumo end-of-speech to first audio, sequential)** | **10679** | **11570** |

Notes: Lumo generates the full reply (blocking), then Piper writes the whole WAV, then plays it, so first audio
= STT + total LLM + TTS. VOSK time here is decoding of the whole file; in live mode part of it overlaps with speech.
Playback start-up and Lumo's 0.5 s mic chunking / endpoint wait are not included.
