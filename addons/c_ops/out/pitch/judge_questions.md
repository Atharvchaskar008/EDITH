# 15 Hardest Judge Questions and Honest Operational Answers

---

### Q1: Where does your collision probability come from when public TLEs contain no covariance matrices?
**Answer:** Because standard Two-Line Element (TLE) sets do not publish covariance matrices, we calibrate empirical position uncertainty ellipsoids from historical orbital dispersion and maximum probability formulations (such as Alfano/Foster max Pc). We also support operator-supplied covariance matrices when available, falling back to conservative bounding ellipsoids for public debris catalogue objects. This ensures that every conjunction produces a mathematically consistent probability bound for operational screening rather than an ungrounded guess.

---

### Q2: How accurate are public TLEs, and how does that affect your collision risk assessment?
**Answer:** Public TLEs propagated with SGP4 typically have position errors on the order of several hundred metres to approximately one kilometre, depending on object altitude, atmospheric drag activity, and time since last epoch observation. Because of this intrinsic uncertainty, our collision probabilities are designed specifically for triage and risk prioritization rather than certified sub-metre close encounters. As closer tracking passes become available within 24 to 48 hours of TCA, the uncertainty bounds shrink, allowing operators to make well-informed manoeuvre commitments.

---

### Q3: Why should an operator trust your recommended avoidance manoeuvre?
**Answer:** Our manoeuvre optimization engine evaluates hundreds of burn geometries to identify the minimum-energy impulse that guarantees safe miss distance clearance while verifying that the new trajectory does not generate secondary conjunctions. Every recommended burn includes explicit timing, directional orientation (e.g. along-track), delta-v magnitude, and post-manoeuvre miss distance predictions. Crucially, the platform serves as an advisory decision support tool; no commands are sent to spacecraft without human-in-the-loop validation and operator approval.

---

### Q4: What happens if the other object also manoeuvres simultaneously to avoid your satellite?
**Answer:** If the conjunction is with another active, manoeuvrable satellite rather than passive space debris, independent bilateral burns risk deconflicting into each other or worsening the encounter geometry. Our system generates standard CCSDS 508.0 Conjunction Data Messages (CDMs) to enable rapid inter-operator communication through established orbital data exchanges. In future operational iterations, we intend to integrate multi-operator coordination protocols to establish clear right-of-way rules before burn execution.

---

### Q5: Why only one constellation instead of protecting all satellites globally?
**Answer:** Commercial satellite constellation operators manage fleets of dozens to thousands of identical satellites and bear direct operational responsibility and fuel budgets for maintaining their specific orbital planes. Constellation operators have proprietary telemetry and thruster control over their own spacecraft, but zero control over passing third-party debris. Our architecture solves the constellation operator's daily pain point: screening their entire operational fleet against the entire public debris catalog and finding fuel-optimal avoidance and return burns.

---

### Q6: Why build a machine learning model for risk prediction, and did it actually beat the baseline?
**Answer:** We trained a gradient boosting model on 162,634 real European Space Agency warnings to predict whether early conjunction alerts (available 2+ days before TCA) will escalate or fade away. On continuous risk prediction, our model cuts Mean Absolute Error by 47% compared to the baseline (MAE 2.67 vs 5.08, and RMSE 5.04 vs 9.53). However, for binary threshold triage at the critical 10⁻⁶ risk level, early warnings remain noisy and the simple persistence baseline achieved higher recall (0.78 vs 0.22, F2 0.35 vs 0.20), which we report transparently.

---

### Q7: How does this differ from existing services like LeoLabs or Slingshot?
**Answer:** Established commercial tracking services focus primarily on operating independent ground radar networks and selling raw tracking data feeds. Our platform operates as an autonomous decision support layer that transforms raw orbits into end-to-end operational actions, including automated delta-v synthesis, return burn planning, and live drift-detection alerts. We are sensor-agnostic and designed to ingest public TLEs, commercial radar observations, or owner-operator ephemerides interchangeably.

---

### Q8: What would be needed for real operations in certified orbital environments?
**Answer:** Moving from advisory decision support to certified flight operations requires ingesting high-precision numerical orbit propagators (accounting for high-order gravity fields and solar radiation pressure) and calibrated radar covariances. It also requires integrating with operator ground station communication APIs, hardware propulsion limitations, and formal flight software qualification standards (e.g., ECSS or NASA software assurance). In our current architecture, the platform operates safely as an operator assistant that flags events and prepares briefing files without commanding spacecraft.

---

### Q9: How do you handle unmodeled non-conservative forces, such as atmospheric drag spikes during solar storms?
**Answer:** Atmospheric drag fluctuations are the largest source of along-track orbital error in Low Earth Orbit, especially during solar storm events. In our analysis of ESA's dataset, space weather indices (F10.7 solar flux and geomagnetic AP) are directly correlated with covariance inflation along the in-track direction. Our operational pipeline dynamically widens along-track position uncertainty when orbit update ages exceed 24 hours, ensuring that avoidance burns provide robust clearance even under drag perturbations.

---

### Q10: What is your screening latency when analyzing thousands of constellation passes?
**Answer:** Our pipeline utilizes vectorized filters—including apogee/perigee altitude filtering and orbital plane intersection screening—to eliminate 99.9% of non-threatening pairs before running detailed numerical conjunction checks. On a standard multi-core machine, full screening of our test constellation against the public catalog completes in [VALIDATION NUMBERS FROM TEAMMATE B: e.g. < 60 seconds]. This low latency allows flight teams to re-screen the entire operational sky immediately whenever Space-Track publishes fresh orbital data.

---

### Q11: How do you guarantee that an avoidance burn does not accidentally create a secondary collision?
**Answer:** When synthesizing an avoidance burn, the candidate post-burn trajectory is immediately propagated through the screening pipeline against all cataloged objects within the conjunction window. Candidate burns that create any secondary conjunctions with a miss distance under 5 km or probability above 10⁻⁶ are instantly penalized and rejected by the solver. The briefing package explicitly reports the number of secondary conjunctions created (verified to be zero in our sample runs).

---

### Q12: Why did you implement a return burn rather than leaving the satellite in its new orbit?
**Answer:** Commercial satellite constellations (such as communication or imaging networks) require satellites to maintain precise relative phasing within dedicated orbital slots to provide continuous coverage. A permanent avoidance burn causes along-track orbital drift that eventually degrades constellation geometry and coverage quality. Our return burn calculation applies an equal and opposite impulse after the conjunction window passes, safely restoring the satellite to its nominal stationkeeping slot with minimal along-track residual offset.

---

### Q13: How does your alert engine prevent alert fatigue when orbit determination updates fluctuate?
**Answer:** Our `compare.py` engine matches events across runs using persistent object identifiers and a 10-minute TCA shift tolerance, tracking full risk history rather than treating each update as a new event. It triggers high-severity alerts only for actionable changes: when an event escalates into a higher risk band, when a new critical event appears, or when an avoidance burn plan becomes ready. Minor numerical fluctuations within the same risk band are logged to event history without triggering interruptive operator alarms.

---

### Q14: Can the machine learning model be trusted when predicting rare, catastrophic collision events?
**Answer:** Because real collision events in space are extremely rare (only 2.8% of events in ESA's dataset end with risk above 10⁻⁶), any machine learning model must be treated as a secondary prioritization tool rather than a replacement for physical propagation. We tuned the classification decision threshold strictly on training data using the F2 metric, which penalizes false negatives twice as heavily as false positives to prioritize safety. Our dashboard always presents the physics-based maximum probability (`pc_max`) alongside any model predictions so operators have complete physical transparency.

---

### Q15: What standard formats do you support for coordinating conjunctions with other space agencies?
**Answer:** Our system natively implements the Consultative Committee for Space Data Systems standard CCSDS 508.0-B-1 (Conjunction Data Message) in Key-Value Notation (KVN). Every high-risk conjunction exports full relative metadata, cartesian state vectors, and position covariance variances into `.cdm.txt` files compatible with NASA CARA, ESA Space Debris Office, and 18th Space Defense Squadron exchange protocols. We also output machine-readable JSON shift briefings and standardized summary feeds for modern web dashboards.
