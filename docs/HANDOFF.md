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
| 1 Scaffold, contracts, fixtures | Done except the sample files in `data/fixtures/` (they need real objects, so make them at the end of prompt 2 from a real download) |
| 2 Ingest and propagate | Not started. Helpers already exist in `fusion/core/sat.py` |
| 3 Screen and refine | Not started. The exact closest-approach step already exists in `fusion/core/refine.py` |
| 4–12 | Not started |
| D1–D6 | Not started |

## What exists in the code (20 tests passing)

| File | What it does |
|---|---|
| `fusion/config.py` | Every tunable number |
| `fusion/contracts.py` | Pydantic models: `SpaceObject`, `ConjunctionEvent`, `ManeuverPlan`, `Alert`; `risk_level_for()` |
| `fusion/frames.py` | RTN basis, vector and covariance rotation |
| `fusion/core/sat.py` | `satrec_from_omm`, `get_satrec(obj)` (cached), `state_at`, `state_at_offset`, `period_s`, `perigee_apogee_km`, `object_from_omm`, `state_to_omm`, `fit_omm_to_state` |
| `fusion/core/refine.py` | `closest_approach(sat1, sat2, t_lo, t_hi)`: exact time and distance of closest approach |
| `fusion/core/spacetrack.py` | `load_leo_objects()`: every tracked LEO object from Space-Track, cached; returns nothing when `.env` has no login. Tested with a fake session only; the query has not yet run against the live service, so check the first real response. `load_catalog` in prompt 2 must merge these with the CelesTrak groups, de-duplicated by `norad_id` |
| `fusion/synthetic.py` | `make_conjunction(primary, t_tca, miss_km)`: labelled test object passing a chosen distance from a real satellite |
| `tests/conftest.py` | Made-up Iridium-like test satellite (`primary` fixture) |

Notes for whoever continues:

- A `SpaceObject` stores its raw OMM record in `.omm`; always get its `Satrec` with `get_satrec(obj)`. Never build a `Satrec` any other way, so saved objects reproduce the same orbit.
- `make_conjunction` takes a crossing angle between the two velocity vectors, not an inclination as the prompt text says. The test object lands within centimetres of the requested miss distance.
- For bulk propagation in prompt 2 use `sgp4.api.SatrecArray` over `get_satrec(obj)` for each object.

**Next step:** prompt 2 in `docs/harness_ATHARV.md` (download the catalogue and vectorised propagation), then create the fixture files, then prompt 3.
