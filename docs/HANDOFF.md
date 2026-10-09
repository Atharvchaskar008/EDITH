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
| Protected satellites | Configurable list `PRIMARY_GROUPS` in `fusion/config.py`. Starts as `iridium-NEXT` for speed; widen to more constellations or all active LEO once run time is measured (prompt 9). No code may assume Iridium |
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

Atharv wants about 50 commits over the whole project, in plain natural language (for example "Add the close-approach search with a KD-tree coarse pass"). So: commit small and often, one logical step per commit, roughly 3 to 5 per prompt, each with tests passing. Push to `origin main` after each prompt.

## Environment

- Windows 11, PowerShell. Python 3.14 in `.venv` (`.venv\Scripts\python`). Packages in `requirements.txt` are installed; `sgp4` runs with its fast compiled backend.
- Node 24 is installed for the dashboard later.

## Progress

| Prompt | Status |
|---|---|
| 1 Scaffold, contracts, fixtures | In progress: `config.py`, `contracts.py`, `frames.py` and their tests are done. Still to do: `fusion/synthetic.py` (test object generator), `data/fixtures/` sample files, empty module folders |
| 2–12 | Not started |
| D1–D6 | Not started |

**Next step:** finish prompt 1 (the synthetic test object and fixtures, as described in `docs/harness_ATHARV.md`), then prompt 2.
