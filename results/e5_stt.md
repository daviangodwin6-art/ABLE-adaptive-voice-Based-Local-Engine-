# E5 speech recognizer: small vs lgraph

**DEVELOPMENT LAPTOP - NOT FINAL NUMBERS.** Synthetic Piper speech, fake real-time mic, audio not played (first audio = `PlaySound` call). Each cell is `median / worst` in ms over all questions of all passes (n = questions x passes). Peaks are the maximum over all replies.

| Config | n | A end-of-speech->text | B text->1st token | C LLM total | D text->1st audio | **E end-of-speech->1st audio** | tok/s | prompt tokens | B ms per prompt token | peak CPU cores | peak RAM MB | replies cut off |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `stt_small` (5 thr) | 15 | 1212 / 1320 | 4577 / 5492 | 6605 / 7280 | 6525 / 8132 | **7584 / 9272** | 6.1 | 54 | 85 | 8.9 | 2721 | 0/15 |
| `stt_lgraph` (5 thr) | 15 | 1746 / 2034 | 4581 / 5497 | 6660 / 7126 | 6587 / 7946 | **8517 / 9619** | 6.1 | 54 | 86 | 8.4 | 2964 | 0/15 |

| Config | per-pass median of E (ms) | per-pass median of B (ms) |
|---|---|---|
| `stt_small` | 7410, 7756, 7584 | 4369, 4591, 4602 |
| `stt_lgraph` | 8619, 8517, 8406 | 4581, 4612, 4473 |
