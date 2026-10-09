# Fusion: contracts for the main project

This is Atharv's reference for the main project: data shapes, function signatures and API routes. `ARCHITECTURE.md` explains the overall design. The three teammate files are self-contained and repeat the shapes they need, so teammates do not need this file. If a shape changes here, the same change must be made in the teammate files.

## What we are building

An autonomous collision-avoidance system for a satellite constellation. Input is public TLE data from CelesTrak. Output is a ranked list of upcoming close approaches with collision probability, a verified avoidance burn for the riskiest one, and alerts when the picture changes.

**Our story:** in 2009 Iridium 33 was destroyed by the dead satellite Cosmos 2251. We protect today's Iridium NEXT constellation (about 80 satellites at 780 km) against the whole catalogue, including the debris from that collision.

- **Primaries** (satellites we protect and can manoeuvre): a configurable list of CelesTrak groups, `PRIMARY_GROUPS` in `fusion/config.py`. It can be one constellation (`iridium-NEXT`), several (`oneweb`, `starlink`, ...), or every active LEO satellite. Development starts with `iridium-NEXT` because it is fast; the set is widened once the run time is measured. Nothing in the code may assume Iridium.
- **Secondaries** (everything else): groups `active`, `cosmos-2251-debris`, `iridium-33-debris`, `fengyun-1c-debris`
- **Look-ahead window:** 72 hours from the run time
- **Monitoring:** the full pipeline re-runs every 6 hours

## Conventions (non-negotiable)

| Thing | Convention |
|---|---|
| Language | Python 3.11, type hints, `numpy` arrays for bulk data |
| Frame | TEME (what SGP4 returns). No conversion between modules |
| Units | km, km/s, seconds. Delta-v is reported in m/s in the final output only |
| Time | UTC, ISO 8601 strings in JSON (`2026-10-09T14:03:22Z`), `datetime` with tzinfo in code |
| Object id | NORAD catalogue number as `int` |
| RTN axes | R = position direction, N = orbit normal (r × v), T = N × R (roughly along velocity) |
| Models | `pydantic` v2 models in `fusion/contracts.py`, written by Atharv |
| Config | All thresholds and tunable numbers in `fusion/config.py`, nowhere else |

## Repo layout

Everything outside `addons/` is Atharv's.

```
fusion/
  contracts.py          pydantic models below
  config.py             thresholds, window, step sizes
  addons.py             optional hooks into the teammate packs, each with a fallback
  pipeline.py           run_pipeline(): all stages, writes the run folder
  core/                 ingest.py, propagate.py, screen.py, refine.py
  risk/                 covariance.py, pc.py
  maneuver/             planner.py, verify.py
  monitor/              scheduler.py
  replay/               replay_2009.py (runs teammate A's 2009 data through the pipeline)
  api/                  main.py (FastAPI)
dashboard/              React + CesiumJS
addons/a_history/       teammate A's pack (replay depth, sizes, history, test kit)
addons/b_trust/         teammate B's pack (measured uncertainty, validations)
addons/c_ops/           teammate C's pack (alert feed, summaries, briefings, prediction, pitch)
data/cache/             raw downloads, git-ignored
data/runs/<run_id>/     one folder per run: catalog.json, events.json, plans.json, log.json, DONE (C's watcher adds alerts.json, summary.json)
data/fixtures/          sample JSON matching the contracts
tests/                  one file per module
```

`run_id` is the run start time, for example `20261009T1200Z`.

## Data contracts

### `SpaceObject`
```json
{ "norad_id": 43070, "name": "IRIDIUM 106", "object_type": "PAYLOAD",
  "tle_line1": "...", "tle_line2": "...", "epoch": "2026-10-09T03:11:05Z",
  "perigee_km": 776.2, "apogee_km": 779.8, "is_primary": true,
  "operational": true, "radius_m": 2.0 }
```
- `object_type` is one of `PAYLOAD`, `DEBRIS`, `ROCKET_BODY`, `UNKNOWN`.
- `operational` and `radius_m` come from SATCAT where available. Defaults: `operational = is_primary`, `radius_m = 5.0`.

### `ConjunctionEvent` (Atharv's engine fills geometry and risk, C fills the history)
```json
{ "event_id": "43070-34427-20261011T0412",
  "primary_id": 43070, "secondary_id": 34427,
  "tca": "2026-10-11T04:12:37Z",
  "miss_distance_km": 0.412,
  "relative_speed_kms": 14.71,
  "r_primary_km": [x, y, z], "v_primary_kms": [x, y, z],
  "r_secondary_km": [x, y, z], "v_secondary_kms": [x, y, z],
  "miss_rtn_km": [r, t, n],
  "primary_tle_age_days": 0.6, "secondary_tle_age_days": 2.3,

  "pc": 3.1e-5, "pc_max": 4.4e-4,
  "sigma_rtn_primary_km": [r, t, n], "sigma_rtn_secondary_km": [r, t, n],
  "sigma_source": "MEASURED",
  "hbr_km": 0.01,
  "risk_level": "RED",
  "pc_predicted_final": 5.0e-5,

  "first_seen": "2026-10-09T12:00:00Z",
  "history": [ { "run_id": "20261009T1200Z", "pc_max": 2.0e-4, "miss_distance_km": 0.63 } ] }
```
- State vectors are at TCA, in TEME.
- `miss_rtn_km` is the secondary's position relative to the primary, in the primary's RTN frame.
- `hbr_km` is the sum of the two objects' `radius_m`, in km.
- `sigma_source` is `MEASURED` (from TLE history) or `MODELLED` (from the fallback table).
- `risk_level`: `RED` if `pc_max` ≥ 1e-4, `AMBER` if ≥ 1e-5, otherwise `GREEN`.
- `pc_predicted_final` comes from C's ML model and may be `null`.
- **Same event across runs:** same pair of ids and TCA within 10 minutes. The event keeps the `event_id` from the run that first saw it.

### `ManeuverPlan` (Atharv)
```json
{ "event_id": "43070-34427-20261011T0412",
  "decision": "MANEUVER",
  "burn_time": "2026-10-11T01:42:00Z",
  "lead_time_orbits": 1.5,
  "dv_rtn_ms": [0.0, 0.034, 0.0],
  "dv_magnitude_ms": 0.034,
  "miss_before_km": 0.412, "miss_after_km": 2.96,
  "pc_before": 3.1e-5, "pc_after": 2.0e-8,
  "secondary_conjunctions_created": 0,
  "return_burn_time": "2026-10-11T05:53:00Z",
  "return_dv_rtn_ms": [0.0, -0.034, 0.0],
  "residual_along_track_km": 0.9,
  "search_grid": { "lead_orbits": [...], "dv_ms": [...], "pc_after": [[...]] } }
```
`decision` is one of `MANEUVER`, `MONITOR`, `NO_ACTION`.

### `Alert`
```json
{ "alert_id": "20261009T1800Z-43070-34427",
  "run_id": "20261009T1800Z",
  "event_id": "43070-34427-20261011T0412",
  "kind": "ESCALATED",
  "from_level": "AMBER", "to_level": "RED",
  "message": "IRIDIUM 106 vs COSMOS 2251 DEB: risk rose from AMBER to RED, closest approach in 34 h" }
```
`kind` is one of `NEW` (first seen at AMBER or RED), `ESCALATED`, `DOWNGRADED`, `CLEARED` (no longer within the threshold), `PLAN_READY`.

## Function signatures between modules

```python
# spine (Atharv)
load_catalog(use_cache: bool = True) -> list[SpaceObject]
propagate(objs: list[SpaceObject], times: np.ndarray) -> tuple[np.ndarray, np.ndarray]
    # times: seconds from t0. Returns r[n_obj, n_t, 3] km and v[n_obj, n_t, 3] km/s, NaN where SGP4 fails
screen(catalog: list[SpaceObject], t0: datetime, hours: float = 72,
       threshold_km: float = 5.0) -> list[ConjunctionEvent]   # geometry fields only
sigma_rtn(obj: SpaceObject, tle_age_days: float) -> tuple[np.ndarray, str]   # ([3] km, sigma_source)
pc_2d(r1, v1, C1, r2, v2, C2, hbr_km) -> tuple[float, float]            # (pc, pc_max); C are 3x3 in TEME
assess(event: ConjunctionEvent, catalog: dict[int, SpaceObject]) -> ConjunctionEvent   # fills risk fields
plan(event: ConjunctionEvent, catalog: list[SpaceObject]) -> ManeuverPlan
run_pipeline(t0: datetime | None = None, on_progress=None) -> str       # returns run_id
    # on_progress(stage: str, percent: float, message: str)


# Alerts, event history, run summaries, the SOCRATES comparison and the 2009 data are produced
# by the teammate packs, not by the main project. The main project only reads their output files.

# add-on hooks in fusion/addons.py: used if the teammate pack is present, skipped silently if not
enrich_catalog(objs: list[dict]) -> list[dict]                           # A: addons/a_history/enrich.py
measured_sigma(norad_id: int, object_type: str, tle_age_days: float) -> np.ndarray | None   # B: addons/b_trust/tle_error.py
predict_final_risk(event: dict) -> float | None                          # C: addons/c_ops/predict.py
```
The add-on functions take and return plain dicts in the JSON shapes above, not pydantic objects.

## API

| Route | Returns |
|---|---|
| `POST /run` | Starts the full pipeline, returns the run id |
| `GET /run/{id}/status` | Stage name, percent, log lines (for the autonomy timeline) |
| `GET /monitor` | Scheduler state: last run, next run, number of runs so far |
| `GET /events?limit=50` | `ConjunctionEvent[]` from the latest run, sorted by `pc_max` descending |
| `GET /events/{event_id}` | One event plus ±10 minutes of both trajectories around TCA |
| `GET /events/{event_id}/plan` | `ManeuverPlan` |
| `GET /alerts?since=<run_id>` | `Alert[]`, newest first |
| `GET /objects/{norad_id}/track?hours=3` | Positions for drawing an orbit |
| `GET /validation` | Our events versus SOCRATES for the same pairs |
| `GET /replay/2009` | The same shapes as above for the Iridium 33 / Cosmos 2251 replay |

The system always runs live on fresh data. While a run is in progress, every route serves the previous completed run.

## Rules for working with the AI assistant

- Ask for tests alongside every function. A function without a passing test is not done.
- Do not let it invent orbital data, column names or library functions. If it is unsure, make it check the library docs or load the file and print the columns.
- If a number looks wrong (for example a miss distance of 0 km, or a probability above 1e-2), find the cause instead of tuning it away.
