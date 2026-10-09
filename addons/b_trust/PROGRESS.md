# Progress

Built on 9 October 2026, on `main`, by the project lead's assistant (the teammate's branch never arrived). All eight tasks are done; none is blocked.

## Task 1: reference probability calculator
- Status: DONE
- Files: `pc_reference.py`, `test_pc_reference.py`, `make_pc_cases.py`, `out/pc_test_cases.json`
- Derivation of the worst case (in the module docstring): with the covariance scaled by k and a small disc, Pc(k) = hbr² exp(−d²/2k) / (2k √det Cp); setting the derivative to zero gives k = d²/2 and Pc_max = hbr² / (e d² √det Cp).
- Numbers: 33 tests pass. On 9 cases (Pc from 3e-5 to 1e-2, including uncertainty stretched 20 to 1 both ways and a rotated ellipse) the integral is within 2.0 standard errors of 10 to 40 million random draws. The fast one-dimensional form equals the direct double integral to 7 digits. 30 reference cases written.
- Note: the direct double integral took 5 ms to several seconds per call, too slow for the bulk studies, so `pc_integral` is the exact one-dimensional form (0.1 ms) and the double integral is kept as `pc_integral_2d` to check it.
- Result for the main engine: `tests/test_pc.py` now runs against the 30 cases and passes (both numbers within 2%).

## Task 2: orbit history sample
- Status: DONE
- What the Space-Track documentation says: log in with a POST to `/ajaxauth/login` (`identity`, `password`); history is the class `gp_history`, queried as `/basicspacedata/query/class/gp_history/NORAD_CAT_ID/<comma list>/EPOCH/<start>--<end>/orderby/EPOCH asc/format/json`; limits are 30 requests a minute and 300 an hour.
- Files: `spacetrack.py`, `test_spacetrack.py`, `make_history.py`, `out/history_sample.json`
- Numbers: 779 objects, 30,687 element sets. Median element sets per object: Iridium NEXT 87, Starlink 31, other working satellites 41, dead satellites 43, rocket bodies 41, debris 24. 280 objects were taken from teammate A's 30-day history file instead of being downloaded again; the other 499 needed 10 Space-Track requests.
- Differences from the brief: the sample covers six kinds of object across all of low Earth orbit (the project now covers all of it, not one constellation); 16 days of history, not 45, to keep the download to about 10 MB on a slow connection.

## Task 3: measured element-set error
- Status: DONE
- Files: `tle_error.py`, `test_tle_error.py`, `out/tle_error.json`, `out/tle_error_growth.png`, `out/tle_error_summary.md`
- Numbers: 325,558 pairs from 768 objects; 711 objects have their own measurement. Along-track error after 1 / 3 / 7 days: Starlink 12.3 / 76.8 / 423 km; other working satellites 0.37 / 1.44 / 5.95; Iridium NEXT 0.12 / 0.43 / 1.63; dead satellites 0.06 / 0.17 / 0.48; rocket bodies 0.15 / 0.47 / 1.63; debris 0.22 / 0.75 / 2.98. Radial and cross-track for debris after one day: 0.05 and 0.05 km. Pairs dropped as manoeuvres: Starlink 27%, Iridium NEXT 44%, the others 4 to 6%.
- The chart shows along-track error growing with age and well above radial and cross-track for every kind of object.
- Differences from the brief, each for a stated reason: error size is taken about zero (the median of |error|), because for Starlink the older set is consistently about 10 km ahead after a day and a spread about the median would hide it; `measured_sigma` reads the binned values because the error grows faster than a straight line; `measured_sigma` takes the object's name and operational flag as optional extra arguments so it can tell a Starlink from a dead satellite.
- Tests: one orbit re-issued at 20 epochs shows under 50 m of error; a random 1 km/day drift is recovered within 20%; pairs across an injected 1 km orbit raise are flagged and the rest stay clean.

## Task 4: check against ESA data
- Status: DONE
- Files: `esa_check.py`, `out/esa_pc_check.json`, `out/esa_pc_check.png`, `out/esa_sigma_stats.json`
- Columns, printed from `train_data.csv` (103 columns, 162,634 rows): `relative_position_r/t/n` and `miss_distance` in metres, `relative_velocity_r/t/n` in m/s, `t_sigma_r/t/n` and `c_sigma_r/t/n` in metres, correlations `t_ct_r`, `t_cn_r`, `t_cn_t` and the same for the chaser (all within −1 to 1), sizes `t_span` and `c_span` in metres, `time_to_tca` in days, `risk` and `max_risk_estimate` as log10. The floor of `risk` is −30.
- Numbers (20,000 of 95,394 usable rows, fixed seed): with the hard-body radius read as half the sum of the two spans, the median offset from ESA's risk is −0.001 in log10; with the full sum it is +0.606 (a factor of 4), so half the sum is the reading ESA used. Median absolute difference 0.125; for the 2,100 warnings above 1e-6 it is 0.010 with 77% within 0.1; one in ten of all rows differs by more than 2.7. ESA's maximum risk is matched with a median difference of 0.017 (76% within 0.1, correlation 0.976).
- Assumption stated in the module: the chaser's covariance is rotated from its own RTN frame into the target's, rebuilt from the relative velocity and the target's circular speed.
- ESA's stated uncertainty for debris one to two days before a pass: median 1.18 km along-track, 0.04 km radial, 0.03 km cross-track.

## Task 5: validation against SOCRATES
- Status: DONE
- What the documentation says: columns `NORAD_CAT_ID_1`, `OBJECT_NAME_1`, `DSE_1`, `NORAD_CAT_ID_2`, `OBJECT_NAME_2`, `DSE_2`, `TCA`, `TCA_RANGE` (km), `TCA_RELATIVE_SPEED` (km/s), `MAX_PROB`, `DILUTION` (km); the full results are at `https://celestrak.org/SOCRATES/sort-minRange.csv` (21.6 MB; also sorted by probability and by time).
- Files: `socrates.py`, `validate.py`, `test_validate.py`, `make_socrates_validation.py`, `out/socrates_validation.json`, `out/socrates_validation.png`
- Numbers: the first 6 MB (53,018 rows, ranges up to 2.7 km, 8,515 under 1 km over 7 days) were downloaded. For the 200 closest, the very element sets SOCRATES used were found for all 200 in Space-Track's history (6 requests). Recomputed: 200 of 200 matched; distance differs by a median of 0.35 m (90% within 1.1 m, largest 25 m), time by 0.4 ms (90% within 0.13 s), relative speed by 0.27 m/s.
- Maximum probability: rank agreement with SOCRATES is 0.65 when we use its shape of uncertainty and −0.04 with our measured uncertainty (174 pairs).
- Difference from the brief: the brief said to use current element sets and report how the difference depends on updates. Using the element sets SOCRATES itself used separates method from data completely; the effect of newer data is measured by the main system's own comparison (`python -m fusion.validation`).

## Task 6: robustness study
- Status: DONE
- Files: `robustness.py`, `test_robustness.py`, `out/robustness.json`, `out/robustness.png`, `out/robustness_notes.md`
- Numbers (175 passes): uncertainty halved or doubled: 10 of the top 10 stay, 0 passes change level. Object size 5 m or 20 m: 7 and 7 of the top 10 stay, 38 and 16 passes change level. Guessed uncertainty table: 7 of the top 10 stay, rank agreement 0.67 (worst case) and 0.46 (plain probability). Closeness alone agrees with the worst-case ranking at 0.31.

## Task 7: validation report and packaging
- Status: DONE
- Files: `make_report.py`, `out/VALIDATION_REPORT.md`, `out/pc_monte_carlo_check.json`, `README.md`, `charts.py`
- The report is generated from the JSON files, so every number in it is in one of them.
- Tests: 54 passed.

## Task 8: final report
- Status: DONE
- Files: `REPORT.md`
- Git: committed on `main` by the project lead.
