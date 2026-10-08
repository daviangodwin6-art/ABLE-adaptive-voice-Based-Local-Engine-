# Ablation: v0 -> E1 (runtime settings) -> E2 (short prompt) -> E3 (streaming)

**DEVELOPMENT LAPTOP - NOT FINAL NUMBERS.** Synthetic Piper speech, fake real-time mic, audio not played (first audio = `PlaySound` call). Each cell is `median / worst` in ms over all questions of all passes (n = questions x passes). Peaks are the maximum over all replies.

| Config | n | A end-of-speech->text | B text->1st token | C LLM total | D text->1st audio | **E end-of-speech->1st audio** | tok/s | prompt tokens | B ms per prompt token | peak CPU cores | peak RAM MB | replies cut off |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `v0_chk` (4 thr) | 15 | 1173 / 1385 | 7927 / 11975 | 10323 / 14511 | 11115 / 15699 | **12317 / 16863** | 5.2 | 82 | 100 | 6.9 | 2714 | 0/15 |
| `v1_defaults` (4 thr) | 15 | 1173 / 1385 | 8062 / 11701 | 10376 / 15055 | 11227 / 16205 | **12435 / 17372** | 5.3 | 82 | 98 | 5.5 | 2713 | 0/15 |
| `e1_nb8` (4 thr) | 15 | 1173 / 1409 | 7997 / 11351 | 10405 / 13753 | 11419 / 14922 | **12621 / 16087** | 5.2 | 81 | 99 | 4.7 | 2712 | 0/15 |
| `e1_nb128` (4 thr) | 15 | 1173 / 1385 | 7429 / 10262 | 9471 / 12670 | 10373 / 13905 | **11574 / 15070** | 5.2 | 81 | 92 | 4.5 | 2727 | 0/15 |
| `e1_nb256` (4 thr) | 15 | 1172 / 1385 | 7288 / 10210 | 9980 / 12515 | 10770 / 13764 | **11971 / 14929** | 5.4 | 81 | 91 | 4.7 | 2726 | 0/15 |
| `e1_nb512` (4 thr) | 15 | 1173 / 1384 | 7248 / 9955 | 9729 / 12275 | 10562 / 13370 | **11827 / 14535** | 5.3 | 81 | 88 | 5.0 | 2726 | 0/15 |
| `e1_t4` (4 thr) | 15 | 1172 / 1386 | 7474 / 10509 | 9823 / 13519 | 10567 / 14648 | **11952 / 15813** | 5.2 | 81 | 94 | 4.7 | 2725 | 0/15 |
| `e1_t5` (5 thr) | 15 | 1174 / 1385 | 6746 / 9906 | 8972 / 12013 | 9827 / 13335 | **11032 / 14500** | 5.5 | 81 | 84 | 6.7 | 2727 | 0/15 |
| `e1_t6` (6 thr) | 15 | 1172 / 1386 | 6245 / 10755 | 8747 / 13547 | 9721 / 14684 | **10923 / 16068** | 5.8 | 82 | 75 | 7.8 | 2725 | 0/15 |
| `e2_ctrl` (4 thr) | 15 | 1173 / 1385 | 7298 / 10219 | 10077 / 11972 | 11009 / 13158 | **12211 / 14325** | 5.3 | 81 | 89 | 4.5 | 2726 | 0/15 |
| `e2` (4 thr) | 15 | 1173 / 1387 | 5071 / 5961 | 7332 / 8258 | 8169 / 9210 | **9556 / 10504** | 5.3 | 56 | 90 | 5.1 | 2720 | 0/15 |
| `e3_off` (5 thr) | 24 | 1173 / 1520 | 5153 / 9672 | 8147 / 20771 | 9110 / 23077 | **10275 / 24265** | 5.6 | 58 | 87 | 6.2 | 2736 | 7/24 |
| `e3_on` (5 thr) | 24 | 1180 / 1524 | 5172 / 9260 | 8018 / 20452 | 8577 / 16067 | **9814 / 17295** | 5.4 | 59 | 88 | 10.4 | 2734 | 5/24 |

| Config | per-pass median of E (ms) | per-pass median of B (ms) |
|---|---|---|
| `v0_chk` | 12315, 12317, 13158 | 7927, 7817, 8447 |
| `v1_defaults` | 12435, 12617, 12163 | 8062, 8098, 7825 |
| `e1_nb8` | 13622, 12103, 12621 | 9046, 7817, 7753 |
| `e1_nb128` | 13002, 11343, 11574 | 7835, 7066, 6922 |
| `e1_nb256` | 10663, 11971, 12122 | 6304, 7288, 7729 |
| `e1_nb512` | 11827, 11795, 11867 | 6575, 7389, 7438 |
| `e1_t4` | 11499, 12479, 12073 | 7055, 7834, 7537 |
| `e1_t5` | 11834, 11032, 10854 | 7093, 6771, 6613 |
| `e1_t6` | 12278, 10145, 10431 | 6871, 6054, 6107 |
| `e2_ctrl` | 12227, 12211, 11420 | 7298, 7453, 7093 |
| `e2` | 9652, 9314, 9556 | 4800, 5071, 5098 |
| `e3_off` | 10071, 15743, 10040 | 5225, 5065, 5168 |
| `e3_on` | 9793, 9861, 9837 | 5172, 5180, 5184 |

## E3 per question: streaming off (e3_off) vs on (e3_on)

E2 settings at 5 threads, 8 questions (BENCH_LONG=1), 3 passes. Medians over the passes, ms. Simulated playback takes the real audio time. Gaps are the silences between one sentence ending and the next starting.

| Questions | Config | A | B | C | D | E | E worst | sentences | gaps median / worst | tok/s | peak cores | peak machine CPU % | peak RAM MB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Q1 | `e3_off` | 1173 | 3265 | 4621 | 5452 | 6625 | 6936 | 1 | - | 5.2 | 5.6 | 100 | 2693 |
| Q1 | `e3_on` | 1173 | 3247 | 4651 | 5492 | 6664 | 6736 | 1 | - | 4.9 | 5.6 | 96 | 2693 |
| Q2 | `e3_off` | 969 | 4916 | 6305 | 7003 | 7972 | 8226 | 1 | - | 5.0 | 5.6 | 90 | 2704 |
| Q2 | `e3_on` | 973 | 4929 | 6380 | 7067 | 8039 | 8435 | 1 | - | 5.2 | 5.6 | 100 | 2704 |
| Q3 | `e3_off` | 1201 | 4618 | 7611 | 8606 | 9807 | 9865 | 1 | - | 5.6 | 5.6 | 90 | 2708 |
| Q3 | `e3_on` | 1202 | 4698 | 7862 | 7481 | 8684 | 8790 | 2 | 0 / 0 (0 of 3 over 300) | 5.3 | 7.6 | 100 | 2708 |
| Q4 | `e3_off` | 1165 | 5260 | 8182 | 9111 | 10277 | 18191 | 1 | - | 5.6 | 5.6 | 93 | 2712 |
| Q4 | `e3_on` | 1166 | 5277 | 8141 | 9066 | 10232 | 10263 | 1 | - | 5.6 | 5.8 | 95 | 2713 |
| Q5 | `e3_off` | 1385 | 5730 | 7292 | 8143 | 9528 | 13344 | 1 | - | 5.1 | 5.6 | 96 | 2726 |
| Q5 | `e3_on` | 1384 | 5857 | 7376 | 8249 | 9632 | 9675 | 1 | - | 5.2 | 6.2 | 89 | 2721 |
| Q6 | `e3_off` | 1089 | 5125 | 15073 | 17310 | 18401 | 18440 | 1 | - | 5.9 | 5.9 | 100 | 2727 |
| Q6 | `e3_on` | 1089 | 5090 | 15540 | 8911 | 10000 | 10188 | 3 | 0 / 756 (2 of 7 over 300) | 5.6 | 10.1 | 100 | 2723 |
| Q7 | `e3_off` | 1187 | 9159 | 19047 | 21294 | 22481 | 24265 | 1 | - | 5.9 | 5.6 | 100 | 2731 |
| Q7 | `e3_on` | 1190 | 9125 | 19927 | 13367 | 14557 | 17295 | 3 | 0 / 1 (0 of 8 over 300) | 5.4 | 10.4 | 100 | 2731 |
| Q8 | `e3_off` | 1025 | 8837 | 14893 | 16512 | 18032 | 22096 | 1 | - | 5.9 | 6.2 | 99 | 2736 |
| Q8 | `e3_on` | 1523 | 8955 | 15053 | 12845 | 14369 | 17005 | 2 | 0 / 20 (0 of 3 over 300) | 5.6 | 9.1 | 100 | 2734 |
| **Short (Q1-5)** | `e3_off` | 1174 | 4916 | 7146 | 8059 | 9400 | 18191 | 1 | - | 5.3 | 5.6 | 100 | 2726 |
| **Short (Q1-5)** | `e3_on` | 1173 | 4929 | 7376 | 7481 | 8684 | 10263 | 1 | 0 / 0 (0 of 3 over 300) | 5.3 | 7.6 | 100 | 2721 |
| **Long (Q6-8)** | `e3_off` | 1091 | 8837 | 15395 | 17352 | 18440 | 24265 | 1 | - | 5.9 | 6.2 | 100 | 2736 |
| **Long (Q6-8)** | `e3_on` | 1190 | 8955 | 15631 | 12666 | 13852 | 17295 | 3 | 0 / 756 (2 of 18 over 300) | 5.6 | 10.4 | 100 | 2734 |
| **All** | `e3_off` | 1173 | 5153 | 8147 | 9110 | 10275 | 24265 | 1 | - | 5.6 | 6.2 | 100 | 2736 |
| **All** | `e3_on` | 1180 | 5172 | 8018 | 8577 | 9814 | 17295 | 1.5 | 0 / 756 (2 of 21 over 300) | 5.4 | 10.4 | 100 | 2734 |

| Q | Config | Reply (pass 1) | Reply ends a sentence (passes) |
|---|---|---|---|
| Q1 | `e3_off` | The capital city of France is Paris. | 3/3 |
| Q1 | `e3_on` | The capital city of France is Paris. | 3/3 |
| Q2 | `e3_off` | There are seven days in a week. | 3/3 |
| Q2 | `e3_on` | There are 7 days in a week. | 3/3 |
| Q3 | `e3_off` | Why did the scarecrow win an award? Because he was outstanding in his field! | 3/3 |
| Q3 | `e3_on` | Why did the scarecrow win an award? Because he was outstanding in his field! | 3/3 |
| Q4 | `e3_off` | The sky appears blue because of the way Earth's atmosphere scatters sunlight. | 2/3 |
| Q4 | `e3_on` | The sky appears blue because of the way Earth's atmosphere scatters sunlight. | 3/3 |
| Q5 | `e3_off` | William Shakespeare wrote the play Romeo and Juliet. | 3/3 |
| Q5 | `e3_on` | William Shakespeare wrote the play Romeo and Juliet. | 3/3 |
| Q6 | `e3_off` | A rainbow is formed when sunlight passes through water droplets in the air, such as after a rain shower. The light is refracted, or bent, as it enters the droplet, and then reflected off the back of the droplet before being dispersed into its component colors (red, | 0/3 |
| Q6 | `e3_on` | A rainbow is formed when sunlight interacts with moisture in the atmosphere, such as after a rain shower. The light is refracted (bent) as it enters the water droplet, causing it to separate into its component colors - red, orange, yellow, green, blue, indigo, | 0/3 |
| Q7 | `e3_off` | 1. Break down your study time into smaller chunks to avoid burnout. 2. Use a planner or calendar to keep track of important dates and deadlines. 3. Take breaks throughout the day to recharge and stay motivated. | 1/3 |
| Q7 | `e3_on` | 1. Break down your study time into manageable chunks by setting aside specific times each day or week to work on assignments and exams. 2. Use a planner or calendar to keep track of important dates and deadlines, and prioritize tasks based on their importance and due date. 3 | 1/3 |
| Q8 | `e3_off` | Photosynthesis is the process by which green plants, algae, and some bacteria convert light energy from the sun into chemical energy in the form of organic compounds such as glucose. | 2/3 |
| Q8 | `e3_on` | Photosynthesis is the process through which plants, algae, and some bacteria convert light energy from the sun into chemical energy in the form of organic compounds, such as glucose. | 3/3 |

## Reading

- **E1 (runtime settings).** n_batch 8 -> 128 cuts time per prompt token by about 7-11 %; 128, 256 and 512 are identical here because every prompt fits in one batch. Threads 4 -> 5 -> 6 give 94 -> 84 -> 75 ms per prompt token; median E 11952 -> 11032 -> 10923. Chosen: n_batch 128, 5 threads (6 is no better on median E and has a worse worst case; one physical core stays free for Piper).
- **E2 (short prompt, last exchange only, max_tokens 60), at 4 threads.** Median E 12211 -> 9556 ms (-22 %), worst 14325 -> 10504. Cost per prompt token unchanged (89 vs 90 ms): the gain is fewer prompt tokens (81 -> 56). The five answers stay correct and complete.
- **E3 (streaming), at 5 threads.** First audio improves only when the reply has more than one sentence:
  - one-sentence replies (Q1, Q2, Q4, Q5): no change (within 100 ms);
  - Q3 (two sentences): 9807 -> 8684 ms;
  - long replies (Q6-8): median E 18440 -> 13852 ms (-25 %), Q6 18401 -> 10000, Q7 22481 -> 14557, Q8 18032 -> 14369; worst E 24265 -> 17295.
- **Gaps between sentences:** 21 gaps, median 0 ms, 2 over 300 ms (439 and 756 ms, both before the last chunk of Q6, waiting for the LLM to finish it).
- **CPU contention:** decode speed on long replies 5.9 -> 5.6 tokens/s (-5 %) while Piper runs alongside. Machine CPU reaches 100 % in both modes. The recorded process peak (10.4 vs 6.2 cores) is a 100 ms sample maximum and exceeds the 5 LLM threads, so the exact figure is not reliable. RAM unchanged (2.73 GB).
- **Limits.** max_tokens 60 cuts long answers mid-sentence in BOTH modes (Q6: 0 of 3 complete); the E2 prompt asks for one or two short sentences, so the long questions push against it. Replies vary between passes (temperature 0.7); one streaming reply (pass 3, Q8) began "is the process ..." without its first word, which is the model's own output as recorded token by token. Q3 was misheard as "tell media short joke" in most passes. E2 itself was measured at 4 threads; `e3_off` is the same configuration at 5 threads with 8 questions.
- **What is left:** after streaming, reading the prompt (B, 5-9 s) is most of the remaining delay.
