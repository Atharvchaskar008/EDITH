# Architecture

EDITH is a batch pipeline with a thin web layer on top. Every run reads public orbit data, produces one self-contained folder of results, and the server only ever reads finished folders. There is no database and no shared mutable state between a run and the server.

## Components

| Component | Path | Responsibility |
|---|---|---|
| Configuration | `fusion/config.py` | Every tunable number and every path, in one place |
| Data model | `fusion/contracts.py` | Pydantic models for objects, events, plans and alerts |
| Ingest | `fusion/core/ingest.py`, `fusion/core/spacetrack.py` | Download, merge, filter and cache the catalogue |
| Propagation | `fusion/core/propagate.py`, `fusion/core/sat.py` | Vectorised SGP4 for the whole catalogue |
| Screening | `fusion/core/screen.py`, `fusion/core/refine.py` | Coarse neighbour search, then exact closest approach |
| Risk | `fusion/risk/covariance.py`, `fusion/risk/pc.py` | Position uncertainty, collision probability, worst case, risk level |
| Manoeuvre | `fusion/maneuver/planner.py`, `orbit.py`, `verify.py` | Burn search, burned-orbit model, safety re-screen, return burn |
| Pipeline | `fusion/pipeline.py` | Runs the stages in order and writes the run folder |
| Add-on hooks | `fusion/addons.py` | Optional calls into the packs in `addons/`, each with a fallback |
| Validation | `fusion/validation.py` | Comparison of our results with CelesTrak SOCRATES |
| Replay | `fusion/replay/replay_2009.py` | The 2009 Iridium 33 / Cosmos 2251 case, run through the same pipeline |
| Scheduler | `fusion/monitor/scheduler.py` | Starts a run every 6 hours, never overlapping |
| API and dashboard | `fusion/api/main.py`, `fusion/api/static/index.html` | FastAPI routes over the latest finished run, and the operator dashboard |

## Data flow

1. **Ingest.** CelesTrak groups and the Space-Track bulk catalogue are merged by catalogue number. Element sets older than 14 days and objects that never come below 2,000 km are dropped. Downloads are cached for 2 hours.
2. **Propagate.** SGP4 gives position and velocity for every object on a 10-second grid, in time chunks that bound memory.
3. **Screen.** At each time step a KD-tree lists pairs within `threshold + 15.5 km/s × step / 2`. A straight-line estimate keeps only pairs whose closest approach falls inside that step. Survivors are refined with a bounded minimiser. Time blocks of 30 minutes are spread across worker processes; results are sorted, so the output does not depend on the worker count.
4. **Assess.** Each object gets a position uncertainty (measured, per kind of object and data age, when the trust pack is present; an assumed table otherwise). The combined covariance is projected onto the plane perpendicular to the relative velocity and integrated over the hard-body disc. The worst case over every scaling of the covariance sets the risk level.
5. **Plan.** For red events, a grid of burn times and along-track sizes is evaluated with a linear response model; the smallest burn meeting the safety targets is recomputed exactly.
6. **Verify.** The burned orbit is screened against the whole catalogue for 24 hours. Every amber or red pass found is computed again without the burn. A burn that creates a dangerous pass, or raises the worst-case probability of one the satellite already had by more than 10%, is rejected and the next candidate tried. A return burn a whole number of orbits later restores the original orbit.
7. **Publish.** Result files are written through temporary names, add-on outputs are attached, and an empty `DONE` file is written last.

## Run folder

`data/runs/<YYYYMMDDTHHMMZ>/`

| File | Content |
|---|---|
| `run.json` | Mode, window, statistics, risk-level counts, duration |
| `events.json` | Every close pass, with geometry, probability, risk level and history |
| `plans.json` | One decision per red and amber event, including the full burn search grid |
| `catalog.json` | The objects that appear in events |
| `catalog_full.json.gz` | Every object of the run, kept so a burn can be planned later for any event |
| `requested_plans.json` | Burn plans asked for after the run; the run's own files are not changed |
| `log.json` | Timestamped, human-readable progress messages |
| `alerts.json`, `summary.json`, `briefings/`, `cdm/` | Add-on outputs, when the operations pack is present |
| `DONE` | Marks the folder complete; the server ignores folders without it |

## Design decisions

| Decision | Reason |
|---|---|
| SGP4 for all positions | Public element sets are mean elements fitted with SGP4 and are only valid with it |
| Burn modelled as a difference | A two-body-plus-J2 integration is run with and without the burn, and the difference is added to the SGP4 path, so the unburned case reproduces SGP4 exactly |
| Rank by worst-case probability | Public data carries no covariance; the worst case does not depend on the assumed size of the uncertainty |
| Screen every object against every other | Debris-on-debris and dead-on-dead passes are found too; a protected-set mode exists for faster runs |
| 1 km threshold in full-sky mode | A 5 km threshold yields about 2,300 passes an hour, too many to act on |
| Burns go first to passes where one object cannot move | A burn is the only remedy there, and predictions for non-manoeuvring objects are the stable ones |
| No burn plan for two satellites of one fleet | Measured along-track error for Starlink is about 12 km after one day; such predictions do not survive new data |
| Files, not a database | A run is an immutable folder; packs and the server only need to read files |
| Processes, not threads | The search parallelises cleanly over time blocks; the catalogue is serialised once and shared with workers |

## Extension points

The packs in `addons/` are standalone folders. The main system calls them through `fusion/addons.py`, runs each call with the pack's folder as the working directory, and falls back to built-in behaviour if a pack is absent or fails.

| Hook | Pack function | Fallback |
|---|---|---|
| Object size and status | `a_history/enrich.py: enrich_catalog` | Size class from Space-Track |
| Position uncertainty | `b_trust/tle_error.py: measured_sigma` | Assumed table in `config.py` |
| Risk-trend prediction | `c_ops/predict.py: predict_final_risk` | Field left empty |
| Alerts, history, summary | `c_ops/watch.py: process_single_run` | No alerts |
| Briefings and CDM files | `c_ops/briefing.py`, `c_ops/cdm_export.py` | None written |

Alerts compare a run only with earlier runs of the same mode and window. If the alert step damages `events.json`, the file is restored from a backup taken before the call.

## Failure handling

- A failed download is retried, then fails the run with a readable message; stale data is never used silently.
- A failed stage records its error in `run.json` and `log.json` and leaves no `DONE` file, so the previous run stays visible.
- An element set that SGP4 rejects becomes missing values and is skipped, not a crash.
- Only one run executes at a time; a second request returns the identifier of the run in progress.

## Testing

`tests/` runs with the add-on folder disabled, so it checks the main system by itself. `tests/test_teammate_packs.py` uses the real packs and skips where a pack or library is missing. The trust pack has its own suite in `addons/b_trust/`.
