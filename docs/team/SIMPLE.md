# EDITH in one page

If you are an AI assistant: explain this to me simply, then help me practise saying it to a judge in 3 minutes. Use only what is written here.

## The problem

About 30,000 tracked objects fly around the Earth below 2,000 km: satellites, dead satellites, rocket stages and debris. Each moves at 7.5 km every second. If two collide, both are destroyed and thousands of new pieces are made. The hackathon task: from public orbit data, predict close passes, rank them by collision probability, and recommend an avoidance move.

## What EDITH does

1. **Downloads** the orbit of every tracked object in low Earth orbit (about 29,700) from two public catalogues.
2. **Predicts** where each one will be for the next 1 to 3 days.
3. **Finds** every pair that will pass within 1 km. That is 440 million pairs, searched in about 3.5 minutes on a laptop.
4. **Ranks** each pass by collision probability and marks it red, amber or green.
5. **Recommends a burn** for the dangerous ones: which satellite moves, when, which way and how hard. It picks the smallest burn that makes the pass safe.
6. **Checks** that the burn does not create a new danger, and plans a second burn to put the satellite back.
7. **Reports** what changed since the last run and writes a one-page briefing for each dangerous pass.
8. **Repeats** every 6 hours by itself.

## Real results (9 October 2026)

- 1,756 close passes in the next 24 hours: 35 red, 183 amber, 1,538 green.
- 5 burns planned, all checked safe.
- Example: the satellite KUIPER-00053 and a dead rocket stage would pass 251 m apart. EDITH says: slow down by 43 mm/s, 10.5 hours early. The pass becomes 2.66 km. Risk falls from 1 in 900 to 1 in 500,000.

## How we know it is right

- **Against CelesTrak** (a public service that does the same calculation): our distances match theirs to 0.35 m on 200 passes.
- **Against the European Space Agency**: our probability matches theirs on 20,000 real warnings, with no offset.
- **We measured how wrong public data is**, from 325,558 pairs of orbit records. After one day: debris is off by about 0.22 km, a Starlink by about 12 km.
- **2009 replay**: given only the data public one day before the real Iridium and Cosmos collision, EDITH ranked that pass first, at the right time, and rated it amber.

## Smart choices

- It ranks by the **worst-case** probability, so a wrong guess about uncertainty cannot hide a danger.
- It plans burns first for a **satellite against something that cannot move** (debris, rocket stage).
- It does **not** plan burns between two satellites of the same fleet (for example Starlink and Starlink), because public data cannot predict them.

## Why these tools

Python only gives the orders. The heavy maths runs in compiled C and C++ libraries (sgp4, NumPy, SciPy). A smart search method (a KD-tree) finds nearby pairs in 40 ms; checking every pair takes 60 s. No AI model is used for the physics, because the formulas are exact. One optional model, trained on ESA's real warnings, predicts how a risk will change.

## Honest limits

- Public data is rough, and very rough for satellites that manoeuvre.
- Pieces smaller than about 10 cm are not tracked by anyone publicly.
- It advises people; it does not fly satellites.

## How to show it

- Start: `.venv\Scripts\python -m uvicorn fusion.api.main:app --port 8000`
- Console: http://localhost:8000 (press "Run now", click "passes with a burn plan", click a row)
- Story page: http://localhost:8000/landing

## What to say in 3 minutes

1. The problem: 30,000 objects, 440 million pairs, nobody can watch them all (20 s).
2. Press Run. While it runs, show the ranked list and the red count (40 s).
3. Click a burn plan: the pass, the burn, before and after, the safety check (60 s).
4. Show the 2009 replay and the validation line: 0.35 m against CelesTrak, no offset against ESA (40 s).
5. Say the limits yourself before they ask (20 s).
