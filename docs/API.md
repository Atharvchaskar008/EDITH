# EDITH API

The server is `fusion/api/main.py`. Start it with `.venv\Scripts\python -m uvicorn fusion.api.main:app --port 8000`. Interactive documentation generated from the code is at http://localhost:8000/docs.

All times are UTC ISO 8601. Distances are km, speeds km/s, delta-v m/s. Results always come from the newest completed run; while a run is in progress the previous one stays visible. Cross-origin requests are allowed from `http://localhost:5173`.

## Routes

| Method and path | Returns |
|---|---|
| `POST /run` | Starts a run. Body (all optional): `{"synthetic": false, "quick": false, "mode": null}`. Returns `{"run_id", "already_running"}`. If a run is in progress, returns that run's id with `already_running: true` |
| `GET /run/{run_id}/status` | `{"run_id", "status", "stage", "percent", "log", "error"}`. `status` is `RUNNING`, `DONE` or `FAILED` |
| `GET /monitor` | `{"running", "current_run", "last_run", "run_count", "next_run", "interval_hours", "scheduler_on", "read_only", "story_url"}`. `read_only` is true on a show-only server (`FUSION_READ_ONLY=1`), which presents finished runs and answers 403 to `POST /run`, `POST /events/{id}/plan`, `GET /objects/search` and `GET /objects/{id}/passes` |
| `GET /latest` | The latest run's `run.json`: mode, window, statistics, risk-level counts, duration; plus `any_collision_chance`, the chance that at least one of the run's passes is a collision, from the best-estimate probability of each. 404 before the first run |
| `GET /events?limit=50&level=RED&plan=MANEUVER&fleet=STARLINK` | List of events, highest worst-case probability first. `level`, `plan`, `fleet` and `own_fleet` are optional filters; `fleet` keeps the events that involve a working satellite of that fleet, and `own_fleet=false` leaves out passes between two satellites of one fleet. Each event carries `own_fleet` (true or false). Each event carries `plan_decision` (`MANEUVER`, `MONITOR` or `null` for green events), so a table can mark the passes with a burn planned without a second request |
| `GET /events/{event_id}` | `{"event", "plan", "what_if_plan", "track", "encounter"}` (see below) |
| `GET /events/{event_id}/plan` | The plan for one event. 404 for green events, which have none |
| `POST /events/{event_id}/plan` | Searches now for a burn for one event of the latest run and returns the plan, with `what_if` and `requested_at` added. It takes about 20 seconds against the full catalogue, up to a minute when several burns have to be checked, and blocks until done. A run plans every red event it can, up to `MAX_PLANS_PER_RUN`; this plans one left over at that ceiling, or shows what a burn would take for an event the system only watches. If the system's rules call for a burn, the result stands in for the run's decision in every other route. If they say to watch (the event is not red, or both satellites are of one fleet), a burn is searched for anyway and returned with `what_if: true`; it then appears as `what_if_plan` in the event detail and the decision stays `MONITOR`. 409 while another search is in progress, or for a run made before the full catalogue was kept |
| `GET /fleets` | One row per fleet of working satellites with a close pass in the run, the fleets with most to act on first: `[{"fleet", "satellites", "passes", "red", "amber", "red_to_act_on", "red_own_fleet", "burns", "dv_total_ms", "worst"}]`. A fleet is the leading word of a satellite's name. `red_own_fleet` counts red passes between two satellites of the fleet, which are left to its operator; `red_to_act_on` counts the other red passes. `burns` and `dv_total_ms` cover the burns planned for the fleet's satellites. `worst` is its most dangerous pass: `{"event_id", "other", "pc_max", "miss_distance_km"}`. `satellites` is `null` for a run made before the full catalogue was kept |
| `GET /alerts?since=<run_id>&kind=NEW&severity=CRITICAL&own_fleet=false&limit=20` | Alerts for the latest run, or for all runs after `since`. All parameters are optional. `own_fleet=false` leaves out alerts about passes inside one fleet. `kind` is `NEW`, `ESCALATED`, `DOWNGRADED`, `CLEARED` or `PLAN_READY`; `severity` is `CRITICAL`, `WARNING` or `INFO`. A full-sky run produces hundreds of alerts, so filter them. Written by teammate C's alert engine at the end of each run; empty without that pack |
| `GET /summary` | The latest run's summary from teammate C's pack. 404 without it |
| `GET /objects/search?q=iss&limit=8` | Objects of the latest run whose name contains `q` or whose catalogue number is `q`: `[{"norad_id", "name", "object_type", "operational", "perigee_km", "apogee_km"}]`. Exact and leading matches first |
| `GET /objects/{norad_id}/passes?hours=24&threshold_km=10` | Checks one object now against everything that shares its altitude, using the latest run's orbit data: `{"object", "from", "hours", "threshold_km", "run_id", "objects_screened", "seconds", "passes"}`. `passes` are events in the usual shape, most dangerous first, with the checked object as primary. They are not part of the run, so they have no plan and no entry under `/events`. It takes 6 to 20 seconds, depending on how crowded the object's altitude is, and blocks until done; 409 while another check is in progress |
| `GET /objects/{norad_id}/track?hours=3&step_s=30` | `{"norad_id", "name", "object_type", "start", "step_s", "positions_km"}`, starting now. Only objects in the latest run's `catalog.json` |
| `GET /replay/2009` | `{"run", "events", "plans", "what_if_plans", "predictions", "notes"}`. 404 until the replay is built with `python -m fusion.replay.replay_2009` |
| `GET /validation` | The comparison with CelesTrak SOCRATES, built by `python -m fusion.validation`: `{"generated", "source", "summary", "same_input", "latest_run", "report"}`. `summary` is two sentences for display. `same_input` is our closest-approach code run on the element sets CelesTrak used; `latest_run` matches our latest run against CelesTrak's list. Each has `all_matches`, `same_element_sets` and `newer_element_sets` (`matched` plus median, 90th percentile and maximum of the time, distance and speed differences) and `pairs` (our distance and CelesTrak's, for a scatter chart); `latest_run` also has `coverage`. `report` is a path under `/addons/files/` to the full validation report with its charts. 404 until it is built |
| `GET /proof` | The validation pack's results gathered for the dashboard: `{"celestrak", "esa", "error_growth", "robustness", "report"}`. `celestrak` has `matched`, `median_m`, `median_time_s` and `pairs_m` (CelesTrak's distance and ours, in metres), or is `null` until `python -m fusion.validation` has run. `esa` has the number of warnings compared, the median offset and differences in log10, and the path of its chart. `error_growth.kinds` gives, for each kind of object, `age_days`, `along_track_km` and `after_1_day_km`. `robustness` lists how many of the top 10 passes stay in the top 10 under each changed assumption. 404 without the pack |
| `GET /addons` | `{"hooks", "packs", "validation_report", "alerts_for_latest_run", "briefings_for_latest_run", "cdm_for_latest_run", "replay_2009"}`. The briefing and CDM entries are counts |
| `GET /addons/files/{path}` | A file from `addons/` (json, md, png, txt, csv only) |
| `GET /runs/latest/files/{path}` | A file from the latest run folder: `briefings/<event_id>.briefing.json`, `cdm/<event_id>.cdm.txt`, `summary.json`. Add `?source=replay` for the replay folder |
| `GET /dashboard` | The operator dashboard. Its stylesheet and script are `GET /static/dashboard.css` and `GET /static/dashboard.js` |
| `GET /` | The front page: the dashboard, or on a show-only server the story page, whose button leads to `/dashboard`. A show-only server also answers the story page's own files from the root (`/_nuxt/...`, `/gl/...` and so on), after every route above |
| `GET /landing` | Redirects to the story page: `/` on a show-only server, `http://localhost:3000/` otherwise, or the address in `FUSION_STORY_URL`. The page is a separate site that only starts at the root of a host. `/monitor` gives the same address as `story_url` |

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
- `sigma_source` is `MEASURED` when both objects' uncertainty came from teammate B's measurement of real element-set history, otherwise `MODELLED` (the assumed table).
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
  "other_passes_checked": 2, "other_passes_worsened": 0,
  "return_burn_time": "...", "return_dv_rtn_ms": [0.0, 0.043, 0.0],
  "residual_along_track_km": 5.4,
  "search_grid": { "lead_orbits": [...], "dv_ms": [...],
                   "pc_after": [[...]], "pc_max_after": [[...]], "miss_after_km": [[...]],
                   "radial_30mms_pc_max_after": [...], "cross_track_30mms_pc_max_after": [...] } }
```

- `reason` says why a `MONITOR` plan proposes no burn: `BELOW_THRESHOLD` (an amber event), `NEITHER_CAN_MOVE`, `SAME_FLEET`, `TOO_SOON`, `NO_SAFE_BURN` (every burn tried failed the exact check or would create or worsen another dangerous pass) or `LIMIT` (the run's ceiling of burn searches was reached). It is `null` for other decisions and in runs made before it existed. `/events` gives it as `plan_reason`.
- `decision` is `MANEUVER`, `MONITOR` or `NO_ACTION`. For the last two, only `event_id`, `decision`, `rationale` and the "before" numbers are set; `MONITOR` may also carry `maneuvering_id` and `search_grid`.
- `dv_rtn_ms` is radial, along-track, cross-track in the frame of the object named by `maneuvering_id`. Positive along-track is along the direction of travel.
- `other_passes_checked` counts the other dangerous (amber or red) passes of the moving satellite in the 24 hours after the burn. Each is computed with and without the burn; `other_passes_worsened` counts those whose worst-case probability rises by more than 10%. A recommended burn always has 0 here and 0 in `secondary_conjunctions_created`. Both fields are `null` in runs made before this check existed.
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
