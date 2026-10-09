# Fusion API

The server is `fusion/api/main.py`. Start it with `.venv\Scripts\python -m uvicorn fusion.api.main:app --port 8000`. Interactive documentation generated from the code is at http://localhost:8000/docs.

All times are UTC ISO 8601. Distances are km, speeds km/s, delta-v m/s. Results always come from the newest completed run; while a run is in progress the previous one stays visible. Cross-origin requests are allowed from `http://localhost:5173`.

## Routes

| Method and path | Returns |
|---|---|
| `POST /run` | Starts a run. Body (all optional): `{"synthetic": false, "quick": false, "mode": null}`. Returns `{"run_id", "already_running"}`. If a run is in progress, returns that run's id with `already_running: true` |
| `GET /run/{run_id}/status` | `{"run_id", "status", "stage", "percent", "log", "error"}`. `status` is `RUNNING`, `DONE` or `FAILED` |
| `GET /monitor` | `{"running", "current_run", "last_run", "run_count", "next_run", "interval_hours", "scheduler_on"}` |
| `GET /latest` | The latest run's `run.json`: mode, window, statistics, risk-level counts, duration. 404 before the first run |
| `GET /events?limit=50&level=RED&plan=MANEUVER` | List of events, highest worst-case probability first. `level` and `plan` are optional filters. Each event carries `plan_decision` (`MANEUVER`, `MONITOR` or `null` for green events), so a table can mark the passes with a burn planned without a second request |
| `GET /events/{event_id}` | `{"event", "plan", "what_if_plan", "track", "encounter"}` (see below) |
| `GET /events/{event_id}/plan` | The plan for one event. 404 for green events, which have none |
| `GET /alerts?since=<run_id>&kind=NEW&severity=CRITICAL&limit=20` | Alerts for the latest run, or for all runs after `since`. All parameters are optional. `kind` is `NEW`, `ESCALATED`, `DOWNGRADED`, `CLEARED` or `PLAN_READY`; `severity` is `CRITICAL`, `WARNING` or `INFO`. A full-sky run produces hundreds of alerts, so filter them. Written by teammate C's alert engine at the end of each run; empty without that pack |
| `GET /summary` | The latest run's summary from teammate C's pack. 404 without it |
| `GET /objects/{norad_id}/track?hours=3&step_s=30` | `{"norad_id", "name", "object_type", "start", "step_s", "positions_km"}`, starting now. Only objects in the latest run's `catalog.json` |
| `GET /replay/2009` | `{"run", "events", "plans", "what_if_plans", "predictions", "notes"}`. 404 until the replay is built with `python -m fusion.replay.replay_2009` |
| `GET /validation` | The SOCRATES comparison. 404 until it is built |
| `GET /addons` | `{"hooks", "packs", "validation_report", "alerts_for_latest_run", "briefings_for_latest_run", "cdm_for_latest_run", "replay_2009", "pitch_files"}`. The briefing and CDM entries are counts |
| `GET /addons/files/{path}` | A file from `addons/` (json, md, png, txt, csv only) |
| `GET /runs/latest/files/{path}` | A file from the latest run folder: `briefings/<event_id>.briefing.json`, `cdm/<event_id>.cdm.txt`, `summary.json`. Add `?source=replay` for the replay folder |
| `GET /` | The plain test page |

The event routes accept `?source=replay` to read the 2009 replay folder instead of the latest run.

Briefings and CDM files exist for red and amber events only, and only when teammate C's pack is present. A missing file returns 404.

## Stages in a run's log

`INGEST`, `PROPAGATE`, `SCREEN`, `ASSESS`, `PLAN`, `VERIFY`, `DONE`. Each log entry is `{"time", "stage", "percent", "message"}`, and the messages are written to be shown to a person.

## Event

```json
{ "event_id": "41917-99001-20261009T2054",
  "primary_id": 41917, "secondary_id": 99001,
  "primary_name": "IRIDIUM 106", "secondary_name": "SYNTHETIC TEST OBJECT",
  "tca": "2026-10-09T20:54:11.000004Z",
  "miss_distance_km": 0.05, "relative_speed_kms": 7.5,
  "r_primary_km": [x, y, z], "v_primary_kms": [x, y, z],
  "r_secondary_km": [x, y, z], "v_secondary_kms": [x, y, z],
  "miss_rtn_km": [r, t, n],
  "primary_tle_age_days": 0.7, "secondary_tle_age_days": 0.7,
  "synthetic": true,
  "pc": 6.7e-6, "pc_max": 1.0e-4,
  "sigma_rtn_primary_km": [r, t, n], "sigma_rtn_secondary_km": [r, t, n],
  "sigma_source": "MODELLED", "hbr_km": 0.003,
  "risk_level": "RED", "pc_predicted_final": null,
  "first_seen": null, "history": [] }
```

- `synthetic: true` marks the test object; always label it on screen.
- `pc_max` is the worst-case probability and decides `risk_level`: RED at 1e-4 or more, AMBER at 1e-5 or more.
- `first_seen` and `history` are filled by teammate C's alert engine at the end of each run; `history` entries are `{"run_id", "pc_max", "miss_distance_km"}`, oldest first. Only runs of the same mode and window are compared.
- `pc_predicted_final` is a probability: where teammate C's model, trained on ESA's warning messages, expects the risk to end up. It is `null` without that pack. Treat it as a trend estimate, not a second opinion on `pc`.
- An event seen in an earlier run keeps that run's `event_id`, even if its closest approach has moved into a different minute.

## Plan

```json
{ "event_id": "...", "decision": "MANEUVER",
  "rationale": "SYNTHETIC TEST OBJECT cannot manoeuvre, so IRIDIUM 106 moves. Smallest safe burn found: 43 mm/s against the direction of travel, 7.5 orbits before the pass.",
  "maneuvering_id": 41917,
  "burn_time": "2026-10-09T08:21:00Z", "lead_time_orbits": 7.5,
  "dv_rtn_ms": [0.0, -0.043, 0.0], "dv_magnitude_ms": 0.043,
  "miss_before_km": 0.05, "miss_after_km": 5.1,
  "pc_before": 6.7e-6, "pc_after": 8.9e-7,
  "pc_max_before": 1.0e-4, "pc_max_after": 2.9e-6,
  "secondary_conjunctions_created": 0,
  "return_burn_time": "...", "return_dv_rtn_ms": [0.0, 0.043, 0.0],
  "residual_along_track_km": 5.4,
  "search_grid": { "lead_orbits": [...], "dv_ms": [...],
                   "pc_after": [[...]], "pc_max_after": [[...]], "miss_after_km": [[...]],
                   "radial_30mms_pc_max_after": [...], "cross_track_30mms_pc_max_after": [...] } }
```

- `decision` is `MANEUVER`, `MONITOR` or `NO_ACTION`. For the last two, only `event_id`, `decision`, `rationale` and the "before" numbers are set; `MONITOR` may also carry `maneuvering_id` and `search_grid`.
- `dv_rtn_ms` is radial, along-track, cross-track in the frame of the object named by `maneuvering_id`. Positive along-track is along the direction of travel.
- `search_grid` matrices are indexed `[dv][lead]`: one row per value in `dv_ms` (signed, along-track), one column per value in `lead_orbits`. Use `pc_max_after` for the decision map.

## Event detail

`track`:

```json
{ "times_s": [-600, -595, ..., 600],
  "primary_km": [[x, y, z], ...], "secondary_km": [[x, y, z], ...],
  "maneuvered_km": [[x, y, z], ...], "maneuvering_id": 41917, "what_if": false }
```

Positions are TEME, every 5 s for 10 minutes either side of closest approach. `maneuvered_km` is the burning object's new path and is `null` when no burn is planned.

`what_if_plan` is `null` except in the 2009 replay. There, the system's own decision for the collision pair is not a burn, so the burn it would have recommended is stored separately and marked as a what-if. When the plan is not a burn and a what-if exists, `maneuvered_km` and `miss_after_km` show the what-if burn and `track.what_if` is `true`. Always label it on screen as a what-if.

`encounter`:

```json
{ "miss_km": [0.05, 0.0], "covariance_km2": [[a, b], [b, c]],
  "hbr_km": 0.003, "miss_after_km": [0.22, -5.1] }
```

This is the plane perpendicular to the relative velocity, with the primary at the origin and the first axis along the miss vector. `miss_km` is where the secondary passes; `covariance_km2` is the combined position uncertainty centred there; `hbr_km` is the radius of the collision disc at the origin; `miss_after_km` is where the secondary passes after the burn, in the same axes. It comes from the same code as the probability, so a picture drawn from it matches the numbers.
