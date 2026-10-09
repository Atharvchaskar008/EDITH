# Final Report: Operations, Alerting & ML Risk Prediction (`c_ops`)

## 1. Task Execution Summary

| Task | Topic | Status | Result Summary |
|---|---|---|---|
| **Task 1** | Data models & sample runs | **DONE** | Pydantic v2 models created; 3 sequential runs generated in `sample_runs/` telling the required escalation narrative. |
| **Task 2** | Alert engine | **DONE** | Matching engine tolerates 10-min TCA shifts & swapped IDs; accurately generates plain-language alerts for all 5 kinds. |
| **Task 3** | Alert feed, summary & watcher | **DONE** | Feed updates (`out/alert_feed.json`), ANSI colored console table, shift `summary.json`, and robust directory watcher implemented. |
| **Task 4** | ESA dataset & statistics | **DONE** | Zenodo dataset downloaded & analyzed (162,634 CDMs, 13,154 events); overview facts exported & risk evolution chart plotted. |
| **Task 5** | Risk-trend model | **DONE** | LightGBM operational model trained; cuts continuous risk MAE by 47% (2.67 vs 5.08); operational `predict_final_risk` created. |
| **Task 6** | Operator data | **DONE** | Standard CCSDS 508.0-B-1 KVN `.cdm.txt` export and JSON one-page shift briefings (`.briefing.json`) generated for all high-risk events. |
| **Task 7** | Pitch pack & packaging | **DONE** | 7 slides with word caps (`slides.md`), 3-min demo script (`demo_script.md`), 15 tough judge Q&As (`judge_questions.md`), and `README.md`. |
| **Task 8** | Final report | **DONE** | Final verification complete; test suite 100% passing; report compiled for project lead. |

---

## 2. Key Numbers Produced and Originating Files

| Metric | Measured Value | Source File |
|---|---|---|
| Total ESA Conjunction Warnings (CDMs) | 162,634 | `out/esa_overview.json` |
| Total ESA Conjunction Events | 13,154 | `out/esa_overview.json` |
| Warnings per Event | Median = 13.0, Max = 23, Min = 1 | `out/esa_overview.json` |
| Floor Risk Value in Dataset | -30.0 [log10 Pc] | `out/esa_overview.json` |
| Events Ending Above Critical Risk (-6.0) | 365 (2.8%) | `out/esa_overview.json` |
| Events Ending at Risk Floor (-30.0) | 8,349 (63.5%) | `out/esa_overview.json` |
| Early vs Final Risk Disagreement across -6.0 | 1,188 events (9.03%) | `out/esa_overview.json` |
| Qualifying Events for Model Training | 8,293 events (>= 2 days available, last <= 1 day) | `out/risk_model_report.json` |
| Train / Test Split Event Counts | 6,634 train / 1,659 test (80/20 split) | `out/risk_model_report.json` |
| Baseline Mean Absolute Error (MAE) | 5.0795 | `out/risk_model_report.json` |
| Operational Model Mean Absolute Error (MAE) | 2.6712 (Winner: Model, 47.4% error reduction) | `out/risk_model_report.json` |
| Baseline Root Mean Squared Error (RMSE) | 9.5268 | `out/risk_model_report.json` |
| Operational Model Root Mean Squared Error (RMSE) | 5.0426 (Winner: Model, 47.1% error reduction) | `out/risk_model_report.json` |
| Baseline Binary Precision / Recall / F2 (at -6.0) | Precision = 0.1077, Recall = 0.7778, F2 = 0.3465 | `out/risk_model_report.json` |
| Operational Model Precision / Recall / F2 (at -6.0) | Precision = 0.1333, Recall = 0.2222, F2 = 0.1961 | `out/risk_model_report.json` |
| Top Operational Model Feature | `latest_risk` (importance: 270 splits) | `out/risk_model_report.json` |
| Sample Run 2 Escalation Alert Counts | 1 ESCALATED, 1 NEW, 1 PLAN_READY, 0 CLEARED | `sample_runs/20261009T1200Z/summary.json` |
| Sample Run 2 Event Counts & Deltas | RED: 1 (+1), AMBER: 2 (+0), GREEN: 5 (-1) | `sample_runs/20261009T1200Z/summary.json` |
| Synthesized Avoidance Burn & Return Burn Size | 34.0 mm/s along-track, return burn 34.0 mm/s | `sample_runs/20261009T1200Z/briefings/43070-34427-20261011T0412.briefing.json` |

---

## 3. Inventory of Output Files (`out/`)

- `out/alert_feed.json`: Live dashboard alert feed containing the last 200 alerts across all runs, newest first.
- `out/watcher_state.json`: State file tracking processed run identifiers for idempotent background watching.
- `out/esa_overview.json`: Complete summary facts, risk distributions, and column unit mappings for the ESA challenge dataset.
- `out/esa_risk_evolution.png`: Visual plot showing collision risk trajectories over time to TCA for 30 high-risk vs 30 low-risk events.
- `out/risk_model_report.json`: Side-by-side performance comparison, classification triage metrics, and feature importances.
- `out/risk_model.png`: Test set scatter plot comparing predicted vs actual final risk with MAEs in the title.
- `out/risk_model_operational.joblib`: Serialized LightGBM model bundle using the 14 operational numerical features.
- `out/risk_model_full.joblib`: Serialized LightGBM model bundle trained on all dataset features including object category.

---

## 4. Known Gaps and Operational Boundaries

1. **Public TLE Accuracy**: Public Two-Line Element sets have position errors on the order of 0.5 to 1.5 km. Risk predictions and collision probabilities are designed for screening and triage, not certified flight telemetry.
2. **Covariance Approximation**: Because public TLEs lack published covariance, RTN sigmas are estimated from historical tracking scatter unless operator-provided ephemeris is available.
3. **ML Early-Warning Volatility**: While our gradient boosting model cuts continuous risk prediction error (MAE) by 47% (2.67 vs 5.08), predicting whether early low-risk warnings cross the rare critical threshold (-6.0) remains challenging due to orbital update volatility; the baseline persistence heuristic achieves higher binary recall (0.78 vs 0.22), which is reported honestly.
4. **Advisory Decision Support**: All manoeuvre recommendations and risk scores are decision support outputs; no autonomous burn commands are transmitted to spacecraft.
5. **No Blocked Tasks**: Zero tasks were blocked; all tasks completed successfully.

---

## 5. Test Suite Verification

- **Command to run test suite:**
  ```powershell
  .venv\Scripts\pytest.exe
  ```
- **Last test suite execution output:**
  ```text
  ============================= test session starts =============================
  platform win32 -- Python 3.12.14, pytest-9.1.1, pluggy-1.6.0
  rootdir: C:\Users\USER\Desktop\Fusion\Fusion-skn\addons\c_ops
  collected 34 items

  test_compare.py .........                                                [ 26%]
  test_esa_data.py ...                                                     [ 35%]
  test_model.py ....                                                       [ 47%]
  test_models.py ....                                                      [ 58%]
  test_operator_data.py ......                                             [ 76%]
  test_pitch_pack.py ....                                                  [ 88%]
  test_watch.py ....                                                       [100%]

  ============================= 34 passed in 18.25s =============================
  ```
- **Total tests:** 34 passed, 0 failed.
