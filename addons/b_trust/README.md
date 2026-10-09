# Trust pack: measured uncertainty and independent validation

This pack answers one question about the main system: how do you know your numbers are right? It is standalone: nothing here imports code from outside this folder, and the main system only reads the files below.

## What it contains

| Module | What it does |
|---|---|
| `pc_reference.py` | Reference collision-probability calculator, checked three ways (closed form, random sampling, direct double integral) |
| `make_pc_cases.py` | Writes 30 reference cases for anyone's probability code |
| `spacetrack.py` | Small Space-Track client: one login, rate limit of 20 a minute and 200 an hour, every answer cached |
| `make_history.py` | Downloads recent element sets for a sample of every kind of object |
| `tle_error.py` | Measures how wrong a public element set is at each age; `measured_sigma` is what the main system calls |
| `esa_check.py` | Recomputes the probability of 20,000 real ESA warnings and compares with ESA's own |
| `socrates.py`, `validate.py` | Load CelesTrak SOCRATES; compare any list of events with it |
| `make_socrates_validation.py` | Recomputes CelesTrak's 200 closest conjunctions from the same element sets |
| `robustness.py` | How much the ranking depends on each assumption |
| `make_report.py` | Builds `out/VALIDATION_REPORT.md` from the JSON results |
| `charts.py` | One look and one colour order for every chart |

## Files in `out/`

| File | What it is | How the main system uses it |
|---|---|---|
| `VALIDATION_REPORT.md` | One page for judges: what was checked, the numbers, the limits | Shown in the dashboard's validation tab (`/addons/files/b_trust/out/VALIDATION_REPORT.md`) |
| `pc_test_cases.json` | 30 cases with full inputs and reference `pc` and `pc_max` | `tests/test_pc.py` checks the main engine against it to 2% |
| `pc_monte_carlo_check.json` | Calculated probability against random sampling on 9 cases | Quoted in the report |
| `tle_error.json` | Measured error by object, by kind of object and by type, per one-day age bin | Read by `measured_sigma`; replaces the assumed uncertainty |
| `tle_error_growth.png`, `tle_error_summary.md` | Chart and table of the same | Pitch and validation tab |
| `history_sample.json` | The element sets the measurement was made from (779 objects) | Not used directly |
| `esa_pc_check.json`, `esa_pc_check.png` | Our probability against ESA's on 20,000 real warnings | Validation tab |
| `esa_sigma_stats.json` | ESA's operator-grade uncertainty by object type and days to the pass | For comparison with ours |
| `socrates_validation.json`, `socrates_validation.png` | CelesTrak's 200 closest conjunctions recomputed, with the element sets used | `python -m fusion.validation` reruns the main engine on the same element sets |
| `robustness.json`, `robustness.png`, `robustness_notes.md` | Effect of each assumption on the ranking | Pitch |

## Usage

```python
# 1. probability of one encounter: states in km and km/s (TEME), sigmas in km along R, T, N
from pc_reference import cov_rtn_to_teme, pc_event
C1 = cov_rtn_to_teme([0.1, 1.0, 0.1], r1, v1)
C2 = cov_rtn_to_teme([0.1, 2.0, 0.1], r2, v2)
pc, pc_max = pc_event(r1, v1, C1, r2, v2, C2, hbr_km=0.01)
```

```python
# 2. measured 1-sigma error (km along R, T, N) of an element set of a given age
from tle_error import measured_sigma
measured_sigma(25544, "PAYLOAD", 1.5)                                   # an object in the sample: its own measurement
measured_sigma(99999, "PAYLOAD", 1.5, name="STARLINK-1", operational=True)  # otherwise its kind of object
measured_sigma(99999, "DEBRIS", 1.5)                                    # or just its type
# returns None when nothing was measured for that type
```

```python
# 3. compare any events (the project's event JSON shape) with CelesTrak SOCRATES
from socrates import load_socrates
from validate import compare
result = compare(events, load_socrates(), window=("2026-10-09T10:00:00Z", "2026-10-10T10:00:00Z"), max_range_km=1.0)
print(result["all_matches"], result["same_element_sets"], result["coverage"])
```

## Rebuilding everything

```
python make_pc_cases.py
python make_history.py              # Space-Track login needed; about 10 MB
python tle_error.py
python esa_check.py                 # needs ./esa/train_data.csv (221 MB download from Zenodo record 4463683)
python make_socrates_validation.py  # Space-Track login needed
python robustness.py
python make_report.py
python -m pytest -q
```

Use the project's Python (`..\..\.venv\Scripts\python`) with `requirements-addons.txt` installed. The Space-Track login is read from `.env` in this folder, or from the project root's `.env` if this folder has none.

## Known gaps

- **The uncertainty is measured between element sets, not against true positions.** It understates the real error, and it says nothing about a brand-new element set: below half a day of age `measured_sigma` returns the half-day value. ESA's warnings state a median along-track uncertainty for debris about 5 times ours at one to two days.
- **The error grows faster than a straight line.** The brief asked for a straight-line fit; it is stored (`sigma0_km`, `rate_km_per_day`) but `measured_sigma` reads the measured value for each age from the bins, because the straight line overstates Starlink's error at one to three days by about a factor of three.
- **Error size is taken about zero, not about the median.** For Starlink the older element set is consistently ahead by about 10 km after a day; a spread about the median would hide that.
- **The manoeuvre filter drops 44% of Iridium NEXT pairs.** Those satellites change orbit in small steady steps, so a threshold of five times the median step flags many. The filter is applied as specified.
- **The history covers 16 days, not 45** (30 days for the objects reused from teammate A's file), to keep the download small on a slow connection. Seven-day age gaps are fully covered.
- **No objects of unknown type were sampled,** so `measured_sigma` returns None for them and the main system falls back to its assumed table.
- **The ESA comparison has a long tail.** Over all warnings, one in ten of our values differs from ESA's by more than a factor of about 500, in both directions; almost all of those are warnings ESA itself rates as negligible. The file does not show how ESA treated those cases.
- **SOCRATES was downloaded only as far as 2.7 km** (the first 6 MB of a 21 MB file sorted by distance).
- **The object-size reading for ESA's data (half the sum of the two spans) was chosen because it removes the offset**; the dataset's description does not state it.
