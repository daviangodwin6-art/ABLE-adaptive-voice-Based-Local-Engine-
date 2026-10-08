# Gate A: Lumo vs jarvis_v0

**DEVELOPMENT LAPTOP - NOT FINAL NUMBERS.** Synthetic Piper speech, fake real-time mic, audio not played (first audio = `PlaySound` call). Each cell is `median / worst` in ms over all questions of all passes (n = 5 questions x passes). Peaks are the maximum over all replies.

| Config | n | A end-of-speech->text | B text->1st token | C LLM total | D text->1st audio | **E end-of-speech->1st audio** | tok/s | prompt tokens | B ms per prompt token | peak CPU cores | peak RAM MB | replies cut off |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `lumo` (4 thr) | 15 | 1173 / 1394 | 8455 / 14037 | 10764 / 17438 | 11737 / 19329 | **12938 / 20495** | 5.4 | 88 | 97 | 5.0 | 2715 | 0/15 |
| `v0` (4 thr) | 15 | 1172 / 1448 | 7644 / 10993 | 9937 / 13031 | 10767 / 14128 | **11977 / 15294** | 5.3 | 82 | 98 | 6.4 | 2714 | 0/15 |

| Config | per-pass median of E (ms) | per-pass median of B (ms) |
|---|---|---|
| `lumo` | 12938, 12859, 13107 | 8455, 8437, 8661 |
| `v0` | 11977, 12112, 11677 | 7644, 7839, 7340 |
