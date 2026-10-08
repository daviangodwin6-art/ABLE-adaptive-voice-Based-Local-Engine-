| # | Heard (VOSK) | Prompt chars | A. End of speech -> text (ms) | B. Text -> 1st LLM token (ms) | C. LLM total (ms) | Tokens | D. Text -> first audio (ms) | **E. End of speech -> first audio (ms)** |
|---|---|---|---|---|---|---|---|---|
| 1 | what is the capital of france | 169 | 1172 | 4928 | 6264 | 8 | 6999 | 8172 |
| 2 | how many days are there in a week | 252 | 968 | 7429 | 8772 | 8 | 9438 | 10406 |
| 3 | tell me a short joke | 281 | 1259 | 8183 | 10489 | 14 | 11323 | 12582 |
| 4 | why is the sky blue | 294 | 1165 | 7847 | 12275 | 28 | 13373 | 14538 |
| 5 | who wrote the play romeo and juliet | 407 | 1449 | 11422 | 12902 | 9 | 13723 | 15172 |
| | **Median** | 281 | 1172 | 7847 | 10489 | 9 | 11323 | 12582 |
| | **Worst** | 407 | 1449 | 11422 | 12902 | 28 | 13723 | 15172 |

Breakdown (medians): endpoint wait before final decode starts 1161 ms; final AcceptWaveform call 13 ms; Result() 0.6 ms; Piper run 821 ms; LLM prefill (= text->1st token) 7847 ms; decode speed 5.4 tokens/s.

Replies: Q1: 'The capital city of France is Paris.' / Q2: 'There are seven days in a week.' / Q3: 'Why did the tomato turn red? Because it saw the salad dressing!' / Q4: "The sky appears blue because of the way Earth's atmosphere scatters sunlight, like a prism splitting white light into its colors." / Q5: 'William Shakespeare wrote the play Romeo and Juliet.'

Linear fit time-to-first-token vs prompt length: 26.8 ms per prompt character + 433 ms (5 points)
Audio length of replies (s): 3.1, 2.4, 4.5, 7.9, 3.8; sample rate 22050 Hz
Peaks per reply (proc cores busy / % of 12 threads / system CPU % / process working set MB): Q1: 4.7 / 39% / 54% / 2690; Q2: 4.5 / 38% / 76% / 2696; Q3: 4.5 / 38% / 69% / 2702; Q4: 4.5 / 38% / 83% / 2706; Q5: 4.5 / 38% / 76% / 2713
overall 2713.390625 1785.6953125 0 0 91 3.052675700004329
