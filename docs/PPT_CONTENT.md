# Content for the Fusion 2026 presentation

**How to use this file:** it follows the six slides of the official template, in order. Put each section's text on the matching slide and keep the template's headings, logos and layout. Each slide lists the text first, then the pictures to add. Keep the wording and every number exactly as written; shorten only if a slide overflows. Items in [square brackets] must be filled in by the team.

The numbers come from running our own system on live data on 9 October 2026.

---

## Slide 1: Title

- **Problem Statement ID –** [fill in]
- **Problem Statement Title –** Autonomous Collision Avoidance for LEO Satellite Constellations
- **Team Name –** [fill in]
- **Team Leader Name –** Atharv Chaskar
- **Members Names –** [fill in three names]

---

## Slide 2: Idea Title

**Idea title:** Fusion: an autonomous traffic guard for low Earth orbit

### Proposed solution

- One pipeline that runs with no human in the loop: download public orbit data → predict every object's path for 72 hours → find close passes → rank them by collision probability → recommend an avoidance burn → check the burn is safe.
- Covers all of low Earth orbit: 29,686 tracked objects, including 9,892 pieces of debris.
- Re-runs automatically every 6 hours and raises an alert when a risk appears or gets worse.

### How it addresses the problem

- **Predicts close approaches:** finds every pass closer than 1 km between any two tracked objects.
- **Ranks by collision probability:** each pass gets a probability and a red, amber or green level, so operators see the dangerous ones first.
- **Recommends a manoeuvre:** burn time, direction and size in mm/s, for every red event where a satellite can move.

### Innovation and uniqueness

- **Verified manoeuvres:** after choosing a burn, the system re-checks the new orbit against the whole catalogue and plans the burn that returns the satellite to its slot.
- **Honest probability:** public orbit data has no error bars. We model the uncertainty and also report the worst-case probability.
- **Explainable decisions:** a decision map shows every burn the system considered and why it picked one.
- **Proven on history:** replay of the 2009 Iridium 33 – Cosmos 2251 collision using only data available before it happened.

**Pictures to add:** a dashboard screenshot showing the ranked list and the globe [to be supplied]; a small before-and-after sketch of two orbits, with and without the burn.

---

## Slide 3: Technical Approach

### Technologies

| Layer | Tools |
|---|---|
| Language | Python |
| Orbit prediction | SGP4 (`sgp4` library), the standard model for TLE data |
| Search and maths | NumPy, SciPy (KD-tree search, numerical integration, optimisation) |
| Server and scheduling | FastAPI, APScheduler |
| Dashboard | React, TypeScript, CesiumJS (3D globe), Plotly |
| Data | CelesTrak, Space-Track, ESA Collision Avoidance Challenge dataset |
| Machine learning | Gradient boosting on the ESA dataset, to predict how a warning's risk will change |
| Hardware | None needed: runs on a laptop |

### Methodology (draw this as a flow chart, left to right)

1. **Ingest:** download the latest orbits for every tracked object.
2. **Propagate:** compute all positions for the next 72 hours with SGP4.
3. **Screen:** KD-tree search every 10 seconds, then exact time and distance of closest approach.
4. **Assess:** collision probability in the encounter plane, plus the worst-case probability.
5. **Plan:** search burn times and sizes; pick the smallest burn that makes the pass safe.
6. **Verify:** re-screen the new orbit for 24 hours; plan the return burn.
7. **Monitor:** repeat every 6 hours, compare with the last run, raise alerts.

### Working prototype (measured on live data)

- Full catalogue downloaded and filtered in about 15 seconds.
- All of low Earth orbit screened for 72 hours in about 32 minutes on one laptop.
- One avoidance plan computed and safety-checked in about 75 seconds.
- 65 automated tests, including checks against textbook orbital formulas.

**Pictures to add:** the seven-step flow chart; a screenshot of the terminal or test page showing real ranked events [to be supplied].

---

## Slide 4: Feasibility and Viability

### Feasibility

- The core engine is already built and running on real data: search, probability and burn planning all work.
- Uses only free public data and open-source software.
- Needs no special hardware.

### Challenges and risks

| Challenge | Why it matters |
|---|---|
| Public orbit data is only accurate to about a kilometre | Probabilities are estimates, good for triage, not final decisions |
| The data carries no uncertainty information | Probability cannot be computed without it |
| Tens of thousands of objects | Checking every pair directly is far too slow |
| Dangerous real events are rare and often only hours away | Hard to demonstrate a full avoidance on a given day |
| Dependence on external data services | A failed download stops a run |

### How we overcome them

- **Accuracy:** report the worst-case probability alongside the estimate, and state the limits openly.
- **Uncertainty:** model it by object type and data age, and measure it from orbit history.
- **Scale:** a KD-tree search with straight-line pruning cuts the work to minutes.
- **Rare events:** a clearly labelled test object and the 2009 replay show the full loop on demand.
- **Data services:** caching, retries and clear failure messages; the last good result stays on screen.

**Pictures to add:** a small chart of position error growing with data age [from teammate's pack, if ready].

---

## Slide 5: Impact and Benefits

### Impact

- **Safer orbits:** one collision can create thousands of fragments that threaten other satellites for decades. The 2009 collision's debris still crosses busy orbits today.
- **Less work for operators:** on 9 October 2026 our system found about 57 passes closer than 1 km every hour across low Earth orbit. It marks only a few of them red, so teams can focus on those.
- **Faster response:** a recommended burn is ready as soon as a risk is found, with its cost and its safety check.

### Benefits

- **For satellite operators:** fewer missed warnings, less fuel wasted on unnecessary manoeuvres, burns measured in millimetres per second.
- **For small operators and universities:** a free tool built on public data, with no paid tracking service needed.
- **For the space environment:** fewer collisions means less new debris.
- **For trust:** every recommendation can be traced, checked and explained.

**Pictures to add:** a globe view showing debris and satellites together [screenshot to be supplied]; a simple before-and-after bar: all warnings versus red warnings.

---

## Slide 6: Research and References

### Data sources

- CelesTrak, current orbital element sets: https://celestrak.org/NORAD/elements/
- ESA Collision Avoidance Challenge dataset: https://zenodo.org/records/4463683
- Space-Track, full catalogue of tracked objects: https://www.space-track.org
- CelesTrak SOCRATES conjunction reports, used to validate our results: https://celestrak.org/SOCRATES/

### Methods

- Hoots, F. R. and Roehrich, R. L., "Spacetrack Report No. 3: Models for Propagation of NORAD Element Sets", 1980.
- Vallado, D. A., Crawford, P., Hujsak, R. and Kelso, T. S., "Revisiting Spacetrack Report #3", AIAA 2006-6753, 2006.
- Foster, J. L. and Estes, H. S., "A Parametric Analysis of Orbital Debris Collision Probability and Maneuver Rate for Space Vehicles", NASA JSC-25898, 1992.
- Alfano, S., "Relating Position Uncertainty to Maximum Conjunction Probability", Journal of the Astronautical Sciences, 2005.
- Clohessy, W. H. and Wiltshire, R. S., "Terminal Guidance System for Satellite Rendezvous", Journal of the Aerospace Sciences, 1960.
- Uriot, T. et al., "Spacecraft Collision Avoidance Challenge: Design and Results of a Machine Learning Competition", Astrodynamics, 2022.
- CCSDS 508.0-B-1, "Conjunction Data Message", Recommended Standard.

### Software

- python-sgp4 by Brandon Rhodes: https://pypi.org/project/sgp4/
- SciPy, NumPy, FastAPI, CesiumJS.

**Pictures to add:** none needed.

---

## Notes for whoever builds the slides

- Do not add statistics that are not in this file. If a slide needs one more fact, leave a marked gap for the team.
- Say "collision probability" and "close pass", not "guaranteed collision": the system estimates risk, it does not predict collisions with certainty.
- The 2009 replay and the dashboard are still being built. If they are not ready when the slides are due, remove the replay bullet on slide 2 and use the flow chart in place of the dashboard screenshots.
