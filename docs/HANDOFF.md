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
| Uncertainty | Measured from element-set history by the trust pack (`addons/b_trust/tle_error.py`), per object, per kind of object and per age; the assumed table in config is the fallback (objects of unknown type, or no pack) |
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
| 9 Harden the engine on real data | Done: parallel search and planning, repeatability and failure tests, timings |
| 10 Connect A's pack | Done: measured sizes, test kit checked, 2009 replay built and served |
| 11 Connect B's and C's packs | Done. C: alerts, history, summary, briefings, CDM files, risk-trend prediction. B (built by us on 9 October 2026 because the teammate's branch never arrived): measured uncertainty, reference probability cases, validation against ESA and CelesTrak |
| 12 Close out session 1 | Done: `docs/RUN.md`, `docs/API.md`, and the event detail route already returns tracks and the encounter picture |
| D1–D6 | Not started |

## Measured on real data (9 October 2026, CelesTrak plus Space-Track)

Space-Track is working: the login is in `.env` and the bulk query returns the full LEO catalogue in about 14 s. Object type and size class (`RCS_SIZE`) come from Space-Track; sizes map to a radius through `RCS_RADIUS_M` in config.

| What | Result |
|---|---|
| Catalogue | 29,686 usable LEO objects: 17,597 payloads, 9,892 debris, 1,571 rocket bodies, 626 unknown; 15,891 operational; 692 with no size class (5 m default) |
| `PRIMARIES` search (80 Iridium NEXT), 72 h | about 4 minutes single-process; 258 events within 5 km per 24 h |
| `ALL_LEO` search, 72 h | about 7 minutes on 11 worker processes (32 minutes single-process); about 65 events within 1 km per hour |
| Full `ALL_LEO` run, 24 h window, 5 burn plans | about 4 minutes |
| Risk assessment | under 1 ms per event |
| Risk levels, `PRIMARIES`, 24 h | 0 RED, 0 AMBER, 258 GREEN (top worst-case probability 9e-6) |
| Risk levels, `ALL_LEO`, 2 h | 3 RED, 22 AMBER, 89 GREEN |

What this means:

- With real object sizes, Iridium alone usually has no RED event on a given day. A demo of the burn planner needs either `ALL_LEO` mode (about 100 RED events per 72 h) or the synthetic test object.
- The search and the burn planning both run across CPU cores. A full-sky 24-hour run with five burn plans takes about 4 minutes, so it can be started early in a demo and shown finishing.
- Before Space-Track, with CelesTrak only (18,539 objects, every object assumed 5 m): `ALL_LEO` took 14 minutes and a third of events were RED. Those numbers are superseded.

## What exists in the code (110 tests passing in the main project, 54 in the trust pack, none skipped)

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
| `fusion/addons.py` | The three optional hooks into the teammate packs, each with a fallback, and `after_run` (alerts, briefings, CDM files) |
| `fusion/replay/replay_2009.py` | The 2009 replay: builds the catalogue known a day before the collision, runs the pipeline, stores a what-if burn |
| `scripts/why_python.py` | Measures compiled SGP4 and the KD-tree against plain Python and against checking every pair |
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

## Teammate packs: what arrived and how they are connected (9 October 2026)

Two pull requests were merged into `main`. Teammate A's came as a copy of the whole project in `addons_A_history/`; the pack was moved to `addons/a_history/` and the copy (identical to an older version of our files) was removed. Teammate B's pack has not arrived.

| Pack | What we use | How |
|---|---|---|
| A sizes | `enrich.enrich_catalog` | Hook in `fusion/addons.py`, called at the end of `load_catalog`. We take the pack's radius only where it has a measured radar size (`_has_real_rcs`); elsewhere we keep the Space-Track size class. 11,063 of 29,685 objects get a measured size; debris median radius goes from 0.40 m to 0.10 m. First call downloads `satcat.csv` into the pack's `cache/` |
| A test kit | `out/testkit/cases.json` | `tests/test_teammate_packs.py` checks our search against the kit and against an independent dense calculation. We do not call the kit's `check()`: its expected lists hold one closest approach per pair, which is incomplete for cases 1, 5, 6 and 7 |
| A replay | `out/replay_2009.json` | `python -m fusion.replay.replay_2009` writes `data/replay_2009/` |
| C alerts | `watch.process_single_run` | `addons.after_run`, called by the pipeline after the run files are written and before `DONE`. It is given only earlier runs of the same mode and window. `events.json` is backed up and restored if the pack damages it; plan ids are kept in step if the pack renames an event |
| C briefings, CDM | `briefing.generate_run_briefings`, `cdm_export.export_run_cdms` | Same step; one file per red and amber event |
| C prediction | `predict.predict_final_risk` | Hook; the pack returns log10 of the probability, we store a probability in `pc_predicted_final` and pass the run time as `run_time` |
| C pitch files | `out/pitch/*.md` | Listed by `GET /addons`. Several answers in `judge_questions.md` describe things our system does not do (measured uncertainty, one constellation only, a 99.9% plane filter); use `docs/PROJECT_EXPLAINED.md` instead |

Rules that follow from this:

- The packs need `requirements-addons.txt`. Without those libraries the hooks log a warning and fall back.
- Our tests run as if `addons/` were empty (session fixture in `tests/conftest.py`). Tests that use the real packs ask for the `real_packs` fixture and skip when a pack or library is missing. `pytest.ini` limits collection to `tests/`, because the packs have their own tests.
- Never start `addons/c_ops/watch.py` against `data/runs`; it would compare runs of different modes.
- A replay run (`run_dir` given) gets briefings and CDM files but no alerts.

2009 replay result, as it came out, nothing tuned: at 9 February 2009 17:00 UTC, from 2,899 objects public at that time, Iridium 33 has 2 passes within 5 km in the next 48 hours. Rank 1 is Cosmos 2251: closest approach 10 February 16:55:59 UTC (the reported collision time is 16:56), predicted miss 0.584 km, 11.65 km/s. With the measured uncertainty (kind of object only; see below) the probability is 2.0e-9 and the worst case 1.1e-5: AMBER by a hair, decision MONITOR, and the stored what-if burn is only 1 mm/s. Before the trust pack, with the assumed table, the same pass had probability 2.0e-5 and worst case 9.7e-5 (AMBER just under the RED line) and a what-if burn of 43 mm/s. The lesson to present is that public data put the pass at 584 m with about 200 m of measured uncertainty, and the two still collided.

How stable the predictions are (measured between the 08:31 and 10:38 UTC downloads, 1,747 passes): the predicted miss moved by a median of 0.03 km when neither object can manoeuvre, 0.55 km when one or both are operational, and 26.5 km for two Starlink satellites. This is why same-fleet pairs get no burn plan and why burn searches go first to passes where exactly one object can move.

## The trust pack (teammate B's part, built by us)

`addons/b_trust/` follows `docs/harness_B_trust.md` and is standalone. Its `REPORT.md` and `out/VALIDATION_REPORT.md` have every number. What the main project uses:

| What | How |
|---|---|
| Measured uncertainty | `fusion/addons.measured_sigma` calls the pack's `measured_sigma(norad_id, object_type, age, name, operational)`. The last two arguments are passed only if the pack's function takes them; they let it tell a Starlink from a dead satellite. Events then carry `sigma_source: MEASURED` |
| Reference probability cases | `tests/test_pc.py` checks our `pc_2d` against `out/pc_test_cases.json` (30 cases, 2%) |
| CelesTrak comparison | `python -m fusion.validation` writes `data/validation.json`: our `closest_approach` on the element sets CelesTrak used, and our latest run against CelesTrak's list. The pipeline refreshes it at the end of a run, without downloading, when the pack's copy of the list is under 12 hours old |

Results worth knowing when building on this:

- With measured uncertainty the first full-sky run went from 40 red, 300 amber to 35 red, 181 amber.
- A satellite whose own along-track position is uncertain by kilometres (Starlink 12 km after a day, some Kuiper) cannot be made safe by shifting it along its track, so the planner now often picks a burn half an orbit before the pass, which separates the two radially. Burn sizes then reach the 100 mm/s top of the search grid.
- The first run after a change of uncertainty model raises many downgraded and escalated alerts (165 and 28); the run after that is quiet again.
- An object's own measurement is used only when its orbit data is recent (within 60 days of today). For the 2009 replay the hook passes catalogue number 0, so the pack answers with the kind of object: number 22675 is today a fragment of Cosmos 2251, not the satellite of 2009.
- `pc_reference.pc_integral` is the exact one-dimensional form (0.1 ms). The direct double integral is `pc_integral_2d`, kept as a check; it takes milliseconds to seconds.
- The pack's `cache/` (74 MB) and `esa/` (434 MB) are git-ignored. To rebuild everything see the pack's `README.md`.

## The landing page and the `frontend/` folder

- `landing/index.html` is our own page for visitors, branded EDITH: one file, no build step, black and white, served at `/landing`. Its text, code and visuals (drawn on canvas and in SVG) are ours. It reads live numbers from `/latest` and falls back to the figures of 9 October 2026 when the server is not running.
- `frontend/` arrived through pull request #3. It is a downloaded copy of the United Nations web feature "The Race to Save Space" with a small local server, not our work, and it also contains a saved location lookup of the machine that downloaded it. It must not be presented as ours, renamed or edited to hide its origin. Atharv has been asked whether to remove it from the repository; until he answers, leave it alone and do not build on it.

## How the planner behaves (so later steps match it)

- A burn is planned only for RED events (or with `force=True`). AMBER gives `MONITOR`, GREEN gives `NO_ACTION`.
- Two operational satellites of the same fleet (same leading word in the name, for example STARLINK) get `MONITOR` with the reason; `force=True` overrides.
- The burn searches of a run (at most `MAX_PLANS_PER_RUN`) go first to red passes where exactly one object can move (`slot_priority`), then by worst-case probability.
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

**Next step:** the backend is complete with all three packs connected. Start the frontend (prompts D1 to D6 in `docs/harness_ATHARV.md`, building from `docs/API.md`). The validation tab has real content now: `GET /validation` and the report at `/addons/files/b_trust/out/VALIDATION_REPORT.md` with its four charts.

Notes from hardening:

- The search hands 30-minute blocks to worker processes; results are sorted, so a run gives identical events however many workers are used (there is a test for this).
- The catalogue is pickled once and handed to workers as bytes; passing the object list directly made start-up take almost a minute.
- The burn safety re-screen uses a 30 s step (`VERIFY_STEP_S`), with every candidate refined exactly; this cut a plan from about 80 s to about 30 s with the same result.
- Worker start-up costs about 35 s on the full catalogue, so small jobs (below `PARALLEL_MIN_WORK`) stay in one process.