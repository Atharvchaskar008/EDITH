# Running Fusion

All commands are run from the project root on Windows, using the project's own Python.

## One-time setup

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pip install -r requirements-addons.txt
copy .env.example .env
```

The second install is only for the teammate packs in `addons/` (risk-trend model, measured sizes). The main system runs without it; the pack features are then switched off and a warning is logged.

Fill in `.env` with a free Space-Track login to get the full catalogue, including all debris. Without it the system runs on CelesTrak data only, with partial debris coverage.

## Commands

| What | Command |
|---|---|
| Run the tests | `.venv\Scripts\python -m pytest -q` |
| One run from the terminal | `.venv\Scripts\python -m fusion.pipeline` |
| Start the server | `.venv\Scripts\python -m uvicorn fusion.api.main:app --port 8000` |
| Open the test page | http://localhost:8000 |
| Build the 2009 collision replay | `.venv\Scripts\python -m fusion.replay.replay_2009` (about 1 minute; needs teammate A's pack) |
| Compare with CelesTrak's own list | `.venv\Scripts\python -m fusion.validation` (downloads 6 MB when its copy is over 12 hours old) |
| Run the trust pack's own tests | `cd addons\b_trust` then `..\..\.venv\Scripts\python -m pytest -q` |
| Time the search on real data | `.venv\Scripts\python scripts\measure.py ALL_LEO 12` |
| Measure compiled libraries against plain Python | `.venv\Scripts\python scripts\why_python.py` |
| Rebuild the sample files | `.venv\Scripts\python scripts\make_fixtures.py` |

Options for `fusion.pipeline`:

| Option | Effect |
|---|---|
| `--synthetic` | Adds one clearly labelled test object set to pass 50 m from an operational satellite |
| `--quick` | 24-hour window instead of 72 |
| `--mode PRIMARIES` | Screens only the protected satellites (Iridium NEXT by default) against the rest |
| `--mode ALL_LEO` | Screens every tracked object against every other (the default) |
| `--hours H` | Any window length |

Environment variables for the server:

| Variable | Effect |
|---|---|
| `FUSION_SCHEDULER=0` | Switches off the automatic run every 6 hours |
| `FUSION_RUNS_DIR=path` | Moves the runs folder |

## How long things take

Measured on a 12-core laptop on 9 October 2026, with 29,686 objects.

| Run | Time |
|---|---|
| Full sky, 24 hours, 5 burn plans, both teammate packs, orbit data already downloaded | 3 minutes (177 s) |
| The same when the orbit data has to be downloaded on a slow connection | 7 minutes (438 s, of which 173 s is the download) |
| Full sky, 72 hours, search only | about 7 minutes |
| Protected set only, 24 hours, 1 burn plan | about 2.5 minutes |
| 2009 replay | about 1 minute |

The teammate packs add about 15 s to a full-sky run: 5 s for the size lookup, 10 s for 1,700 risk-trend predictions, 4 s for alerts, 340 briefings and 340 CDM files.

`scripts\why_python.py`, same laptop, same catalogue:

| What | Result |
|---|---|
| Orbit prediction with the compiled SGP4 library | 1.5 million positions per second on one core, 18 times the same maths in plain Python |
| Finding nearby objects at one moment (440 million pairs) with the KD-tree | 40 ms |
| The same by checking every pair with NumPy | 60 s, same answer |
| One day of search on one core: KD-tree, every pair with NumPy, plain Python | 6 minutes, 145 hours, 32 days |

## Where results go

Each run writes `data/runs/<run_id>/`, where the run id is the UTC start time, for example `20261009T0714Z`.

| File | Content |
|---|---|
| `events.json` | Every close pass, most dangerous first |
| `plans.json` | One entry for every red and amber event |
| `catalog.json` | The objects that appear in events, plus the protected satellites and any test object |
| `log.json` | Timestamped progress messages |
| `run.json` | Status, mode, window, statistics, risk-level counts, duration |
| `alerts.json`, `summary.json` | What changed since the previous run of the same mode and window (teammate C's pack) |
| `briefings/`, `cdm/` | One operator briefing and one standard warning message for every red and amber event (teammate C's pack) |
| `DONE` | Empty file written last; a failed run has none |

After a run with teammate C's pack, each event in `events.json` also carries `first_seen` and its `history` across runs.

Other locations:

| Path | Content |
|---|---|
| `data/cache/` | Downloaded orbit data, reused for 2 hours |
| `data/replay_2009/` | The 2009 replay run, built by the replay command |
| `data/alert_feed.json` | The latest 200 alerts across runs |
| `data/validation.json` | Comparison with CelesTrak SOCRATES, built by `python -m fusion.validation` and refreshed at the end of each run when the pack's copy of CelesTrak's list is under 12 hours old |
| `addons/a_history/`, `addons/b_trust/`, `addons/c_ops/` | The three packs. The main project calls them and never edits A's or C's. `addons/b_trust/out/VALIDATION_REPORT.md` is the page to hand to judges |
| `addons/a_history/cache/satcat.csv` | The size catalogue teammate A's pack downloads on first use (about 3 minutes on a slow connection, then reused) |

Do not start `addons/c_ops/watch.py` yourself: the pipeline already calls the alert engine at the end of every run, and compares only runs of the same mode and window.

## Settings

Every tunable number is in `fusion/config.py`. The ones most likely to be changed:

| Setting | Default | Meaning |
|---|---|---|
| `SCREEN_MODE` | `ALL_LEO` | Full sky or protected set only |
| `PRIMARY_GROUPS` | `iridium-NEXT` | CelesTrak groups that form the protected set |
| `WINDOW_HOURS`, `QUICK_WINDOW_HOURS` | 72, 24 | Look-ahead windows |
| `SCREEN_THRESHOLD_ALL_LEO_KM`, `SCREEN_THRESHOLD_KM` | 1, 5 | Largest miss distance reported in each mode |
| `RED_PC_MAX`, `AMBER_PC_MAX` | 1e-4, 1e-5 | Risk levels, on worst-case probability |
| `TARGET_PC_AFTER`, `TARGET_PC_MAX_AFTER` | 1e-6, 1e-5 | What a burn must achieve |
| `MAX_PLANS_PER_RUN` | 5 | Burn searches per run |
| `VERIFY_HOURS` | 24 | How long a burn is re-screened for new close passes |
| `SCHEDULER_INTERVAL_HOURS` | 6 | Time between automatic runs |
| `RCS_RADIUS_M`, `DEFAULT_RADIUS_M` | 0.15 / 0.4 / 2.0, 5 | Object radius by Space-Track size class, and when unknown |

## Known gaps

- **The measured uncertainty understates the real error.** It comes from comparing element sets of the same object with each other (325,558 pairs, 768 objects), not with true positions. ESA's warnings state an along-track uncertainty for debris about 5 times ours. It cannot measure a brand-new element set, and nothing was measured for objects of unknown type (those keep the assumed table; 61 of 1,731 passes in the first run). This is why ranking uses the worst case over every size of uncertainty.
- **Predictions for satellites that manoeuvre do not last.** Measured along-track error after one day: 0.06 km for dead satellites, 0.15 km for rocket bodies, 0.22 km for debris, 0.37 km for working satellites other than Starlink, 12 km for Starlink. Of CelesTrak's passes from data a day older, 39% of those with one object that cannot manoeuvre are still in our run, 11% of those between two fleets, none of those within one fleet.
- **Same-fleet pairs get no burn plan.** Because of the point above, a red pass between two satellites of one fleet is listed with the reason and left to its operator. Fleets are recognised from the leading word of the name.
- **Agreement with CelesTrak proves the method, not the data.** From the same element sets our closest approach matches CelesTrak's 200 closest conjunctions to a median of 0.35 m. That says nothing about how close public data is to reality.
- **Burns are treated as instantaneous**, and a burn for a satellite whose own position is uncertain by kilometres along its track (Starlink, Kuiper) is planned for radial separation half an orbit before the pass, at up to the 100 mm/s limit of the search.
- **Teammate A's test kit lists one closest approach per pair.** Our search also reports the same pair coming back inside the threshold half an orbit later, and leaves out pairs drifting together at under 0.1 km/s. Both differences are checked in `tests/test_teammate_packs.py`.
- **The risk-trend prediction is experimental.** It was trained on ESA's warnings, which use far more precise orbit data than ours and start two days before the pass. Teammate C's own report says a simple rule beats it at catching events that end above the danger line.
- **Briefing text for "monitor" decisions is generic.** Teammate C's briefing ignores our plan's own reason. The plan card should show our reason.
- **The CDM files label the probability method as `MAXIMUM_PC`**, which is not a standard value, and the value written is our normal probability. They are marked as not certified.
- **In the 2009 replay only 2,897 of teammate A's 5,152 background objects are used.** The others have orbit data dated after the replay time, so they were not public yet.
- **The radius for objects with no measured radar size is still a guess** by size class (2 m for "large").
- A burn's safety re-screen covers 24 hours, not the full 72-hour window.
- When two operational satellites of different operators meet, the system picks one to move; it has no knowledge of what the other operator plans.
