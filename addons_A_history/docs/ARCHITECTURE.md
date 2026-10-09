# Fusion: final architecture

Autonomous collision avoidance for the Iridium NEXT constellation, built on public TLE data. `CONTRACTS.md` holds the exact data shapes; `harness_ATHARV.md` is the build sequence for the main project; the three teammate files describe the add-on packs.

## How the work is organised

Atharv builds the **main project**, end to end: it finds close passes, ranks them, recommends and verifies a burn, and shows it on a dashboard.

Each teammate builds an **add-on pack** in a separate folder. The packs never touch the main project and need nothing from it. Nobody builds the same thing twice: the main project only connects to the packs' finished output and displays it. A feature whose pack is missing is simply absent.

| Who | Builds | Role |
|---|---|---|
| Atharv | Engine, pipeline, server, scheduler, dashboard, test object for the demo | The product |
| A | `addons/a_history`: replay depth, real object sizes, orbit history, test kit | Better data, stronger opening |
| B | `addons/b_trust`: measured uncertainty, reference calculator, ESA and SOCRATES validation, robustness | Proof the numbers are right |
| C | `addons/c_ops`: alert feed and run summaries, briefings, standard-format messages, prediction model, pitch | Operations polish and the pitch |

## System at a glance

```
 DATA                         MAIN PROJECT (Atharv)                          ADD-ON PACKS (optional)
 ───────────────             ────────────────────────────────────────       ──────────────────────────────
 CelesTrak GP   ───────────► 1 INGEST      catalogue                  ◄──── A: real sizes and status
                                  ▼
                             2 PROPAGATE   SGP4, 72 h
                                  ▼
                             3 SCREEN      altitude filter → KD-tree  ◄──── A: test kit (check only)
                                           → exact closest approach
                                  ▼
                             4 ASSESS      uncertainty → Pc, Pc max   ◄──── B: measured uncertainty
                                           → risk level               ◄──── C: predicted final risk
                                  ▼
                             5 PLAN        search burns, pick the
                                           cheapest safe one
                                  ▼
                             6 VERIFY      re-screen new orbit,
                                           return burn
                                  ▼
                             run folder    data/runs/<run_id>/*.json  ────► C: watcher → alerts, history,
                                  ▼                                            summaries, briefings, CDM files
                             SERVER        FastAPI + 6-hour scheduler
                                  ▼
                             DASHBOARD     timeline, ranked table, globe, encounter view,
                                           decision map, plan card, alerts, validation, replay

                             REPLAY        same pipeline, t0 = 9 Feb 2009 ◄── A: 2009 data and history
                             VALIDATION    display only                   ◄── B: comparison and report
```

The only links between the main project and the packs are three optional function hooks in `fusion/addons.py` and the run folder on disk. Every hook has a fallback, so a missing or broken pack changes nothing.

## Locked decisions

| Topic | Decision | Reason |
|---|---|---|
| What we protect | Any list of CelesTrak groups, set in config: one constellation, several, or all active LEO satellites, each screened against the rest of the catalogue | The problem covers all of LEO; the protected set is a setting, and only run time limits its size. Development starts with Iridium NEXT (fast, ties to the 2009 collision) |
| Look-ahead | 72 hours | TLE predictions degrade quickly beyond a few days |
| Propagator | SGP4 (`sgp4` package, vectorised) | It is the model TLEs are made for |
| Frame and units | TEME, km, km/s, UTC everywhere | No conversions between modules means no conversion bugs |
| Screening | Altitude-band filter, then KD-tree every 10 s, then exact refinement | Avoids checking every pair, cannot miss a fast crossing |
| Uncertainty | Assumed table built in; B's measured values used where present | TLEs carry no covariance; the project must not wait for the measurement |
| Probability | 2D encounter-plane integral, reported with worst-case `pc_max` | Standard method; `pc_max` protects against our uncertainty being wrong |
| Ranking key | `pc_max`, descending | Same convention as SOCRATES |
| Maneuver | Along-track burn, grid search over lead time and size, cheapest burn reaching Pc < 1e-6 | Fuel-efficient direction; the grid doubles as the decision map |
| Burn on an SGP4 orbit | Difference method (burned minus unburned numerical orbit, added to SGP4) | A delta-v cannot be applied to a TLE directly |
| Safety check | Re-screen the new orbit against the full catalogue, then a return burn | Makes the recommendation trustworthy |
| Monitoring | Full pipeline every 6 hours, alerts on new or worsening events | Orbit data only updates a few times a day |
| Test object | A clearly labelled synthetic object can be injected | Real high-risk events are rare; the demo must not depend on luck |
| Storage | One folder per run, JSON files, `DONE` marker last | No database; the previous run stays visible while a new one is in progress |
| Stack | Python 3.11, numpy, scipy, sgp4, pydantic, FastAPI, APScheduler; React, CesiumJS, Plotly | Proven and free |

## Run modes

- **Live:** the scheduler or the Run button runs the pipeline on fresh data.
- **Replay:** the same pipeline with `t0` on 9 February 2009 and the historical TLEs.

## Milestones for the main project

| After prompt | You have |
|---|---|
| 6 | A working answer to the problem statement in the terminal |
| 9 | The full product on the dashboard with live data |
| 10 | A's pack connected: the 2009 replay, real sizes |
| 11 | B's and C's packs connected: measured uncertainty, validation, alerts, briefings |
| 12 | A rehearsed live demo |

## Out of scope

- Sending commands to real satellites.
- High-precision orbit determination, drag or space-weather modelling.
- Screening every object against every other object.
- Anything needing paid or restricted data.

## Known limits (say these in the pitch)

- TLE accuracy is roughly a kilometre, so probabilities are estimates for triage, not operational values.
- Uncertainty is measured or modelled by us; it is not supplied with the data.
- Other operators' planned maneuvers are unknown to us.
