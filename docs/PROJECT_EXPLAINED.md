# Fusion: the whole project explained

**How to use this file.** This is a complete description of a hackathon project called Fusion, as it stands on the evening of 9 October 2026, after the first judging round. If you are an AI assistant given this file: explain it to me, section by section, the way you would to a 10-year-old, then help me practise explaining it to judges in my own words. Use only the facts in this file. If I ask about something that is not here, say so instead of guessing.

**Who I am.** Atharv, lead of a four-person team. I built the main system. Two teammates' add-on packs are now connected to it; the third has not arrived.

**Every number in this file was measured on our own laptop on 9 October 2026**, unless it says otherwise.

---

## 1. The problem we were given

**The organisers' words:** "Autonomous Collision Avoidance for LEO Satellite Constellations." Using public orbit data, predict upcoming close approaches, rank them by collision probability, and recommend an automated avoidance manoeuvre (when to fire the thruster and in which direction) for at least one event.

**In simple words:** space near Earth is crowded. Satellites and pieces of junk fly around at about 7.5 km every second (27,000 km/h). When two of them cross paths they can meet at up to 15 km per second. At that speed even a small piece destroys a satellite, and every crash makes thousands of new pieces that can cause more crashes.

So the job is an early-warning system that does three things by itself:

1. **Predict:** which objects will pass dangerously close to each other in the next few days?
2. **Rank:** which of those passes is most likely to be a real collision?
3. **Recommend:** for a dangerous one, exactly when and how should a satellite move out of the way?

**A real example.** On 10 February 2009 a working American satellite (Iridium 33) and a dead Russian one (Cosmos 2251) crashed about 790 km above Siberia. Nobody moved either of them. About 700 pieces from that crash are still in orbit and are in our data today.

**The data the organisers pointed to, and how we use both:**

| Data | What it is | Where we use it |
|---|---|---|
| CelesTrak orbit data | Public, current orbit information for tracked objects | The main system, every run |
| ESA collision-warning dataset | 162,634 real warning messages the European Space Agency received | Teammate C's risk-trend model, which adds a "predicted final risk" to every pass |

We added a third source, **Space-Track** (the US government's public catalogue), because CelesTrak alone does not list all the debris.

---

## 2. Our answer in one minute

Fusion downloads the orbit of every publicly tracked object in low Earth orbit (about 29,700 today), works out where each will be over the next days, finds every pair that will pass within 1 km, calculates how likely each pass is to be a collision, and marks it red, amber or green. For the dangerous passes where one object cannot move, it searches hundreds of small thruster firings, picks the smallest one that makes the pass safe, checks that the move does not steer the satellite into something else, and plans a second firing to put the satellite back. Then it reports what changed since the last run, writes a one-page briefing for each dangerous pass, and repeats every 6 hours. A full run takes about 3 minutes.

### The 60-second version to say out loud

> "There are about 30,000 tracked objects in low Earth orbit, and they cross each other's paths at up to 15 km a second. We built a system that watches all of them. Every run it checks 440 million pairs, finds every pass closer than 1 km, and ranks them by collision probability. Today it found about 1,700 such passes in the next 24 hours, 40 of them red. For a red pass where one side cannot move, such as a satellite against a dead rocket stage, it finds the smallest burn that makes it safe: typically 4 to 7 centimetres per second, half a day ahead, which moves the pass from a few hundred metres to about 3 km. It then checks the new path against everything else and plans the burn that puts the satellite back. We replayed 2009: one day before the Iridium–Cosmos collision, using only data public at that time, the system puts that pass at the top of the list, at 16:55:59, against a reported collision time of 16:56. And we measured where public data can and cannot be trusted, and the system acts on that."

---

## 3. How it works, step by step

Think of it as an assembly line. Each run of the line takes about 3 minutes.

### Step 1: Get the data

- **Simple words:** every tracked object has an "address card": a few numbers that describe its orbit. We download all the cards.
- **Real names:** the card is a TLE (two-line element set). We use the same numbers in a newer format, OMM, because the old text format cannot hold catalogue numbers above 99,999.
- **Detail:** CelesTrak and Space-Track are merged, cards older than 14 days are dropped, and so is anything not in low Earth orbit. Teammate A's pack then replaces our size guess with a measured radar size for 11,063 objects.
- **Code:** `fusion/core/ingest.py`, `fusion/core/spacetrack.py`

### Step 2: Predict where everything will be

- **Simple words:** a standard maths recipe turns an address card into "where is this object at any moment".
- **Real name:** SGP4. The address cards are made for this recipe and only give right answers with it.
- **Detail:** position and speed of all objects every 10 seconds across the look-ahead window (72 hours by default, 24 for a quick run).
- **Code:** `fusion/core/propagate.py`, `fusion/core/sat.py`

### Step 3: Find the close passes

- **Simple words:** 30,000 objects make 440 million pairs. Checking every pair at every moment is far too slow, so we sort objects into neighbourhoods and only compare neighbours.
- **Real names:** screening; the neighbourhood sort is a KD-tree.
- **Detail:** every 10 seconds the KD-tree lists nearby pairs; a straight-line estimate drops the ones that will not get close; the rest get an exact closest-approach calculation. The work is split across 11 processor cores. In the latest run about 7,250 candidates became 1,686 passes within 1 km.
- **Code:** `fusion/core/screen.py`, `fusion/core/refine.py`

### Step 4: Work out how dangerous each pass is

- **Simple words:** we never know exactly where an object is. Picture each as sitting somewhere inside a fuzzy cloud. The collision probability is the chance that the two real objects, somewhere in their clouds, actually touch.
- **Real names:** the cloud is the position uncertainty (covariance); the chance is the collision probability, Pc; the combined size of the two objects is the hard-body radius.
- **Detail:**
  - We calculate the probability for our assumed cloud, and the **worst-case probability**: the highest it could be for any cloud size. We rank by the worst case, so a wrong guess about the cloud cannot hide a danger.
  - **Risk levels**, on the worst case: RED at 1 in 10,000 or more, AMBER at 1 in 100,000 or more, GREEN below.
  - Teammate C's model adds a **predicted final risk**: where it expects the probability to end up, learned from ESA's real warnings.
- **Code:** `fusion/risk/covariance.py`, `fusion/risk/pc.py`

### Step 5: Decide what to do

- **Simple words:** give one satellite a tiny push, early. The push changes how long each lap takes by a tiny amount, so the satellite arrives a little later every lap. After several laps it is kilometres from the danger.
- **Real names:** the push is a burn; its size is the delta-v; "along-track" means along the direction of travel.
- **Who gets a burn plan:**

  | The pass is between | What the system does | Why |
  |---|---|---|
  | A working satellite and something that cannot move (debris, dead satellite, rocket stage) | Burn plan, first in line | A burn is the only way out, and predictions for objects that cannot manoeuvre are the stable ones |
  | Two working satellites of different operators | Burn plan if a slot is free, with a note that the operators must coordinate | Either could move |
  | Two satellites of the same fleet (for example Starlink and Starlink) | Listed, no burn plan | Their operator steers them with precise data we cannot see; our measurement shows public predictions for these pairs are not stable (section 7) |
  | Two objects that cannot move | Warning only | Nobody can act |

- **The search:** up to 31 burn times (half a lap to 8 laps before the pass) times 24 sizes (1 to 100 mm/s, forwards or backwards), up to 744 options. Sideways and up/down burns are also checked.
- **"Safe" means:** probability below 1 in a million, worst case below 1 in 100,000, and a bigger miss distance. The smallest safe burn wins, because fuel is a satellite's lifetime.
- **Code:** `fusion/maneuver/planner.py`, `fusion/maneuver/orbit.py`

### Step 6: Check the fix does not cause a new problem

- **Simple words:** stepping out of the way of one car is no good if you step in front of another.
- **Detail:** the new path is checked against every other object for 24 hours. A burn that creates a new amber or red pass is rejected and the next best is tried. Then a **return burn** (equal and opposite, a whole number of laps later) puts the satellite back.
- **Code:** `fusion/maneuver/verify.py`

### Step 7: Report what changed, and write it up

- **Simple words:** an operator does not want 1,700 lines every 6 hours. They want to know what is new, what got worse, and what to do.
- **Detail (teammate C's pack, called by our pipeline):** each run is compared with the previous run of the same kind. Each pass gets a history across runs. Alerts are raised for new, escalated, downgraded and cleared passes and for new burn plans. Every red and amber pass gets a one-page briefing and a warning message in the space industry's standard format (CDM).
- **Code:** `fusion/addons.py` calling `addons/c_ops/`

### Step 8: Save, serve, repeat

- Each run is saved as one folder of result files. A small web server (FastAPI) hands the results to any screen. The whole line re-runs every 6 hours on fresh data, with no person involved.
- **Code:** `fusion/pipeline.py`, `fusion/api/main.py`, `fusion/monitor/scheduler.py`

---

## 4. What is working today

| Part | Status | Evidence |
|---|---|---|
| Download from CelesTrak and Space-Track | Working | 29,689 objects in the latest run |
| Measured object sizes (teammate A) | Working | 11,063 objects get a measured radar size; debris median radius 0.40 m → 0.10 m |
| Close-pass search over the full sky | Working | Equals an independent calculation on all 7 of teammate A's test cases |
| Collision probability and worst case | Working | Matches a 10-million-sample simulation in tests |
| Burn planner, safety re-check, return burn | Working | 5 burns in the latest run, all creating zero new dangerous passes |
| Alerts and pass history (teammate C) | Working | Second run of the evening: 5 new passes, 5 new plans; 1,668 passes carry a two-run history |
| Briefings and standard warning messages (teammate C) | Working | 340 of each in the latest run |
| Predicted final risk (teammate C) | Working, experimental | Filled for all 1,686 passes |
| 2009 collision replay (teammate A's data) | Working | Section 6 |
| Web server with all data routes | Working | Tested, and checked in a real Chrome browser |
| Automatic re-run every 6 hours | Working | A test shows the scheduler firing repeatedly without overlap. A full 6-hour wait has not been watched |
| Plain test page | Working | Shows today's passes, plans, alerts, and the 2009 replay |
| Automated tests | 101 pass, 1 skipped | The skipped one waits for a file from teammate B |

### What the data covers

| Type | Count |
|---|---|
| Satellites (working and dead) | 17,597 |
| Debris pieces | 9,892 |
| Spent rocket bodies | 1,571 |
| Type not listed | 626 |

(Counts from the morning download; the total moves by a few objects between downloads.) About 15,900 objects are listed as operational. The biggest group is Starlink with 11,132.

---

## 5. Real results from the latest run (10:51 UTC, 24 hours ahead)

- 1,686 passes closer than 1 km: 40 red, 300 amber, 1,346 green. Run time 177 seconds.
- What happened to the 40 red passes:

  | Outcome | Count |
  |---|---|
  | Burn planned and verified | 5 |
  | Same fleet (19 Starlink pairs, 1 Kuiper pair): left to the operator | 20 |
  | Not planned: the limit of 5 burn searches per run was reached | 11 |
  | Neither object can move: warning only | 4 |

- The five burns were for: a Starlink against the dead satellite Cosmos 1758, a Starlink against a Chinese CZ-4C rocket stage, a Kuiper satellite against a Scout rocket stage, a Starlink against an Electron kick stage, and a Starlink against an unnamed object. Sizes: 43 or 66 mm/s.

### One real recommendation

> KUIPER-00053 and the spent rocket stage SCOUT B-1 R/B will pass 251 m apart at 13.2 km/s. Worst-case collision probability: 1 in 4,300. The rocket stage cannot move.
> **Recommendation:** KUIPER-00053 slows down by 43 mm/s (4.3 cm per second), 7.5 laps (about 12 hours) before the pass.
> **Result:** the pass becomes 3.03 km. Worst case falls to about 1 in 710,000. No new dangerous passes. A return burn 49 minutes after the pass restores the orbit.

---

## 6. The 2009 collision, replayed

We gave the system only the orbit data that was public at 17:00 UTC on 9 February 2009, 24 hours before the collision: 2,899 objects from teammate A's pack. Nothing was tuned for this; it is the same code and the same thresholds as today.

| What the system reported, a day before | Value |
|---|---|
| Close passes of Iridium 33 within 5 km in the next 48 hours | 2 |
| Rank of the Cosmos 2251 pass | 1 |
| Predicted closest approach | 10 February 2009, 16:55:59 UTC (the collision is reported at 16:56) |
| Predicted miss distance | 584 m |
| Relative speed | 11.65 km/s |
| Probability / worst case | 2.0e-5 / 9.7e-5 |
| Risk level | AMBER, just under the red line of 1e-4 |
| Decision | Monitor |

**Say this honestly:** the system put the pass at the top of the list at the right time, but rated it amber, not red. The public data of 2009 said the two would miss by 584 m; in reality they hit. That gap is the uncertainty of public data, and it is why we rank by worst case.

**What-if, clearly labelled as such:** had the operator acted on that amber warning, the planner's answer was a 43 mm/s burn 6.75 laps before, moving the pass to 3.99 km.

---

## 7. What we measured about our own accuracy

**How much do predictions move when new orbit data arrives?** We compared two downloads two hours apart: 1,747 passes predicted from the first, recalculated with the second.

| The pass is between | Change in predicted miss distance (median) |
|---|---|
| Two objects that cannot manoeuvre | 0.03 km |
| At least one working satellite | 0.55 km |
| Two Starlink satellites | 26.5 km |

Passes with unchanged data came out identical to the metre. **Meaning:** for debris and dead objects, public data gives stable predictions. For satellites that manoeuvre all the time, it does not, because public data does not include their planned moves. The system acts on this (step 5).

**Other checks:**

- Our close-pass search gives exactly the same passes as an independent brute-force calculation (sampling every half second) on all 7 of teammate A's test cases.
- The probability calculation agrees with a simulation of 10 million random cases.
- A burn of zero reproduces the original pass exactly; a return burn restores the orbit period to within 0.01 s.

---

## 8. Why these tools: answers for judges

**The one-line answer:** Python is the steering wheel, not the engine. Every heavy calculation runs inside compiled C or C++ libraries; Python only tells them what to do.

| Question | Answer, with our own measurement |
|---|---|
| Why Python? | The orbit maths runs in the compiled C++ core of the `sgp4` library, the neighbour search in SciPy's compiled KD-tree, the array maths in NumPy's compiled C. Python connects them. It is also the standard language of this field, and it let one person build and test the whole engine in a day. The result is fast enough by a wide margin: the whole sky in 3 minutes, when the data itself only changes a few times a day |
| Is Python not slow? | Plain Python is, so we do not use it for the heavy part. Compiled SGP4 through NumPy arrays: 1.5 million positions per second on one core, 18 times the same maths in plain Python |
| Why NumPy? | It holds all 30,000 objects as one block of numbers, so one instruction does the work of 30,000 loop steps, in compiled code. It is also what SciPy and `sgp4` take as input, so nothing is copied or converted |
| Why a KD-tree and not just compare everything? | 440 million pairs at each moment, 8,640 moments in a day. The KD-tree finds the nearby pairs in 40 ms. Checking every pair with NumPy takes 60 s and gives the identical answer. Over a day on one core: 6 minutes against 145 hours. The choice of method matters far more than the choice of language |
| Why not C++, Rust or Java? | The slow parts are already C and C++. Rewriting the thin layer on top would cost days and gain little. If we needed 10 times the speed, we would move that one inner loop to compiled code, not rewrite the system |
| Why not MATLAB, STK or GMAT? | MATLAB and STK need paid licences and cannot be shipped as an open web service. GMAT and similar tools are built for precise operator data; ours is public address-card data |
| Why SGP4 and not a more precise physics model? | The address cards are averaged numbers that only give correct positions when read back with SGP4. A "better" model on this data gives worse answers. For the burn we do use real gravity physics, and add the difference onto the SGP4 path |
| Why several processes and not threads or a GPU? | The search splits cleanly into 30-minute time blocks, one per core: 32 minutes on one core became 7 minutes on eleven for a 72-hour search. A KD-tree search does not suit a GPU |
| Why FastAPI? | Small, fast, checks every response against the same data definitions the engine uses, and writes its own documentation page |
| Why files and not a database? | A run is one folder, written so a reader never sees half a file. Teammate packs only need to read and write files. At about 10 MB a run, a database would add setup and no benefit |
| Why no AI model at the core? | Where an object will be and how likely two are to collide are physics and statistics with exact formulas. A trained model would be less accurate, could not explain itself, and has almost nothing to learn from: only a handful of real collisions have ever happened |
| So where is the machine learning? | One place where learning fits: teammate C trained a gradient-boosting model on ESA's 162,634 real warnings to predict how a pass's risk will end up. It cut the average error by 47% against a simple rule. We also report its weakness: at catching the rare passes that end above the danger line, the simple rule did better (it found 78%, the model 22%) |

You can rerun the speed measurements in front of a judge: `.venv\Scripts\python scripts\why_python.py` (about 1 minute).

---

## 9. Other questions judges ask, with answers that match what we built

| Question | Answer |
|---|---|
| Public data has no uncertainty information. Where does your probability come from? | We assume an uncertainty that grows with the age of the data, and we do not trust that assumption: we also calculate the worst-case probability over every possible uncertainty size and rank by that |
| How accurate is public data? | We measured it: predictions for objects that cannot manoeuvre move by about 30 m between updates; for working satellites about half a kilometre; for Starlink pairs tens of kilometres. So we plan burns where the data is trustworthy |
| Why should an operator trust the burn? | It is the smallest of up to 744 options that passes three tests, it is re-checked exactly, its new path is screened against the whole catalogue for 24 hours, and the full grid of options is saved so the choice can be inspected |
| What if the other satellite also moves? | The plan says so when both are operational and names who we propose should move. We cannot see the other operator's intentions. The standard-format warning message exists so the two can coordinate |
| Why are there so many Starlink warnings? | 11,132 of the 30,000 objects are Starlink, flying in tightly packed layers. Seen through public data they look risky; our measurement shows those predictions are unstable, so we list them and leave them to their operator |
| Did you catch the 2009 collision? | A day before, from public data: top of the list, predicted for 16:55:59 against a reported 16:56, rated amber at 9.7e-5 against a red line of 1e-4. We say that plainly and do not tune it |
| How fast is it? | The whole sky, 24 hours ahead, with burn plans, alerts and briefings: 177 seconds on a 12-core laptop with the data already downloaded |
| Does a burn waste the satellite's position in its fleet? | No: a return burn of the same size is planned after the pass |
| How do you avoid drowning the operator in alerts? | Passes are tracked across runs, and only changes raise an alert. On unchanged data the second run raised 10 alerts for 1,686 passes |
| What would real operations need? | Precise orbit data from the operator, measured uncertainty, coordination between operators, and a link to the satellite's command system. Ours is decision support from public data |

**Do not use teammate C's `judge_questions.md` as written.** It was written before the system existed and several answers describe things we do not do: uncertainty "calibrated from historical data" (ours is assumed), protection of "one constellation" (we cover all of low Earth orbit), an "orbital plane filter removing 99.9%" (we use a KD-tree), and compatibility with NASA and ESA exchange systems (not tested). Its slides also contain unfilled placeholders.

---

## 10. What is not done yet

| Item | State |
|---|---|
| The dashboard (the screen judges will see) | Not started. The plain test page is the only screen |
| Teammate B's pack: measured uncertainty, comparison with CelesTrak's own list of close passes | Not received. The system uses its assumed uncertainty instead |
| A full 6-hour automatic cycle watched live | Not yet |

---

## 11. The plan from here

### Build the dashboard (about 6 hours)

| Step | What gets built | Time |
|---|---|---|
| 1 | Page frame; a Run button; a live timeline of the 7 stages; the ranked table; the plan card; the alerts panel | 1 h 15 |
| 2 | A 3D globe with the two orbits of the selected pass, a time slider, and a before/after-burn toggle | 1 h 30 |
| 3 | The uncertainty picture and the decision map (every burn considered, the chosen one marked) | 1 h |
| 4 | A switch to the 2009 replay; buttons for the briefing and the standard warning message | 45 min |
| 5 | Polish: units, plain labels, readable on a projector | 30 min |
| 6 | Demo preparation and a start-up checklist | 1 h |

Everything the dashboard needs is already served by the backend and described in `docs/API.md`.

### If teammate B's pack arrives

About 45 minutes to connect: measured uncertainty replaces the assumption, and the comparison with CelesTrak's list becomes a validation tab.

---

## 12. Who did what

| Person | Built | State |
|---|---|---|
| Atharv | The whole main system: engine, server, monitoring, test page, the connection of the packs | Done except the dashboard |
| Teammate A | History pack: measured sizes, 2009 replay data, a test kit | Received and connected |
| Teammate B | Trust pack: measured uncertainty, outside validation | Not received |
| Teammate C | Operations pack: alerts, pass history, briefings, standard warning messages, the risk-trend model, pitch material | Received and connected |

The main system still runs with the packs removed; each pack adds features.

---

## 13. Honest limits (say these before a judge finds them)

- **Public data is rough for anything that manoeuvres.** Section 7 has our numbers.
- **Uncertainty is assumed, not measured.** That is why we rank by the worst case.
- **Small junk is invisible.** Pieces under about 10 cm are not tracked publicly.
- **Only 5 burn searches per run,** to keep a run to minutes; 11 red passes were left unplanned in the latest run. It is a setting.
- **The safety re-check covers 24 hours,** not the full 72.
- **Slow pairs are left out.** Objects drifting together at under 0.1 km/s (docked or flying in formation) are not assessed; the probability method does not apply to them.
- **The risk-trend model is experimental.** It learned from much more precise data than ours.
- **Sizes are radar sizes or a guess by class,** not true shapes.
- **Not for real operations.** This is decision support built from public data.

---

## 14. The demo, in order

| Time | What is shown |
|---|---|
| 30 s | The 2009 replay: top of the list a day before, at the right time, and the what-if burn |
| 45 s | Press Run on today's sky; the stages run live |
| 75 s | A red pass against a rocket stage: the burn, the miss before and after, the safety check, the return burn |
| 20 s | The alerts since the last run, and one briefing |
| 10 s | The measured limits: what public data can and cannot be trusted for |

All five parts work on the test page today. The dashboard will make them visual.

---

## 15. Words to know

| Word | Meaning |
|---|---|
| LEO | Low Earth orbit: closest point to Earth below 2,000 km |
| TLE / OMM | The "address card" describing an orbit, in old and new formats |
| SGP4 | The standard recipe that turns that card into a position at any time |
| CelesTrak, Space-Track | The two public websites the orbit data comes from |
| Conjunction | A close pass between two objects |
| TCA | Time of closest approach |
| Miss distance | How far apart the two objects are at the closest moment |
| Covariance | The size and shape of the "fuzzy cloud" of where an object might really be |
| Pc | Collision probability |
| Worst-case probability | The highest Pc possible for any cloud size |
| Hard-body radius | The combined size of the two objects |
| Radar cross-section | How big an object looks to a radar; our source for measured sizes |
| Screening | Finding the close passes among millions of pairs |
| KD-tree | A way of sorting points in space so nearby ones are found quickly |
| NumPy, SciPy | Python libraries whose insides are compiled C, C++ and Fortran |
| Burn / manoeuvre | Firing a thruster to change the orbit |
| Delta-v | How much the burn changes the speed, in mm/s |
| Along-track | Along the direction of travel |
| Return burn | A second, opposite burn that restores the original orbit |
| Fleet / constellation | Many satellites run by one operator, such as Starlink |
| CDM | Conjunction data message: the standard format for a collision warning |
| API | The server that hands results to a screen |
