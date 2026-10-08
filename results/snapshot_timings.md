# Snapshot timing of unmodified main.py (5 questions, fake real-time mic)

Times in ms. Input = synthetic Piper speech (not a human voice).

| # | heard | tokens | End of speech -> text (endpoint wait + decode) |   of which: wait for silence/chunk until final decode starts |   of which: final AcceptWaveform call | Text -> first LLM token | LLM total | Piper run (full WAV written) | Text -> first audio | **End of speech -> first audio** |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | what is the capital of france | 8 | 1172 | 1161 | 11 | 4928 | 6264 | 735 | 6999 | 8172 |
| 2 | how many days are there in a week | 8 | 968 | 954 | 13 | 7429 | 8772 | 666 | 9438 | 10406 |
| 3 | tell me a short joke | 14 | 1259 | 1190 | 69 | 8183 | 10489 | 833 | 11323 | 12582 |
| 4 | why is the sky blue | 28 | 1165 | 1153 | 11 | 7847 | 12275 | 1097 | 13373 | 14538 |
| 5 | who wrote the play romeo and juliet | 9 | 1449 | 1372 | 76 | 11422 | 12902 | 821 | 13723 | 15172 |
| | **Median** | 9 | 1172 | 1161 | 13 | 7847 | 10489 | 821 | 11323 | 12582 |
| | **Worst** | 28 | 1449 | 1372 | 76 | 11422 | 12902 | 1097 | 13723 | 15172 |
