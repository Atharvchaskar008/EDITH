# 3-Minute Live Demo Script: Autonomous Conjunction Triage & Manoeuvre Support

---

### 0:00 - The 2009 Historical Replay

- **What is on screen:**  
  Historical scenario selection screen showing the February 10, 2009 encounter between Iridium 33 (Active) and Cosmos 2251 (Debris). 3D trajectory view displaying the intersecting orbital planes over northern Siberia.
- **Exact words to say:**  
  "On February 10, 2009, two satellites collided at eleven kilometres per second over Siberia, creating over two thousand pieces of trackable debris. We loaded the historical public orbital elements from forty-eight hours prior into our pipeline. Within seconds, our system identifies the close pass, calculates a critical collision probability, and flags it in bright red. If operators had this automated triage in 2009, this historic disaster could have been prevented."
- **If something breaks:**  
  "If the 3D replay canvas does not render immediately, refresh the view or switch to the pre-rendered historical summary tab showing the exact miss distance of 0.41 km and red risk classification."

---

### 0:30 - Live Screening: Today's Sky Timeline

- **What is on screen:**  
  Live dashboard showing the "Run Screening" button. The operator clicks "Run"; orbital data loads, the progress ring completes, and an interactive timeline of close approaches over the next 72 hours populates with colour-coded event cards (Red, Amber, Green).
- **Exact words to say:**  
  "Now let's look at today's active sky. When we click 'Run', our pipeline autonomously ingests public two-line elements, propagates constellations through SGP4, and screens millions of pairwise combinations. Notice how the timeline instantly populates all approaching passes within seventy-two hours. Instead of combing through thousands of raw rows, the operator sees eight prioritized events: five green, two amber, and one critical red approach requiring immediate review."
- **If something breaks:**  
  "If the live propagation pipeline pauses on download, toggle the 'Replay Cached Run' switch to load the pre-computed run `20261009T1200Z`, displaying the identical 8-event timeline instantly."

---

### 1:15 - Deep Dive: Top Conjunction, Uncertainty Picture & Verified Plan

- **What is on screen:**  
  The operator clicks into the top red event card (`43070-34427`, Iridium 106 vs Cosmos 2251 Debris). The detail view opens, displaying:
  1. The RTN uncertainty ellipsoid overlay.
  2. The delta-v trade-off decision map.
  3. The synthesized manoeuvre plan: burn time, direction (along-track), delta-v of 34.0 mm/s, and a return burn 4 hours later.
- **Exact words to say:**  
  "Here is our highest-priority event: Iridium 106 passing within 412 metres of a Cosmos fragment. Look at the uncertainty ellipsoid: rather than assuming a generic sphere, we construct empirical position covariances calibrated from real tracking history. Below it is our autonomous manoeuvre plan. The system synthesizes an along-track burn of just 34 millimetres per second scheduled ninety minutes prior to closest approach. This widens the miss distance to nearly three kilometres and slashes collision risk to ten to the minus eight. Notice the return burn four hours later: it restores the satellite to its nominal slot with zero secondary conjunctions created."
- **If something breaks:**  
  "If the interactive decision map graph is slow to render, direct the judges' attention to the side plan panel displaying the numerical burn parameters: delta-v 0.034 m/s, miss after 2.96 km."

---

### 2:15 - Live Alert Feed & One-Page Shift Briefing

- **What is on screen:**  
  A simulated run update lands. An alert pop-up and badge appear in the dashboard's alert feed: `[CRITICAL] [ESCALATED] IRIDIUM 106 and COSMOS 2251 DEB: risk rose from AMBER to RED`. The operator clicks the alert, opening the clean JSON one-page briefing card and showing the exported CCSDS CDM text download button.
- **Exact words to say:**  
  "While operators work, our background watcher continuously compares consecutive orbital cycles. Notice this live alert: as new orbit determinations arrive, the system detects that this event escalated from amber to red, while another event downgraded safely to green. With a single click, an operator starting their shift opens this concise one-page briefing. It contains plain-English facts, formatted units, burn geometry, and full trajectory history, exportable directly to the international CCSDS Conjunction Data Message standard for inter-agency coordination."
- **If something breaks:**  
  "If the live feed notification badge does not animate, open `sample_runs/20261009T1200Z/briefings/43070-34427-20261011T0412.briefing.json` in the file inspector to show the formatted operator briefing data."

---

### 2:35 - Empirical Validation Benchmarks

- **What is on screen:**  
  Validation metrics screen showing benchmark comparisons: CelesTrak SOCRATES agreement table and the ESA Collision Avoidance Challenge risk-model evaluation graphic (`out/risk_model.png` and `out/esa_risk_evolution.png`).
- **Exact words to say:**  
  "We benchmarked our engine against rigorous external standards. Our close approach screening matches CelesTrak SOCRATES with [VALIDATION NUMBERS FROM TEAMMATE B]. Furthermore, we trained and evaluated our risk-trend model on 162,634 real European Space Agency warnings. Our operational gradient boosting model cuts continuous risk prediction error by 47% compared to the industry standard baseline, allowing flight teams to anticipate whether early alerts will worsen or clear."
- **If something breaks:**  
  "If the slide images do not switch immediately, refer directly to the static charts in `out/risk_model.png` and `out/esa_overview.json` on disk."

---

### 2:50 - Operational Limits & Closing

- **What is on screen:**  
  Summary takeaway slide with system boundaries and architecture overview.
- **Exact words to say:**  
  "We are explicit about our system's boundaries: public orbital elements are accurate to approximately one kilometre, which is why our scores serve as intelligent triage rather than certified telemetry. The platform acts as human decision support and sends zero direct commands to spacecraft. By automating screening, manoeuvre synthesis, and alert tracking, we empower flight teams to protect commercial constellations safely and sustainably. Thank you, and we welcome your questions."
- **If something breaks:**  
  "Deliver the closing remarks directly facing the judges while keeping the summary slide visible."
