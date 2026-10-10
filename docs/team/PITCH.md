# EDITH: the recorded pitch

Notes for one video of about seven minutes. Each part has four things:

- **Screen:** what to show and click.
- **Say this much:** a short version, about as long as the time allows.
- **More you can say:** facts, reasons and examples to pick from, in your own words.
- **Simple picture:** one everyday comparison, where it helps.

You will not say everything here. Read a part, look at the screen, and explain it your way. If you only say the short versions, the video is about seven minutes.

Numbers in [square brackets] change with every run: read them off the screen. Every other number is fixed.

## Before you record

1. Start the landing page: `node landing\server.js` (http://localhost:3000).
2. Start the system: `.venv\Scripts\python -m uvicorn fusion.api.main:app --port 8000` (http://localhost:8000).
3. Press **Run now** and wait about seven minutes, so the passes are fresh.
4. Open one browser tab, on the landing page. The whole video stays in that tab. Hide the bookmarks bar and set the zoom to 110%.
5. On the dashboard, find one row that says **Burn ready** and one that says **No safe burn**. You will click these two.
6. Speak slowly. To save time, leave out parts 7 and 8.

Record on the laptop, not on the public link: only the laptop has the satellite search. Show the public link at the very end.

## The whole thing in four sentences

If you forget everything else, say these.

1. About 30,000 objects fly in low orbit, and nobody can watch 440 million pairs by hand.
2. EDITH watches all of them from public data: it finds every close pass, works out the risk, and plans the smallest safe move.
3. Every move is checked against the whole sky before it is recommended.
4. We proved it against CelesTrak, the European Space Agency and the real 2009 collision.

## The parts

### 1. The problem (0:00 to 0:40)

**Screen:** the landing page, at the top. Scroll slowly while you talk.

**Say this much:**

> "This is EDITH. Right now about thirty thousand tracked objects are circling the Earth in low orbit: working satellites, dead satellites, old rocket stages and debris. Each one moves at seven and a half kilometres every second. When two of them cross, they can meet at fifteen kilometres a second. At that speed even a small piece destroys a satellite, and the wreck becomes thousands of new pieces."

**More you can say:**

- Low Earth orbit means below 2,000 km. That is where most satellites are.
- What is up there, in our own data: about 17,600 satellites (working and dead), 9,900 pieces of debris and 1,570 old rocket stages.
- About 15,900 of them are working satellites. Starlink alone is about 11,100.
- 7.5 km every second is 27,000 km an hour. One lap of the Earth takes about 95 minutes.
- Two objects going opposite ways meet at up to 15 km a second.
- A collision does not end the problem. It makes more debris, and more debris makes more collisions.
- A real one happened in 2009. About 700 pieces from it are still in orbit, and they are in our data today.
- Pieces smaller than about 10 cm are not tracked by anyone publicly.

**Simple picture:** a rifle bullet travels about one kilometre a second. These objects are seven to fifteen times faster.

### 2. The task (0:40 to 1:10)

**Screen:** keep scrolling the landing page.

**Say this much:**

> "Our task: use only public orbit data to predict which objects will pass dangerously close, rank those passes by how likely a collision is, and recommend an avoidance move, with its timing and direction. Two things make it hard. Thirty thousand objects make four hundred and forty million pairs. And public data comes with no error bars, so nobody tells you how wrong a position might be."

**More you can say:**

- The problem statement was "Autonomous Collision Avoidance for LEO Satellite Constellations".
- It asks for three things: predict, rank, recommend.
- 30,000 objects make 440 million pairs. Each pair has to be checked at every moment of the day, not once.
- Public orbit data is a few numbers for each object, updated a few times a day. It says where the object is, never how sure anyone is about that.
- Satellites that can steer change their orbit without telling the public.
- So the hard parts are speed (too many pairs) and trust (data with no error bars).

**Simple picture:** every object has an address card. The card says where it lives, but not how old or how exact the address is.

### 3. The solution (1:10 to 1:35)

**Screen:** click **Open dashboard** at the top right as you finish.

**Say this much:**

> "EDITH does the whole job by itself, every six hours. It downloads every public orbit, predicts the next twenty-four hours, finds every close pass, works out the risk, plans the smallest safe move, and checks that move against everything else in the sky. This is its dashboard."

**More you can say:**

- Six steps: download, predict, search, work out the risk, plan a move, check the move.
- Then it reports what changed and repeats every six hours, with no person involved.
- It covers the whole of low orbit, not one fleet. Debris against debris is found too.
- A full run takes about seven minutes on a laptop.
- It does all three things the task asks, and two more: it checks its own burns, and it checks itself against a public reference after every run.
- It advises people. It does not fly satellites.

**Simple picture:** a weather forecast for collisions, refreshed four times a day, with advice attached.

### 4. The four numbers (1:35 to 2:20)

**Screen:** the top of the dashboard. Point at each number with the mouse as you name it.

**Say this much:**

> "These four numbers come from the latest run. Objects watched: every tracked object in low orbit. Close passes ahead: every pair that will come within one kilometre in the next day. The small line under it matters: all those passes together make about a one in three hundred chance of a collision today. Collisions are rare; close passes are not. To check: the passes whose worst-case risk is one in ten thousand or more, the level where operators start to act. Burns ready: avoidance moves already planned and verified. And here: our distances match CelesTrak, the public reference, to thirty-five centimetres."

**More you can say:**

- **Objects watched** [29,678]: from two public catalogues, CelesTrak and Space-Track. Orbit data older than 14 days is dropped.
- **Close passes ahead** [2,497]: two objects within 1 km of each other in the next 24 hours.
- **"1 in [336] chance of a collision"**: all the passes added together, by our best estimate. It shows that a real collision on any one day is unlikely.
- **To check** [76]: red passes. The worst-case chance is 1 in 10,000 or more. That is the level operators commonly act at.
- **To watch** [259] is amber: 1 in 100,000 or more. **Safe** [2,162] is green.
- **Why the worst case:** public data has no error bars. So we ask: what is the highest chance this could be, for any amount of error? A wrong guess about the error cannot hide a danger.
- A typical red pass has a worst case of about 1 in 4,900, but a best estimate of about 1 in 1.5 million. Red means "look at this", not "this will hit".
- Only about 130 of the 15,900 working satellites have a red pass on a given day.
- **Burns ready** [17]: every one was checked against the whole sky.
- **"Last run ... Next ..."**: it runs by itself every six hours.

**Simple picture:** a smoke alarm. It goes off far more often than there is a fire, because missing a fire costs too much.

### 5. The list (2:20 to 3:00)

**Screen:** the Priority list. Move the mouse along the column headings.

**Say this much:**

> "The page opens on Priority: the passes to check, leaving out those between two satellites of one fleet, because their operator steers those with better data than the public has. Each row is one pass. Level is red, amber or green. Distance is how close they will come. Risk is the worst-case chance of a collision. Plan is the decision. Burn ready means a move is planned. Cannot move means both objects are dead. Too soon means there is no time left. No safe burn means every move we tried would cause a new problem."

**More you can say:**

- **Priority** shows [24] of the [76] red passes. The other [52] are between two satellites of one fleet, mostly Starlink and Starlink.
- **Why fleets are left out:** we measured that public data for a Starlink is off by 12 km after one day. Its operator has exact data and steers the satellites itself.
- Our own check: of 427 such passes that CelesTrak listed, only one was still there a day later.
- **Every row ends in a burn or a reason.** Nothing is left unexplained.
- **Who moves:** the object that can. If both can, the one with newer data, and the plan says the two operators must agree.
- The other tabs: **All** is every pass, **With a plan** is only the burns, **Fleets** is one line per operator, **2009 replay** is the real collision.

**Simple picture:** a hospital triage list. Everyone is listed, the urgent ones are on top, and each has a decision next to the name.

### 6. One burn (3:00 to 4:05)

**Screen:** click the **Burn ready** row. Point at each figure, then at each of the three pictures, then at the two links.

**Say this much:**

> "Let me open one. These two would pass [76 metres] apart, closing at over twelve kilometres a second. EDITH says: slow down by [66] millimetres per second, [half an orbit] before the pass. That is a tiny push, but the pass grows from [76 metres] to [451 metres], and the worst-case risk falls from [one in 200] to [one in 700,000]. 'Zero new, zero worse' means we flew the new path against every other object for twenty-four hours: it creates no new danger and makes no other pass worse. Here is which satellite moves, our best estimate of the risk, and the burn that puts the satellite back afterwards. The first picture is the gap between them, with and without the burn. The second shows every burn we tried: dark is safe, and the ring is the one we chose. The third is the risk at each run, and its ring is a small machine-learning model forecasting where the risk will end. These two links are the standard warning message that operators exchange, and a briefing."

**More you can say:**

- **How a tiny push works:** it changes how long one lap takes by a tiny amount. Lap after lap the satellite arrives a little earlier or later, until it is far from the meeting point.
- **A push half a lap early works differently:** it changes the satellite's height at the meeting point.
- **How small:** 66 mm/s is a quarter of a kilometre an hour. The satellite is doing 27,000 km an hour.
- **How it chooses:** it tries up to 744 burns (31 times, 24 sizes) and takes the smallest that is safe, because fuel is the satellite's life.
- **Safe means three things:** the chance drops below 1 in a million, the worst case drops below 1 in 100,000, and the two pass further apart.
- **The check:** the new path is flown against every other object for 24 hours. Each dangerous pass found is worked out again without the burn, to see if the burn caused it or made it worse.
- **A burn that harms another pass is never recommended.** The planner tries a different kind of burn instead.
- **Burn back:** an equal and opposite push later puts the satellite back in its old orbit.
- **Earlier is cheaper:** one pass needed 43 mm/s with ten hours in hand, and 66 mm/s when there was little time left.
- **It is advice.** A real operator would first get better tracking. The burn is ready so no time is lost if the risk is confirmed.
- **CDM** means conjunction data message: the standard format operators use to warn each other.

**Simple picture:** leaving home ten seconds later so you do not reach the corner at the same moment as the other person. Then checking that the new timing does not make you meet someone else.

### 7. A pass with no burn (4:05 to 4:25)

**Screen:** click the **No safe burn** row. If the list has none today, skip this part.

**Say this much:**

> "Sometimes the right answer is no burn. These two meet on every orbit, so a burn that clears one meeting pushes the danger to the next. EDITH tried five burns, saw that, and says so."

**More you can say:**

- A real example from our runs: one satellite and a Starlink met once every lap, at 7.9, 5.0, 2.4, 0.18, 1.7, 3.2 and 4.4 km.
- Of the five burns tried, two created a new dangerous pass and three made another one worse.
- The card says exactly that, with the counts.
- The other reasons a pass has no burn: both objects are dead, there is no time left, or both belong to one fleet.
- A system that always answers "burn" is easy to build. One that knows when not to is more useful.

**Simple picture:** two runners on the same track at nearly the same speed. Dodging at one corner just means meeting at the next.

### 8. Any satellite, and fleets (4:25 to 4:50)

**Screen:** type `ISS` in the box and click the first result. When the list appears, click **Fleets**.

**Say this much:**

> "Any satellite can be checked by name. The Space Station: [four] passes within ten kilometres today, none to check, found in six seconds. And Fleets gives each operator one line: its passes to check and its burns."

**More you can say:**

- Any of the 29,700 objects can be found by name or catalogue number.
- The check is done live, against everything at that satellite's height. For the Space Station that is about 1,500 objects.
- It looks out to 10 km, wider than the 1 km of the main run, so there is always something to show.
- A Starlink takes about 17 seconds, because its height is crowded: about 11,700 objects.
- **Fleets:** about 230 fleets. Starlink has about 11,100 satellites, [18] passes to check and [45] inside its own fleet.
- The Burns column also adds up the fuel: the total push in mm/s.

### 9. Proof (4:50 to 5:35)

**Screen:** click **Proof** under the Run button. Point at each of the four pictures in turn.

**Say this much:**

> "How do we know this is right? Four checks. One: we recomputed CelesTrak's two hundred closest passes from the same data. All two hundred matched, to thirty-five centimetres. Two: we compared our probability with twenty thousand real warnings from the European Space Agency. No offset. Three: since public data has no error bars, we measured them ourselves, from three hundred and twenty-five thousand pairs of orbit records. After one day, debris is off by about two hundred metres, and a Starlink by twelve kilometres. Four: the ranking holds when our assumptions change."

**More you can say:**

- **Picture 1, distance:** each dot is one pass, CelesTrak's distance across and ours up. On the line means equal. 200 of 200 matched; the middle difference is 0.35 m and 0.4 thousandths of a second.
- **Picture 2, probability:** our collision chance against the European Space Agency's on 20,000 real warnings. No offset. For the 2,100 that matter most, the middle difference is 2%.
- **Picture 3, error of public data:** we compared 325,558 pairs of old and new orbit records of 768 objects. After one day: a dead satellite is off by 60 m, debris by 220 m, a working satellite by 370 m, a Starlink by 12 km.
- **Why Starlink is so different:** those satellites push almost all the time, and public data does not include their planned moves.
- **Picture 4, ranking:** halve or double the error and the top 10 stays the same, 10 of 10. Change the assumed size of the objects and 7 of 10 stay.
- **Our own honesty about it:** the measured error is too small, because it compares public data with public data, not with the truth. That is the reason we rank by the worst case.
- **One more finding:** we tried looking three days ahead. Passes outside fleets stayed at about 1,150 a day, but passes inside fleets grew from 862 to 9,209. Those are not real, so we look 24 hours ahead.
- There are also 123 automatic tests, run on every change.

**Simple picture:** we did not mark our own homework. We compared our answers with two outside answer sheets.

### 10. The 2009 collision (5:35 to 6:00)

**Screen:** scroll up, click **2009 replay**, then click the first row.

**Say this much:**

> "And one real case. In 2009 Iridium 33 and Cosmos 2251 collided. We gave EDITH only the data that was public the day before. It found that pass, at the right second, as the most dangerous pass of Iridium 33. It rated it amber, not red, because public data predicted a miss of 584 metres. That is the honest answer, and it is why we rank by the worst case."

**More you can say:**

- It happened on 10 February 2009, about 790 km above Siberia. Iridium 33 was a working American satellite, Cosmos 2251 a dead Russian one. Nobody moved either.
- We used only data public at 17:00 the day before, 23 hours 56 minutes ahead.
- Same code, same thresholds, nothing tuned for this case.
- EDITH predicted the pass for 16:55:59. The collision is reported at 16:56.
- Predicted miss: 584 m. Worst-case chance: 1 in 90,000. That is amber.
- It was the most dangerous of Iridium 33's passes, and the only one flagged.
- **Say it carefully:** "most dangerous pass of Iridium 33", not "ranked number one". The replay checks that one satellite, and it found two passes.
- **Why not red:** public data was wrong by at least 584 m that day. Nobody could have rated it red from that data, and we do not move the line to make the story look better.
- The lesson: public data alone is not enough, which is why we measure its error and rank by the worst case.

### 11. Which tool does what (6:00 to 6:50)

**Screen:** click **Priority**, then click the first **Burn ready** row so its card is open, and scroll to the top of the dashboard. Point at each item as you name its tool, in this order: objects watched, close passes ahead, the Risk column, the burn card, the third picture, the "Last run" line.

**Say this much:**

> "Every item on this page comes from one tool. The orbits behind this number are downloaded from CelesTrak and Space-Track, and Pydantic checks each record. For the close passes, SGP4, a compiled C++ library, predicts every position; NumPy holds them as arrays; and SciPy's KD-tree finds the neighbours in forty milliseconds, where checking every pair takes sixty seconds. The risk is our own probability maths, on NumPy and SciPy. The burn search flies each candidate orbit with SciPy's integrator. This forecast ring is LightGBM, trained on the European Space Agency's real warnings. APScheduler starts a run every six hours, FastAPI serves the results, and this page is plain JavaScript. Python only gives the orders; the heavy maths is compiled C and C++, which is why the whole sky takes about seven minutes on a laptop."

**More you can say:**

- **Why Python:** it is the steering wheel, not the engine. The engine is compiled C and C++ inside the libraries.
- **How fast:** 1.5 million positions a second on one core. That is 18 times the same maths written in plain Python.
- **Why SGP4:** public orbit data is made to be read with SGP4. A "better" model on this data gives worse answers.
- **Why a KD-tree:** it sorts objects by where they are and only compares neighbours. 40 milliseconds against 60 seconds, for the identical answer.
- **Over a whole day, one core:** 6 minutes with the KD-tree, 145 hours checking every pair. The method matters more than the language.
- **Why several processes:** the search splits into 30-minute blocks of time, one per core. Eleven cores turned 32 minutes into 7.
- **Why no AI for the physics:** where an object will be and the chance of a hit are exact formulas. A trained model would be less accurate and could not explain itself.
- **Where the machine learning is:** one place where learning fits. A LightGBM model, trained on 162,634 real warnings, forecasts how a pass's risk will change.
- **Why files, not a database:** each run is one folder that is never changed afterwards. Anyone can read it.
- **Why plain JavaScript:** one page, no build step, nothing to install.

**Simple picture:** Python is the conductor. The orchestra is C and C++.

### 12. Limits and close (6:50 to 7:10)

**Screen:** open https://edith-guhk.onrender.com in the last few seconds.

**Say this much:**

> "The limits: public data is rough, pieces smaller than ten centimetres are not tracked, and EDITH advises people; it does not fly satellites. Every change is checked by a hundred and twenty-three automatic tests. And it is live at this address. Thank you."

**More you can say:**

- Public data is rough, and very rough for satellites that steer.
- Our measured error is itself too small, so we rank by the worst case.
- Burns are treated as instant, and each is checked for 24 hours.
- Some passes get no burn, and the system says why.
- What real operations would need: exact data from the operator, agreement between operators, and a link to the satellite itself. EDITH is built so better data can replace the public data without changing the rest.
- The tests run on GitHub on every change, on four versions of Python.
- The public link shows a recorded run. The live system runs on a laptop.

## Numbers worth remembering

| Number | What it is |
|---|---|
| 30,000 | Tracked objects in low orbit |
| 440 million | Pairs of objects |
| 7.5 km/s | Speed of each object; 15 km/s when two meet head-on |
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

## What the words on the dashboard mean

| On screen | Meaning |
|---|---|
| Objects watched | Every tracked object whose orbit comes below 2,000 km |
| Close passes ahead | Pairs that will come within 1 km of each other in the next 24 hours |
| "together, a 1 in N chance of a collision" | The chance that at least one of all those passes is a collision, by our best estimate |
| To check | Red passes: worst-case risk of 1 in 10,000 or more |
| To watch / safe | Amber: 1 in 100,000 or more. Green: below that |
| Burns ready | Avoidance burns the run has planned and verified |
| Priority | The red passes that are not between two satellites of one fleet |
| Distance | How far apart the two objects are at the closest moment |
| Risk | The worst-case chance of a collision, over every size the uncertainty could have |
| Risk, best estimate | The chance using the uncertainty we measured |
| Burn ready | A burn is planned for this pass |
| Cannot move | Neither object can manoeuvre; a warning only |
| Too soon | The pass is too close in time to plan a burn |
| No safe burn | Every burn tried would create or worsen another dangerous pass |
| Own fleet | Both are satellites of one operator, who steers them with better data |
| Watch | An amber pass: keep watching as new data arrives |
| "Slow down by 66 mm/s" | The burn: a change of speed along the direction of travel, here 66 millimetres per second |
| "0.5 orbits early" | When to burn: half a lap of the Earth, about 47 minutes, before the pass |
| "0 new, 0 worse" | The burned path, checked against every object for 24 hours, creates no dangerous pass and worsens none |
| Burn back to its old orbit | The equal and opposite burn that restores the orbit after the pass |
| Gap at the pass | Distance between the two objects around the closest moment: solid now, dashed after the burn |
| Every burn tried | Each square is one burn. Across: how early. Up and down: speed up or slow down. Dark is safe; the ring is the one chosen |
| Risk, run by run | The worst-case risk of this pass at each run that saw it. The ring is the model's forecast of where it ends |
| Warning message (CDM) | The standard message format operators use to warn each other |
| Proof | Our results against CelesTrak, against the European Space Agency, and our measurement of public data's error |

## Which tool does what

Part 11 names these while you point. This table is the full list: what each one gives us, and what we gain from it.

| Tool | What it gives us | How that helps |
|---|---|---|
| Python | The language that joins everything | One person built and tested the whole engine quickly. The heavy maths does not run in Python itself |
| sgp4 (compiled C++) | The standard model that turns public orbit data into a position at any time | 1.5 million positions a second on one core, 18 times plain Python. It is also the only model that reads this data correctly |
| NumPy (compiled C) | All positions held as arrays | One instruction handles 30,000 objects. sgp4 and SciPy both use the same arrays, so nothing is copied |
| SciPy KD-tree | Finds which objects are near each other | 40 ms where checking every pair takes 60 s. Over a day: 6 minutes, not 145 hours |
| SciPy minimiser | The exact moment and distance of closest approach | Our distances match CelesTrak's to 0.35 m |
| SciPy integrator | Flies an orbit under the Earth's real gravity after a burn | Every recommended burn is worked out exactly, not estimated |
| Python processes | The search and the burn checks spread over all cores | A three-day search fell from 32 minutes to 7; "Plan now" from 47 seconds to 20 |
| Pydantic | One definition for every object, pass and plan | A bad record is rejected, not a crash. Engine, server and teammates' packs all agree on the data |
| Requests | Downloads from CelesTrak and Space-Track | Retries, and keeps a copy, so a refused download does not stop a run |
| FastAPI and Uvicorn | The server that hands results to any screen | About 25 routes with little code, each response checked, and a documentation page written for us |
| APScheduler | The six-hour timer | Runs with no person involved, and never starts two runs at once |
| LightGBM | A model that forecasts where a pass's risk will end | Trained on 162,634 real warnings from the European Space Agency. It is the forecast ring on the dashboard |
| pandas, scikit-learn, joblib | Used to train, measure and store that model | The model and its test results can be rebuilt from the data |
| Matplotlib | The charts in the validation report | Evidence a judge can look at, not just numbers |
| HTML, CSS and JavaScript, no framework | The dashboard, with pictures drawn as SVG | Three files, nothing to build or install, and it loads at once |
| pytest and GitHub Actions | 123 tests, run on every change on four versions of Python | A mistake is caught before it reaches the demo. The badge on GitHub proves it |
| Render | The public show-only site | One link anyone can open, at no cost |
| Git and GitHub | The history of every change | Teammates' work was merged through pull requests |

The three data sources, and what each is for:

| Source | What it gives us | How that helps |
|---|---|---|
| CelesTrak | Current orbit data, and its own published list of close passes | The data for every run, and an outside answer sheet to check our distances against |
| Space-Track | The full catalogue with all debris, and the history of each object's orbit data | Complete coverage, and the history we used to measure how wrong public data is |
| European Space Agency warning dataset | 162,634 real collision warnings | We checked our probability against 20,000 of them, and the forecast model learned from all of them |

Longer answers to judges' questions are in `PROJECT_EXPLAINED.md`, sections 8 and 9.
