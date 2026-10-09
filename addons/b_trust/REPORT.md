# Trust pack: final report

Built on 9 October 2026. All eight tasks are done and none is blocked. Details and deviations from the brief are in `PROGRESS.md`.

## 1. Tasks

| Task | Topic | Status | Result |
|---|---|---|---|
| 1 | Reference probability calculator | DONE | Checked against a closed form, random sampling and a direct double integral; 30 reference cases; the main engine agrees on all 30 within 2% |
| 2 | Orbit history sample | DONE | 779 objects of six kinds, 30,687 element sets |
| 3 | Measured element-set error | DONE | 325,558 pairs from 768 objects; along-track error after one day from 0.06 km (dead satellites) to 12 km (Starlink) |
| 4 | Check against ESA data | DONE | 20,000 real warnings: no offset from ESA's probability; median difference 0.010 in log10 for warnings above 1e-6 |
| 5 | Validation against SOCRATES | DONE | CelesTrak's 200 closest conjunctions recomputed from the same element sets: median difference 0.35 m |
| 6 | Robustness study | DONE | Ranking by worst case is unaffected by the size of the uncertainty; object size moves 16 to 38 of 175 passes across a level |
| 7 | Validation report and packaging | DONE | `out/VALIDATION_REPORT.md`, generated from the JSON results; `README.md` |
| 8 | Final report | DONE | This file |

## 2. Key numbers

| Number | Value | File |
|---|---|---|
| Probability against random sampling, largest deviation on 9 cases | 2.0 standard errors | `out/pc_monte_carlo_check.json` |
| Reference cases for other implementations | 30 | `out/pc_test_cases.json` |
| Objects and element sets in the history sample | 779 and 30,687 | `out/history_sample.json` |
| Pairs of element sets measured, and objects | 325,558 and 768 | `out/tle_error.json` |
| Along-track error after 1 day: dead satellites, rocket bodies, debris | 0.06, 0.15, 0.22 km | `out/tle_error.json`, `out/tle_error_summary.md` |
| Along-track error after 1 day: working satellites other than Starlink, Starlink | 0.37, 12.3 km | same |
| Starlink along-track error after 3 days | 76.8 km | same |
| ESA warnings compared | 20,000 of 95,394 usable | `out/esa_pc_check.json` |
| Median offset from ESA's probability (log10) | −0.001 | same |
| Median absolute difference, all warnings; warnings above 1e-6 | 0.125; 0.010 | same |
| Share within 0.1 in log10, warnings above 1e-6 | 77% | same |
| Worst case against ESA's maximum risk: median difference, correlation | 0.017; 0.976 | same |
| SOCRATES conjunctions recomputed and matched | 200 of 200 | `out/socrates_validation.json` |
| Distance difference: median, 90%, largest | 0.35 m, 1.1 m, 25 m | same |
| Time difference: median, 90% | 0.4 ms, 0.13 s | same |
| Rank agreement of maximum probability with SOCRATES: its shape of uncertainty; our measured one | 0.65; −0.04 | same |
| Top 10 kept when uncertainty is halved or doubled | 10 of 10 | `out/robustness.json` |
| Passes changing level when object size is 5 m or 20 m instead of 10 m | 38 and 16 of 175 | same |
| Rank agreement between closeness alone and worst case | 0.31 | same |

## 3. Files in `out/`

| File | What it is |
|---|---|
| `VALIDATION_REPORT.md` | One page for judges, generated from the JSON files |
| `pc_test_cases.json` | 30 reference cases with inputs and expected `pc`, `pc_max` |
| `pc_monte_carlo_check.json` | Probability against random sampling, case by case |
| `history_sample.json` | Element-set history of the 779 sampled objects |
| `tle_error.json` | Measured error per object, per kind of object and per type |
| `tle_error_growth.png`, `tle_error_summary.md` | Chart and table of the measured error |
| `esa_pc_check.json`, `esa_pc_check.png` | Our probability against ESA's on real warnings |
| `esa_sigma_stats.json` | ESA's stated uncertainty by object type and days to the pass |
| `socrates_validation.json`, `socrates_validation.png` | The recomputation of CelesTrak's closest conjunctions, with the element sets used |
| `robustness.json`, `robustness.png`, `robustness_notes.md` | Effect of each assumption on the ranking |

## 4. Known gaps

- The uncertainty is measured between element sets of the same object, not against true positions. It understates the real error; ESA's stated along-track uncertainty for debris at one to two days is about 5 times ours. It cannot measure a brand-new element set at all.
- Nothing was measured for objects of unknown type; the main system keeps its assumed table for those (61 of 1,731 passes in the first run with this pack).
- The ESA comparison is tight where it matters and loose in the far tail: one in ten of all warnings differs by more than 2.7 in log10. The file does not show why.
- The reading of ESA's size columns (half the sum of the two spans) was inferred from the data: it removes the offset exactly, where the full sum leaves a factor of 4.
- The maximum probability published by SOCRATES could not be reproduced, because its object sizes are not documented.
- 16 days of history were used, not 45; the manoeuvre filter drops 44% of Iridium NEXT pairs; SOCRATES was downloaded up to 2.7 km only. Reasons are in `PROGRESS.md`.

## 5. Tests

Command, from this folder: `..\..\.venv\Scripts\python -m pytest -q`

Last output:

```
......................................................                   [100%]
54 passed in 8.57s
```
