# EDITH: the whole project explained

**How to use this file.** This is a complete description of a hackathon project called EDITH (its code package is named `fusion`), as it stands late on 9 October 2026, after the first judging round and a night of work on the dashboard. If you are an AI assistant given this file: explain it to me, section by section, the way you would to a 10-year-old, then help me practise explaining it to judges in my own words. Use only the facts in this file. If I ask about something that is not here, say so instead of guessing.

**Who I am.** Atharv, lead of a four-person team. I built the main system and the validation work. Two teammates' add-on packs are connected to it.

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
| ESA collision-warning dataset | 162,634 real warning messages the European Space Agency received | Two places: we checked our probability maths against 20,000 of them, and teammate C trained a risk-trend model on them |

We added a third source, **Space-Track** (the US government's public catalogue), because CelesTrak alone does not list all the debris, and because it holds the history we used to measure how accurate public data is.

---

## 2. Our answer in one minute

EDITH downloads the orbit of every publicly tracked object in low Earth orbit (about 29,700 today), works out where each will be over the next 24 hours, finds every pair that will pass within 1 km, calculates how likely each pass is to be a collision using uncertainty we measured ourselves, and marks it red, amber or green. For the dangerous passes where one object cannot move, it searches hundreds of small thruster firings, picks the smallest one that makes the pass safe, checks that the move does not steer the satellite into something else, and plans a second firing to put the satellite back. Then it reports what changed since the last run, writes a one-page briefing for each dangerous pass, compares itself with CelesTrak's own list, and repeats every 6 hours. A full run takes about 7 minutes. Between runs it answers three requests: what a burn would take for a pass it only watches, the close passes of any satellite found by name, and a summary of each fleet.

### The 60-second version to say out loud

> "There are about 30,000 tracked objects in low Earth orbit, crossing each other's paths at up to 15 km a second. We built a system that watches all of them. Every run it checks 440 million pairs, finds every pass closer than 1 km, and ranks them by collision probability. Today that is about 2,300 passes in the next 24 hours, 69 of them red. For every red pass where a burn is possible, it finds the smallest burn that makes it safe, checks the new path against everything else, and plans the burn that puts the satellite back.
>
> We did not take our own word for it. From the same orbit data, our close-approach distances match CelesTrak's own to 35 centimetres. Our probability matches the European Space Agency's on 20,000 real warnings with no offset. And because public data has no error bars, we measured them from 325,000 pairs of orbit records: debris is predictable to about 200 metres a day, Starlink to about 12 kilometres. The system acts on that: it does not pretend to plan burns between two satellites of a fleet whose positions it cannot predict."

---

## 3. How it works, step by step

Think of it as an assembly line. Each run of the line takes about 7 minutes.

### Step 1: Get the data

- **Simple words:** every tracked object has an "address card": a few numbers that describe its orbit. We download all the cards.
- **Real names:** the card is a TLE (two-line element set). We use the same numbers in a newer format, OMM, because the old text format cannot hold catalogue numbers above 99,999.
- **Detail:** CelesTrak and Space-Track are merged, cards older than 14 days are dropped, and so is anything not in low Earth orbit. Teammate A's pack then replaces our size guess with a measured radar size for 11,063 objects.
- **Code:** `fusion/core/ingest.py`, `fusion/core/spacetrack.py`

### Step 2: Predict where everything will be

- **Simple words:** a standard maths recipe turns an address card into "where is this object at any moment".
- **Real name:** SGP4. The address cards are made for this recipe and only give right answers with it.
- **Detail:** position and speed of all objects every 10 seconds across the next 24 hours. It can look 72 hours ahead, but section 7 shows why that is not worth doing.
- **Code:** `fusion/core/propagate.py`, `fusion/core/sat.py`

### Step 3: Find the close passes

- **Simple words:** 30,000 objects make 440 million pairs. Checking every pair at every moment is far too slow, so we sort objects into neighbourhoods and only compare neighbours.
- **Real names:** screening; the neighbourhood sort is a KD-tree.
- **Detail:** every 10 seconds the KD-tree lists nearby pairs; a straight-line estimate drops the ones that will not get close; the rest get an exact closest-approach calculation. The work is split across 11 processor cores.
- **Code:** `fusion/core/screen.py`, `fusion/core/refine.py`

### Step 4: Work out how dangerous each pass is

- **Simple words:** we never know exactly where an object is. Picture each as sitting somewhere inside a fuzzy cloud. The collision probability is the chance that the two real objects, somewhere in their clouds, actually touch.
- **Real names:** the cloud is the position uncertainty (covariance); the chance is the collision probability, Pc; the combined size of the two objects is the hard-body radius.
- **Detail:**
  - **The size of each cloud is measured, not guessed.** Public data has no error bars, so we compared 325,558 pairs of old and new address cards of the same objects. A day ahead, the cloud for a Starlink is 12 km long; for a dead satellite, 60 m (section 7).
  - We calculate the probability for that cloud, and the **worst-case probability**: the highest it could be for any cloud size. We rank by the worst case, so an error in the cloud's size cannot hide a danger.
  - **Risk levels**, on the worst case: RED at 1 in 10,000 or more, AMBER at 1 in 100,000 or more, GREEN below.
  - Teammate C's model adds a **predicted final risk**, learned from ESA's real warnings.
- **Code:** `fusion/risk/covariance.py`, `fusion/risk/pc.py`, `addons/b_trust/tle_error.py`

### Step 5: Decide what to do

- **Simple words:** give one satellite a tiny push, early. The push changes how long each lap takes by a tiny amount, so the satellite arrives a little later every lap. After several laps it is kilometres from the danger.
- **Real names:** the push is a burn; its size is the delta-v; "along-track" means along the direction of travel.
- **Who gets a burn plan:**

  | The pass is between | What the system does | Why |
  |---|---|---|
  | A working satellite and something that cannot move (debris, dead satellite, rocket stage) | Burn plan, first in line | A burn is the only way out, and predictions for objects that cannot manoeuvre are the stable ones |
  | Two working satellites of different operators | Burn plan, with a note that the operators must coordinate | Either could move |
  | Two satellites of the same fleet (for example Starlink and Starlink) | Listed, no burn plan | Their operator steers them with precise data we cannot see, and we measured that public predictions for them are off by kilometres |
  | Two objects that cannot move | Warning only | Nobody can act |

- **The search:** up to 31 burn times (half a lap to 8 laps before the pass) times 24 sizes (1 to 100 mm/s, forwards or backwards), up to 744 options. Sideways and up/down burns are also checked.
- **"Safe" means:** probability below 1 in a million, worst case below 1 in 100,000, and a bigger miss distance. The smallest safe burn wins, because fuel is a satellite's lifetime.
- **Something the search found by itself:** when the satellite's own position along its path is very uncertain (a Starlink), sliding it further along the path does not help, because that is the direction nobody is sure about. The search then lands on a burn half a lap before the pass, which changes the satellite's height at the meeting point. Separating in height this way is a standard technique among operators.
- **Code:** `fusion/maneuver/planner.py`, `fusion/maneuver/orbit.py`

### Step 6: Check the fix does not cause a new problem

- **Simple words:** stepping out of the way of one car is no good if you step in front of another.
- **Detail:** the new path is checked against every other object for 24 hours. Every dangerous pass found is computed a second time without the burn. A burn that creates a dangerous pass, or raises the worst case of one the satellite already had by more than 10%, is rejected. The planner then tries a different kind of burn: the other direction, another time, and last the latest possible burn, which keeps the satellite off its path for the shortest time. If none is clean it proposes no burn and says why. Then a **return burn** (equal and opposite, a whole number of laps later) puts the satellite back.
- **A case this catches:** two objects in similar orbits can meet once every lap. A burn that clears one meeting moves the danger to the next. Section 5 has a real one.
- **Code:** `fusion/maneuver/verify.py`

### Step 7: Report what changed, and write it up

- **Simple words:** an operator does not want 1,750 lines every 6 hours. They want to know what is new, what got worse, and what to do.
- **Detail (teammate C's pack, called by our pipeline):** each run is compared with the previous run of the same kind. Each pass gets a history across runs. Alerts are raised for new, escalated, downgraded and cleared passes and for new burn plans. Every red and amber pass gets a one-page briefing and a warning message in the space industry's standard format (CDM).
- **Code:** `fusion/addons.py` calling `addons/c_ops/`

### Step 8: Check itself, save, serve, repeat

- At the end of a run the system compares its own list of passes with CelesTrak's published list.
- Each run is saved as one folder of result files. A small web server (FastAPI) hands the results to any screen. The whole line re-runs every 6 hours on fresh data, with no person involved.
- Each run also keeps its full list of objects, so that between runs the server can show what a burn would take for a pass it only watches ("Plan now"), check any one satellite against everything at its height, and summarise each fleet.
- **Code:** `fusion/validation.py`, `fusion/pipeline.py`, `fusion/api/main.py`, `fusion/monitor/scheduler.py`

---

## 4. What is working today

| Part | Status | Evidence |
|---|---|---|
| Download from CelesTrak and Space-Track | Working | 29,683 objects in the latest run |
| Measured object sizes (teammate A) | Working | 11,063 objects get a measured radar size |
| Close-pass search over the full sky | Working | Matches CelesTrak to 0.35 m on its 200 closest conjunctions; equals an independent calculation on all 7 of teammate A's test cases |
| Collision probability and worst case | Working | No offset from ESA's on 20,000 real warnings; matches random sampling; matches 30 independent reference cases to 2% |
| Measured uncertainty | Working | 2,276 of 2,332 passes in the latest run use it; the other 56 involve objects of unknown type and use an assumed value |
| Burn planner, safety re-check, return burn | Working | 17 burns in the latest run, each creating no new dangerous pass and worsening none |
| What-if burn on request ("Plan now") | Working | A verified burn in about 20 seconds for a pass the system only watches |
| Check of any one satellite | Working | The ISS: 4 passes within 10 km in the next 24 hours, checked against 1,549 objects in 6 seconds |
| Fleet summary | Working | Starlink: 11,129 satellites, 19 dangerous passes to act on, 25 inside its own fleet |
| Alerts and pass history (teammate C) | Working | Latest run: 7 new passes; most passes carry a history of nine runs or more |
| Briefings and standard warning messages (teammate C) | Working | 304 of each in the latest run |
| Predicted final risk (teammate C) | Working, experimental | Filled for every pass |
| 2009 collision replay (teammate A's data) | Working | Section 6 |
| Comparison with CelesTrak's list after each run | Working | 270 passes in common in the latest run |
| Web server with all data routes | Working | Tested, and checked in a real Chrome browser |
| Automatic re-run every 6 hours | Working | Watched on a second copy of the server with the timer set to 2 minutes: it started a run by itself, the run finished in 242 seconds (2,184 passes, 5 burns), and the timer firing twice more during the run started nothing. The 6-hour wait itself has not been sat through |
| Dashboard | Working | A priority list, burn plans with three pictures, Plan now, the satellite check, fleets, alerts, the validation line, and the 2009 replay |
| Automated tests | 123 in the main system, 54 in the validation pack, all passing | GitHub runs them on every push, on Python 3.11 to 3.14 |

### What the data covers

| Type | Count |
|---|---|
| Satellites (working and dead) | 17,597 |
| Debris pieces | 9,892 |
| Spent rocket bodies | 1,571 |
| Type not listed | 626 |

(Counts from the morning download; the total moves by a few objects between downloads.) About 15,900 objects are listed as operational. The biggest group is Starlink with 11,132.

---

## 5. Real results from the latest run (21:18 UTC, 24 hours ahead)

The numbers change with every run. Read the current ones off the dashboard.

- 29,679 objects; 2,332 passes closer than 1 km: 69 red, 235 amber, 2,028 green.
- What happened to the 69 red passes:

  | Outcome | Count |
  |---|---|
  | Burn ready, verified | 17 |
  | Same fleet (Starlink and Qianfan pairs): left to the operator | 45 |
  | No safe burn: every burn tried would create or worsen another dangerous pass | 4 |
  | Neither object can move: warning only | 2 |
  | Too soon to burn | 1 |

- The dashboard's Priority list is the 24 red passes that are not inside one fleet. Every one has a burn ready or says why not.
- Burn sizes: 19 to 100 mm/s. 11 of the 17 reach the full safety target. The other 6 bring the worst case back to green at the largest burn searched (100 mm/s) but leave the best-estimate probability just above 1 in a million; each says it is the best available.
- The run took 6 min 45 s: under 2 minutes for the search and under 4 for the 21 burn searches.

**"Burn ready" is advice, not an order.** A pass is red on its worst case, because public data does not say how uncertain the positions really are. Our best estimate is usually far lower (for KUIPER-00053 below: worst case 1 in 900, best estimate 1 in 64,000). A real operator would first get better tracking, and would burn only if the risk stayed above about 1 in 10,000 close to the pass. The burn is ready so that no time is lost if it does.

### Four real cases

> **A burn, and why early is cheaper.** KUIPER-00053 and the spent rocket stage SCOUT B-1 R/B will pass 251 m apart at 13.2 km/s. Worst case: 1 in 900. The rocket stage cannot move.
> **Recommendation in the evening, a few hours before the pass:** slow down by 66 mm/s half a lap before the pass. The pass becomes 585 m and the worst case 1 in 880,000.
> **The same pass at midday, with 10 more hours in hand:** 43 mm/s, 6.5 laps early, moved it to 2.66 km. The earlier the burn, the smaller it is.

> **A late change of height.** STARLINK-6223 and an unnamed object will pass 238 m apart at 13.3 km/s. The Starlink's position along its path is uncertain by kilometres, so sliding it along the path would not help.
> **Recommendation:** speed up by 100 mm/s half a lap before the pass, which changes its height at the meeting point.
> **Result:** the pass becomes 419 m, and the worst case falls from 1 in 5,000 to 1 in 1.2 million.

> **Two working satellites.** STARLINK-4043 and FLOCK 4G-8 will pass 76 m apart at 12.7 km/s, worst case 1 in 196. Either could move.
> **Recommendation:** the Starlink slows down by 66 mm/s half a lap early, because its orbit data is newer. The plan says the two operators would need to agree.
> **Result:** the pass becomes 451 m and the worst case 1 in 737,000.

> **A pass that gets no burn, and why.** 2024-173D and STARLINK-38027 meet once every lap, at 7.9, 5.0, 2.4, 0.18, 1.7, 3.2 and 4.4 km. The 0.18 km meeting is red.
> **What the system did:** tried 5 burns. 2 created a new dangerous pass and 3 made another dangerous pass of the satellite worse, because clearing one meeting moves the danger to the next.
> **Result:** no burn proposed. The list says "No safe burn" and the card gives the count above.

---

## 6. The 2009 collision, replayed

We gave the system only the orbit data that was public at 17:00 UTC on 9 February 2009, 24 hours before the collision: 2,899 objects from teammate A's pack. Nothing was tuned for this; it is the same code, the same thresholds and the same measured uncertainty as today.

| What the system reported, a day before | Value |
|---|---|
| Close passes of Iridium 33 within 5 km in the next 48 hours | 2 |
| Rank of the Cosmos 2251 pass | 1 |
| Predicted closest approach | 10 February 2009, 16:55:59 UTC (the collision is reported at 16:56) |
| Predicted miss distance | 584 m |
| Relative speed | 11.65 km/s |
| Probability / worst case | 2 in a billion / 1.1 in 100,000 |
| Risk level | AMBER, just over the amber line |
| Decision | Monitor |

**How to say the rank.** It is first of two: the replay checks Iridium 33 against the 2009 objects, not every object against every other. Say "the most dangerous pass of Iridium 33, and the only one flagged". Do not say "ranked number one" by itself.

**Why amber and not red.** Red needs a worst case of 1 in 10,000. At a predicted miss of 584 m the worst case is 1 in 90,000. The predicted miss would have had to be under about 200 m. Lowering the red line to catch it would turn every amber pass of today's run red.

**Say this honestly, because it is the most important lesson in the project:** the system found the pass, put it first, and timed it right. But public data said the two would miss by 584 m, and by the uncertainty we measured for such objects (about 200 m) that looked safe: 2 chances in a billion. They collided. So that day public data was wrong by at least 584 m, about three times its typical error. Two things follow. First, this is why we rank by the worst case, which still flagged the pass amber. Second, public data alone did not make this pass look red; operators need better tracking, and ours is built so better data can be dropped in.

Because the pass sat right on the amber line, the smallest burn that passes the system's own safety test is tiny (1 mm/s). We do not present that as "what would have saved it".

---

## 7. What we measured about our own accuracy

### How wrong is public orbit data?

We took 779 objects of six kinds, downloaded their orbit records for the last 16 to 30 days, and for 325,558 pairs of records compared where the older one says the object is with where the newer one says it is.

| Kind of object | Error along the direction of travel after 1 day | After 3 days |
|---|---|---|
| Dead satellites | 0.06 km | 0.17 km |
| Rocket bodies | 0.15 km | 0.47 km |
| Debris | 0.22 km | 0.75 km |
| Working satellites other than Starlink | 0.37 km | 1.44 km |
| Starlink | 12 km | 77 km |

Up-and-down and sideways errors are several times smaller (about 0.05 km for debris after a day). Starlink is so different because those satellites thrust almost all the time and public data does not include their planned moves.

**Its limit:** this compares public records with each other, not with the true position, so it understates the real error. ESA's own warnings state an uncertainty for debris about 5 times ours.

### Is our close-approach calculation right?

CelesTrak publishes its own list of predicted close passes. For its 200 closest, we fetched the exact orbit records it used and ran our own calculation.

| | Difference from CelesTrak (median) |
|---|---|
| Distance at closest approach | 0.35 m (CelesTrak publishes to the nearest metre) |
| Time of closest approach | 0.4 thousandths of a second |
| Matched | 200 of 200 |

### Is our probability right?

- **Against ESA.** On 20,000 real warnings ESA received for its satellites, our probability has no offset from ESA's own. For the 2,100 warnings ESA rated above 1 in a million, the median difference is 2%. Our worst case matches ESA's own "maximum risk" with a median difference of 4%. For warnings ESA rates as negligible the two can differ a lot; one in ten of all warnings differs by a factor of 500 or more, and the dataset does not show why.
- **Against random sampling.** On 9 cases, the formula agrees with 10 to 40 million random draws.
- **Against an independent calculator.** The main engine matches 30 reference cases to 2%.

### Do predictions survive new data?

CelesTrak's list was computed from data about a day older than ours. Of its close passes that fall in our window:

| The pass is between | Also in our run, a day of data later |
|---|---|
| A satellite and something that cannot manoeuvre | 40% |
| Two working satellites of different fleets | 11% |
| Two satellites of the same fleet | 0% (1 of 427) |

This is the practical meaning of the 12 km: a predicted close pass between two Starlinks is gone by the next day.

### How far ahead is worth looking?

We ran the whole sky once for 72 hours instead of 24 (9 October 2026: 18,497 passes, 15 minutes).

| Day of the window | Passes outside fleets | Passes between two working satellites of one fleet |
|---|---|---|
| 1 | 1,179 | 862 |
| 2 | 1,182 | 4,941 |
| 3 | 1,124 | 9,209 |

Passes outside fleets stay level. Passes inside a fleet grow tenfold, and 14,916 of the 15,012 are Starlink pairs. Fleets keep their satellites spaced so that they miss each other; the error in public data (77 km for a Starlink after three days) scrambles that spacing. So the later passes are not predictions, and the scheduled run looks 24 hours ahead.

### How much do our assumptions matter?

On 175 close passes: halving or doubling the uncertainty changes nothing in the worst-case ranking. Changing the assumed object size from 10 m to 5 m or 20 m moves 38 and 16 passes across a level. Ranking by closeness alone agrees with the worst-case ranking only weakly (0.31 on a scale where 1 is identical): a pass at 141 m can be 500 times more dangerous than one at 87 m, depending on which way the miss points.

The page to hand a judge is `addons/b_trust/out/VALIDATION_REPORT.md`, with four charts beside it.

---

## 8. Why these tools: answers for judges

**The one-line answer:** Python is the steering wheel, not the engine. Every heavy calculation runs inside compiled C or C++ libraries; Python only tells them what to do.

| Question | Answer, with our own measurement |
|---|---|
| Why Python? | The orbit maths runs in the compiled C++ core of the `sgp4` library, the neighbour search in SciPy's compiled KD-tree, the array maths in NumPy's compiled C. Python connects them. It is also the standard language of this field, and it let one person build and test the whole engine in a day. The result is fast enough by a wide margin: the whole sky searched in under 2 minutes, when the data itself only changes a few times a day |
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
| How do you know your numbers are right? | Three outside checks. Same data in, our close-approach distance matches CelesTrak's to 0.35 m on 200 conjunctions. Our probability has no offset from ESA's on 20,000 real warnings. And our uncertainty is measured from 325,000 pairs of real orbit records |
| Public data has no uncertainty information. Where does your probability come from? | We measured it, per kind of object and per age of the data. Because that measurement understates the true error, we also calculate the worst case over every possible size of uncertainty and rank by that |
| How accurate is public data? | After one day: about 60 m for a dead satellite, 220 m for debris, 370 m for a working satellite, 12 km for a Starlink |
| Why should an operator trust the burn? | It is the smallest of up to 744 options that passes three tests, it is re-checked exactly, its new path is screened against the whole catalogue for 24 hours, and the full grid of options is saved so the choice can be inspected |
| What if the other satellite also moves? | The plan says so when both are operational and names who we propose should move. We cannot see the other operator's intentions. The standard-format warning message exists so the two can coordinate |
| If collisions are rare, why are so many passes flagged? | Close passes worth a check are common; collisions are not. In the latest run 76 of 2,497 passes are red, and all 2,497 together make about a 1 in 340 chance of a collision in the day. A typical red pass has a worst case of 1 in 4,900 and a best estimate of 1 in 1.5 million. Red is judged on the worst case because public data does not say how uncertain positions are; an operator with precise tracking would clear most of them. The dashboard therefore says "to check", not "dangerous" |
| Why are there so many Starlink warnings? | 11,132 of the 30,000 objects are Starlink, flying in tightly packed layers. Seen through public data they look risky, but that data is off by 12 km a day for them, and of 427 same-fleet passes CelesTrak listed a day earlier, one was still there. So we list them and leave them to their operator |
| Did you catch the 2009 collision? | A day before, from public data: the most dangerous pass of Iridium 33 (first of two), at the right second, rated amber. Public data said a 584 m miss; they hit. We say that plainly: it shows the limit of public data and why we rank by worst case |
| Why was 2009 amber and not red? | Public data predicted a 584 m miss, which gives a worst case of 1 in 90,000. Red starts at 1 in 10,000. Nobody could have rated it red from that data, and we do not move the line to make the story look better |
| Why only 24 hours ahead? | We ran 72 hours once. Passes outside fleets stayed at about 1,150 a day. Passes inside one fleet grew from 862 on day one to 9,209 on day three, which is the error of public data, not real danger |
| Why does a dangerous pass have no burn? | Four honest reasons, and the list says which: both satellites are of one fleet; neither object can move; the pass is too soon; or every burn tried would create or worsen another dangerous pass |
| Does a satellite have to move when it says "Burn ready"? | No. It is advice. Red is judged on the worst case, and our best estimate is usually far lower. The burn is ready in case better tracking confirms the risk |
| What is "Plan now" for? | The run plans every dangerous pass it can. Plan now shows what a burn would take for a pass the system only watches, in about 20 seconds, marked as a what-if |
| Can I check one satellite? | Yes. Type its name or number. It is checked against everything at its height for the next 24 hours: the ISS takes 6 seconds, a Starlink about 17 |
| How fast is it? | The whole sky, 24 hours ahead, with measured uncertainty, a burn search for every dangerous pass, alerts, briefings and the CelesTrak comparison: about 7 minutes on a 12-core laptop with the data already downloaded. The search itself is under 2 minutes and the 21 burn searches under 4 |
| Does a burn waste the satellite's position in its fleet? | No: a return burn of the same size is planned after the pass |
| How do you avoid drowning the operator in alerts? | Passes are tracked across runs, and only changes raise an alert: the latest run raised 7 for 2,332 passes. The dashboard opens on 24 priority passes, not on 2,332 |
| What would real operations need? | Precise orbit data from the operator, coordination between operators, and a link to the satellite's command system. Ours is decision support from public data, built so better data can replace the public data without changing the rest |

---

## 10. What is not done yet

| Item | State |
|---|---|
| A 3D view of the orbits | Not built. The dashboard shows three flat pictures for each pass |
| A burn for pairs that meet every lap | Not built. The system detects the case and proposes no burn |
| The 2009 replay across the whole sky | Not run. The replay checks Iridium 33 only |
| The 6-hour wait itself | Not sat through. An automatic run was watched with the timer shortened to 2 minutes (section 4) |

---

## 11. What was added on the night of 9 October

| Added | What it does | Checked on live data |
|---|---|---|
| Safer burns | Every dangerous pass found after a burn is computed again without it. A burn that creates one, or worsens one the satellite already had, is rejected, and a different kind of burn is tried | The plan card shows "0 new, 0 worse"; the 2024-173D case above |
| Every dangerous pass planned | A run searches for a burn for every dangerous pass it can, and each row says "Burn ready" or gives the reason there is none | 17 burns ready and 7 reasons in the run of 21:18 UTC |
| Plan now | What a burn would take for a pass the system only watches | About 20 seconds |
| Three pictures per pass | The gap with and without the burn; every burn tried, with the chosen one ringed; the risk at each run | In a real Chrome browser |
| Check any satellite | Its passes within 10 km for the next 24 hours | The ISS: 4 passes, none dangerous, 6 seconds |
| Fleets | One row per fleet: passes, dangerous passes to act on, passes inside the fleet, burns planned | Starlink, Yaogan, Flock, Kuiper and 220 more |
| Priority list | The dashboard opens on the dangerous passes that are not inside one fleet | 24 of 69 |
| 24-hour scheduled run | The automatic run looks 24 hours ahead, not 72 | Section 7 has the reason |
| Proof section | The dashboard draws the four validation results: distances against CelesTrak, probability against ESA, the error of public data by its age, and how far the ranking depends on our assumptions | In a real Chrome browser |
| Documents on each plan | Links to the standard warning message (CDM) and the briefing written for that pass | Both open |
| Tests on GitHub | The 120 and 54 tests run on every push, with a badge on the README | Green |

---

## 12. Who did what

| Person | Built | State |
|---|---|---|
| Atharv | The whole main system: engine, server, monitoring, dashboard, the connection of the packs. Also the validation pack (reference calculator, measured uncertainty, checks against ESA and CelesTrak), which was planned for teammate B | Done |
| Teammate A | History pack: measured sizes, 2009 replay data, a test kit | Received and connected |
| Teammate C | Operations pack: alerts, pass history, briefings, standard warning messages, the risk-trend model | Received and connected |

The main system still runs with the packs removed; each pack adds features.

---

## 13. Honest limits (say these before a judge finds them)

- **Public data is rough, and for anything that manoeuvres it is very rough.** Section 7 has our numbers.
- **Our measured uncertainty is itself too small.** It compares public records with each other. The 2009 replay shows the consequence.
- **Small junk is invisible.** Pieces under about 10 cm are not tracked publicly.
- **Object size is the assumption that matters most,** and public data gives it only roughly (a radar size, or a guess by class).
- **Some burns stop short of the target.** The search goes up to 100 mm/s. 6 of the 17 burns in the latest run bring the worst case back to green but leave the best estimate just above 1 in a million. Each says it is the best available.
- **Some passes get no burn.** For a pair that meets every lap, no burn on our grid clears every meeting. The system says so; it does not solve it.
- **We look 24 hours ahead.** Further out, public data is too rough for satellites that manoeuvre (section 7).
- **Burns are treated as instantaneous,** and the safety re-check covers 24 hours.
- **Slow pairs are left out.** Objects drifting together at under 0.1 km/s (docked or flying in formation) are not assessed; the probability method does not apply to them.
- **The risk-trend model is experimental.** It learned from much more precise data than ours.
- **Not for real operations.** This is decision support built from public data.

---

## 14. The demo, in order

The timed script, with what to click and what to say, is in `docs/team/SIMPLE.md` under "What to say in 3 minutes". The order:

| Time | What is shown |
|---|---|
| 25 s | The problem, in three sentences |
| 25 s | The four numbers at the top, and the line "distances match CelesTrak to 0.35 m" |
| 45 s | A burn plan: the burn, the gap with and without it, every burn tried, "0 new, 0 worse" |
| 25 s | The Plan column: every dangerous pass has a burn ready or a stated reason |
| 20 s | A satellite the judge names, typed into the box |
| 25 s | The 2009 replay: found, timed right, rated amber, and what that teaches |
| 15 s | The limits, said by us |

Do not press "Run now" during the talk; a run takes about seven minutes.

---

## 15. Words to know

| Word | Meaning |
|---|---|
| LEO | Low Earth orbit: closest point to Earth below 2,000 km |
| TLE / OMM | The "address card" describing an orbit, in old and new formats |
| SGP4 | The standard recipe that turns that card into a position at any time |
| CelesTrak, Space-Track | The two public websites the orbit data comes from |
| SOCRATES | CelesTrak's own published list of predicted close passes |
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
| Along-track, radial, cross-track | Along the direction of travel; up and down; sideways |
| Return burn | A second, opposite burn that restores the original orbit |
| Fleet / constellation | Many satellites run by one operator, such as Starlink |
| CDM | Conjunction data message: the standard format for a collision warning |
| API | The server that hands results to a screen |
