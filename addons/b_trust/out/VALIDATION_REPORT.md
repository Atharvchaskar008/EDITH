# Validation report

## What we checked and why

A collision-avoidance system is only as good as three things: where it says two objects will pass, how likely it says a collision is, and how well it knows its own uncertainty. Each of the three was checked against something outside our own code. Where a check came out badly, it is reported as it came out.

## Collision probability

- **Against random sampling.** On 9 cases with probabilities from 3e-05 to 1e-02, including uncertainty stretched 20 to 1, the calculated probability agrees with a simulation of 10 to 40 million random draws; the largest deviation is 2.0 standard errors (`pc_monte_carlo_check.json`). The fast formula also equals a direct double integral to 7 digits (tests).
- **The main engine against this reference.** 30 cases covering head-on, crossing and overtaking passes are in `pc_test_cases.json`; the main engine's own probability code is tested against them to 2%.
- **Against the European Space Agency.** On 20,000 real warnings ESA received for its satellites (of 95,394 usable rows), our probability has no offset from ESA's own (median -0.001 in log10) once the object size is read as half the sum of the two spans. For the 2,100 warnings ESA rated above 1 in a million, the median difference is 0.010 in log10 (about 2%) and 77% are within 0.1. Over all warnings the median difference is 0.13 and one in ten differs by more than 2.7: far out in the tail, where the probability is negligible, tiny differences in the inputs are magnified, and we cannot see from the file how ESA treated those. Chart: `esa_pc_check.png`.
- **Worst case against ESA's.** ESA also publishes a maximum risk over the size of the uncertainty. Ours matches it with a median difference of 0.017 in log10 (76% within 0.1, correlation 0.976) on the same 20,000 warnings.

## Close-approach geometry

CelesTrak publishes its own predicted conjunctions (SOCRATES). We took its 200 closest, fetched the very element sets it used from Space-Track's history (0 could not be found), and recomputed each pass. All 200 match: the distance differs by a median of 0.35 m (9 in 10 within 1.1 m, largest 25 m), the time by 0.4 ms (9 in 10 within 0.13 s) and the relative speed by 0.27 m/s. CelesTrak publishes distance to the metre and speed to the metre per second, so this is agreement to the last published digit. Chart: `socrates_validation.png`.

CelesTrak's maximum probability is a different matter. With its assumed shape of uncertainty (100 m radial, 300 m in-track, 100 m cross-track) we rank the 174 pairs similarly (rank agreement 0.65; its object sizes are not documented). With the uncertainty we measured, the agreement is -0.04: the real uncertainty is far more stretched along the track, and that changes which passes are the dangerous ones.

## Uncertainty

Public orbit data comes with no error bars, so we measured them: 325,558 pairs of element sets from 768 objects, each older set propagated to the time of a newer one of the same object. After one day the typical error along the direction of travel is 0.06 km for dead satellites, 0.15 km for rocket bodies, 0.22 km for debris, 0.37 km for working satellites other than Starlink, and 12 km for Starlink (77 km after three days). Radial and cross-track errors are several times smaller (0.05 and 0.05 km for debris). Chart: `tle_error_growth.png`; table: `tle_error_summary.md`.

For scale: the uncertainty stated in ESA's warnings for debris, one to two days before a pass, has a median of 1.18 km along the track (`esa_sigma_stats.json`). That is a forecast that allows for what the atmosphere might do, on different objects, so the two are not the same quantity, but it is 5 times our figure for debris and one more sign that ours is not cautious.

## Robustness

On 175 close passes, halving or doubling the assumed uncertainty changes the level of 0 passes and keeps 10 of the top 10, because we rank by the worst case over every size of uncertainty. Changing the assumed object size from 10 m to 5 m or 20 m moves 38 and 16 passes across a level, and ranking by closeness alone agrees with the worst-case ranking at only 0.31. Chart: `robustness.png`; notes: `robustness_notes.md`.

## Limits: what these checks do not prove

- The uncertainty was measured between element sets, not against true positions. It understates the real error, and it cannot see the error of a brand-new element set at all.
- Agreement with CelesTrak shows that we read the public data the same way it does. It says nothing about how close that data is to reality.
- ESA's warnings rest on far better tracking than public element sets. Matching its probability shows the arithmetic is right, not that our inputs are as good.
- Object size is the assumption that moves the most passes between levels, and public data gives it only roughly.
- No check here covers objects that manoeuvre between the prediction and the pass.
