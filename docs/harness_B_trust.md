# Teammate B: trust pack (measured uncertainty and independent validation)

**Your assistant:** Opus 5.5. **Time:** 7 hours. **Your folder:** `addons/b_trust/`.

## What you are doing and why

Our team is building a system that predicts close approaches between satellites, ranks them by collision probability, and recommends avoidance burns. Atharv is building the complete working system alone. You are building the add-on pack that answers the judges' hardest question: **"how do you know your numbers are right?"**

1. **A reference collision-probability calculator**, proven three ways, that Atharv's engine can be checked against.
2. **Measured uncertainty.** Public orbit data comes with no error bars. You measure the real error from history. Almost no other team will do this.
3. **Validation on real operational data** from the European Space Agency.
4. **Validation against CelesTrak's own conjunction service.**
5. **A robustness study** showing how much the ranking depends on our assumptions.

Your work is fully independent. You never need Atharv's code, and Atharv never waits for you. Everything you produce is a file or a function in your own folder.

## How to work

1. Create the folder and environment once:
   ```
   mkdir addons\b_trust
   cd addons\b_trust
   python -m venv .venv
   .venv\Scripts\activate
   pip install sgp4 numpy scipy requests pandas matplotlib pytest
   ```
2. Create a free account at `https://www.space-track.org` (needed from prompt 2). Put the login in a file called `.env` in your folder and never commit it.
3. Start the 221 MB download of `https://zenodo.org/records/4463683` now, into `addons/b_trust/esa/`, so it is ready for prompt 4.
4. Open a new session with your assistant in this folder. Paste **Prompt 0** first, every time you start a new session.
5. Paste the prompts in order, one at a time. After each one, run the **check**. If it fails, paste the error back. Move on only when the check passes.
6. If your assistant can run commands itself, let it. If it is chat-only, run what it gives you and paste back the output.
7. Commit after each prompt.
8. If a prompt is stuck for more than 20 minutes past its time box, write what happened in `README.md` and move on. Prompts 1, 3 and 5 matter most.

| Prompt | Topic | Time |
|---|---|---|
| 1 | Reference probability calculator | 1:15 |
| 2 | Orbit history sample | 0:45 |
| 3 | Measured TLE error | 1:30 |
| 4 | Check against ESA data | 1:15 |
| 5 | Validation against SOCRATES | 1:00 |
| 6 | Robustness study | 0:45 |
| 7 | Validation report, packaging | 0:30 |

## Prompt 0: context (paste at the start of every session)

```text
You are helping me build a validation pack for a satellite collision-avoidance project. Another person is building the main system; my work must be fully standalone and must not assume any of their code exists.

Rules for everything you write:
- Python 3.11, type hints, small functions, pytest tests for every module.
- All code lives in the current folder (addons/b_trust/). Outputs go in ./out/. Raw downloads are cached in ./cache/ and never downloaded twice.
- Orbit propagation uses the `sgp4` Python package only. Positions are in the TEME frame, in km and km/s. Times are UTC, ISO 8601 with a trailing Z in JSON.
- Objects are identified by NORAD catalogue number as an int.
- RTN frame: R = unit position vector, N = unit(r x v), T = N x R.
- Never invent data, column names, API parameters or results. If you are not sure how an API or file is structured, fetch or load it and print what is there before writing code against it.
- Never claim something works unless you ran it and showed me the output.
- When a comparison disagrees, report the disagreement. Never tune a parameter to make two numbers match.
- Be polite to data providers: cache every response, and never loop one web request per object.

A conjunction event is stored in this JSON shape:
{ "event_id": "43070-34427-20261011T0412", "primary_id": 43070, "secondary_id": 34427,
  "tca": "2026-10-11T04:12:37Z", "miss_distance_km": 0.412, "relative_speed_kms": 14.71,
  "r_primary_km": [x,y,z], "v_primary_kms": [x,y,z], "r_secondary_km": [x,y,z], "v_secondary_kms": [x,y,z],
  "miss_rtn_km": [r,t,n], "primary_tle_age_days": 0.6, "secondary_tle_age_days": 2.3,
  "pc": 3.1e-5, "pc_max": 4.4e-4, "sigma_rtn_primary_km": [r,t,n], "sigma_rtn_secondary_km": [r,t,n],
  "hbr_km": 0.01 }
State vectors are at the time of closest approach (TCA).

Confirm you understand and wait for my first task.
```

## Prompt 1: reference probability calculator

```text
Write pc_reference.py: a reference implementation of short-encounter collision probability.

Functions:
1. rtn_to_teme(r, v) -> 3x3 rotation matrix, and cov_rtn_to_teme(sigma_rtn, r, v) -> 3x3 covariance from three standard deviations in RTN (diagonal in RTN).
2. encounter_plane(r1, v1, r2, v2) -> (m, basis): two orthonormal vectors spanning the plane perpendicular to the relative velocity, and the 2-vector m of the relative position projected onto them.
3. project_cov(C_teme, basis) -> 2x2.
4. pc_integral(m, Cp, hbr_km) -> float: the integral of a 2D Gaussian with mean m and covariance Cp over a disc of radius hbr_km centred on the origin, by numerical integration (scipy). Must be accurate when the disc is thousands of times smaller than the sigmas.
5. pc_monte_carlo(m, Cp, hbr_km, n) -> (estimate, standard_error): sampling in chunks so n = 1e8 fits in memory.
6. pc_max(m, Cp, hbr_km) -> float: the largest probability obtainable by scaling Cp by any positive factor. Derive the small-disc closed form and show me the derivation; also implement a numerical version (scalar optimisation over the scale factor) and use it to verify the closed form.
7. pc_event(r1, v1, C1, r2, v2, C2, hbr_km) -> (pc, pc_max) combining the above with C = C1 + C2.

Tests (all must pass, show me the output):
- Zero miss, isotropic sigma s: Pc = 1 - exp(-hbr^2 / (2 s^2)).
- pc_integral agrees with pc_monte_carlo within 3 standard errors on at least eight cases with Pc between 1e-2 and 1e-5, including a 20:1 stretched ellipse with the miss along the long axis, the same along the short axis, and a rotated (correlated) ellipse.
- pc_max >= pc always; closed form agrees with the numerical maximum within 1% when hbr is much smaller than the sigmas.
- Rotating both objects' states and covariances by the same random rotation leaves Pc unchanged.
- Pc decreases as the miss distance increases with everything else fixed.

Then write make_pc_cases.py that saves ./out/pc_test_cases.json: 30 cases with full inputs (r1, v1, sigma_rtn_1, r2, v2, sigma_rtn_2, hbr_km) and the reference outputs (pc, pc_max), covering realistic low-Earth-orbit geometries: head-on, crossing at 90 degrees, and overtaking, with miss distances from 50 m to 5 km and along-track sigmas from 0.2 to 5 km. Someone else will run their own implementation against this file.
```

**Check:** `pytest` passes and `out/pc_test_cases.json` has 30 cases.
## Prompt 2: orbit history sample

```text
Write spacetrack.py: a small client for https://www.space-track.org.

First, read the Space-Track API documentation for how to log in and how to query the gp_history class, and tell me what you found before writing code. Do not guess the URL structure.

Requirements:
- Username and password from a .env file. Never print them.
- One logged-in session, reused.
- A hard rate limiter in code: at most 20 requests per minute and 200 per hour.
- Every response cached under ./cache/spacetrack/ keyed by the query, never requested twice.
- history(norad_ids, start, end) -> list of element sets, oldest first, many ids in ONE query (chunks of at most 50 ids).

Then:
1. Download the current element sets for these CelesTrak groups, once each, cached: iridium-NEXT, cosmos-2251-debris, iridium-33-debris, fengyun-1c-debris, from https://celestrak.org/NORAD/elements/gp.php?GROUP=<group>&FORMAT=json
2. Choose a sample: all Iridium NEXT satellites, 150 random debris objects across the three debris groups (fixed random seed), and 30 rocket bodies or dead payloads between 700 and 900 km from the CelesTrak "active" group's complement if you can identify them; if not, skip that part and tell me.
3. Fetch 45 days of history for the sample and save ./out/history_sample.json as {norad_id: [element sets oldest first]} with the object's name and type (PAYLOAD if Iridium NEXT, DEBRIS if the name contains "DEB", ROCKET_BODY if it contains "R/B").
Print the number of objects and the median number of element sets per object, per type.

Tests: rate limiter with a fake clock; cache hit avoids a request (mock the HTTP layer).
```

**Check:** `out/history_sample.json` exists, with a median of well over 10 element sets per object.

## Prompt 3: measured TLE error

```text
Public TLEs carry no uncertainty. We will measure it. Write tle_error.py.

Method:
For one object with element sets E1..En ordered by epoch, for every pair (Ei, Ej) with j > i and epoch gap up to 7 days:
- propagate Ei to the epoch of Ej with sgp4,
- take Ej evaluated at its own epoch as the reference position and velocity,
- express (position from Ei minus reference position) in the RTN frame of the reference,
- record one sample: age_days = epoch gap, and the R, T, N error in km.

Manoeuvre filter: active satellites manoeuvre, which would look like huge error. For each object, flag consecutive element sets where the semi-major axis changes by more than 5 times that object's median absolute change, and drop every pair that spans a flagged step. Report how many pairs were dropped per object type.

Statistics:
- Per object: bin samples by age (0-1, 1-2, ... 6-7 days). In each bin compute a robust standard deviation (1.4826 x median absolute deviation) per axis.
- Fit sigma(age) = sigma0 + rate * age per axis by least squares on the bin values.
- Per object type: the same, pooling all objects of the type.

Outputs:
- ./out/tle_error.json: { "by_object": {norad_id: {"n_samples":..., "sigma0_km":[r,t,n], "rate_km_per_day":[r,t,n]}}, "by_type": {"PAYLOAD":{...}, "DEBRIS":{...}, "ROCKET_BODY":{...}} }
- measured_sigma(norad_id: int, object_type: str, tle_age_days: float) -> numpy array [3] km or None: the object's own fit if it has at least 10 samples, else the type fit, else None. It loads ./out/tle_error.json once.
- ./out/tle_error_growth.png: along-track sigma against age for PAYLOAD and DEBRIS with the binned points and fitted lines; a second panel for radial and cross-track.
- ./out/tle_error_summary.md: a small table of sigma at age 0, 1, 3 days per type and axis, and three sentences on what it shows.

Tests: a synthetic history generated from ONE orbit sampled at several epochs gives errors near zero; a synthetic history with a known injected along-track drift recovers the rate within 20%; the manoeuvre filter removes a pair spanning an injected semi-major-axis jump.

Be honest in the summary: the newer TLE is not ground truth, so this measures TLE-to-TLE consistency and understates the true error somewhat.
```

**Check:** the chart shows along-track error growing with age and much larger than radial and cross-track. If along-track is not the largest, something is wrong with the RTN frame; ask the assistant to recheck it.
## Prompt 4: check the reference calculator against ESA data

```text
The folder ./esa/ contains the ESA Collision Avoidance Challenge dataset (Zenodo record 4463683): real conjunction warnings from 2015-2019. Each row is one warning. Unzip it if needed and list the files.

Step 1: load the training CSV with pandas, print every column name, the dtypes, and three sample rows. Read the dataset description on the Zenodo page and the original challenge page for the meaning and units of the columns. Tell me which columns give: relative position components, relative velocity components, the position standard deviations of both objects, the position correlation terms of both objects, the sizes of both objects, the miss distance, the time to TCA, and the risk. Tell me the units you found and where you found them. If something needed is not in the file, say so; do not substitute a guess.

Step 2: write esa_check.py. For each row that has the needed columns:
- build each object's 3x3 position covariance in RTN from the sigmas and correlations,
- the dataset gives relative position and velocity in an RTN frame, so compute the encounter plane directly in that frame (no rotation to TEME needed) and state this assumption,
- combined hard-body radius from the object size columns (explain your choice; if sizes are missing use the row's stated value or skip),
- compute our Pc with pc_reference and compare log10(Pc) with the dataset's risk column (which is log10 of probability, with a floor value for negligible risk; find the floor and exclude those rows from the comparison).

Use up to 20,000 rows chosen with a fixed seed.

Outputs:
- ./out/esa_pc_check.png: scatter of our log10 Pc against ESA's risk with the 1:1 line.
- ./out/esa_pc_check.json: number of rows compared, median and 90th-percentile absolute difference in log10 units, the mean signed offset, and the correlation.
- Three sentences interpreting the result. A constant offset usually means a different object-size assumption; describe it, do not tune it away.

Step 3: also save ./out/esa_sigma_stats.json: median R, T, N position sigma of the chaser object grouped by its object type and by whole days to TCA. This is operator-grade tracking uncertainty, for comparison with our measured TLE error.
```

**Check:** the scatter plot follows the 1:1 line (possibly with an offset), and the JSON reports the differences. If the assistant says a needed column is missing, accept that and note it in the README.

## Prompt 5: validation against SOCRATES

```text
CelesTrak runs a service called SOCRATES that publishes predicted conjunctions computed from public orbit data: https://celestrak.org/SOCRATES/ . Its output format is documented at https://celestrak.org/SOCRATES/socrates-format.php .

Step 1: read both pages and tell me how to download the full current results as CSV and what each column means. Download once into ./cache/ and print the columns and five rows.

Step 2: write socrates.py with load_socrates() -> list of dicts: the two NORAD ids, names, TCA (UTC), minimum range in km, relative speed in km/s, maximum probability, and any other fields present.

Step 3: independent recomputation. For the 200 SOCRATES conjunctions with the smallest minimum range that involve at least one object from CelesTrak's iridium-NEXT, cosmos-2251-debris, iridium-33-debris or fengyun-1c-debris groups (if fewer than 200, take the top 200 overall):
- fetch the current element sets for the objects involved (by group download, cached; do not make one request per object unless under 50 objects remain),
- compute the closest approach with sgp4: sample every 5 s within +-10 minutes of SOCRATES' TCA and refine with scipy.optimize.minimize_scalar,
- record our TCA, miss distance and relative speed next to SOCRATES' values, plus the epoch of the element sets we used.

Step 4: write validate.py with compare(events: list[dict], socrates: list[dict]) -> dict that matches by the pair of ids (in either order) and TCA within 60 s, and returns matched count and the distribution of differences. `events` uses the event JSON shape from the context, so the same function will later be run on the main system's output.

Outputs:
- ./out/socrates_validation.json: per pair, both sets of values and the differences; plus summary: n matched, median and 90th-percentile TCA difference in seconds, miss-distance difference in metres, relative-speed difference in m/s.
- ./out/socrates_validation.png: our miss distance against SOCRATES' on log axes with the 1:1 line.
- Three sentences interpreting it. Differences are expected because the element sets may have been updated since SOCRATES ran; report how the difference depends on that.

Also compare maximum probability: compute pc_max with pc_reference using a combined hard-body radius of 10 m and the type-level measured sigmas from ./out/tle_error.json, and report how our pc_max ranks the pairs compared with SOCRATES' maximum probability (Spearman rank correlation). Explain any assumption SOCRATES documents that we could not replicate.

Tests: compare() on a small hand-made list, including a reversed pair of ids and a TCA just outside the 60 s tolerance.
```

**Check:** the plot hugs the 1:1 line for most points, and the summary gives the median differences. This is the headline number for the pitch.

## Prompt 6: robustness study

```text
Write robustness.py. Use the 200 pairs from the SOCRATES step with our own computed geometry.

Question: how much does our ranking depend on the assumptions we had to make?

1. Baseline: sigmas from measured type-level fits at each object's element-set age, hard-body radius 10 m. Rank by pc_max.
2. Vary one assumption at a time: sigma scaled by 0.5 and by 2; hard-body radius 5 m and 20 m; a simple guessed sigma table instead of measured values (radial 0.1 km + 0.05 km/day, along-track 0.5 km + 1.0 km/day for payloads and 2.0 km/day otherwise, cross-track 0.1 km + 0.05 km/day).
3. For each variation report: Spearman rank correlation with the baseline for pc and for pc_max, how many of the baseline top 10 remain in the top 10, and how many events change risk level (RED if pc_max >= 1e-4, AMBER if >= 1e-5, else GREEN).
4. Also show why ranking by miss distance alone is not enough: Spearman correlation between miss-distance rank and pc_max rank, and the three clearest examples where a larger miss has a higher probability, with the reason (older data, worse geometry).

Outputs: ./out/robustness.json, ./out/robustness.png (bar chart of top-10 overlap per variation), and ./out/robustness_notes.md of about 120 words in plain language with the numbers.
```

**Check:** the notes quote numbers that appear in the JSON. The examples in point 4 are a strong pitch slide.

## Prompt 7: validation report and packaging

```text
Part 1: write ./out/VALIDATION_REPORT.md, one page, for hackathon judges who are engineers but not orbital specialists. Sections:
- What we checked and why (three sentences).
- Collision probability: checked against Monte Carlo (numbers), against ESA operational data (numbers, chart reference).
- Close-approach geometry: checked against CelesTrak SOCRATES (numbers, chart reference).
- Uncertainty: measured from N element-set pairs across M objects (numbers, chart reference).
- Robustness (two sentences with numbers).
- Limits: what these checks do not prove.
Use only numbers from the JSON files in ./out/. If a check was skipped or failed, say so plainly.

Part 2: write README.md for this folder: what the pack contains, a table of every file in ./out/ with one line on what it is and how the main system uses it, a five-line usage example for each of pc_event, measured_sigma, compare, and a "known gaps" section.

Part 3: run the whole test suite and show me the output. Fix failures.
```

**Check:** `pytest` passes, and every number in the report can be found in a JSON file.

## When you finish

You never need anything from Atharv, and you do not need to send, explain or hand over anything to Atharv. Put the finished `addons/b_trust/` folder (without `.env`, `.venv` and the raw ESA data) in the team's shared project. Your `README.md` must explain everything by itself. The pieces that plug into the main system:

| File | Use |
|---|---|
| `out/pc_test_cases.json`, `pc_reference.py` | Check of Atharv's probability function |
| `out/tle_error.json`, `tle_error.py` (`measured_sigma`) | Replaces guessed uncertainty with measured values |
| `out/socrates_validation.*`, `validate.py` | Headline validation, and the tool to re-run on Atharv's events |
| `out/esa_pc_check.*`, `esa_sigma_stats.json` | Second validation |
| `out/robustness.*`, `tle_error_growth.png` | Pitch slides |
| `out/VALIDATION_REPORT.md` | Shown in the dashboard's validation tab and handed to judges |