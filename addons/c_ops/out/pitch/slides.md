# Pitch Deck: Autonomous Satellite Conjunction Triage & Manoeuvre Planning

---

## Slide 1: The Collision Crisis in Low Earth Orbit

- February 2009: Iridium 33 collided with inactive Cosmos 2251 at 11 km/s.
- Thousands of conjunction warnings overload satellite flight dynamics teams every single day.
- Operators urgently need automated triage before critical close approach windows close.

**Speaker Notes:**
In 2009, an active Iridium satellite slammed into an abandoned Russian Cosmos satellite, creating thousands of lethal debris fragments that orbit Earth to this day. Today, satellite constellations are growing exponentially while flight dynamics operations remain bottlenecked by small human teams. Flight operators receive hundreds of false alarms daily, leaving them paralyzed by alert fatigue and uncertainty. Without autonomous screening and rapid triage, the risk of a catastrophic orbital cascade increases every week.

---

## Slide 2: What We Built: End-to-End Autonomous Conjunction Triage

- An automated pipeline transforming raw orbital data into actionable collision decisions.
- Full cycle: download orbits, predict trajectories, compute risk, and verify manoeuvres.
- Live background monitoring continuously alerts operators to high-risk trajectory changes.

**Speaker Notes:**
We built an autonomous end-to-end decision support platform that ingests orbital data and handles conjunction management from start to finish. Our pipeline downloads fresh two-line elements, propagates trajectories, screens for close passes, and computes rigorous collision probabilities. When risk exceeds safety thresholds, the engine synthesizes an optimal avoidance burn and calculates a return burn that maintains mission orbit. Finally, our monitoring engine watches for newly emerging threats and delivers standard-format operator alerts.

---

## Slide 3: Live Demonstration: Four Key Operational Steps

- Step 1: Historical validation recreating the catastrophic 2009 Iridium-Cosmos encounter.
- Step 2: Live screening of today's operational satellite constellation orbits.
- Steps 3 and 4: Automated manoeuvre planning, live alerts, and operator briefings.

**Speaker Notes:**
Today we will walk you through four operational scenarios in our live environment. First, we replay the 2009 Iridium collision to demonstrate that our system catches the collision days in advance. Next, we run live screening across today's active sky, populating an interactive timeline and inspecting the top conjunction with its verified burn plan. Finally, we show our alert feed and one-page briefing generated automatically for flight controllers.

---

## Slide 4: Rigorous Validation Against Independent Benchmarks

- Conjunction geometry validated against CelesTrak SOCRATES: [VALIDATION NUMBERS FROM TEAMMATE B].
- Probability trends benchmarked on 162,634 real European Space Agency warnings.
- Empirical position uncertainty calibrated from historical telemetry: [VALIDATION NUMBERS FROM TEAMMATE B].

**Speaker Notes:**
Our system is grounded in empirical verification rather than unvalidated assumptions. We benchmarked our close approach geometry against CelesTrak SOCRATES calculations, achieving [VALIDATION NUMBERS FROM TEAMMATE B]. Our risk model was trained and evaluated on 162,634 real Conjunction Data Messages from ESA's Space Debris Office. Furthermore, our covariance bounds reflect measured satellite position dispersion rather than arbitrary spherical covariance assumptions.

---

## Slide 5: Key Architectural Differentiators for Real Operators

- Constellation-level protection screening thousands of satellites simultaneously without human lag.
- Closed-loop avoidance manoeuvres featuring fuel-optimal burns and guaranteed return burns.
- Standard CCSDS Conjunction Data Message exports and shift-ready JSON briefings.

**Speaker Notes:**
Unlike traditional tools that analyze pairs in isolation, we provide coordinated protection across entire commercial constellations. Our manoeuvre planner does not just dodge the primary object; it verifies secondary conjunction clearances and includes a return burn. We provide live change-detection alerts that notify operators when risk escalates between orbital updates. All outputs export directly to international CCSDS standards and machine-readable briefing packages.

---

## Slide 6: System Limits and Operational Boundaries

- Public two-line element tracking accuracy is limited to approximately one kilometre.
- Probabilities serve as triage recommendations rather than certified flight telemetry.
- Advisory decision support only: zero autonomous burn commands sent to spacecraft.

**Speaker Notes:**
We believe in complete transparency regarding the operational limits of public space surveillance data. Public TLE orbits have inherent uncertainties on the order of hundreds of metres to one kilometre. Therefore, our risk scores and machine learning predictions are designed strictly for screening and operational triage. Crucially, the system functions purely as an advisory tool and never transmits commands directly to orbiting satellites.

---

## Slide 7: Future Roadmap: Autonomous Space Traffic Management

- Ingestion of high-precision radar tracking and operator-supplied ephemeris covariance files.
- Multi-constellation coordination resolving simultaneous manoeuvres between competing commercial fleets.
- Direct integration into ground station command pipelines for execution: [FACT NEEDED: partners].

**Speaker Notes:**
Our next phase expands beyond public TLE data to ingest precision owner-operator ephemerides and commercial radar feeds. We are architecting multi-operator negotiation protocols so satellites from different constellations can safely deconflict avoidance burns. We also plan to integrate our verified manoeuvre plans into standard ground station mission planning workflows. Our ultimate goal is building the autonomous traffic management infrastructure necessary for a sustainable orbital economy.
