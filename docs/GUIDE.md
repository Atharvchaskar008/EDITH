# EDITH: the complete guide

This one file explains the whole project, from the problem to the last button on the dashboard, in the order you will present it. Read it once from top to bottom to understand the project. Then use the table below as your running order.

Numbers in [square brackets] change with every run: read them off the screen. Every other number is fixed and measured by us.

## Your running order

| Step | Screen | What you cover | Read |
|---|---|---|---|
| 1 | Landing page, the top only | The problem | Part 2 |
| 2 | Click **Open dashboard** | The solution in a few sentences | Part 3 |
| 3 | Dashboard, at the top | How it works step by step, the tools, why it works well | Parts 4, 5, 6 |
| 4 | Dashboard, top to bottom | Everything on the screen and what each button does | Part 7 |
| 5 | Proof section, then the 2009 replay tab | How we know it is right | Parts 8, 9 |
| 6 | Click **Story**, then scroll the landing page to the end | The story, section by section | Part 10 |
| 7 | The last screen of the landing page | Limits and close | Part 11 |

Before you start: Part 14 has the commands and addresses.

---

## Part 1. The project in one minute

About 30,000 tracked objects fly around the Earth in low orbit. Any two of them can cross paths at up to 15 km a second. That makes 440 million pairs, far too many for people to watch.

EDITH watches all of them by itself, from public data. Every six hours it does six things:

1. Downloads the orbit of every tracked object.
2. Predicts where each one will be for the next 24 hours.
3. Finds every pair that will pass within 1 km.
4. Works out how likely each pass is to be a collision.
5. For the risky ones, finds the smallest push that makes the pass safe.
6. Checks that push against every other object before recommending it.

It shows the result on a dashboard, and we proved its numbers against two outside references and one real collision.

---

## Part 2. The problem

Say this on the landing page, before you click anything.

**The situation**

- Low Earth orbit means below 2,000 km. Most satellites are there.
- About 30,000 objects are tracked there. In our data: about 17,600 satellites (working and dead), 9,900 pieces of debris and 1,570 old rocket stages.
- About 15,900 are working satellites. Starlink alone is about 11,100.
- Each object moves at 7.5 km every second, which is 27,000 km an hour. One lap of the Earth takes about 95 minutes.
- Two objects going different ways can meet at up to 15 km a second.

**Why a collision matters**

- At that speed even a small piece destroys a satellite.
- The wreck becomes thousands of new pieces, and each new piece can cause another collision.
- It has happened: in 2009 two satellites collided. About 700 pieces from that crash are still in orbit and are in our data today.
- Satellites carry navigation, communications, weather and disaster warning. Losing an orbit to debris affects everyone.

**The task we were given**

"Autonomous Collision Avoidance for LEO Satellite Constellations": using public orbit data, predict close passes, rank them by collision probability, and recommend an avoidance move with its timing and direction.

**Why it is hard**

| Difficulty | What it means |
|---|---|
| Too many pairs | 30,000 objects make 440 million pairs, and each must be checked at every moment of the day |
| No error bars | Public data says where an object is, never how sure anyone is |
| Things move | Working satellites change their orbit without telling the public |
| A wrong fix is dangerous | Moving away from one object can move you into another |

**Simple pictures you can use**

- A rifle bullet does about 1 km a second. These objects are 7 to 15 times faster.
- Every object has an address card. The card gives the address, but not how exact it is.

---

## Part 3. The solution

Say this as you open the dashboard.

EDITH is an automatic early-warning system for the whole of low orbit. It does the three things the task asks, and two more.

| The task asks | EDITH does |
|---|---|
| Predict close passes | Finds every pass within 1 km in the next 24 hours, for all 30,000 objects |
| Rank by collision probability | Gives each pass a probability and a worst case, and sorts by the worst case |
| Recommend a move | Finds the smallest safe burn: which object, when, which way, how much |
| (extra) | Checks every burn against the whole sky before recommending it |
| (extra) | Checks its own numbers against a public reference after every run |

Three things to stress:

- **It runs by itself**, every six hours, with no person involved.
- **It covers everything**, not one fleet. Debris against debris is found too.
- **It advises people.** It does not fly satellites. A burn it shows is a recommendation.

---

## Part 4. How it works, step by step

This is the technical workflow. One run goes through these eight steps and takes about seven minutes on a laptop.

### Step 1. Download the data

- **Simple words:** collect the address card of every object.
- **What happens:** orbit data is downloaded from two public catalogues, CelesTrak and Space-Track, and merged by catalogue number. Data older than 14 days is dropped, and so is anything not in low orbit.
- **Detail:** a teammate's pack replaces our size guess with a measured radar size for 11,063 objects.
- **If a download is refused:** CelesTrak refuses to send the same data twice. The run then uses its stored copy, if it is under a day old, and says so.
- **Result:** about 29,700 objects.

### Step 2. Predict where everything will be

- **Simple words:** a standard recipe turns an address card into "where is this object at any moment".
- **What happens:** the recipe is called SGP4. It gives the position and speed of every object every 10 seconds for the next 24 hours.
- **Why SGP4:** public orbit data is made to be read with SGP4. Any other model gives wrong positions from this data.

### Step 3. Find the close passes

- **Simple words:** do not compare everyone with everyone. Sort objects by where they are, and only compare neighbours.
- **What happens:** at each 10-second step a KD-tree lists the objects that are near each other. A quick straight-line estimate throws out pairs that will not get close. The rest get an exact calculation of the closest moment.
- **Speed:** the work is cut into 30-minute blocks of time and spread over all the laptop's cores.
- **Result:** every pass within 1 km. About [2,500] a day.

### Step 4. Work out the risk

- **Simple words:** we never know exactly where an object is. Picture each one inside a fuzzy cloud. The collision chance is the chance that the two real objects, somewhere in their clouds, touch.
- **How big is the cloud:** public data does not say. So we measured it ourselves, from 325,558 pairs of old and new orbit records. A day ahead, debris is off by about 220 m and a Starlink by about 12 km.
- **Two numbers per pass:**
  - **Best estimate:** the chance using the cloud we measured.
  - **Worst case:** the highest the chance could be for any size of cloud.
- **Why the worst case decides:** our measurement of the cloud is itself imperfect. The worst case cannot be fooled by a wrong guess.
- **Levels:** red when the worst case is 1 in 10,000 or more; amber at 1 in 100,000 or more; green below that.
- **Also:** a small machine-learning model adds a forecast of where the risk will end up.

### Step 5. Plan a burn

- **Simple words:** give one satellite a tiny push, early. The push changes how long each lap takes by a tiny amount, so lap after lap the satellite arrives a little earlier or later, until it is far from the meeting point.
- **Who gets a plan:** every red pass where a burn is possible.

| The pass is between | What EDITH does | Why |
|---|---|---|
| A working satellite and something that cannot move | Plans a burn, first in line | A burn is the only way out |
| Two working satellites of different operators | Plans a burn, and says the two must agree | Either could move |
| Two satellites of one fleet | No burn; "Own fleet" | Their operator has exact data; public data for them is off by kilometres |
| Two objects that cannot move | No burn; "Cannot move" | Nobody can act |
| A pass too close in time | No burn; "Too soon" | There is no time to act |

- **The search:** up to 744 burns are tried: 31 times (from half a lap to 8 laps before the pass) and 24 sizes (1 to 100 mm/s, faster or slower).
- **Safe means:** the chance falls below 1 in a million, the worst case below 1 in 100,000, and the two pass further apart.
- **The choice:** the smallest safe burn, because fuel is the satellite's life.

### Step 6. Check the burn

- **Simple words:** stepping out of the way of one car is no good if you step in front of another.
- **What happens:** the new path is flown against every other object for 24 hours. Every risky pass found is worked out a second time without the burn, to see whether the burn caused it or made it worse.
- **The rule:** a burn that creates a risky pass, or makes one worse, is never recommended. The planner tries a different kind of burn: the other direction, another time, or the latest possible moment.
- **If nothing is clean:** it proposes no burn and says "No safe burn", with the reason.
- **Burn back:** an equal and opposite push later puts the satellite back in its old orbit.

### Step 7. Report

- Each run is compared with the previous one. Changes are listed: new passes, passes that got worse, passes that cleared.
- Each pass keeps a history across runs.
- Every red and amber pass gets a one-page briefing and a warning message in the standard format operators use (CDM).
- The run compares its own list with CelesTrak's published list.

### Step 8. Show it, and repeat

- Each run is saved as one folder of files, never changed afterwards.
- A small server hands the results to the dashboard.
- A timer starts the next run six hours later.
- Between runs the server can do two jobs on request: plan a burn for a watched pass, and check any one satellite by name.

**Where the seven minutes go:** download about 15 seconds, prediction and search about 2 minutes, burn searches about 4 minutes, reports about 15 seconds.

---

## Part 5. The tools, and what each one gives us

**The one idea:** Python gives the orders. The heavy maths runs in compiled C and C++ inside the libraries.

| Tool | What it gives us | How that helps |
|---|---|---|
| Python | The language that joins everything | One person built and tested the engine quickly. The heavy maths does not run in Python itself |
| sgp4 (compiled C++) | The standard model that turns orbit data into a position at any time | 1.5 million positions a second on one core, 18 times plain Python. It is also the only model that reads this data correctly |
| NumPy (compiled C) | All positions held as arrays | One instruction handles 30,000 objects, and nothing is copied between libraries |
| SciPy KD-tree | Finds which objects are near each other | 40 ms where checking every pair takes 60 s. Over a day: 6 minutes, not 145 hours |
| SciPy minimiser | The exact moment and distance of closest approach | Our distances match CelesTrak's to 0.35 m |
| SciPy integrator | Flies an orbit under the Earth's real gravity after a burn | Every recommended burn is worked out exactly, not estimated |
| Python processes | Work spread over all cores | A three-day search fell from 32 minutes to 7; "Plan now" from 47 seconds to 20 |
| Pydantic | One definition for every object, pass and plan | A bad record is rejected, not a crash |
| Requests | Downloads from CelesTrak and Space-Track | It retries and keeps a copy, so a refused download does not stop a run |
| FastAPI and Uvicorn | The server that hands results to any screen | 26 routes with little code, and a documentation page written for us |
| APScheduler | The six-hour timer | Runs with no person, and never starts two runs at once |
| LightGBM | A model that forecasts where a pass's risk will end | Trained on 162,634 real warnings from the European Space Agency |
| Matplotlib | The charts in the validation report | Evidence to look at, not just numbers |
| HTML, CSS, JavaScript (no framework) | The dashboard and its pictures | Three files, nothing to install, loads at once |
| pytest and GitHub Actions | 123 tests on every change, on four versions of Python | A mistake is caught before it reaches the demo |
| Render | The public site | One link anyone can open, at no cost |

**The three data sources**

| Source | What it gives us | How that helps |
|---|---|---|
| CelesTrak | Current orbit data, and its own list of close passes | The data for every run, and an outside answer sheet for our distances |
| Space-Track | The full catalogue with all debris, and each object's history | Full coverage, and the history we used to measure how wrong public data is |
| European Space Agency warning dataset | 162,634 real collision warnings | We checked our probability against 20,000, and the forecast model learned from all |

**Why no AI for the physics:** where an object will be, and the chance two objects touch, are exact formulas. A trained model would be less accurate and could not explain itself. Machine learning is used in one place where learning fits: forecasting how a risk will change.

---

## Part 6. Why this is an effective solution

| It is | Because |
|---|---|
| Fast | The whole sky in about seven minutes on a laptop. The KD-tree alone turns 145 hours into 6 minutes |
| Complete | Every tracked object against every other, not one fleet |
| Trustworthy | Checked against CelesTrak (0.35 m) and the European Space Agency (no offset on 20,000 warnings) |
| Careful with bad data | Public data has no error bars, so we measured them, and we rank by the worst case |
| Safe | No burn is recommended until it has been flown against the whole sky, and none that harms another pass |
| Honest | When there is no good burn it says so, with the reason. It calls a red pass "to check", not "dangerous" |
| Automatic | Runs every six hours and reports only what changed |

---

## Part 7. The dashboard: everything on it

Go from top to bottom. For each item: what it shows, what it means, and what happens when you click.

### 7.1 The top bar

| Item | What it is |
|---|---|
| **EDITH** | The name of the system |
| **Story** (link, top right) | Opens the landing page |

### 7.2 The four big numbers

| On screen | What it means |
|---|---|
| **[29,678] objects watched** | Every tracked object in low orbit that the last run used |
| **[2,497] close passes ahead** | Pairs that will come within 1 km of each other in the next 24 hours |
| small line: **together, a 1 in [336] chance of a collision** | All those passes added together, by our best estimate. It shows a real collision today is unlikely |
| **[76] to check** | Red passes: the worst-case chance is 1 in 10,000 or more. This is the level operators commonly act at |
| small line: **[259] to watch, [2,162] safe** | Amber passes (1 in 100,000 or more) and green passes (below that) |
| **[17] burns ready** | Avoidance burns the last run planned and checked |

How to explain "to check": red does not mean "this will hit". A typical red pass has a worst case of about 1 in 4,900 and a best estimate of about 1 in 1.5 million. Red means the worst case is high enough that an operator should look. A smoke alarm works the same way: it sounds far more often than there is a fire.

### 7.3 The Run now button and the line beside it

| Item | What it does |
|---|---|
| **Run now** (button) | Starts a fresh run on live data. It takes about seven minutes. Only one run can go at a time; a second press joins the run in progress |
| **Last run 02:10 AM. Next 08:00 AM.** | When the last run started, and when the timer will start the next one by itself |

While a run is going, the line shows each step as it happens:

| Message | Step |
|---|---|
| Downloading the latest orbit data | Step 1 starts |
| Loaded 29,678 tracked objects ... from CelesTrak and Space-Track | Step 1 done |
| Predicting the path of 29,678 objects for the next 24 hours | Step 2 |
| Searched 12 of 24 hours: 3,772 candidate passes | Step 3 in progress |
| Screened every object against every other: 2,497 close passes within 1 km | Step 3 done |
| Risk levels: 76 red, 259 amber, 2,162 green | Step 4 done |
| Searching for the smallest safe burn for 21 red event(s) | Step 5 starts |
| KUIPER-00053 and SCOUT B-1 R/B: MANEUVER | One burn search finished |
| 17 burn(s) recommended; 17 checked clear of new or worsened close passes | Step 6 done |
| Changes since the previous run: 7 new | Step 7 |
| Wrote 335 operator briefings and 335 standard warning messages | Step 7 |
| Compared with CelesTrak's own list: 270 close passes in common | Step 7 |
| Done. | The page then reloads with the new numbers |

If a run fails, the line says "Failed." with the reason, and the previous run stays on screen.

### 7.4 The line under the button

| Item | What it means |
|---|---|
| **Matches CelesTrak to 0.35 m.** | We recalculated CelesTrak's 200 closest passes from the same data. Our distances differ from theirs by 35 cm in the middle case |
| **Proof** (link) | Jumps down to the Proof section (7.13) |

### 7.5 The five tabs

| Tab | What the list shows |
|---|---|
| **Priority** | The red passes that are not between two satellites of one fleet. The page opens here |
| **All** | Every pass, highest risk first |
| **With a plan** | Only the passes that have a burn ready |
| **Fleets** | One line per fleet (7.11) |
| **2009 replay** | The real 2009 collision, replayed (Part 9) |

### 7.6 The search box

**"Check any satellite: name or number"**

1. Type at least two letters, for example `ISS`, or a catalogue number such as `25544`.
2. A short list appears: the name, its number, and what it is (working satellite, dead satellite, debris or rocket body).
3. Click one. The line says "Checking...".
4. In a few seconds the list shows that object's close passes for the next 24 hours.

What it does behind the screen: it checks that one object, live, against everything at its height, out to 10 km. For the Space Station that is about 1,500 objects and takes 6 seconds. For a Starlink it is about 11,700 objects and takes about 17 seconds.

The result line reads, for example: "4 passes within 10 km in 24 hours, none to check. 1,549 objects checked in 6 s."

Clicking a row then shows one word (To check, Watch or Safe) and the pass's figures. These passes are not part of the scheduled run, so they have no burn.

### 7.7 The grey line under the search box

It changes with the tab.

| Tab | The line | Meaning |
|---|---|---|
| Priority | "[24] of [76] to check. The other [52] are inside one fleet." | The list shows the red passes that someone outside the fleet must look at |
| Fleets | "Own fleet: passes between two of its own satellites." | Explains the "Own fleet" column |
| A fleet you clicked | "STARLINK passes." | The list now shows that fleet's passes |
| 2009 replay | "They collided on 10 February 2009. Public data a day earlier predicted a 584 m miss." | The key fact of the replay |
| After a search | "4 passes within 10 km in 24 hours, none to check. ..." | The result of the check |

### 7.8 The list

Each row is one close pass. Click a row to open it in the Plan panel.

| Column | Meaning |
|---|---|
| **Level** | Red, Amber or Green, set by the worst-case chance |
| **Objects** | The two objects in the pass |
| **Distance** | How far apart they will be at the closest moment |
| **Risk** | The worst-case chance of a collision, written as "1 in N" |
| **Plan** | The decision for this pass |

Every word the Plan column can show:

| Word | Meaning |
|---|---|
| **Burn ready** | A burn is planned and checked for this pass |
| **Cannot move** | Neither object can manoeuvre (two dead objects). A warning only |
| **Own fleet** | Both are satellites of one operator, who steers them with exact data we cannot see |
| **Too soon** | The pass is too close in time to plan a burn with enough notice |
| **No safe burn** | Every burn tried would create a new risky pass or make another one worse |
| **Not planned** | The run reached its ceiling of 40 burn searches. Rare |
| **Watch** | An amber pass: below the action line, watched as new data arrives |
| (empty) | A green pass. No plan is needed |

A small **TEST** tag marks a made-up test object, if one was added. Real runs have none.

### 7.9 The Plan panel: a pass with a burn

Click a **Burn ready** row. The panel shows the recommendation.

**The big line**

"**Slow down by 66 mm/s**" or "**Speed up by 66 mm/s**". This is the burn: a change of speed along the direction of travel. 66 mm/s is a quarter of a kilometre an hour, on a satellite doing 27,000 km an hour.

**The eight figures**

| Figure | Label under it | Meaning |
|---|---|---|
| 0.8 h before the pass | the burn, 0.5 orbits early | When to burn: here half a lap before the pass |
| 76 m to 451 m | distance | How far apart they pass, before and after the burn |
| 1 in 196 to 1 in 737,052 | risk, worst case | The worst-case chance, before and after |
| 0 new, 0 worse | its other passes | The burned path was flown against every object for 24 hours. It creates no risky pass and makes none worse. If it says "3 checked", the satellite had three other risky passes and none got worse |
| STARLINK-4043 | the one that moves | Which of the two objects burns |
| in 7.1 h | the pass | When the closest moment is |
| 1 in 719,131 to 1 in 1,048,396 | risk, best estimate | The chance using the uncertainty we measured, before and after |
| 0.8 h after the pass | burn back to its old orbit | When the equal and opposite burn restores the orbit |

**The paragraph**

It gives the reasoning in plain words:

- Who moves and why: "X cannot manoeuvre, so Y moves", or "Both objects are operational; Y moves because its orbit data is newer. The two operators would need to coordinate."
- The burn: "Smallest safe burn found: 66 mm/s against the direction of travel, 0.5 orbits before the pass."
- Sometimes: "No burn on the grid reaches the safety target; this is the best available." The burn lowers the risk a lot but stops just short of the full target.
- Sometimes: "Burns tried before this one and rejected: 1 made another dangerous pass of the satellite worse." The planner turned down a cheaper burn because of its side effect.
- Sometimes: "The satellite has 3 other dangerous passes in the 24 hours after the burn; none of them gets worse."

**The two links**

| Link | Opens |
|---|---|
| **Warning message (CDM)** | The warning in the standard format operators send each other |
| **Briefing** | A one-page summary of the pass for an operator |

**The three pictures**

| Picture | What it shows | How to read it |
|---|---|---|
| **Gap at the pass** | The distance between the two objects around the closest moment | Solid line: now. Dashed line: after the burn. The dashed line stays higher, so they never get as close. Under it: the closing speed |
| **Every burn tried** | One square per burn | Across: how many laps early. Up: speed up. Down: slow down. White: still risky. Grey: not safe enough. Dark: safe. The ring is the burn that was chosen |
| **Risk, run by run** | The worst-case risk of this pass at each run that saw it | The two dotted lines are the red and amber levels. The ring at the end is the machine-learning forecast of where the risk will end |

### 7.10 The Plan panel: a pass with no burn

Click a row that is not "Burn ready".

- **The big word:** "Watch" (or "Safe" for a green pass).
- **Six figures:** when the pass is; the distance; the risk in the worst case; the risk by best estimate; the closing speed; and "doubt in each position", how unsure we are about where each object is.
- **The paragraph:** the reason there is no burn.
- **The same pictures**, without a burn.

**The Plan now button**

It appears on passes the system only watches: amber passes, and two satellites of one fleet.

1. Press it. The line says "Searching for the smallest safe burn. About 20 seconds, up to a minute."
2. The panel then shows "**What if it moved**" with a full burn card.
3. The decision stays "Watch". The card only shows what a burn would take.

The button does not appear where a new search could not change the answer: Cannot move, Too soon, and No safe burn.

### 7.11 The Fleets tab

One row per fleet. A fleet is a group of working satellites with the same name, such as Starlink or Kuiper.

| Column | Meaning |
|---|---|
| **Fleet** | The fleet's name |
| **Satellites** | How many working satellites it has |
| **Passes** | Close passes that involve one of them |
| **To check** | Red passes with something outside the fleet |
| **Own fleet** | Red passes between two of its own satellites, left to its operator |
| **Burns** | Burns ready for its satellites, and the total push in mm/s |

Click a fleet to see its passes. Click **Fleets** again to return.

### 7.12 What changed

A short list of what is different since the previous run: new red or amber passes, passes that got worse, passes that cleared. Passes inside one fleet are left out. If nothing changed it says "Nothing new since the previous run."

This is what an operator reads first: not 2,500 lines, only the changes.

### 7.13 Proof

Four pictures at the bottom of the page. Part 8 has the detail.

| Picture | One-line meaning |
|---|---|
| **Distance, against CelesTrak** | Each dot is one pass. On the line means our distance equals theirs. 200 of 200 matched |
| **Probability, against ESA** | Our collision chance against the European Space Agency's on 20,000 real warnings. The points follow the line |
| **Error of public data, by its age** | How far an orbit record drifts from a newer one, for each kind of object. Starlink is far above the rest |
| **Does the ranking hold?** | Of the 10 highest-risk passes, how many stay in the top 10 when one assumption changes |

**Full report** opens the written validation report.

### 7.14 Two messages you may see

| Message | Meaning |
|---|---|
| "Cannot reach the system." | The server is not running |
| "Pick a pass." | Nothing is selected yet; click a row |

### 7.15 The public link is slightly different

The public site shows one recorded run. Three things differ from your laptop:

| On the laptop | On the public link |
|---|---|
| Run now button | Hidden |
| Search box and Plan now | Hidden |
| "in 7.1 h" | A date and time, because a recording does not move |
| "Last run ... Next ..." | "Recorded run, 09 Oct 2026 22:52 UTC. The live system runs every six hours." |

---

## Part 8. How we know it is right

| Check | What we did | Result |
|---|---|---|
| Distance | Recalculated CelesTrak's 200 closest passes from the same data | 200 of 200 matched. Middle difference 0.35 m and 0.4 thousandths of a second |
| Probability | Compared ours with the European Space Agency's on 20,000 real warnings | No offset. For the 2,100 that matter most, a middle difference of 2% |
| Worst case | Compared ours with the European Space Agency's "maximum risk" | A middle difference of 4% |
| Random sampling | Checked the formula against 10 to 40 million random draws | Agrees on all 9 cases |
| Error of public data | Compared 325,558 pairs of old and new orbit records of 768 objects | See the table below |
| Ranking | Changed our assumptions and looked at the top 10 | 10 of 10 stay when the error is halved or doubled; 7 of 10 when object size changes |
| Tests | 123 automatic tests, run on every change | All pass, on four versions of Python |

**How wrong public data is, after one day and after three**

| Kind of object | After 1 day | After 3 days |
|---|---|---|
| Dead satellites | 60 m | 170 m |
| Rocket bodies | 150 m | 470 m |
| Debris | 220 m | 750 m |
| Working satellites other than Starlink | 370 m | 1.4 km |
| Starlink | 12 km | 77 km |

Starlink is so different because those satellites push almost all the time, and public data does not include their planned moves. This is why passes inside one fleet are left to the operator.

**Why we look 24 hours ahead, not three days.** We tried three days once. Passes outside fleets stayed at about 1,150 a day. Passes inside fleets grew from 862 on day one to 9,209 on day three. Those extra passes are not real: they come from the error in public data.

**Our own honesty about it.** The error we measured is too small, because it compares public data with public data, not with the truth. That is the reason we rank by the worst case.

---

## Part 9. The 2009 collision

Click the **2009 replay** tab, then the first row.

**What happened.** On 10 February 2009, about 790 km above Siberia, Iridium 33 (a working American satellite) and Cosmos 2251 (a dead Russian one) collided. Nobody moved either.

**What we did.** We gave EDITH only the data that was public at 17:00 the day before, 23 hours 56 minutes ahead. Same code, same thresholds, nothing tuned.

| What EDITH reported, a day before | Value |
|---|---|
| Predicted moment | 16:55:59 (the collision is reported at 16:56) |
| Predicted miss | 584 m |
| Closing speed | 11.65 km/s |
| Worst-case chance | 1 in 90,000 |
| Level | Amber |
| Place among Iridium 33's passes | First of two, and the only one flagged |

**How to say it**

- Say: "It found that pass, at the right second, as the most dangerous pass of Iridium 33."
- Do not say: "It ranked the collision number one." The replay checks one satellite and found two passes.

**Why it is amber and not red.** Public data predicted a miss of 584 m, so public data was wrong by at least that much. Red starts at 1 in 10,000; this was 1 in 90,000. Nobody could have rated it red from that data, and we do not move the line to make the story look better.

**The lesson.** Public data alone is not enough. That is why we measure its error and rank by the worst case.

The panel also shows "What if it moved": a burn of 1 mm/s. It is that small only because the pass sat right on the amber line. Do not present it as "what would have saved it".

---

## Part 10. The landing page story

After the dashboard, click **Story** and scroll from the top to the end. Each row is one screen of the page, in order, with what to say there.

| # | Heading on the page | What to say |
|---|---|---|
| 1 | EDITH: Sentinel of Low Earth Orbit | One line: EDITH watches low orbit and advises when to move |
| 2 | 30,000 Objects. 7.5 km/s. Zero Margin for Error. | The space age began with one satellite in 1957. Today about 30,000 tracked objects share the same space |
| 3 | Orbital Milestones & Critical Collisions | Walk the timeline: the first satellite; the warning that collisions could chain; a satellite destroyed on purpose in 2007, whose pieces are still up; the 2009 collision; the arrival of very large fleets; and EDITH |
| 4 | Rules of Engagement in Crowded Corridors | These are the rules EDITH follows: the satellite that can move, moves; two fleets must agree; two dead objects get a warning; every burn is checked for 24 hours; a second burn restores the orbit |
| 5 | Critical Infrastructure in Low Earth Orbit | What depends on these satellites: navigation, banking time signals, disaster warning, communications |
| 6 | What EDITH Protects Every Day | The four kinds of mission: Earth observation, communications, weather, crewed spaceflight |
| 7 | The Exponential Sky | Launches per year, from a few to thousands. Most low-orbit satellites fly at about 550 km |
| 8 | 30,000 Objects. 440 Million Combinations. | The size of the problem, again: every pair is a possible pass |
| 9 | Tracked vs Untracked Population | Only objects larger than about 10 cm are tracked. Far more small pieces exist that nobody can see |
| 10 | Kinetic Reality: 15 km/s closing speed | Two crossing satellites meet at 54,000 km an hour |
| 11 | The Price of False Alarms vs Missed Collisions | Moving when you did not need to wastes fuel and shortens a satellite's life. Not moving when you should have loses the satellite. This is why the smallest safe burn matters |
| 12 | The EDITH Core Architecture | The six steps again, every six hours |
| 13 | The Autonomous Decision Engine | The four pillars: download, KD-tree search, collision probability, burn planning |
| 14 | 251 Metres at 13.2 km/s, and The Smallest Safe Move | A real example from our runs: a Kuiper satellite and a dead rocket stage, 251 m apart. With ten hours in hand, a 43 mm/s push moved the pass to 2.66 km |
| 15 | The Kessler Cascade | Move the mouse into the orbit ring to show how one collision spreads pieces around the whole orbit |
| 16 | The Risk Matrix | Red: worst case of 1 in 10,000 or more, a burn is planned. Amber: 1 in 100,000 or more, watched |
| 17 | The closing statement on open standards | EDITH uses the standard formats and models of the field, so its results can be checked |
| 18 | "While you spent N minutes on this page..." | A nice last fact: read the number of kilometres satellites covered while you talked |
| 19 | Watch Everything. Move Only When You Must. | Your closing line |

**Three lines on the page that the system does not back.** Do not read them out as results.

| On the page | What is true |
|---|---|
| "eliminates 95% of false-alarm burns" | We never measured this. Say instead: "it recommends the smallest burn, and only for passes above the action line" |
| "1,756 passes" and "5 burns" | Those were one midday run, when a run planned five burns. A run now plans every pass it can: about 2,500 passes and about 17 burns. Use the dashboard's numbers |
| "burn calculated, verified, and queued" and "live orbital telemetry" | EDITH recommends; it does not send commands. It uses public orbit data, refreshed every six hours |

---

## Part 11. Limits, said by you

Say these before a judge finds them.

- Public data is rough, and very rough for satellites that steer.
- Pieces smaller than about 10 cm are not tracked by anyone publicly.
- Our measured error is itself too small, which is why we rank by the worst case.
- Burns are treated as instant, and each is checked for 24 hours.
- Some passes get no burn. Two objects that meet every lap cannot be separated by one small push; EDITH says so.
- Some burns stop just short of the full safety target, because the search stops at 100 mm/s. Each says "this is the best available".
- EDITH advises people. It does not fly satellites.

**What real operations would need:** exact data from the operator, agreement between operators, and a link to the satellite itself. EDITH is built so better data can replace the public data without changing the rest.

**Your closing line:** "Watch everything. Move only when you must."

---

## Part 12. Questions judges ask

| Question | Answer |
|---|---|
| Why Python? Is it not slow? | Python only gives the orders. The heavy maths runs in compiled C and C++: 1.5 million positions a second. The whole sky takes seven minutes, and the data only changes a few times a day |
| Why NumPy? | It holds all 30,000 objects as one block of numbers, so one instruction does the work of 30,000 loop steps in compiled code |
| Why a KD-tree? | 440 million pairs at each moment. The KD-tree finds the near ones in 40 ms; checking every pair takes 60 s for the identical answer |
| Why not C++ or Rust? | The slow parts already are C and C++. Rewriting the thin layer above them would cost days and gain little |
| Why SGP4 and not a better physics model? | Public orbit data is made for SGP4. A "better" model on this data gives worse answers |
| Where is the machine learning? | One model, LightGBM, trained on 162,634 real warnings, forecasts how a pass's risk will change. The physics uses exact formulas |
| How do you know the numbers are right? | Distances match CelesTrak to 0.35 m; probability has no offset from the European Space Agency on 20,000 warnings; the error of public data was measured from 325,558 pairs of records |
| Public data has no uncertainty. Where does the probability come from? | We measured the uncertainty by kind of object and age of data, and we also compute the worst case over every possible size |
| If collisions are rare, why so many flagged passes? | Close passes worth a check are common; collisions are not. All passes of a day together make about a 1 in 340 chance of one collision. Red is judged on the worst case |
| Does a satellite have to move when it says "Burn ready"? | No. It is advice. An operator would first get better tracking. The burn is ready so no time is lost if the risk is confirmed |
| Why does a risky pass have no burn? | Four reasons, and the list says which: one fleet, neither can move, too soon, or no safe burn exists |
| What if the other satellite also moves? | The plan names who we propose should move and says the two operators must agree. The standard warning message exists for that |
| Why are there so many Starlink passes? | About 11,100 of the 30,000 objects are Starlink. Public data for them is off by 12 km a day, so we list those passes and leave them to their operator |
| Did you catch the 2009 collision? | A day before, from public data: the most dangerous pass of Iridium 33, at the right second, rated amber, because public data predicted a 584 m miss |
| Why only 24 hours ahead? | Further out, passes inside fleets multiply tenfold from data error alone. They are not real |
| How fast is it? | About seven minutes for the whole sky on a 12-core laptop: under two for the search, under four for the burn searches |
| How do you avoid drowning the operator in alerts? | Only changes are reported, and the page opens on about 24 priority passes, not 2,500 |
| Why files and not a database? | A run is one folder that is never changed. Anything can read it |

---

## Part 13. Numbers worth remembering

| Number | What it is |
|---|---|
| 30,000 | Tracked objects in low orbit |
| 440 million | Pairs of objects |
| 7.5 km/s | Speed of each object; up to 15 km/s when two meet |
| 1 km | How close counts as a close pass |
| 1 in 10,000 | Worst-case chance that makes a pass red |
| 6 hours | Time between automatic runs |
| 7 minutes | One full run on a laptop |
| 744 | Burns tried for one pass, at most |
| 24 hours | How long each burn is checked against the whole sky |
| 0.35 m | Our distance against CelesTrak's, on 200 passes |
| 20,000 | Real European Space Agency warnings our probability was checked against |
| 325,558 | Pairs of orbit records used to measure the error of public data |
| 220 m and 12 km | Error after one day for debris, and for a Starlink |
| 584 m | What public data predicted for the 2009 collision |
| 40 ms against 60 s | KD-tree against checking every pair |
| 123 | Automatic tests |

---

## Part 14. Starting everything

Open two terminals in the project folder.

| What | Command | Address |
|---|---|---|
| Landing page | `node landing\server.js` | http://localhost:3000 |
| System and dashboard | `.venv\Scripts\python -m uvicorn fusion.api.main:app --port 8000` | http://localhost:8000 |
| Check everything works | `.venv\Scripts\python scripts\check_server.py` | |

Before you present:

1. Press **Run now** about ten minutes early, so the passes are fresh.
2. Open one browser tab on http://localhost:3000. Its **Open dashboard** button leads to the dashboard, and the dashboard's **Story** link leads back.
3. Find one **Burn ready** row and, if there is one, a **No safe burn** row. You will click these.

The public link is https://edith-guhk.onrender.com. It opens on the landing page and shows a recorded run. It sleeps after 15 minutes without a visitor, so open it a minute before you show it.
