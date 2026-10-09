"""Check the reference probability calculator against ESA's own numbers (standalone).

    python esa_check.py

./esa/train_data.csv is the ESA Collision Avoidance Challenge dataset (Zenodo
record 4463683): real conjunction warnings ESA received for its satellites from
2015 to 2019, one warning per row. Each row carries ESA's own collision risk.
We recompute the probability from the same row and compare.

Columns used, as printed from the file and described with the dataset
(distances in metres, speeds in metres per second):
  relative_position_r/t/n, relative_velocity_r/t/n   chaser minus target, in the target's RTN frame
  t_sigma_r/t/n, c_sigma_r/t/n                       position standard deviations of target and chaser
  t_ct_r, t_cn_r, t_cn_t (and c_...)                 correlations between those components (all within -1..1)
  t_span, c_span                                     size of each object
  t_j2k_sma                                          target's semi-major axis, km
  risk                                               log10 of ESA's collision probability; -30 is the floor
  max_risk_estimate                                  log10 of ESA's worst case over covariance scaling
  time_to_tca, c_object_type                         for the uncertainty statistics

Assumptions, stated because the file does not settle them:
- Each object's covariance is given in its own RTN frame, as in the CDM
  standard. The chaser's frame is rebuilt from the relative velocity: both
  objects are at practically the same place, so they share the radial
  direction, and the target moves along its own T axis at circular speed.
- Combined hard-body radius. Two readings of the size columns are computed:
  the sum of the two spans, and half of it. The one that reproduces ESA's risk
  without an offset is reported as the convention; nothing else is adjusted.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from pc_reference import pc_integral, pc_max, pc_max_closed_form

HERE = Path(__file__).resolve().parent
ESA, OUT = HERE / "esa" / "train_data.csv", HERE / "out"
MU_M3_S2 = 3.986004418e14
FLOOR = -30.0
SEED, MAX_ROWS = 20261009, 20000
NEEDED = [
    "risk", "max_risk_estimate", "relative_position_r", "relative_position_t", "relative_position_n",
    "relative_velocity_r", "relative_velocity_t", "relative_velocity_n", "t_sigma_r", "t_sigma_t", "t_sigma_n",
    "c_sigma_r", "c_sigma_t", "c_sigma_n", "t_ct_r", "t_cn_r", "t_cn_t", "c_ct_r", "c_cn_r", "c_cn_t",
    "t_span", "c_span", "t_j2k_sma",
]


def covariance(sr: float, st: float, sn: float, ct_r: float, cn_r: float, cn_t: float) -> np.ndarray:
    """3x3 position covariance in an object's own RTN frame from sigmas and correlations."""
    return np.array([
        [sr * sr, ct_r * st * sr, cn_r * sn * sr],
        [ct_r * st * sr, st * st, cn_t * sn * st],
        [cn_r * sn * sr, cn_t * sn * st, sn * sn],
    ])


def chaser_frame(relative_velocity: np.ndarray, target_sma_km: float) -> np.ndarray:
    """Columns: the chaser's R, T, N axes expressed in the target's RTN frame."""
    target_speed = math.sqrt(MU_M3_S2 / (target_sma_km * 1000.0))
    velocity = relative_velocity + np.array([0.0, target_speed, 0.0])
    R = np.array([1.0, 0.0, 0.0])
    N = np.cross(R, velocity)
    N = N / np.linalg.norm(N)
    return np.column_stack([R, np.cross(N, R), N])


def encounter(row) -> tuple[np.ndarray, np.ndarray]:
    """(miss vector, 2x2 covariance) in the plane perpendicular to the relative velocity, metres."""
    dr = np.array([row.relative_position_r, row.relative_position_t, row.relative_position_n])
    dv = np.array([row.relative_velocity_r, row.relative_velocity_t, row.relative_velocity_n])
    target = covariance(row.t_sigma_r, row.t_sigma_t, row.t_sigma_n, row.t_ct_r, row.t_cn_r, row.t_cn_t)
    M = chaser_frame(dv, row.t_j2k_sma)
    chaser = M @ covariance(row.c_sigma_r, row.c_sigma_t, row.c_sigma_n, row.c_ct_r, row.c_cn_r, row.c_cn_t) @ M.T
    w = dv / np.linalg.norm(dv)
    u1 = dr - (dr @ w) * w
    u1 = u1 / np.linalg.norm(u1)
    basis = np.vstack([u1, np.cross(w, u1)])
    return basis @ dr, basis @ (target + chaser) @ basis.T


def log10(p: float) -> float:
    return math.log10(p) if p > 0.0 else -400.0


def compare(ours: np.ndarray, theirs: np.ndarray) -> dict:
    diff = ours - theirs
    return {
        "rows": int(len(diff)), "median_abs_difference_log10": float(np.median(np.abs(diff))),
        "p90_abs_difference_log10": float(np.percentile(np.abs(diff), 90)),
        "mean_signed_offset_log10": float(diff.mean()), "median_signed_offset_log10": float(np.median(diff)),
        "correlation": float(np.corrcoef(ours, theirs)[0, 1]),
        "share_within_0.1_log10": float((np.abs(diff) < 0.1).mean()),
    }


def sigma_stats(df: pd.DataFrame) -> dict:
    """Median chaser position sigma (m) by object type and whole days to closest approach."""
    table = df.dropna(subset=["c_sigma_r", "c_sigma_t", "c_sigma_n", "time_to_tca", "c_object_type"]).copy()
    table["days_to_tca"] = np.floor(table["time_to_tca"]).astype(int)
    grouped = table.groupby(["c_object_type", "days_to_tca"])[["c_sigma_r", "c_sigma_t", "c_sigma_n"]]
    out: dict = {}
    for (kind, days), values in grouped.median().iterrows():
        out.setdefault(str(kind), {})[str(int(days))] = {
            "median_sigma_rtn_m": [float(values.c_sigma_r), float(values.c_sigma_t), float(values.c_sigma_n)],
            "rows": int(grouped.size()[(kind, days)]),
        }
    return out


def main() -> None:
    df = pd.read_csv(ESA)
    total = len(df)
    correlations = df[["t_ct_r", "t_cn_r", "t_cn_t", "c_ct_r", "c_cn_r", "c_cn_t"]].abs().max().max()
    usable = df.dropna(subset=NEEDED)
    usable = usable[(usable.risk > FLOOR) & (usable.t_span > 0) & (usable.c_span > 0)]
    usable = usable[(usable[["t_sigma_r", "t_sigma_t", "t_sigma_n", "c_sigma_r", "c_sigma_t", "c_sigma_n"]] > 0).all(axis=1)]
    sample = usable.sample(n=min(MAX_ROWS, len(usable)), random_state=SEED)
    print(f"{total:,} rows; {len(usable):,} usable (risk above the floor of {FLOOR:g}, sizes and sigmas present); "
          f"comparing {len(sample):,}. Largest |correlation| in the file: {correlations:.3f}")

    rows = []
    for row in sample.itertuples(index=False):
        try:
            m, Cp = encounter(row)
            if not np.all(np.linalg.eigvalsh(Cp) > 0):
                continue
            half = 0.5 * (row.t_span + row.c_span)
            rows.append((
                row.risk, row.max_risk_estimate, log10(pc_integral(m, Cp, 2.0 * half)), log10(pc_integral(m, Cp, half)),
                log10(pc_max_closed_form(m, Cp, 2.0 * half)), float(np.linalg.norm(m)), 2.0 * half, m, Cp,
                log10(pc_max_closed_form(m, Cp, half)),
            ))
        except (ValueError, np.linalg.LinAlgError, ZeroDivisionError):
            continue
    esa_risk = np.array([r[0] for r in rows])
    esa_max = np.array([r[1] for r in rows])
    ours_sum = np.array([r[2] for r in rows])
    ours_half = np.array([r[3] for r in rows])
    max_sum = np.array([r[4] for r in rows])
    max_half = np.array([r[9] for r in rows])

    by_sum, by_half = compare(ours_sum, esa_risk), compare(ours_half, esa_risk)
    chosen_name = "sum of the two spans" if abs(by_sum["median_signed_offset_log10"]) <= abs(by_half["median_signed_offset_log10"]) else "half the sum of the two spans"
    use_sum = chosen_name.startswith("sum")
    chosen, ours, ours_max = (by_sum, ours_sum, max_sum) if use_sum else (by_half, ours_half, max_half)
    bands = {
        "ESA risk above 1e-6": esa_risk > -6.0,
        "ESA risk from 1e-10 to 1e-6": (esa_risk <= -6.0) & (esa_risk > -10.0),
        "ESA risk below 1e-10": esa_risk <= -10.0,
    }
    by_band = {name: compare(ours[mask], esa_risk[mask]) for name, mask in bands.items() if mask.sum() > 10}

    # worst case: ESA's max_risk_estimate against ours (closed form on every row, numeric on a subset)
    valid = np.isfinite(esa_max) & (esa_max > FLOOR) & (np.array([r[5] for r in rows]) > np.array([r[6] for r in rows]))
    worst = compare(ours_max[valid], esa_max[valid])
    subset = [r for r, ok in zip(rows, valid) if ok][:300]
    radius = (lambda r: r[6]) if use_sum else (lambda r: 0.5 * r[6])
    numeric = np.array([log10(pc_max(r[7], r[8], radius(r))) for r in subset])
    closed = np.array([r[4] if use_sum else r[9] for r in subset])

    result = {
        "dataset": "ESA Collision Avoidance Challenge, train_data.csv (Zenodo 4463683)",
        "rows_in_file": total, "rows_usable": int(len(usable)), "rows_compared": len(rows), "risk_floor": FLOOR,
        "hard_body_radius_used": chosen_name,
        "probability": chosen,
        "probability_by_esa_risk_band": by_band,
        "probability_with_the_other_radius": by_half if use_sum else by_sum,
        "worst_case_against_esa_max_risk_estimate": worst,
        "worst_case_numeric_against_closed_form_on_300_rows_median_abs_log10": float(np.median(np.abs(numeric - closed))),
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "esa_pc_check.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    (OUT / "esa_sigma_stats.json").write_text(json.dumps(sigma_stats(df), indent=1), encoding="utf-8")
    print(json.dumps(result, indent=1))
    plot(ours, esa_risk, chosen, OUT / "esa_pc_check.png")


def plot(ours: np.ndarray, theirs: np.ndarray, stats: dict, path: Path) -> None:
    from charts import GRID, INK_SOFT, SERIES, figure, save, titled

    fig, ax = figure(width=5.6, height=5.2)
    lo, hi = -30.0, 0.0
    ax.plot([lo, hi], [lo, hi], color=INK_SOFT, linewidth=1.0, zorder=1)
    ax.scatter(theirs, np.clip(ours, lo, hi), s=5, color=SERIES[0], alpha=0.25, linewidths=0, zorder=2)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal")
    titled(ax, "Our collision probability against ESA's, same warnings", "ESA's risk, log10 of probability",
           "Ours, log10 of probability")
    ax.annotate(
        f"{stats['rows']:,} real warnings\nmedian difference {stats['median_abs_difference_log10']:.3f} in log10\n"
        f"{100 * stats['share_within_0.1_log10']:.0f}% within 0.1",
        xy=(0.04, 0.96), xycoords="axes fraction", va="top", fontsize=9, color=INK_SOFT,
    )
    ax.annotate("line: equal values", xy=(-6.5, -6.5), xytext=(-13.5, -4.0), fontsize=8.5, color=INK_SOFT,
                arrowprops={"arrowstyle": "-", "color": GRID})
    save(fig, path)


if __name__ == "__main__":
    main()
