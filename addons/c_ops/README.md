# Teammate C Addon: Operations, Alerting & ML Risk Prediction (`addons/c_ops`)

This pack provides autonomous monitoring, operator alerting, CCSDS CDM export, operator shift briefings, and machine learning risk-trend modeling for the Fusion space conjunction assessment platform.

It is completely self-contained within `addons/c_ops/` and communicates with the main system via standard JSON run folders.

---

## What the Pack Contains

1. **Alert Engine & Monitor (`compare.py`, `watch.py`, `notify.py`)**:
   - Detects state changes across consecutive orbital runs: `NEW`, `ESCALATED`, `DOWNGRADED`, `CLEARED`, and `PLAN_READY`.
   - 10-minute TCA shift tolerance and swapped object-order matching.
   - Live dashboard alert feed (`out/alert_feed.json`), ANSI terminal alerts, and shift summaries (`summary.json`).
2. **Operator Data Deliverables (`cdm_export.py`, `briefing.py`)**:
   - Standard CCSDS 508.0-B-1 KVN Conjunction Data Message (`.cdm.txt`) export with verified units.
   - Operator shift briefing data (`.briefing.json`) formatted with human-readable units and zero HTML.
3. **ESA Dataset Analysis & Risk Prediction Model (`esa_data.py`, `train.py`, `predict.py`)**:
   - Trained on 162,634 CDMs from ESA's Collision Avoidance Challenge (Zenodo record 4463683).
   - LightGBM model predicting final risk from early warnings (>= 2 days before TCA), cutting MAE by 47% over baseline.

---

## Scripts and Commands

| Script | Purpose | Command |
|---|---|---|
| `make_samples.py` | Generate 3 sequential sample runs with narrative | `python make_samples.py` |
| `compare.py` | Compare two runs or screen first run | `python compare.py <prev_folder> <curr_folder>` |
| `notify.py` | Feed management, console formatting, and shift summary | Used as module by `watch.py` / `compare.py` |
| `watch.py` | Watch runs directory or replay runs | `python watch.py --runs <dir> [--once] [--replay <dir>]` |
| `esa_data.py` | Load ESA dataset, generate overview facts, plot evolution | `python esa_data.py` |
| `train.py` | Train LightGBM risk models, evaluate metrics, plot results | `python train.py` |
| `predict.py` | Operational inference function `predict_final_risk()` | `python -c "from predict import predict_final_risk; print(predict_final_risk({...}))"` |
| `cdm_export.py` | Export CCSDS 508.0-B-1 KVN `.cdm.txt` files | `python cdm_export.py <run_folder>` |
| `briefing.py` | Export one-page operator briefing JSON files | `python briefing.py <run_folder>` |

---

## How the Main System Plugs In

The main system requires zero code modifications to integrate with this pack:

1. **Run Watcher**:
   - Run `python watch.py --runs ../../data/runs` in the background (or `--once` per cycle).
   - As new run folders (`YYYYMMDDTHHMMZ/`) complete with `events.json` and `DONE`, `watch.py` automatically generates `alerts.json`, `summary.json`, and updates `events.json` with event history.
2. **Dashboard Alert Stream**:
   - The frontend alerts component reads `addons/c_ops/out/alert_feed.json` (stores the 200 most recent alerts, newest first).
3. **Predicted Final Risk Column**:
   - The main pipeline imports `predict_final_risk` from `addons.c_ops.predict` and passes event dictionaries to populate the `pc_predicted_final` column.
4. **Operator Briefings & Standard CDMs**:
   - The UI links directly to `<run_folder>/briefings/<event_id>.briefing.json` for one-page briefing modals.
   - The UI provides a download link to `<run_folder>/cdm/<event_id>.cdm.txt` for CCSDS standard export.

---

## Known Gaps & Operational Boundaries

1. **Public TLE Accuracy**: Public Two-Line Element sets have position errors on the order of 0.5 to 1.5 km. Risk predictions and collision probabilities are designed for screening and triage, not certified flight telemetry.
2. **Covariance Approximation**: Because public TLEs lack published covariance, RTN sigmas are estimated from historical tracking scatter unless operator-provided ephemeris is available.
3. **ML Early-Warning Noise**: While the gradient boosting model cuts continuous risk prediction error (MAE) by 47% (2.67 vs 5.08), predicting whether early low-risk warnings cross the rare critical threshold (-6.0) remains challenging due to orbital update volatility; the baseline persistence heuristic achieves higher binary recall (0.78 vs 0.22).
4. **Advisory Decision Support**: All manoeuvre recommendations and risk scores are decision support outputs; no autonomous burn commands are transmitted to spacecraft.
