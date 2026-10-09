# Teammate A: history, the 2009 replay and the reference test kit

**Your assistant:** Opus 5.5. **Time:** 7 hours. **Your folder:** `addons/a_history/`.

## What you are doing and why

Our team is building a system that predicts close approaches between satellites and recommends avoidance burns. Atharv is building the complete working system alone. You are building an add-on pack that makes it win:

1. **The 2009 replay.** The real collision of Iridium 33 and Cosmos 2251, reconstructed from the public data available before it happened. This opens our demo.
2. **A history of orbit data**, which the live system cannot get by itself.
3. **Real object sizes and types** for every object in the catalogue.
4. **A reference test kit**: orbit pairs with known answers that Atharv's engine can be checked against.

Your work is fully independent. You never need Atharv's code, and Atharv never waits for you. Everything you produce is a file or a function in your own folder. It is added on top of the finished system at the end.

## How to work

1. Create the folder and environment once:
   ```
   mkdir addons\a_history
   cd addons\a_history
   python -m venv .venv
   .venv\Scripts\activate
   pip install sgp4 numpy scipy requests pandas matplotlib pytest
   ```
2. Create a free account at `https://www.space-track.org` (needed from prompt 2). Put the login in a file called `.env` in your folder and never commit it.
3. Open a new session with your assistant in this folder. Paste **Prompt 0** first, every time you start a new session.
4. Paste the prompts in order, one at a time. After each one, run the **check**. If it fails, paste the error back to the assistant. Move on only when the check passes.
5. If your assistant can run commands itself, let it. If it is chat-only, run what it gives you and paste back the output.
6. Commit after each prompt.
7. If a prompt is stuck for more than 20 minutes past its time box, write what happened in `README.md` and move to the next. Prompts 1, 3 and 4 matter most.

| Prompt | Topic | Time |
|---|---|---|
| 1 | TLE snapshot collector | 0:30 |
| 2 | Space-Track history client | 1:00 |
| 3 | 2009 replay data | 1:00 |
| 4 | 2009 day-by-day analysis and replay file | 1:30 |
| 5 | Catalogue enrichment | 1:00 |
| 6 | Reference test kit | 1:15 |
| 7 | Debris statistics, packaging | 0:45 |

## Prompt 0: context (paste at the start of every session)

```text
You are helping me build an add-on pack for a satellite collision-avoidance project. Another person is building the main system; my work must be fully standalone and must not assume any of their code exists.

Rules for everything you write:
- Python 3.11, type hints, small functions, pytest tests for every module.
- All code lives in the current folder (addons/a_history/). Outputs go in ./out/. Raw downloads are cached in ./cache/ and never downloaded twice.
- Orbit propagation uses the `sgp4` Python package only. Positions are in the TEME frame, in km and km/s. Times are UTC, ISO 8601 with a trailing Z in JSON.
- Objects are identified by NORAD catalogue number as an int.
- RTN frame: R = unit position vector, N = unit(r x v), T = N x R.
- Never invent data, column names, API parameters or results. If you are not sure how an API or file is structured, fetch it and print what is there before writing code against it.
- Never claim something works unless you ran it and showed me the output.
- Be polite to data providers: cache every response, and never loop one web request per object.

A space object is stored in this JSON shape everywhere:
{ "norad_id": 43070, "name": "IRIDIUM 106", "object_type": "PAYLOAD",
  "tle_line1": "...", "tle_line2": "...", "epoch": "2026-10-09T03:11:05Z",
  "perigee_km": 776.2, "apogee_km": 779.8, "is_primary": true,
  "operational": true, "radius_m": 2.0 }
object_type is one of PAYLOAD, DEBRIS, ROCKET_BODY, UNKNOWN.

Confirm you understand and wait for my first task.
```

## Prompt 1: TLE snapshot collector

```text
Write snapshot.py.

It downloads these CelesTrak groups: iridium-NEXT, active, cosmos-2251-debris, iridium-33-debris, fengyun-1c-debris, from
https://celestrak.org/NORAD/elements/gp.php?GROUP=<group>&FORMAT=json
and saves each response unchanged to ./snapshots/<UTC timestamp>/<group>.json.

Requirements:
- One request per group, 2 seconds apart, with a clear User-Agent and a 30 s timeout.
- If a snapshot folder younger than 2 hours exists, do nothing and say so.
- Print a one-line summary: timestamp, objects per group.
- Add load_snapshot(path) -> list[dict] that returns objects in the JSON shape from the context, computing perigee_km and apogee_km from mean motion and eccentricity, is_primary = True for the iridium-NEXT group, object_type from the name (contains "DEB" -> DEBRIS, contains "R/B" -> ROCKET_BODY, otherwise PAYLOAD), de-duplicated by norad_id.
- Note that the JSON (OMM) format has no TLE lines. Build an sgp4 Satrec from the OMM fields using the sgp4.omm module, and produce tle_line1 and tle_line2 with sgp4.exporter.export_tle when the catalogue number is below 100000, otherwise leave them null and keep the raw OMM dict under the key "omm".
- Tests: perigee/apogee for a known circular orbit; de-duplication; load of a small saved sample.

Then give me the exact Windows Task Scheduler command to run it twice a day.
Run it once now and show me the summary.
```

**Check:** `python snapshot.py` prints object counts, and `snapshots/` contains five JSON files. Schedule it straight away.

## Prompt 2: Space-Track history client

```text
Write spacetrack.py: a small client for https://www.space-track.org.

First, read the Space-Track API documentation pages for how to log in and how to query the gp_history class, and tell me what you found before writing code. Do not guess the URL structure.

Requirements:
- Read the username and password from a .env file. Never print them.
- One session with login; reuse the cookie.
- A hard rate limiter: at most 20 requests per minute and 200 per hour, enforced in code.
- Every response cached on disk under ./cache/spacetrack/ keyed by the query, and never requested again.
- history(norad_ids: list[int], start: str, end: str) -> list[dict]: all element sets for those objects with epoch in the range, oldest first, many ids in ONE query (chunks of at most 50 ids).
- Convert results to the JSON object shape from the context.

Then write history.py with tle_history(norad_id: int, days: int = 30) -> list[dict], oldest first, which merges our own ./snapshots/ with Space-Track history, de-duplicated by epoch.

Finally fetch and cache 30 days of history for all Iridium NEXT satellites (ids from the latest snapshot) and for 200 randomly chosen objects from the three debris groups. Save the merged result as ./out/history_sample.json and print how many element sets each group has.

Tests: rate limiter with a fake clock; cache hit avoids a request (mock the HTTP layer); de-duplication.
```

**Check:** `out/history_sample.json` exists, and the printed count shows multiple element sets per object.

## Prompt 3: 2009 replay data

```text
We are reconstructing a real event. On 10 February 2009 at about 16:56 UTC, the satellites Iridium 33 (NORAD 24946) and Cosmos 2251 (NORAD 22675) collided.

Using spacetrack.py:
1. Fetch every element set for both objects with epoch from 2009-01-25 to the collision time. Print the epochs so I can see them. Discard any element set with an epoch after 2009-02-10T16:56Z, because those describe debris, not the intact satellites.
2. Fetch background traffic: element sets with epoch between 2009-02-08 and 2009-02-10 for objects whose orbit crosses 700-900 km altitude. Check the API documentation for the right field names for perigee and apogee before querying. Keep one element set per object (the latest before 2009-02-10T00:00Z). If the query is rejected or is too large, split it by altitude band; if it still fails, tell me and continue without background traffic.
3. Save ./out/replay_2009.json:
   { "collision_time_reported": "2009-02-10T16:56:00Z",
     "primary": [...all pre-collision element sets for 24946, oldest first...],
     "secondary": [...same for 22675...],
     "background": [...one element set per background object...] }
   All in the JSON object shape. Iridium 33 has is_primary true and operational true. Cosmos 2251 was a dead satellite: object_type PAYLOAD, operational false.

Print: number of element sets for each of the two satellites, and the number of background objects.
```

**Check:** both satellites have several element sets in early February 2009, and none are after the collision time.

## Prompt 4: day-by-day analysis and the replay file for the dashboard

```text
Write replay_analysis.py using only sgp4, numpy and scipy.

Part 1: closest approach function.
closest_approach(obj_a, obj_b, t_start, t_end) -> dict with tca (UTC), miss_distance_km, relative_speed_kms, r and v of both objects at TCA, and miss_rtn_km (position of b relative to a in a's RTN frame).
Method: sample both orbits every 10 s, find local minima of distance, refine each with scipy.optimize.minimize_scalar (bounded, +-15 s), return the global minimum in the window.
Tests: at the returned TCA the relative position is perpendicular to the relative velocity (dot product ~ 0); two copies of one orbit shifted in time give the expected separation.

Part 2: what would a system have seen each day?
For each day D from 7 days before the collision to the day of the collision: take the latest element set of each satellite with epoch before D 00:00 UTC, and compute the closest approach in the window 2009-02-10T16:00Z to 17:30Z. Record prediction_time, the age in days of each element set, predicted TCA and predicted miss distance.
Save as ./out/replay_2009_predictions.json and plot predicted miss distance against days before collision as ./out/replay_2009_predictions.png.
Report the numbers honestly whatever they are. Do not adjust anything to make the miss look smaller.

Part 3: replay trajectories for a 3D display.
Using the last pre-collision element sets, save ./out/replay_2009_tracks.json with positions of both satellites every 5 s from TCA - 20 minutes to TCA + 5 minutes, plus one full orbit of each at 30 s steps. TEME km, with UTC timestamps.

Part 4: write ./out/replay_2009_notes.md, about 150 words, in plain language: what the public data showed on each day, how close the predicted pass was, and what that implies about warning time. Only use numbers from the JSON you produced.
```

**Check:** the PNG exists, the predictions JSON has about eight rows, and the notes quote the same numbers as the JSON. This is the most important output of your pack; read the notes yourself and make sure they make sense.

## Prompt 5: catalogue enrichment

```text
Write enrich.py.

CelesTrak publishes a satellite catalogue (SATCAT) as CSV. Find the download link from https://celestrak.org/satcat/ , download it once into ./cache/, then print its column names and five sample rows, and show me before writing any more code.

Then implement enrich_catalog(objs: list[dict]) -> list[dict]:
- Match on NORAD catalogue number.
- object_type from the catalogue's object type field, mapped to PAYLOAD, DEBRIS, ROCKET_BODY or UNKNOWN.
- operational from the catalogue's operational status field. Explain the status codes you found and which ones you treat as operational.
- radius_m from the radar cross-section field if it is present and numeric: treat RCS as the area of a disc and take the radius, clipped to the range 0.05 m to 15 m. If it is missing, use 0.5 m for DEBRIS, 2.0 m for ROCKET_BODY and 2.0 m for PAYLOAD.
- Never drop an object. Objects not found in the catalogue come back unchanged with radius_m defaulted.

Run it on the latest snapshot and save ./out/catalog_enriched.json. Print a table: count per object_type, how many are operational, how many had a real RCS value, and the median radius per type.

Tests: every input comes back; an Iridium NEXT satellite is PAYLOAD and operational; a missing catalogue number keeps defaults.
```

**Check:** `out/catalog_enriched.json` has the same number of objects as the snapshot, and the printed table looks sensible (Iridium NEXT are operational payloads).

## Prompt 6: reference test kit

```text
Build a test kit that someone else can use to check their conjunction-screening code without seeing mine. Write make_testkit.py using sgp4 only.

Create synthetic satellites directly from orbital elements with Satrec.sgp4init (WGS72, mode 'i'), all at about 780 km altitude, and export them as TLE lines.

Build these cases, each as a pair (or small group) of objects plus the exact expected answer computed with closest_approach from replay_analysis.py at a 1 s sampling step:
1. Crossing orbits with a miss of about 300 m (near head-on, inclination 86.4 deg against 74 deg).
2. Crossing with a miss of about 2 km.
3. Crossing with a miss of about 8 km (must NOT be reported at a 5 km threshold).
4. Same orbit, 500 km apart along-track (must NOT be reported: relative speed near zero).
5. Two close approaches of one pair within 72 hours (both must be found).
6. A fast crossing that lasts under 10 seconds inside 5 km (catches code whose time step is too coarse).
7. One primary against 50 background objects where exactly 3 come within 5 km.

To hit a target miss distance, adjust the mean anomaly of the second object iteratively and say how you did it.

Save ./out/testkit/cases.json: for each case the objects in the JSON object shape, the screening start time, window length in hours, threshold_km, and expected_events as a list of {primary_id, secondary_id, tca, miss_distance_km, relative_speed_kms}.
Write ./out/testkit/README.md explaining in ten lines how to run someone's screen function against the cases and what tolerance to accept (TCA within 0.5 s, miss within 10 m).
Write ./out/testkit/check.py with a function check(screen_fn) that runs all cases against any function with the signature screen(catalog, t0, hours, threshold_km) -> list of dicts, and prints pass/fail per case. Prove it works by passing in a simple brute-force screen you write yourself.
```

**Check:** `python out/testkit/check.py` prints seven passes with your own brute-force screen.

## Prompt 7: debris statistics and packaging

```text
Part 1: write debris_stats.py. From the latest snapshot, compute for the pitch:
- how many catalogued fragments from the 2009 collision (groups cosmos-2251-debris and iridium-33-debris) are still in orbit today,
- how many of them have an altitude band (perigee to apogee) that overlaps the Iridium NEXT band,
- the same two numbers for fengyun-1c-debris,
- a histogram of fragment count against altitude with the Iridium NEXT band shaded, saved as ./out/debris_altitude.png.
Save the numbers as ./out/debris_stats.json. Only report what the data shows.

Part 2: write README.md for this folder:
- one paragraph on what the pack contains,
- a table of every file in ./out/ with one line on what it is and how the main system uses it,
- a five-line usage example for each of: load_snapshot, tle_history, enrich_catalog, closest_approach, check,
- a "known gaps" section listing anything that failed or was skipped, honestly.

Part 3: run the whole test suite and show me the output. Fix failures.
```

**Check:** `pytest` passes, `README.md` lists every output file, and the debris numbers are in `out/debris_stats.json`.

## When you finish

You never need anything from Atharv, and you do not need to send, explain or hand over anything to Atharv. Put the finished `addons/a_history/` folder (without `.env` and `.venv`) in the team's shared project. Your `README.md` must explain everything by itself. The pieces that plug into the main system:

| File | Use |
|---|---|
| `out/replay_2009.json`, `replay_2009_tracks.json`, `replay_2009_predictions.*`, `replay_2009_notes.md` | The demo's opening |
| `out/catalog_enriched.json`, `enrich.py` | Real sizes and status for every object |
| `history.py`, `out/history_sample.json`, `snapshots/` | Orbit history |
| `out/testkit/` | Independent check of Atharv's engine |
| `out/debris_stats.json`, `debris_altitude.png` | Pitch slide |