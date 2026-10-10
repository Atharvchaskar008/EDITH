# EDITH: the recorded pitch

A script for one video of about seven minutes. Each part says what is on screen, what to click, and what to say. The quoted text is about 1,000 words, which is close to seven minutes at a normal speaking pace. The whole video stays on the landing page and the dashboard.

Numbers in [square brackets] change with every run: read them off the screen. Every other number is fixed.

## Before you record

1. Start the landing page: `node landing\server.js` (http://localhost:3000).
2. Start the system: `.venv\Scripts\python -m uvicorn fusion.api.main:app --port 8000` (http://localhost:8000).
3. Press **Run now** and wait about seven minutes, so the passes are fresh.
4. Open one browser tab, on the landing page. The whole video stays in that tab. Hide the bookmarks bar and set the zoom to 110%.
5. On the dashboard, find one row that says **Burn ready** and one that says **No safe burn**. You will click these two.
6. Speak slowly. The full script runs to about 7:10. Leaving out parts 7 and 8 brings it to about 6:25.

Record on the laptop, not on the public link: only the laptop has the satellite search. Show the public link at the very end.

## The script

### 1. The problem (0:00 to 0:40)

**Screen:** the landing page, at the top. Scroll slowly while you talk.

> "This is EDITH. Right now about thirty thousand tracked objects are circling the Earth in low orbit: working satellites, dead satellites, old rocket stages and debris. Each one moves at seven and a half kilometres every second. When two of them cross, they can meet at fifteen kilometres a second. At that speed even a small piece destroys a satellite, and the wreck becomes thousands of new pieces."

### 2. The task (0:40 to 1:10)

**Screen:** keep scrolling the landing page.

> "Our task: use only public orbit data to predict which objects will pass dangerously close, rank those passes by how likely a collision is, and recommend an avoidance move, with its timing and direction. Two things make it hard. Thirty thousand objects make four hundred and forty million pairs. And public data comes with no error bars, so nobody tells you how wrong a position might be."

### 3. The solution (1:10 to 1:35)

**Do:** click **Open dashboard** at the top right as you finish.

> "EDITH does the whole job by itself, every six hours. It downloads every public orbit, predicts the next twenty-four hours, finds every close pass, works out the risk, plans the smallest safe move, and checks that move against everything else in the sky. This is its dashboard."

### 4. The four numbers (1:35 to 2:20)

**Screen:** the top of the dashboard. Point at each number with the mouse as you name it.

> "These four numbers come from the latest run. Objects watched: every tracked object in low orbit. Close passes ahead: every pair that will come within one kilometre in the next day. The small line under it matters: all those passes together make about a one in three hundred chance of a collision today. Collisions are rare; close passes are not. To check: the passes whose worst-case risk is one in ten thousand or more, the level where operators start to act. Burns ready: avoidance moves already planned and verified. And here: our distances match CelesTrak, the public reference, to thirty-five centimetres."

### 5. The list (2:20 to 3:00)

**Screen:** the Priority list. Move the mouse along the column headings.

> "The page opens on Priority: the passes to check, leaving out those between two satellites of one fleet, because their operator steers those with better data than the public has. Each row is one pass. Level is red, amber or green. Distance is how close they will come. Risk is the worst-case chance of a collision. Plan is the decision. Burn ready means a move is planned. Cannot move means both objects are dead. Too soon means there is no time left. No safe burn means every move we tried would cause a new problem."

### 6. One burn (3:00 to 4:05)

**Do:** click the **Burn ready** row. Point at each figure, then at each of the three pictures, then at the two links.

> "Let me open one. These two would pass [76 metres] apart, closing at over twelve kilometres a second. EDITH says: slow down by [66] millimetres per second, [half an orbit] before the pass. That is a tiny push, but the pass grows from [76 metres] to [451 metres], and the worst-case risk falls from [one in 200] to [one in 700,000]. 'Zero new, zero worse' means we flew the new path against every other object for twenty-four hours: it creates no new danger and makes no other pass worse. Here is which satellite moves, our best estimate of the risk, and the burn that puts the satellite back afterwards. The first picture is the gap between them, with and without the burn. The second shows every burn we tried: dark is safe, and the ring is the one we chose. The third is the risk at each run, and its ring is a small machine-learning model forecasting where the risk will end. These two links are the standard warning message that operators exchange, and a briefing."

### 7. A pass with no burn (4:05 to 4:25)

**Do:** click the **No safe burn** row. If the list has none today, skip this part.

> "Sometimes the right answer is no burn. These two meet on every orbit, so a burn that clears one meeting pushes the danger to the next. EDITH tried five burns, saw that, and says so."

### 8. Any satellite, and fleets (4:25 to 4:50)

**Do:** type `ISS` in the box and click the first result. When the list appears, click **Fleets**.

> "Any satellite can be checked by name. The Space Station: [four] passes within ten kilometres today, none to check, found in six seconds. And Fleets gives each operator one line: its passes to check and its burns."

### 9. Proof (4:50 to 5:35)

**Do:** click **Proof** under the Run button. Point at each of the four pictures in turn.

> "How do we know this is right? Four checks. One: we recomputed CelesTrak's two hundred closest passes from the same data. All two hundred matched, to thirty-five centimetres. Two: we compared our probability with twenty thousand real warnings from the European Space Agency. No offset. Three: since public data has no error bars, we measured them ourselves, from three hundred and twenty-five thousand pairs of orbit records. After one day, debris is off by about two hundred metres, and a Starlink by twelve kilometres. Four: the ranking holds when our assumptions change."

### 10. The 2009 collision (5:35 to 6:00)

**Do:** scroll up, click **2009 replay**, then click the first row.

> "And one real case. In 2009 Iridium 33 and Cosmos 2251 collided. We gave EDITH only the data that was public the day before. It found that pass, at the right second, as the most dangerous pass of Iridium 33. It rated it amber, not red, because public data predicted a miss of 584 metres. That is the honest answer, and it is why we rank by the worst case."

### 11. Which tool does what (6:00 to 6:50)

**Do:** click **Priority**, then click the first **Burn ready** row so its card is open, and scroll to the top of the dashboard. Point at each item as you name its tool, in this order: objects watched, close passes ahead, the Risk column, the burn card, the third picture, the "Last run" line.

> "Every item on this page comes from one tool. The orbits behind this number are downloaded from CelesTrak and Space-Track, and Pydantic checks each record. For the close passes, SGP4, a compiled C++ library, predicts every position; NumPy holds them as arrays; and SciPy's KD-tree finds the neighbours in forty milliseconds, where checking every pair takes sixty seconds. The risk is our own probability maths, on NumPy and SciPy. The burn search flies each candidate orbit with SciPy's integrator. This forecast ring is LightGBM, trained on the European Space Agency's real warnings. APScheduler starts a run every six hours, FastAPI serves the results, and this page is plain JavaScript. Python only gives the orders; the heavy maths is compiled C and C++, which is why the whole sky takes about seven minutes on a laptop."

### 12. Limits and close (6:50 to 7:10)

**Screen:** open https://edith-guhk.onrender.com in the last few seconds.

> "The limits: public data is rough, pieces smaller than ten centimetres are not tracked, and EDITH advises people; it does not fly satellites. Every change is checked by a hundred and twenty-three automatic tests. And it is live at this address. Thank you."

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

Part 11 names these while you point. This table is the full list, for your own understanding and for questions.

| Tool | What it does | Where it shows on the dashboard |
|---|---|---|
| Requests | Downloads the orbit data from CelesTrak and Space-Track | "Objects watched" |
| Pydantic | Checks every record and every result against one data model | Every number on the page |
| sgp4 (compiled C++) | Predicts where each object is, every 10 seconds for 24 hours | "Close passes ahead" |
| NumPy (compiled C) | Holds all the positions as arrays, so one instruction handles 30,000 objects | "Close passes ahead" |
| SciPy KD-tree | Finds the pairs that are near each other without comparing every pair | "Close passes ahead" |
| Python processes | Split the search across the laptop's cores | The run finishing in about 7 minutes |
| Our probability code, on NumPy and SciPy | Collision probability and its worst case | Level, Risk, "to check" |
| SciPy integrator | Flies each candidate burn under the Earth's real gravity | The burn card and "Every burn tried" |
| LightGBM | Forecasts where a pass's risk will end; trained on 162,634 warnings from the European Space Agency | The ring in "Risk, run by run" |
| Matplotlib | Draws the chart of our probability against the European Space Agency's | The second picture under Proof |
| APScheduler | Starts a run every six hours | "Last run ... Next ..." |
| FastAPI and Uvicorn | Serve the results to the page | The whole page |
| HTML, CSS and JavaScript, no framework | The dashboard and its pictures, drawn as SVG | The whole page |
| pytest and GitHub Actions | 123 tests on every change, on four versions of Python | Not on the dashboard; the badge on GitHub |
| Render | Hosts the public show-only site | The public link |

If a judge asks "why Python": Python only gives the orders. The heavy maths runs in compiled C and C++ inside sgp4, NumPy and SciPy, at 1.5 million positions a second.

Longer answers to judges' questions are in `PROJECT_EXPLAINED.md`, sections 8 and 9.
