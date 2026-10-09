# Handoff: where the project stands and what to do next

This file is for whichever AI assistant continues the build (Claude or Gemini). Read it first, then `docs/CONTRACTS.md`, then the next unfinished prompt in `docs/harness_ATHARV.md`. Update the "Progress" section at the end of every working session.

## The project in five lines

- Hackathon problem: from public TLE orbit data, predict close approaches between objects in low Earth orbit, rank them by collision probability, and recommend an avoidance burn (timing and delta-v direction) for at least one event.
- We build "Fusion": download orbits from CelesTrak, propagate with SGP4, find close passes, compute collision probability, plan and verify a burn, re-run every 6 hours, show it on a dashboard.
- Atharv builds this whole main project. Three teammates build optional add-on packs in `addons/` (never edit that folder). The main project must run when `addons/` is empty.
- Backend first (12 hours, prompts 1–12 in `docs/harness_ATHARV.md`), then frontend (about 6 hours, prompts D1–D6 in the same file).
- Repository: https://github.com/Atharvchaskar008/Fusion-skn.git, branch `main`.

## Decisions already made (do not reopen)

| Topic | Decision |
|---|---|
| Coverage | The goal is all of low Earth orbit: every tracked object against every other (`SCREEN_MODE = "ALL_LEO"` in `fusion/config.py`), so every close pass is found, including debris against debris. Burns are only planned for operational satellites; pairs where neither can move get a warning only. `SCREEN_MODE = "PRIMARIES"` screens just the `PRIMARY_GROUPS` list against the rest and is the fast mode for development and tests. Build the screen so both modes share one code path (in `ALL_LEO` use `cKDTree.query_pairs` on one tree). Measure the full run time in prompt 3; if it is too long for a demo, use the 24-hour quick window or multiprocessing over time chunks, do not shrink the coverage silently. No code may assume Iridium |
| Full debris catalogue | CelesTrak's `active` group covers active satellites; its debris groups cover only a few named clouds. Every tracked debris object and rocket body needs the full catalogue from Space-Track (`gp` class, free account, one bulk request per run at most once an hour; check their API docs and limits before coding). Until Atharv provides a login in `.env`, run with the CelesTrak groups and say plainly that debris coverage is partial |
| Data source | CelesTrak GP data in JSON (OMM) form, built into `Satrec` with `sgp4.omm`. Same elements as TLEs; needed because catalogue numbers above 99999 do not fit TLE text |
| Frame and units | TEME, km, km/s, UTC everywhere. No frame conversions. Delta-v in m/s only in outputs |
| RTN frame | R = unit position, N = unit(r × v), T = N × R. Helpers in `fusion/frames.py` |
| Screening | Altitude-band filter → KD-tree every 10 s with radius `threshold + 15.5 × dt / 2` → exact closest approach with `minimize_scalar` |
| Uncertainty | Assumed table in config (sigma0 + rate × data age); teammate B's measured values replace it through a hook when present |
| Probability | 2D encounter-plane integral; also `pc_max` (worst case over covariance scaling). Rank by `pc_max` |
| Risk levels | RED `pc_max` ≥ 1e-4, AMBER ≥ 1e-5, else GREEN |
| Burn | Along-track, grid over lead time and size, smallest burn reaching Pc < 1e-6; applied with the difference method (burned minus unburned two-body+J2 orbit, added to the SGP4 orbit); then re-screen and plan a return burn |
| Storage | One folder per run, `data/runs/<run_id>/` with `catalog.json`, `events.json`, `plans.json`, `log.json`, then an empty `DONE` file last |
| Alerts, 2009 replay data, SOCRATES comparison | Built by teammates, not by us. We only read their output files |
| Always online | No offline mode. While a run is in progress, the API serves the previous completed run |
| User interface in the backend session | One plain HTML test page only (prompt 8). No dashboard work until session 2 |

## Rules for the assistant

- Follow `docs/CONTRACTS.md` for every data shape and signature. Every tunable number goes in `fusion/config.py`.
- Every module gets pytest tests. Run them (`.venv\Scripts\python -m pytest -q`) and only report what actually ran.
- Never invent data, API parameters or library functions; check docs or print what is there.
- If a number looks physically wrong (miss distance exactly 0, probability above 1e-2, delta-v above 1 m/s), find the cause; never tune it away.
- Do not change code in `fusion/core`, `fusion/risk` or `fusion/maneuver` once its tests pass, unless a test fails.
- Cache every download in `data/cache/`; at most one download per CelesTrak group per run.
- Build the simplest correct version. No extra features.

## Commits

Atharv wants about 50 commits over the whole project, in plain natural language (for example "Add the close-approach search with a KD-tree coarse pass"). So: commit small and often, one logical step per commit, roughly 3 to 5 per prompt, each with tests passing. Push to `origin main` after each prompt. Commit messages contain the message only: no "Co-Authored-By" line and no other AI attribution.

## Environment

- Windows 11, PowerShell. Python 3.14 in `.venv` (`.venv\Scripts\python`). Packages in `requirements.txt` are installed; `sgp4` runs with its fast compiled backend.
- Node 24 is installed for the dashboard later.

## Progress

| Prompt | Status |
|---|---|
| 1 Scaffold, contracts, fixtures | Done. `plan_sample.json` and `alerts_sample.json` are still to be added to `data/fixtures/` once the planner exists |
| 2 Ingest and propagate | Done, run on real data |
| 3 Screen and refine | Done, run on real data in both modes |
| 4 Uncertainty and probability | Done, run on real data |
| 5 Manoeuvre planner and verification | Done, run on real RED events |
| 6 Pipeline and run folders | Done, run end to end on real data |
| 7 Server and scheduler | Done, checked against a real run |
| 8 Basic test page | Done (`fusion/api/static/index.html`, served at `/`) |
| 9 Harden the engine on real data | Not started. **This is next** |
| 10–12 | Not started (10 and 11 need the teammate packs) |
| D1–D6 | Not started |

## Measured on real data (9 October 2026, CelesTrak plus Space-Track)

Space-Track is working: the login is in `.env` and the bulk query returns the full LEO catalogue in about 14 s. Object type and size class (`RCS_SIZE`) come from Space-Track; sizes map to a radius through `RCS_RADIUS_M` in config.

| What | Result |
|---|---|
| Catalogue | 29,686 usable LEO objects: 17,597 payloads, 9,892 debris, 1,571 rocket bodies, 626 unknown; 15,891 operational; 692 with no size class (5 m default) |
| `PRIMARIES` search (80 Iridium NEXT), 72 h | about 4 minutes; 258 events within 5 km per 24 h |
| `ALL_LEO` search, 72 h | about 32 minutes (single process); about 57 events within 1 km per hour |
| Risk assessment | under 1 ms per event |
| Risk levels, `PRIMARIES`, 24 h | 0 RED, 0 AMBER, 258 GREEN (top worst-case probability 9e-6) |
| Risk levels, `ALL_LEO`, 2 h | 3 RED, 22 AMBER, 89 GREEN |

What this means:

- With real object sizes, Iridium alone usually has no RED event on a given day. A demo of the burn planner needs either `ALL_LEO` mode (about 100 RED events per 72 h) or the synthetic test object.
- A full 72-hour `ALL_LEO` run takes about half an hour. For a live demo use the 24-hour quick window (about 11 minutes) or `PRIMARIES` mode, or add multiprocessing over time chunks in prompt 9.
- Before Space-Track, with CelesTrak only (18,539 objects, every object assumed 5 m): `ALL_LEO` took 14 minutes and a third of events were RED. Those numbers are superseded.

## What exists in the code (77 tests passing, 1 skipped until teammate B's cases arrive)

| File | What it does |
|---|---|
| `fusion/config.py` | Every tunable number |
| `fusion/contracts.py` | Pydantic models: `SpaceObject`, `ConjunctionEvent`, `ManeuverPlan`, `Alert`; `risk_level_for()` |
| `fusion/frames.py` | RTN basis, vector and covariance rotation |
| `fusion/core/sat.py` | `satrec_from_omm`, `get_satrec(obj)` (cached), `state_at`, `state_at_offset`, `period_s`, `perigee_apogee_km`, `object_from_omm`, `state_to_omm`, `fit_omm_to_state` |
| `fusion/core/refine.py` | `closest_approach(sat1, sat2, t_lo, t_hi)`: exact time and distance of closest approach |
| `fusion/core/spacetrack.py` | `load_leo_objects()`: every tracked LEO object from Space-Track, cached; returns nothing when `.env` has no login. Verified against the live service on 9 October 2026. Also sets `radius_m` from the size class and keeps the TLE lines. `load_catalog` in prompt 2 must merge these with the CelesTrak groups, de-duplicated by `norad_id` |
| `fusion/core/ingest.py` | `load_catalog()` and `load_catalog_with_stats()`: CelesTrak groups (cached 2 h, retried) merged with Space-Track, filtered to fresh LEO objects, then the size add-on hook |
| `fusion/core/propagate.py` | `Propagator(objs).states(t0, times_s)`: vectorised SGP4, NaN for failed objects |
| `fusion/core/screen.py` | `screen(catalog, t0, hours, threshold_km, mode, step_s, on_progress, stats)`: both modes; `order_pair()` gives the stable primary/secondary order |
| `fusion/risk/covariance.py` | `sigma_rtn(obj, age)`: measured value from B's pack if present, else the assumed table |
| `fusion/risk/pc.py` | `pc_2d`, `pc_disc`, `pc_max_disc`, `encounter_plane`, `event_covariances`, `assess(event, catalog_by_id)` |
| `fusion/addons.py` | The three optional hooks into the teammate packs, each with a fallback |
| `fusion/maneuver/orbit.py` | `ManeuveredOrbit(obj, burn_time, dv_rtn_ms, duration_s, return_after_s)`: SGP4 orbit plus the integrated effect of a burn and its return burn; `.states(seconds)`, `.delta(seconds)` |
| `fusion/maneuver/verify.py` | `closest_approach_to_orbit(orbit, other, centre_s, half_window_s)` and `new_conjunctions(orbit, catalog, exclude_ids, baseline=...)` |
| `fusion/maneuver/planner.py` | `plan(event, catalog, now, baseline, force, verify)` returns a `ManeuverPlan`; `choose_mover()` decides which object burns |
| `fusion/pipeline.py` | `run_pipeline(...)` runs every stage and writes the run folder; `new_run_id`, `load_run`, `write_json`; command line `python -m fusion.pipeline [--synthetic] [--quick] [--mode ...] [--hours H]` |
| `fusion/monitor/scheduler.py` | `Monitor`: re-runs the pipeline every 6 hours; the first run is one interval after start-up |
| `fusion/api/main.py` | FastAPI server. Start with `.venv\Scripts\python -m uvicorn fusion.api.main:app --port 8000`. Set `FUSION_SCHEDULER=0` to switch the scheduler off and `FUSION_RUNS_DIR` to move the runs folder |
| `scripts/make_fixtures.py` | Rebuilds `data/fixtures/` from a real download |
| `fusion/synthetic.py` | `make_conjunction(primary, t_tca, miss_km)`: labelled test object passing a chosen distance from a real satellite |
| `tests/conftest.py` | Made-up Iridium-like test satellite (`primary` fixture) |

Notes for whoever continues:

- A `SpaceObject` stores its raw OMM record in `.omm`; always get its `Satrec` with `get_satrec(obj)`. Never build a `Satrec` any other way, so saved objects reproduce the same orbit.
- `make_conjunction` takes a crossing angle between the two velocity vectors, not an inclination as the prompt text says. The test object lands within centimetres of the requested miss distance.
- For bulk propagation in prompt 2 use `sgp4.api.SatrecArray` over `get_satrec(obj)` for each object.

## How the main project must fit the teammate packs

These points keep our code consistent with what the packs expect. Follow them when building prompts 3, 6, 10 and 11.

- **Only real runs go in `data/runs/`.** Teammate C's watcher treats every run-id folder there as a run and compares it with the previous one. The 2009 replay is written to `data/replay_2009/` and the SOCRATES comparison to `data/validation.json`.
- **Run ids are unique and sortable:** `YYYYMMDDTHHMMZ`. If a folder with that id already exists, wait for the next minute; never overwrite a run.
- **The pair order in an event is stable.** If exactly one of the two objects is operational, it is the primary; otherwise the lower catalogue number is the primary. The same pair must come out the same way in every run.
- **C's watcher rewrites `events.json`** after a run (adding history and `first_seen`) and adds `alerts.json` and `summary.json`. The server must re-read files from disk on every request.
- **The packs take and return plain dicts,** not our pydantic models. Convert with `model_dump(mode="json")` and `model_validate`.
- **A's objects may have TLE lines but no OMM record.** `get_satrec` handles both.
- **A's test kit calls `screen(catalog, t0, hours, threshold_km)` with dict objects and expects a list of dicts.** Write a small adapter in our tests; do not change our signature for it.
- **B's `measured_sigma(norad_id, object_type, tle_age_days)`** returns three RTN sigmas in km or `None`. Our hook in `fusion/addons.py` adapts the arguments.
- **B's probability test cases** give RTN sigmas per object; build each covariance with `cov_rtn_to_teme` before calling our `pc_2d`.

## How the planner behaves (so later steps match it)

- A burn is planned only for RED events (or with `force=True`). AMBER gives `MONITOR`, GREEN gives `NO_ACTION`.
- The object that burns is the operational one; if both are operational, the one with newer orbit data; if neither is, the plan is `MONITOR` with "warning only". `maneuvering_id` says which object burns, and `dv_rtn_ms` is in that object's frame.
- A burn must be at least 30 minutes after `now`. If the pass is sooner than half an orbit plus that, the plan is `MONITOR` with "too soon".
- A burn counts as safe when the probability after it is below 1e-6 AND the worst-case probability is below 1e-5 AND the miss distance grew. If nothing on the grid reaches that, the best available burn is returned and the rationale says so.
- The grid uses a linear response (fast); the chosen burn is then recomputed exactly and re-screened for 24 hours (`VERIFY_HOURS`), not 72, because each re-screen propagates thousands of objects. One plan takes about 6 s in a small test and about 75 s against the full catalogue.
- Plans carry extra fields beyond `docs/CONTRACTS.md`: `maneuvering_id`, `pc_max_before`, `pc_max_after`, and in the grid `pc_max_after` and the two comparison rows for radial and cross-track burns.

## How the pipeline and server behave (so later steps match them)

- A full run in `PRIMARIES` mode with a 24-hour window and one burn plan takes about 2.5 minutes on the full catalogue.
- `catalog.json` in a run folder holds only the objects that appear in events, plus the primaries and any test object, not all 29,686. Anything that needs an object's orbit later (tracks, the event detail) reads it from there.
- A run folder also has `run.json`: status, mode, window, catalogue and screening statistics, risk-level counts, duration.
- Every RED event gets a plan entry. At most `MAX_PLANS_PER_RUN` of them become burns; the rest say the limit was reached. Every AMBER event gets a `MONITOR` entry. GREEN events have no plan entry.
- The test object, when requested, is aimed at the first operational primary, 30 hours ahead (or 60% of the window if shorter), at 50 m.
- Server routes beyond `docs/CONTRACTS.md`: `GET /latest` (the latest run's `run.json`), `GET /runs/latest/files/<path>` and `GET /addons/files/<path>` (serve add-on outputs; only json, md, png, txt, csv), `source=replay` on the event routes to read the 2009 replay folder.
- `GET /events/{id}` returns `{event, plan, track, encounter}`. `track` has positions every 5 s for 10 minutes either side of closest approach for both objects, plus the manoeuvred track when a burn is planned. `encounter` has the miss vector and covariance in the encounter plane, the hard-body radius, and the miss vector after the burn. Prompt 12's API additions are therefore already done.

**Next step:** prompt 9 in `docs/harness_ATHARV.md` (harden the engine on real data: repeat runs, sanity checks, failure handling, speed). Speed is the main issue: a 72-hour `ALL_LEO` run takes about 32 minutes single-process; splitting the search across CPU cores by time chunk is the obvious fix.