# Atharv: the whole project, end to end

**Your assistant:** Claude. **Time:** 12 hours for the backend (session 1, with a basic test page), then 5 to 6 hours for the frontend and demo (session 2). **Your folder:** the project root (everything except `addons/`).

## What you are building

The complete system, working by itself: download public orbit data, predict close approaches to the Iridium NEXT constellation, rank them by collision probability, recommend and verify an avoidance burn, monitor continuously with alerts, and show it all on a dashboard, with a replay of the 2009 Iridium–Cosmos collision.

The three teammates build add-on packs in `addons/`. You do not build anything they are building. Your side only connects to their finished work and displays it:

| Feature | Who builds it | Your part |
|---|---|---|
| Orbit download, close-pass search, probability, burn planner, safety check, pipeline | You | All of it |
| Server, 6-hour scheduler, dashboard | You | All of it |
| Test object for the demo | You | All of it |
| 2009 replay data and day-by-day history | A | Run A's data through your pipeline and show it |
| Real object sizes and status | A | One hook; 5 m default without it |
| Test kit for the close-pass search | A | Run it against your code |
| Measured uncertainty | B | One hook; assumed table without it |
| Validation against CelesTrak and ESA, reference calculator, robustness | B | Run B's comparison on your events and show B's report |
| Alerts between runs, risk history, run summary | C | Show C's alert feed and summary |
| Briefings and standard-format messages | C | Two buttons on the plan card |
| Predicted final risk | C | One hook; column stays empty without it |
| Slides, demo script, judge questions | C | Use them |

If a pack does not arrive, its feature is simply absent: the panel says "not available" and everything else works. Your own part always produces the ranked close passes, the burn recommendation and the dashboard.

## How to work

1. One-time setup:
   ```
   git init
   python -m venv .venv
   .venv\Scripts\activate
   pip install sgp4 numpy scipy pydantic fastapi uvicorn requests apscheduler pytest httpx
   ```
   Node.js 20 or later is only needed in session 2, for the dashboard.
2. Start each session by pasting **Prompt 0**, with `CONTRACTS.md` open to the assistant.
3. Paste the prompts in order. Run the **check** after each. Commit after each.
4. Session 1 spends no time on the dashboard. Prompt 8 is a single plain test page; do not let it grow.
5. If a prompt runs 20 minutes over its time box, take the simplest thing that works and move on.
6. Your plan has usage limits that reset on a timer. Check them with `/usage`. Do the hard-maths prompts (3, 4, 5) while you have plenty left.

## Session 1 (first 12 hours): engine, monitoring, basic test page

| Prompt | Topic | Time | Running total |
|---|---|---|---|
| 1 | Scaffold, contracts, fixtures | 0:45 | 0:45 |
| 2 | Ingest and propagate | 0:45 | 1:30 |
| 3 | Screen and refine | 1:30 | 3:00 |
| 4 | Uncertainty and probability | 1:15 | 4:15 |
| 5 | Manoeuvre planner and verification | 2:00 | 6:15 |
| 6 | Pipeline and run folders | 0:45 | 7:00 |
| 7 | Server and scheduler | 0:45 | 7:45 |
| 8 | Basic test page | 0:30 | 8:15 |
| 9 | Harden the engine on real data | 1:15 | 9:30 |
| 10 | Connect A's pack: replay, sizes, test kit | 0:45 | 10:15 |
| 11 | Connect B's and C's packs: uncertainty, validation, alerts, briefings | 0:45 | 11:00 |
| 12 | Close out session 1 | 1:00 | 12:00 |

Session 2 (dashboard and demo) is at the end of this file.

## Prompt 0: context (paste at the start of every session)

```text
We are building "Fusion": an autonomous collision-avoidance system for the Iridium NEXT satellite constellation, from public TLE data. Read docs/CONTRACTS.md now; it defines every data shape, function signature, API route and the repo layout. Follow it exactly and tell me before changing it.

Rules:
- Python 3.11, type hints, pydantic v2 models from fusion/contracts.py, every tunable number in fusion/config.py.
- Orbit propagation uses the sgp4 package. Everything is TEME, km, km/s, UTC. No frame conversions.
- RTN frame: R = unit position, N = unit(r x v), T = N x R.
- Every module gets pytest tests. Run them and show me the output. Never say something works unless you ran it.
- Never invent data, API parameters or library functions. If unsure, check the docs or print what is there.
- If a number looks physically wrong (miss distance of exactly 0, probability above 1e-2, delta-v above 1 m/s), stop and find the cause instead of tuning it away.
- Cache every download in data/cache/. At most one download per CelesTrak group per run.
- The folder addons/ belongs to other people. Never edit it. The main project must run when addons/ is empty.
- Build the simplest correct version first. No extra features, no speculative abstractions.
```

## Prompt 1: scaffold, contracts, fixtures

```text
Create the repo layout from CONTRACTS.md (empty modules with docstrings), a .gitignore (data/cache, data/runs, .env, .venv, node_modules), and:

1. fusion/contracts.py: pydantic models SpaceObject, ConjunctionEvent, ManeuverPlan, Alert exactly as in CONTRACTS.md. Risk and history fields are optional so an event can exist with geometry only. Add primary_name and secondary_name as optional strings on ConjunctionEvent.
2. fusion/config.py: groups, window (72 h), screening step (10 s), screening threshold (5 km), maximum closing speed (15.5 km/s), risk thresholds (RED 1e-4, AMBER 1e-5), target probability after a burn (1e-6), default radius (5 m), maximum TLE age (14 days), scheduler interval (6 h).
3. fusion/frames.py: rtn_basis(r, v) -> 3x3, teme_to_rtn and rtn_to_teme for vectors, and cov_rtn_to_teme. Tests with a circular equatorial orbit where the answer is obvious.
4. fusion/synthetic.py: make_conjunction(primary: SpaceObject, t_tca, miss_km, inclination_deg) -> SpaceObject that builds a fake secondary crossing the primary's path at t_tca with about the requested miss distance. Build it from orbital elements with Satrec.sgp4init and adjust the mean anomaly iteratively until the closest approach, computed by sampling at 1 s, is within 20 m of the target. Name it "SYNTHETIC TEST OBJECT" with a NORAD id of 99001 upward so it can never be mistaken for a real object.
5. data/fixtures/: catalog_sample.json (20 real objects fetched once from CelesTrak's iridium-NEXT group plus the synthetic object at 300 m miss, 30 hours ahead), and hand-written events_sample.json, plan_sample.json, alerts_sample.json that validate against the models.

Tests: models round-trip the fixtures; frames; the synthetic object lands within 20 m of the requested miss.
```

**Check:** `pytest` passes, and the fixtures load.

## Prompt 2: ingest and propagate

```text
Write fusion/core/ingest.py and fusion/core/propagate.py.

ingest.load_catalog(use_cache=True) -> list[SpaceObject]:
- Download https://celestrak.org/NORAD/elements/gp.php?GROUP=<group>&FORMAT=json for each group in config, one request per group, 2 s apart, cached in data/cache/ with a timestamp; reuse a cache younger than 2 hours.
- Use the JSON (OMM) format because catalogue numbers above 99999 do not exist in TLE text. Build Satrec objects with the sgp4.omm module. Keep the Satrec on the object in a private, non-serialised attribute or a side dict keyed by norad_id, so propagation does not re-parse. Fill tle_line1 and tle_line2 with sgp4.exporter.export_tle when the catalogue number allows it, otherwise null; add an optional "omm" dict field to SpaceObject for those.
- De-duplicate by norad_id (an object in iridium-NEXT stays primary). object_type from the name: "DEB" -> DEBRIS, "R/B" -> ROCKET_BODY, else PAYLOAD. Perigee and apogee from mean motion and eccentricity. Drop element sets older than the configured age and log the count.
- An optional inject: list[SpaceObject] parameter appends extra objects (used for the synthetic object and the replay).

propagate.propagate(objs, t0, times_s) -> (r, v): SatrecArray, vectorised, arrays shaped [n_obj, n_t, 3], NaN where sgp4 reports an error. Process in time chunks so memory stays under about 1 GB.

Tests: perigee/apogee for a known orbit; de-duplication keeps the primary flag; propagation to an object's own epoch matches the single-satellite sgp4 API to 1 mm; an invalid element set gives NaN and does not crash.
Run load_catalog() for real and print: objects per group, primaries, dropped for age.
```

**Check:** the real run prints counts, with about 80 primaries.

## Prompt 3: screen and refine

```text
Write fusion/core/screen.py and fusion/core/refine.py.

screen(catalog, t0, hours=72, threshold_km=5.0, on_progress=None) -> list[ConjunctionEvent] with geometry fields filled:

1. Altitude filter: keep secondaries whose perigee-to-apogee band overlaps the union band of the primaries padded by 30 km.
2. Coarse search: time step dt from config. At each step build scipy.spatial.cKDTree on the secondaries' positions and query with the primaries' positions at radius threshold_km + vmax * dt / 2. Skip NaN rows. Also query primaries against primaries. Collect (primary, secondary, step) hits and merge consecutive hits of a pair into one window. Propagate in chunks; never hold the whole 72 hours in memory.
3. Refine: for each window minimise the distance with scipy.optimize.minimize_scalar (bounded, window padded by dt) using the two Satrec objects directly. If the bounded minimum sits on a boundary, widen once. Keep events with miss below threshold_km.
4. Drop events with relative speed below 0.1 km/s (formation neighbours). For primary-primary pairs keep each pair once.
5. Fill tca, miss_distance_km, relative_speed_kms, both state vectors at TCA, miss_rtn_km in the primary's RTN frame, both TLE ages at TCA, names, and event_id as <primary>-<secondary>-<TCA to the minute>.

Tests:
- The synthetic object from the fixtures is found with TCA within 0.5 s and miss within 20 m of its design values.
- At every returned TCA, relative position dot relative velocity is near zero.
- Two objects in the same orbit 500 km apart are not reported.
- A synthetic 8 km miss is not reported at a 5 km threshold.
- Running with dt = 5 s finds the same events as dt = 10 s.

Then run it on the real catalogue with the synthetic object injected. Print the run time, the number of candidates after each stage, and the ten closest events. If the full run takes over 10 minutes, profile it and fix the slowest part (larger dt with the matching radius, or multiprocessing over time chunks) while keeping the tests passing.
```

**Check:** the real run finishes in under 10 minutes and lists events, with the synthetic one at about 300 m.

## Prompt 4: uncertainty and probability

```text
Write fusion/risk/covariance.py and fusion/risk/pc.py.

covariance.sigma_rtn(obj, tle_age_days) -> (sigma[3] km, source):
- First try fusion.addons.measured_sigma (see below); if it returns an array, source = "MEASURED".
- Otherwise the assumed table in config, source = "MODELLED": sigma = sigma0 + rate * age, with radial 0.1 km + 0.05 km/day, along-track 0.5 km + 1.0 km/day for PAYLOAD and 2.0 km/day for DEBRIS, ROCKET_BODY and UNKNOWN, cross-track 0.1 km + 0.05 km/day.

pc.pc_2d(r1, v1, C1, r2, v2, C2, hbr_km) -> (pc, pc_max):
1. C = C1 + C2 in TEME.
2. Encounter plane perpendicular to the relative velocity: build two orthonormal vectors, project the relative position to a 2-vector m and C to a 2x2 Cp.
3. pc = integral of the 2D Gaussian (mean m, covariance Cp) over a disc of radius hbr_km at the origin, by numerical integration that stays accurate when the disc is thousands of times smaller than the sigmas.
4. pc_max = the maximum over all positive scalings of Cp. Small-disc closed form: d2 = m^T Cp^-1 m; pc_max = hbr^2 / (e * d2 * sqrt(det Cp)) when d2 >= 2, otherwise pc_max = pc. Verify the closed form numerically in a test.

pc.assess(event, catalog) -> event with pc, pc_max, both sigma vectors, sigma_source (MEASURED only if both objects were measured), hbr_km = sum of both radius_m in km, risk_level from pc_max, and pc_predicted_final from fusion.addons.predict_final_risk if available.

Create fusion/addons.py now with three functions that each try to import from the teammate packs and return a neutral fallback on ANY exception, logging one line the first time:
- enrich_catalog(objs) -> objs unchanged if addons/a_history/enrich.py is absent,
- measured_sigma(obj, age) -> None if addons/b_trust/tle_error.py or its out/tle_error.json is absent,
- predict_final_risk(event) -> None if addons/c_ops/predict.py is absent.
The packs take plain dicts, so convert with model_dump and back. Call enrich_catalog at the end of load_catalog.

Tests:
- Zero miss, isotropic sigma s: pc = 1 - exp(-hbr^2 / (2 s^2)).
- Agreement with a 10-million-sample Monte Carlo on three cases with pc between 1e-2 and 1e-4.
- pc_max >= pc; pc falls as miss grows; rotating everything by a random rotation leaves pc unchanged.
- addons functions return their fallbacks when addons/ is empty.
- If addons/b_trust/out/pc_test_cases.json exists, run pc_2d against every case and require agreement within 2%; skip the test cleanly if the file is absent.

Run assess on the events from prompt 3 and print the top ten by pc_max with risk levels.
```

**Check:** tests pass, and the synthetic event ranks at or near the top. If nothing is RED, that is expected with kilometre-level uncertainty; the synthetic event's miss can be reduced in the fixture until it is RED.

## Prompt 5: manoeuvre planner and verification

```text
Write fusion/maneuver/planner.py and fusion/maneuver/verify.py.

Decision: pc_max >= RED threshold -> MANEUVER; >= AMBER -> MONITOR; else NO_ACTION. The primary moves. If the secondary is also a primary, move the one with the newer element set and record why. If the secondary is not operational it cannot move; record that in a "rationale" string field (add it to ManeuverPlan as optional).

Applying a burn to an SGP4 orbit (difference method):
1. Primary state (r, v) at burn time from sgp4.
2. dv in TEME from RTN components.
3. Integrate two trajectories from the burn time to TCA + 2 orbits with two-body + J2 gravity (scipy solve_ivp, DOP853, rtol 1e-10, atol 1e-12, dense output): one from (r, v), one from (r, v + dv).
4. Manoeuvred position(t) = sgp4 position(t) + (burned(t) - unburned(t)); same for velocity.

Search:
- Burn times: TCA - k * period / 4 for k = 2..32 (half an orbit to 8 orbits before), skipping any earlier than now + 30 minutes.
- Along-track dv: both signs, 12 values from 1 to 100 mm/s on a log grid. Plus one row each of pure radial and pure cross-track at 30 mm/s to show they were considered.
- For each grid point: new closest approach against the secondary (refine within +-2 minutes of the old TCA), then pc_2d with the SAME covariances as the original event.
- Choose the smallest |dv| with pc_after < target and miss_after > miss_before; tie-break on the later burn time. If nothing reaches the target, choose the lowest pc_after and say so in the rationale.
- Store the whole along-track grid in search_grid (lead_orbits, dv_ms signed, pc_after and miss_after matrices) for the dashboard heatmap.

Verify (verify.py):
- Screen the manoeuvred primary alone against the full catalogue from burn time for 72 hours, using the manoeuvred trajectory instead of sgp4 for the primary (sample it on the same time grid; reuse the KD-tree and refinement code with a position callback).
- Exclude the original secondary. Assess each new event. If any is AMBER or RED, reject this grid point and take the next best, up to 5 attempts. Record secondary_conjunctions_created for the accepted plan.
- Return burn: equal and opposite dv at the first whole number of orbits after the burn that is also after TCA + 10 minutes. Compute residual_along_track_km as the along-track offset from the original sgp4 orbit one orbit after the return burn.

Tests:
- Zero dv reproduces the original miss distance and pc.
- For 30 mm/s along-track applied 1.5 orbits before TCA, the along-track displacement at TCA is within 10% of 3 * dv * dt.
- On the synthetic RED event, the plan reduces pc by at least 100 times with |dv| under 0.1 m/s.
- The return burn brings the orbital period back to within 0.01 s of the original.

Run it on the top event and print the plan in plain language: when to burn, which way, how many mm/s, miss and probability before and after, new conjunctions created, return burn, leftover offset.
```

**Check:** the printed plan reads sensibly and the tests pass. This is the heart of the project; read the numbers yourself.

## Prompt 6: pipeline and run folders

```text
Write fusion/pipeline.py.

run_pipeline(t0=None, on_progress=None, catalog=None, run_dir=None, inject_synthetic=False) -> run_id:
- Stages with progress callbacks on_progress(stage, percent, message): INGEST, PROPAGATE, SCREEN, ASSESS, PLAN, VERIFY, DONE. Messages are sentences a judge can read, with real numbers, for example "Screened 9,412 objects against 80 Iridium NEXT satellites: 37 close passes within 5 km".
- catalog overrides the download (used by the replay). t0 defaults to now.
- inject_synthetic adds the synthetic object; every event involving it carries "synthetic": true (add the optional field) so the dashboard can label it.
- Plan every RED event, up to 5 per run, most dangerous first. MONITOR decisions for AMBER.
- Do not compare with earlier runs and do not write alerts.json: a separate add-on (addons/c_ops/watch.py) watches the runs folder, and after DONE appears it writes alerts.json, summary.json and an updated events.json (with history and first_seen) into the run folder.
- Write data/runs/<run_id>/catalog.json, events.json (sorted by pc_max descending), plans.json, log.json (the progress messages with timestamps), then an empty file named DONE as the last step. Write each JSON file to a temporary name and rename it, so a watcher never reads a half-written file.
- Any stage failure writes the error to log.json and re-raises; a failed run has no DONE file.

Add python -m fusion.pipeline [--synthetic] that runs it and prints the log and the top five events.

Tests: a run on the 21-object fixture catalogue completes, writes all files, and DONE is last; a failing stage leaves no DONE file.
Run it for real with --synthetic.
```

**Check:** a run folder exists with all files, and the terminal shows the top five. You now have a working answer to the problem statement.

## Prompt 7: server and scheduler

```text
Part 1: fusion/monitor/scheduler.py: APScheduler job that calls run_pipeline every 6 hours (from config), never overlapping, exposing last_run, next_run, run_count.

Part 2: fusion/api/main.py (FastAPI) with every route in CONTRACTS.md.
- Alerts are produced by an add-on, not by us. GET /alerts returns the contents of alerts.json from the latest run folder if the file exists, otherwise an empty list. GET /summary returns that run's summary.json path if present. Always re-read events.json from disk on each request, because the add-on rewrites it with history.
- POST /run starts run_pipeline in a background thread and returns the run id; a second POST while one is running returns the running id. Body option {"synthetic": true}.
- GET /run/{id}/status returns stage, percent and log lines; works for finished runs from log.json.
- GET /events, /events/{id}, /events/{id}/plan, /alerts serve from the latest run folder that has a DONE file. /events/{id} adds positions of both objects every 5 s for +-10 minutes around TCA, and, if a plan exists, the manoeuvred primary track too.
- GET /objects/{norad_id}/track?hours=3 at 30 s steps.
- GET /validation and GET /replay/2009 serve data/runs/validation.json and the replay run folder; return 404 with a clear message while they do not exist (prompts 10 and 11 create them from the add-on packs).
- GET /addons reports which add-on packs are present and which outputs exist (validation report, briefings, alert feed), with their file paths served under /addons/files/.
- The system always runs live on fresh data; there is no offline mode. While a run is in progress, every route keeps serving the previous completed run, so the dashboard is never empty.
- If a download fails, retry twice with a pause, then fail the run with a clear message in the log; never fall back silently to old data.
- CORS for http://localhost:5173 (the dashboard comes in a later session; build no user interface in this task).

Tests with TestClient: every route validates against the models using a fixture run folder; while a run is in progress the previous run is still served; a failed download produces a failed run with a readable log message.
Start the server and show me /events and /monitor.
```

**Check:** `uvicorn fusion.api.main:app` serves `/events` from your real run.

## Prompt 8: basic test page

```text
Make one plain test page so I can see results in a browser. This is a testing tool, not the product dashboard, so keep it as small as possible: a single file fusion/api/static/index.html served by FastAPI at "/", plain HTML with a little vanilla JavaScript and a few lines of CSS. No framework, no build step, no npm, no charts, no map. Aim for under 200 lines. Do not add anything I have not listed.

On the page:
1. A Run button (POST /run) with a checkbox "include test object", and under it the current stage and the log lines from /run/{id}/status, refreshed every 2 seconds while a run is in progress.
2. A table of /events: risk level as text, the two names, time of closest approach, hours until then, miss distance in km, pc and pc_max in scientific notation, where the uncertainty came from, and a TEST tag for the test object. Clicking a row selects it.
3. For the selected event: the plan from /events/{id}/plan as a short plain-text block (decision, burn time, direction in words, size in mm/s, miss and probability before -> after, new close passes created, return burn, rationale), or "No plan" if there is none.
4. A list of /alerts, one sentence per line, or "No alerts yet".
5. A line at the bottom from /monitor: last run, next run, run count.
If a request fails, show the error text on the page.

Open it against the real server and tell me what you see.
```

**Check:** you can press Run in the browser, watch the stages, and read the table and the plan. Do not spend more time here; the real dashboard is session 2.

## Prompt 9: harden the engine on real data

```text
The engine now runs end to end. Before anything is built on top of it, check it against reality. Do the following and give me a short written report with the numbers.

1. Make three full real runs (one with the test object, two without) and record for each: total time, time per stage, objects downloaded, objects dropped for age, candidates after each screening stage, events within 5 km, 1 km and 500 m, and the count per risk level.
2. Sanity of the events: the distribution of relative speeds (expect roughly 0.1 to 15 km/s), of miss distances, and of element-set ages. Flag anything outside physical limits.
3. Repeatability: two runs a few minutes apart on the same cached data must give identical events. Two runs on freshly downloaded data should mostly agree; show me how many events match within 60 s and how much the miss distances differ.
4. Probability sanity: for the top 20 events show miss distance, sigmas, pc and pc_max side by side. Confirm no pc above 1e-2 without a miss under about 100 m, and explain any that looks odd.
5. Planner sanity: plan every RED and the top three AMBER events (forcing a plan for testing only). For each, check that the chosen burn is under 0.1 m/s, that the miss increased, that verification found no new AMBER or RED event, and that the return burn restores the period. Show me a table.
6. Failure handling: run with the network cut for one group download, with one corrupted element set injected, and with an empty primary group. Each must fail or degrade with a clear log message, never a stack trace into the run folder and never a silent wrong answer.
7. Speed: if a full run takes over 5 minutes, profile it and fix the slowest part while keeping every test passing. Then add a "quick" option to run_pipeline and POST /run that uses a 24-hour window, and time it.
8. Fix every real problem found, add a test for each fix, and rerun the whole test suite.
```

**Check:** you have the report, a full run time you are happy with, and all tests pass. This is the step that makes the numbers trustworthy on stage.

## Prompt 10: connect A's pack (replay, sizes, test kit)

```text
Teammate A's finished pack should be in addons/a_history/. Read its README.md first and tell me what is there and what its "known gaps" section says. Do not edit anything inside addons/. Do not rebuild anything the pack already provides. If the pack is missing, tell me and skip this whole task.

1. Sizes: confirm fusion.addons.enrich_catalog finds addons/a_history/enrich.py and that a new run shows real radius_m values and operational flags. Print how many objects changed.

2. Test kit: if addons/a_history/out/testkit/ exists, run its check() against our screen() and show me the result. If a case fails, the bug is ours: fix our code.

3. Replay: fusion/replay/replay_2009.py.
- Load addons/a_history/out/replay_2009.json (element sets for Iridium 33 and Cosmos 2251 before the collision of 10 February 2009, plus background objects). We do not download any historical data ourselves.
- Take the latest element set of each satellite with epoch before 2009-02-09T17:00Z, about 24 hours before the collision.
- Call run_pipeline(t0 = 2009-02-09T17:00Z, catalog = those two plus the background, run_dir = data/runs/replay_2009).
- Print what our system reports a day before: predicted time, miss distance, pc, pc_max, risk level, and the plan if one is produced. Report the numbers as they come out. If the event is not RED under our thresholds, say so plainly; do not change thresholds or sigmas to force it.
- Copy addons/a_history/out/replay_2009_predictions.json and replay_2009_notes.md into the run folder if they exist.
- Confirm GET /replay/2009 serves the run. Add one link on the test page that shows the replay events in the same table. Nothing more on the page.
```

**Check:** the replay run exists and you have its numbers written down. They decide how you open the demo.

## Prompt 11: connect B's and C's packs (uncertainty, validation, alerts, briefings)

```text
Teammates' finished packs should be in addons/b_trust/ and addons/c_ops/. Read each README.md first and tell me what is there and what the "known gaps" sections say. Do not edit anything inside addons/. Do not rebuild anything a pack already provides. Skip the part for any pack that is missing.

B's pack:
1. Uncertainty: confirm fusion.addons.measured_sigma loads addons/b_trust/tle_error.py and that new events show sigma_source MEASURED. Compare the top 20 events before and after and tell me what changed.
2. Probability check: run the test that compares our pc_2d with addons/b_trust/out/pc_test_cases.json. If a case disagrees by more than 2%, the bug is probably ours: find it.
3. Validation: use the pack's own loader and compare function (socrates.py and validate.py; read their signatures) to compare the events of our latest real run with CelesTrak SOCRATES, excluding the test object, and save the result as data/runs/validation.json. We do not write our own comparison. Print the summary.

C's pack:
4. Alerts: start addons/c_ops/watch.py pointed at data/runs. Make two runs and confirm that alerts.json, summary.json and the updated events.json (with history) appear in the second run folder and that /alerts serves them. Add the watcher's start command to the startup notes; do not import its code into ours.
5. Prediction: confirm fusion.addons.predict_final_risk fills pc_predicted_final.
6. Operator outputs: run the pack's cdm_export.py and briefing.py on the latest run folder after each run (call them as commands from the scheduler job) and confirm the files appear and are served under /addons/files/.

Finally: run our full test suite, then one full real run with the watcher on, and show me both outputs. Then rename addons/ temporarily, run again, and confirm everything still works.
```

**Check:** `/addons` lists what is present, alerts appear after a second run, and the project still runs with `addons/` removed.

## Prompt 12: close out session 1

```text
Wrap up the engine so the next session can be spent only on the dashboard.

1. Write RUN.md: exact commands to start the server and the alert watcher, make a run, and open the test page; every config value and what it does; where each output file is written.
2. Write API.md from the running server: every route, its parameters, and one real example response trimmed to a few items. The dashboard will be built from this file, so it must match the code exactly; generate the examples by calling the server, do not write them by hand.
3. Make sure the API returns the two things the dashboard will need, with tests:
   - GET /events/{id} includes positions of both objects every 5 s for 10 minutes either side of closest approach, and the manoeuvred primary track when a plan exists (confirm this from prompt 7 works);
   - GET /events/{id} includes an "encounter" object (the 2-vector miss, the 2x2 projected covariance, the hard-body radius, and the after-burn miss vector when a plan exists), computed by the same code as pc_2d so a picture drawn from it can never disagree with the number.
4. Run the whole test suite and one full real run. List anything still failing or unfinished, honestly, as a "known gaps" section in RUN.md.
5. Commit everything.
```

**Check:** all tests pass, a fresh run works from `RUN.md` alone, and `API.md` matches what the server returns. Session 1 is done: you have a complete, tested engine with monitoring and the teammate packs connected.

---

# Session 2 (next 5 to 6 hours): dashboard and demo

Start a new session, paste Prompt 0, and add: "Read API.md and RUN.md. The engine is finished; do not change anything in fusion/core, fusion/risk or fusion/maneuver unless a test fails."

| Prompt | Topic | Time | Running total |
|---|---|---|---|
| D1 | Shell, timeline, ranked table, plan card, alerts panel | 1:15 | 1:15 |
| D2 | Globe | 1:30 | 2:45 |
| D3 | Encounter view and decision map | 1:00 | 3:45 |
| D4 | Replay toggle, validation tab, briefing buttons | 0:45 | 4:30 |
| D5 | Polish and labels | 0:30 | 5:00 |
| D6 | Demo preparation and rehearsal | 1:00 | 6:00 |

Cut order if time runs short: encounter view, then the validation tab, then the replay toggle. Never cut the plan card or the decision map.

## Prompt D1: shell, timeline, table, plan card, alerts

```text
Create dashboard/ with Vite + React + TypeScript. Dark theme, one screen, no page scroll at 1920x1080. Types in src/types.ts generated from API.md. A small API client with the base URL from an env variable. Poll /events, /alerts and /monitor every 15 s.

Layout: a top bar, a left column (40%), a centre area (reserved for the globe), a right column, and a bottom card.

1. Top bar: product name, a Run button (POST /run, with "include test object" and "quick run" checkboxes), the autonomy timeline (the seven stages as steps that light up from /run/{id}/status, polled every second while running, with the latest log message underneath), and the next scheduled run from /monitor.
2. Ranked table (left): one row per event sorted by pc_max. Columns: risk colour chip with the level in text, the two names, live countdown to closest approach, miss distance, probability and worst-case probability in scientific notation, a small trend line of pc_max from history, predicted final risk if present, and a "TEST" tag when synthetic is true. Clicking a row selects the event.
3. Plan card (bottom): for the selected event, in plain language: decision; burn time with countdown; direction in words ("along the direction of travel" / "against the direction of travel") and size in mm/s; miss distance and probability before -> after; new close passes created; return burn; leftover offset; the rationale. For MONITOR and NO_ACTION show the reason.
4. Alerts panel (right, top): /alerts newest first, coloured by kind, each a single sentence, clicking selects the event; a "Run summary" link when one exists; "No alerts yet" when empty.
5. Empty, loading and error states for every panel. If the API is unreachable, a clear banner.

Risk colours must never be the only signal: always show the level as text too.
```

**Check:** you can press Run, watch the timeline fill, click the top event and read the plan.

## Prompt D2: globe

```text
Add the globe in the centre: CesiumJS through resium, with an Earth imagery layer that needs no account or token (check Cesium's documentation for the current way to set this up).
- All primaries as bright points at the current time, secondaries involved in events as dimmer points.
- For the selected event: both orbit tracks from /objects/{id}/track, a red line between the two objects, and a time slider spanning 10 minutes either side of closest approach using the positions from /events/{id}; a "Go to closest approach" button; the camera flies to the pair.
- If a plan exists: a toggle "Original / After burn" that swaps the primary's track to the manoeuvred one and shows the new miss distance.
- Positions are TEME; for display, rotate to Earth-fixed with the Greenwich sidereal angle for each timestamp (a z-rotation is accurate enough for display). Put the rotation in one function with a comment saying it is display-only.
Check the layout at 1920x1080 and at 1366x768.
```

**Check:** selecting an event flies to the pair, and the slider moves both objects through the close pass.

## Prompt D3: encounter view and decision map

```text
1. Encounter view (right, middle), Plotly, drawn only from the "encounter" object in GET /events/{id}: the plane perpendicular to the relative velocity at closest approach. The primary at the origin with its hard-body disc, the combined 1-sigma and 3-sigma uncertainty ellipses centred on the secondary's position, the miss vector, axes in km. When a plan exists, show the after-burn position as a second marker with an arrow from before to after.
2. Decision map (right, bottom), Plotly heatmap from plan.search_grid: x = burn lead time in orbits, y = signed delta-v in mm/s, colour = log10 of probability after the burn, a contour at the target probability, and a marker on the chosen burn. Title: "Every burn we considered. Marked: the smallest one that is safe."
```

**Check:** the top event shows the ellipse picture and a heatmap with one marked point that matches the plan card.

## Prompt D4: replay, validation, operator outputs

```text
1. A "2009 replay" toggle in the top bar that switches every panel to /replay/2009, with a banner "Replay: public data from 9 February 2009, 24 hours before the collision". If the day-by-day predictions file is present, show it as a small chart in the banner area. Hide the toggle when the replay run does not exist.
2. A "Validation" tab: the summary from /validation in one sentence, a scatter of our miss distance against SOCRATES' with the 1:1 line, then the validation report from teammate B's pack rendered with its charts (through /addons/files/). Hide the tab when neither exists.
3. On the plan card, when the files exist: an "Open briefing" button that renders teammate C's briefing JSON as a one-page printable view (C's pack supplies data only, no HTML), and a "Download CDM" button. Also render the run summary JSON behind the "Run summary" link.
```

**Check:** the replay toggle and validation tab show real content, or are hidden when their data is missing.

## Prompt D5: polish and labels

```text
Review the whole dashboard as a judge would see it.
- Every number has a unit; every term is plain words or has a short tooltip (closest approach, worst-case probability, along-track).
- The test object is clearly marked wherever it appears.
- Each panel has a one-line title that says what it shows.
- A footer line: "Decision support from public orbit data. Not for operational use."
- Nothing overlaps or scrolls at 1920x1080 and 1366x768; text is readable from two metres away on a projector.
- Loading and error states look deliberate.
Show me a list of what you changed.
```

**Check:** someone who has never seen the project can say what each panel shows.

## Prompt D6: demo preparation and rehearsal

```text
1. With the alert watcher running, make two consecutive real runs a few minutes apart, the second with the test object injected if the real sky has no RED event, so that the second run gets NEW and PLAN_READY alerts. Confirm the replay run and validation.json are in place.
2. Time a full run and a quick run from pressing Run to DONE on the dashboard.
3. Go through every panel and both toggles and list anything that fails or looks wrong. Fix it.
4. Write DEMO.md: the exact commands to start the server, the watcher and the dashboard, and a checklist to run 15 minutes before presenting, including making one fresh full run so the dashboard opens with current data.
5. List the five most likely failure points during a live demo and what to do for each.
```

Then, without the assistant: rehearse the 3-minute demo twice with a timer using C's script in `addons/c_ops/out/pitch/`, and record a clean screen capture as a backup. Bring a phone hotspot in case the venue's internet fails.

**Demo order:** 2009 replay (30 s) → Run on today's sky (45 s) → top event: globe, uncertainty picture, decision map, plan (75 s) → new alert in the feed, briefing opens (20 s) → validation numbers and limits (10 s).

**Check:** the whole demo runs from a cold start using only `DEMO.md`, and you know how long a run takes on stage.
