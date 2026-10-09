# Running Fusion

All commands are run from the project root on Windows, using the project's own Python.

## One-time setup

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
```

Fill in `.env` with a free Space-Track login to get the full catalogue, including all debris. Without it the system runs on CelesTrak data only, with partial debris coverage.

## Commands

| What | Command |
|---|---|
| Run the tests | `.venv\Scripts\python -m pytest -q` |
| One run from the terminal | `.venv\Scripts\python -m fusion.pipeline` |
| Start the server | `.venv\Scripts\python -m uvicorn fusion.api.main:app --port 8000` |
| Open the test page | http://localhost:8000 |
| Time the search on real data | `.venv\Scripts\python scripts\measure.py ALL_LEO 12` |
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
| Full sky, 24 hours, 5 burn plans | about 4 minutes |
| Full sky, 72 hours, search only | about 7 minutes |
| Protected set only, 24 hours, 1 burn plan | about 2.5 minutes |

## Where results go

Each run writes `data/runs/<run_id>/`, where the run id is the UTC start time, for example `20261009T0714Z`.

| File | Content |
|---|---|
| `events.json` | Every close pass, most dangerous first |
| `plans.json` | One entry for every red and amber event |
| `catalog.json` | The objects that appear in events, plus the protected satellites and any test object |
| `log.json` | Timestamped progress messages |
| `run.json` | Status, mode, window, statistics, risk-level counts, duration |
| `DONE` | Empty file written last; a failed run has none |

Other locations:

| Path | Content |
|---|---|
| `data/cache/` | Downloaded orbit data, reused for 2 hours |
| `data/replay_2009/` | The 2009 replay run (needs teammate A's pack) |
| `data/validation.json` | Comparison with CelesTrak SOCRATES (needs teammate B's pack) |
| `addons/` | The three teammate packs; never edited by the main project |

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

- Uncertainty is an assumed table until teammate B's measured values are connected.
- Alerts, run history, briefings, the 2009 replay and the SOCRATES comparison come from the teammate packs and are absent until those arrive.
- The radius for Space-Track's "large" size class is a guess of 2 m; that class has no upper limit.
- A burn's safety re-screen covers 24 hours, not the full 72-hour window.
- When two operational satellites meet, the system picks one to move; it has no knowledge of what the other operator plans.
- The test page has only been checked by request, not by hand in a browser.
