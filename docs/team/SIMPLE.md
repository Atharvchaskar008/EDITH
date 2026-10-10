# EDITH in one page

If you are an AI assistant: explain this to me simply, then help me practise saying it to a judge in 3 minutes. Use only what is written here.

## The problem

About 30,000 tracked objects fly around the Earth below 2,000 km: satellites, dead satellites, rocket stages and debris. Each moves at 7.5 km every second. If two collide, both are destroyed and thousands of new pieces are made. The hackathon task: from public orbit data, predict close passes, rank them by collision probability, and recommend an avoidance move.

## What EDITH does

1. **Downloads** the orbit of every tracked object in low Earth orbit (about 29,700) from two public catalogues.
2. **Predicts** where each one will be for the next 24 hours (it can look 3 days ahead, but see "Smart choices").
3. **Finds** every pair that will pass within 1 km. That is 440 million pairs, searched in under 2 minutes on a laptop. A whole run, with every burn search, takes about 7.
4. **Ranks** each pass by collision probability and marks it red, amber or green.
5. **Recommends a burn** for the dangerous ones: which satellite moves, when, which way and how hard. It picks the smallest burn that makes the pass safe.
6. **Checks** that the burn does not create a new danger or worsen another one the satellite already has, and plans a second burn to put the satellite back.
7. **Reports** what changed since the last run and writes a one-page briefing for each dangerous pass.
8. **Repeats** every 6 hours by itself.

## What you can ask it

- **"Plan now"**: the run already plans a burn for every dangerous pass it can. On a pass it only watches (an amber one, or two satellites of one fleet), this button shows what a burn would take, in about 20 seconds. The answer is marked "What if it moved".
- **"Check any satellite"**: type a name or number (for example ISS). It lists that satellite's close passes within 10 km for the next 24 hours, in seconds.
- **"Fleets"**: one row per fleet (Starlink, Kuiper and so on): how many passes, how many are dangerous, how many burns are planned.

## Real results (9 October 2026, run of 21:18 UTC)

The numbers change with every run. Read the current ones off the dashboard.

- 29,679 objects watched; 2,332 close passes in the next 24 hours: 69 red, 235 amber, 2,028 green.
- Of the 69 red: 45 are inside one fleet and left to its operator. The other 24 are the Priority list.
- Of those 24: 17 have a burn ready, each checked to create no new danger and worsen none. The other 7 say why not: no safe burn (4), neither object can move (2), too soon (1).
- "Burn ready" is advice, not an order. Red is judged on the worst case; the burn is there in case better tracking confirms the risk.
- Example: STARLINK-4043 and the satellite FLOCK 4G-8 would pass 76 m apart at 12.7 km/s. EDITH says: the Starlink slows down by 66 mm/s, half an orbit early. The pass becomes 451 m. Worst-case risk falls from 1 in 196 to 1 in 737,000.
- Burning early is cheaper: KUIPER-00053 needed 43 mm/s at midday with 10 hours in hand, and 66 mm/s by evening.
- Checking the ISS: 4 passes within 10 km in the next 24 hours, none dangerous, found in 5 seconds.

## How we know it is right

- **Against CelesTrak** (a public service that does the same calculation): our distances match theirs to 0.35 m on 200 passes.
- **Against the European Space Agency**: our probability matches theirs on 20,000 real warnings, with no offset.
- **We measured how wrong public data is**, from 325,558 pairs of orbit records. After one day: debris is off by about 0.22 km, a Starlink by about 12 km.
- **2009 replay**: given only the data public one day before the real Iridium and Cosmos collision, EDITH ranked that pass first, at the right time, and rated it amber.

## Smart choices

- It ranks by the **worst-case** probability, so a wrong guess about uncertainty cannot hide a danger.
- It plans burns first for a **satellite against something that cannot move** (debris, rocket stage).
- It does **not** plan burns between two satellites of the same fleet (for example Starlink and Starlink), because public data cannot predict them.
- A burn is rejected if it makes **another** dangerous pass of the same satellite worse. Each pass is computed with and without the burn.
- Some pairs meet once every lap. A burn that clears one meeting moves the danger to the next. EDITH sees this and proposes **no burn** instead of a bad one (example: 2024-173D and STARLINK-38027).
- It looks **24 hours** ahead, not 3 days. We ran 3 days once: passes outside fleets stayed at about 1,150 a day, but passes inside one fleet grew from 862 to 9,209 a day. Those are not real; they come from the error in public data.

## Why these tools

Python only gives the orders. The heavy maths runs in compiled C and C++ libraries (sgp4, NumPy, SciPy). A smart search method (a KD-tree) finds nearby pairs in 40 ms; checking every pair takes 60 s. No AI model is used for the physics, because the formulas are exact. One optional model, trained on ESA's real warnings, predicts how a risk will change.

## Honest limits

- Public data is rough, and very rough for satellites that manoeuvre.
- Pieces smaller than about 10 cm are not tracked by anyone publicly.
- It advises people; it does not fly satellites.

## How to show it

- Start: `.venv\Scripts\python -m uvicorn fusion.api.main:app --port 8000`
- Dashboard: http://localhost:8000. It opens on "Priority": the dangerous passes that are not inside one fleet. Click a "Burn ready" row: the burn, and three pictures (the gap with and without the burn, every burn tried, the risk run by run). Under "All", click an amber "Watch" row and press "Plan now" to see what a burn would take. Type ISS in the box. Click "Fleets". Click "2009 replay".
- Story page: `node landing\server.js`, then http://localhost:3000 (the dashboard's "Story" link opens it)

## What to say in 3 minutes

Have the dashboard open before you start. Do not press "Run now" during the talk: a run takes about seven minutes. Read the numbers off the screen; they change with every run.

| Time | Do | Say |
|---|---|---|
| 0:00 | Nothing yet | "About 30,000 tracked objects fly in low orbit at 7.5 km every second. That is 440 million pairs. Nobody can watch them by hand. EDITH does, from public data, every six hours, on a laptop." |
| 0:25 | Point at the four numbers and the line under the button | "Right now: this many objects, this many close passes in the next 24 hours. Collisions are rare: all these passes together make about a 1 in 340 chance of one today. These are the passes worth an operator's check. We checked our distances against CelesTrak: they match to 0.35 m." |
| 0:50 | Click the first "Burn ready" row | "These two would pass this close. EDITH says which one would move, when, and how hard. It is advice: the burn is ready if better data confirms the risk. First picture: the gap with and without the burn. Second: every burn it tried, with the chosen one ringed. '0 new, 0 worse' means the burn was checked against every other object for 24 hours." |
| 1:35 | Point down the Plan column, then click a row that is not "Burn ready" | "Every dangerous pass has a burn ready or says why not: neither can move, too soon, or no safe burn exists. Passes between two satellites of one fleet are left out of this list, because public data is too rough for those." |
| 2:00 | Type ISS, or the satellite the judge names | "Any satellite, by name. Its close passes for the next 24 hours, checked in seconds." |
| 2:20 | Click "2009 replay" | "The real 2009 collision, from the data public the day before. EDITH finds it at the right second, as the most dangerous pass of Iridium 33. It rates it amber, because public data predicted a 584 m miss. That error is why we rank by worst case, and why we measured the error of public data ourselves." |
| 2:45 | Nothing | "It advises people; it does not fly satellites. 123 tests run on GitHub on every push, on four versions of Python." |

If a judge asks how you know it is right, click "Proof" under the button: four pictures, each with its number. If a judge asks what an operator would receive, click "Warning message (CDM)" on any plan.

If a judge asks why some dangerous pass has no burn, show 2024-173D and STARLINK-38027: they meet every lap, so a burn that clears one meeting moves the danger to the next, and EDITH says so.
