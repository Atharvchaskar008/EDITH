# Addon A: Orbit History, 2009 Replay, and Reference Test Kit

The `a_history` add-on package provides historical satellite TLE orbit data collection, real object size and operational status enrichment, historical 2009 Iridium 33 / Cosmos 2251 collision reconstruction data for interactive 3D replay, debris statistics, and an independent 7-case reference test kit for validating conjunction screening engines.

## Output Files Summary (`./out/`)

| File | Description & Main System Usage |
|---|---|
| `out/history_sample.json` | 30-day TLE element set history sample across 280 space objects used for testing history queries. |
| `out/replay_2009.json` | Pre-collision element sets for Iridium 33, Cosmos 2251, and 5,152 background objects used for demo opening. |
| `out/replay_2009_predictions.json` | Day-by-day conjunction predictions (7 days prior to collision) used for prediction timeline analysis. |
| `out/replay_2009_predictions.png` | Plot of predicted miss distance against days before collision used for dashboard charts. |
| `out/replay_2009_tracks.json` | High-res (5s) and full-orbit (30s) TEME orbital trajectories for 3D globe visualization. |
| `out/replay_2009_notes.md` | Executive plain-language summary of 2009 replay findings and warning time implications. |
| `out/catalog_enriched.json` | Enriched satellite catalogue with real RCS physical sizes, object types, and operational status. |
| `out/testkit/cases.json` | Benchmark test suite with 7 orbital conjunction cases and exact expected TCA / miss answers. |
| `out/testkit/README.md` | Guide and tolerance standards (TCA <= 0.5s, miss <= 10m) for testing custom screening code. |
| `out/testkit/check.py` | Automated checker script executing screen functions against benchmark test cases. |
| `out/debris_stats.json` | Statistics on 2009 collision fragments and Fengyun-1C debris overlapping Iridium NEXT altitude band. |
| `out/debris_altitude.png` | Histogram chart of catalogued debris vs altitude with shaded Iridium NEXT operational band. |

## Quick Usage Examples

### 1. `load_snapshot`
```python
from snapshot import load_snapshot
objs = load_snapshot("./snapshots/2026-10-09T07-26-14Z")
print(f"Loaded {len(objs)} objects; first object: {objs[0]['name']}")
```

### 2. `tle_history`
```python
from history import tle_history
hist = tle_history(norad_id=25544, days=30)
print(f"ISS history contains {len(hist)} element sets from {hist[0]['epoch']} to {hist[-1]['epoch']}")
```

### 3. `enrich_catalog`
```python
from snapshot import load_snapshot
from enrich import enrich_catalog
objs = load_snapshot("./snapshots/2026-10-09T07-26-14Z")
enriched = enrich_catalog(objs)
print(f"Enriched {len(enriched)} objects; payload radius: {enriched[0]['radius_m']} m")
```

### 4. `closest_approach`
```python
from replay_analysis import closest_approach
res = closest_approach(obj_a, obj_b, t_start="2009-02-10T16:00:00Z", t_end="2009-02-10T17:30:00Z")
print(f"Predicted TCA: {res['tca']}, Miss distance: {res['miss_distance_km']} km")
```

### 5. `check`
```python
from out.testkit.check import check, brute_force_screen
success = check(brute_force_screen)
print(f"Testkit benchmark suite result: {'PASSED' if success else 'FAILED'}")
```

## Known Gaps

- **Space-Track Rate Limit Restrictions**: Space-Track API limits requests to 20/min and 200/hour. All queries are cached on disk under `./cache/spacetrack/` to prevent hitting rate limits during re-runs.
- **Scipy C-Extension AppLocker Restriction**: Standard `scipy.optimize` C-extension DLLs are restricted by Windows Application Control Policy on some systems; interval minimization in `replay_analysis.py` uses a pure NumPy golden section search algorithm to guarantee execution on all systems.
- **RCS Size Fallback**: Satellite radar cross-section (RCS) data in CelesTrak SATCAT is missing for some payloads/debris; fallback physical radius estimates (0.5 m for DEBRIS, 2.0 m for PAYLOAD/ROCKET_BODY) are applied when RCS is omitted or non-numeric.
