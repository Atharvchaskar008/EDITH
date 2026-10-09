# Progress Tracking - Teammate C (c_ops)

## Setup
- Status: DONE
- Virtual environment created (.venv, Python 3.12).
- Installed packages: pydantic, pandas, numpy, scikit-learn, lightgbm, matplotlib, requests, watchdog, pytest.

## Task 1: Data models and sample runs
- Status: DONE
- Files produced:
  - `models.py`: ConjunctionEvent, ManeuverPlan, Alert models with `extra='allow'`, load_run, save_events, save_plans, save_alerts.
  - `make_samples.py`: Creates 3 sequential sample runs in `sample_runs/` (20261009T0600Z, 20261009T1200Z, 20261009T1800Z).
  - `test_models.py`: 4 pytest unit tests covering extra fields, full load, validation errors, and alerts.
- Key numbers: 3 sample run folders created, 8 events per run, 4 pytest tests passed.

## Task 2: Alert engine
- Status: DONE
- Files produced:
  - `compare.py`: `compare_runs()` engine with 10-minute TCA shift tolerance, swapped object ids tolerance, history appending, alert generation (NEW, ESCALATED, DOWNGRADED, CLEARED, PLAN_READY), plain-language messaging, and CLI interface.
  - `test_compare.py`: 9 pytest unit tests covering all alert types, TCA shifts (9 min vs 11 min), swapped IDs, and sample runs 1->2 and 2->3.
- Key numbers:
  - Run 1 -> Run 2 produced: 1 ESCALATED (CRITICAL), 1 NEW (WARNING), 1 PLAN_READY (CRITICAL), and 0 CLEARED (vanished GREEN event correctly ignored).
  - Run 2 -> Run 3 produced: 1 DOWNGRADED (INFO).
  - 13 total pytest unit tests passing.

## Task 3: Alert feed, run summary and run watcher
- Status: DONE
- Files produced:
  - `notify.py`: `write_feed` (appends to `./out/alert_feed.json`, newest first, max 200), `print_console` (ANSI-colored severity table), `write_summary` (operator shift JSON with counts, changes, alerts by kind, top 5 events, recommended burns with units).
  - `watch.py`: Watches run folder, handles complete runs (events.json + DONE or 10s quiet), state persistence, skip corrupt runs, `--once` mode, `--replay` demo mode.
  - `test_watch.py`: 4 pytest unit tests verifying folder pattern, watcher once execution, count verification, corrupt file skipping, idempotency, and network prohibition.
- Key numbers:
  - Sample Run 2 counts verified: RED: 1 (+1), AMBER: 2 (+0), GREEN: 5 (-1).
  - 17 total pytest unit tests passing.

## Task 4: ESA dataset and statistics
- Status: DONE
- Files produced:
  - `esa_data.py`: `load_cdms()` returning training DataFrame, dataset facts extraction, overview JSON generator, and risk evolution plotting.
  - `out/esa_overview.json`: Complete overview dataset metrics.
  - `out/esa_risk_evolution.png`: Risk evolution trajectory visualization (30 high final risk vs 30 low final risk events over time to TCA).
  - `test_esa_data.py`: 3 unit tests verifying load, columns, overview JSON, and image generation.
- Exact Column Names, Scales, Units, and Sources (read from `raw_data_2015-2019.txt` in dataset):
  - Event identifier: `event_id` (unit: integer ID, source: line 37)
  - Time to closest approach: `time_to_tca` (unit: days [days], source: line 38)
  - Risk value and scale: `risk` (scale: base-10 logarithm [log10 Pc], unit: dimensionless log-probability, floor: -30.0, source: line 36)
  - Miss distance: `miss_distance` (unit: meters [m], source: line 42)
  - Relative speed: `relative_speed` (unit: meters per second [m/s], source: line 43)
  - Position standard deviations of target: `t_sigma_r`, `t_sigma_t`, `t_sigma_n` (unit: meters [m], source: lines 70, 72, 61)
  - Position standard deviations of chaser: `c_sigma_r`, `c_sigma_t`, `c_sigma_n` (unit: meters [m], source: lines 70, 72, 61)
  - Object type of second object: `c_object_type` (type: categorical string, e.g. DEBRIS, PAYLOAD, source: line 50)
- Key Numbers:
  - Total warnings (CDMs): 162,634
  - Total unique events: 13,154
  - Warnings per event: median = 13.0, max = 23, min = 1
  - Final risk distribution:
    - Above -6: 365 (2.8%)
    - Between -6 and -10: 2,023 (15.4%)
    - Below -10: 10,766 (81.8%)
    - At floor value (-30.0): 8,349 (63.5%)
  - Risk shift across threshold -6 (first warning vs final warning): 1,188 events (9.03%) flip across the critical threshold.
- 20 total pytest unit tests passing.

## Task 5: Risk-trend model
- Status: DONE
- Files produced:
  - `train.py`: Data filtering (8,293 events with >= 2 days available and last warning within 1 day), strict feature cut-off at >= 2 days before TCA, 80/20 train/test split by event, Baseline vs Full LightGBM vs Operational LightGBM training, threshold optimization on train set, report generation and plotting.
  - `predict.py`: Operational prediction function `predict_final_risk()` with documented unit conversions, input validation, and missing value handling.
  - `out/risk_model_report.json`: Detailed side-by-side performance metrics and feature importances.
  - `out/risk_model.png`: Test set predicted vs actual final risk scatter plot with MAE comparison.
  - `out/risk_model_operational.joblib`: Serialized operational model bundle.
  - `out/risk_model_full.joblib`: Serialized full model bundle.
  - `test_model.py`: 4 unit tests verifying zero event leakage between train and test, strict >= 2 days feature isolation, prediction float output, and missing field handling.
- Key numbers (Test Set):
  - Baseline MAE: 5.0795 | Operational Model MAE: 2.6712 (Winner: Model, error reduced by 47.4%)
  - Baseline RMSE: 9.5268 | Operational Model RMSE: 5.0426 (Winner: Model, error reduced by 47.1%)
  - Baseline Precision: 0.1077 | Operational Model Precision: 0.1333 (Winner: Model)
  - Baseline Recall: 0.7778 | Operational Model Recall: 0.2222 (Winner: Baseline)
  - Baseline F2 Score: 0.3465 | Operational Model F2 Score: 0.1961 (Winner: Baseline)
- Honest pitch statement:
  "The gradient boosting model strongly outperforms the baseline on continuous risk prediction (MAE 2.67 vs 5.08, cutting error by 47%), but early warnings remain noisy: binary threshold triage reaches F2=0.20 compared to baseline F2=0.35."
- 24 total pytest unit tests passing.

## Task 6: Operator data
- Status: DONE
- Files produced:
  - `cdm_export.py`: Standard CCSDS 508.0-B-1 KVN export with non-certified / TEME header comments, mandatory keyword verification, correct unit conversions (km->m, km/s->m/s, variances to m^2).
  - `briefing.py`: Generates operator briefing JSON for RED and AMBER events (headline, formatted facts with units, risk history, burn details with direction and size in mm/s, return burn, alerts, footer). Contains no HTML tags.
  - `test_operator_data.py`: 6 unit tests covering syntax compliance, unit conversions, missing data resiliency, briefing structure with/without plan, zero HTML tags, and sample run outputs.
- Key numbers:
  - Verified CDM outputs in `sample_runs/*/cdm/` for all RED/AMBER events.
  - Verified Briefing JSON outputs in `sample_runs/*/briefings/` for all RED/AMBER events.
- 30 total pytest unit tests passing.

## Task 7: Pitch pack and packaging
- Status: DONE
- Files produced:
  - `out/pitch/slides.md`: 7-slide pitch adhering strictly to word count (titles <= 8 words, <= 3 bullets per slide, bullets <= 12 words, 3-4 sentence speaker notes). All unmeasured figures formatted as placeholders.
  - `out/pitch/demo_script.md`: 3-minute timed script with exact timestamps (0:00, 0:30, 1:15, 2:15, 2:35, 2:50), on-screen descriptions, spoken dialogue, and failure contingencies.
  - `out/pitch/judge_questions.md`: 15 toughest judge questions covering all required architectural, mathematical, and operational domains with 2-3 sentence honest answers.
  - `README.md`: Complete package overview, execution table, system integration instructions, and known gaps.
  - `test_pitch_pack.py`: 4 pytest unit tests verifying slide lengths, demo timestamps, question coverage, and documentation.
- 34 total pytest unit tests passing.

## Task 8: Final report
- Status: DONE
- Files produced:
  - `REPORT.md`: Comprehensive 1-page summary covering task status table, key numbers and sources, out/ directory inventory, known gaps, and test suite execution results.
- 34 total pytest unit tests passing.
