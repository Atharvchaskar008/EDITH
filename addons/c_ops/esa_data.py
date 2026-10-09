from __future__ import annotations

import glob
import json
import os
from typing import Optional, Tuple
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_PATH = os.path.join(
    BASE_DIR, "esa", "Collision Avoidance Challenge - Dataset", "kelvins_competition_data", "train_data.csv"
)
OUT_DIR = os.path.join(BASE_DIR, "out")


def find_train_data_path() -> str:
    if os.path.isfile(DEFAULT_DATA_PATH):
        return DEFAULT_DATA_PATH
    candidates = glob.glob(os.path.join(BASE_DIR, "esa", "**", "train_data.csv"), recursive=True)
    if candidates:
        return candidates[0]
    raise FileNotFoundError("Could not find train_data.csv in ./esa/ directory.")


def load_cdms(data_path: Optional[str] = None) -> pd.DataFrame:
    """Loads the ESA Collision Avoidance Challenge training dataset as a pandas DataFrame."""
    path = data_path or find_train_data_path()
    df = pd.read_csv(path)
    return df


def print_dataset_info(df: pd.DataFrame) -> None:
    print(f"Dataset Shape: {df.shape[0]} rows x {df.shape[1]} columns")
    print("\n--- All Column Names ---")
    for i, col in enumerate(df.columns):
        print(f"{i+1:3d}. {col} ({df[col].dtype})")

    print("\n--- Dtypes Summary ---")
    print(df.dtypes.value_counts())

    print("\n--- First 3 Rows ---")
    print(df.head(3))


def generate_overview_facts(df: pd.DataFrame, out_path: str = os.path.join(OUT_DIR, "esa_overview.json")) -> dict:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    total_warnings = int(len(df))
    num_events = int(df["event_id"].nunique())
    warn_per_event = df.groupby("event_id").size()
    median_warnings = float(warn_per_event.median())
    max_warnings = int(warn_per_event.max())
    min_warnings = int(warn_per_event.min())

    # Sort each event by time_to_tca descending so first row is earliest warning and last row is final warning
    df_sorted = df.sort_values(["event_id", "time_to_tca"], ascending=[True, False])
    first_warnings = df_sorted.groupby("event_id").first()
    final_warnings = df_sorted.groupby("event_id").last()

    floor_risk = float(df["risk"].min())  # -30.0
    final_risks = final_warnings["risk"]

    above_minus_6 = int((final_risks > -6.0).sum())
    between_minus_6_and_minus_10 = int(((final_risks <= -6.0) & (final_risks > -10.0)).sum())
    at_floor = int((final_risks == floor_risk).sum())
    below_minus_10_not_floor = int(((final_risks <= -10.0) & (final_risks > floor_risk)).sum())

    first_risks = first_warnings["risk"]
    first_above = first_risks > -6.0
    final_above = final_risks > -6.0
    different_sides = int((first_above != final_above).sum())
    fraction_different_sides = float(different_sides / num_events)

    facts = {
        "dataset_name": "ESA Collision Avoidance Challenge (Zenodo record 4463683)",
        "number_of_warnings": total_warnings,
        "number_of_events": num_events,
        "warnings_per_event": {
            "median": median_warnings,
            "max": max_warnings,
            "min": min_warnings,
        },
        "floor_risk_value": floor_risk,
        "final_risk_distribution": {
            "above_minus_6": above_minus_6,
            "between_minus_6_and_minus_10": between_minus_6_and_minus_10,
            "below_minus_10_total": int((final_risks <= -10.0).sum()),
            "at_floor_value": at_floor,
            "between_minus_10_and_floor": below_minus_10_not_floor,
        },
        "early_vs_final_risk_shift": {
            "events_with_different_sides_of_minus_6": different_sides,
            "percentage_different_sides": round(fraction_different_sides * 100, 2),
        },
        "column_mapping_and_units": {
            "event_identifier": {"column": "event_id", "unit": "integer ID", "source": "raw_data_2015-2019.txt line 37"},
            "time_to_closest_approach": {"column": "time_to_tca", "unit": "days", "source": "raw_data_2015-2019.txt line 38"},
            "risk_value": {"column": "risk", "scale": "base-10 logarithm [log10 Pc]", "unit": "dimensionless log-probability", "source": "raw_data_2015-2019.txt line 36"},
            "miss_distance": {"column": "miss_distance", "unit": "meters [m]", "source": "raw_data_2015-2019.txt line 42"},
            "relative_speed": {"column": "relative_speed", "unit": "meters per second [m/s]", "source": "raw_data_2015-2019.txt line 43"},
            "position_standard_deviations_target": {"columns": ["t_sigma_r", "t_sigma_t", "t_sigma_n"], "unit": "meters [m]", "source": "raw_data_2015-2019.txt lines 70, 72, 61"},
            "position_standard_deviations_chaser": {"columns": ["c_sigma_r", "c_sigma_t", "c_sigma_n"], "unit": "meters [m]", "source": "raw_data_2015-2019.txt lines 70, 72, 61"},
            "chaser_object_type": {"column": "c_object_type", "type": "categorical string", "unit": "dimensionless category", "source": "raw_data_2015-2019.txt line 50"},
        },
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(facts, f, indent=2)

    print("\n--- Basic Facts Saved to", out_path, "---")
    print(f"Total Warnings: {total_warnings:,}")
    print(f"Total Events: {num_events:,}")
    print(f"Warnings per Event: median={median_warnings}, max={max_warnings}")
    print(f"Final Risk > -6: {above_minus_6} ({above_minus_6 / num_events * 100:.1f}%)")
    print(f"Final Risk [-10, -6]: {between_minus_6_and_minus_10} ({between_minus_6_and_minus_10 / num_events * 100:.1f}%)")
    print(f"Final Risk at Floor (-30.0): {at_floor} ({at_floor / num_events * 100:.1f}%)")
    print(f"First vs Final Risk on Different Sides of -6: {different_sides} ({fraction_different_sides * 100:.2f}%)")

    return facts


def plot_risk_evolution(
    df: pd.DataFrame,
    out_path: str = os.path.join(OUT_DIR, "esa_risk_evolution.png"),
    n_high: int = 30,
    n_low: int = 30,
) -> str:
    """Plots risk evolution against time to TCA for 30 high final risk and 30 low final risk events."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    df_sorted = df.sort_values(["event_id", "time_to_tca"], ascending=[True, False])
    event_counts = df_sorted.groupby("event_id").size()

    # Filter to events that have at least 6 warnings and span at least 2 days so the trend line is clear
    valid_events = event_counts[event_counts >= 6].index
    df_valid = df_sorted[df_sorted["event_id"].isin(valid_events)]

    final_risks = df_valid.groupby("event_id")["risk"].last()

    # High final risk: final risk > -5.0
    high_candidates = final_risks[final_risks > -5.0].index.tolist()
    # Low final risk: final risk < -12.0
    low_candidates = final_risks[final_risks < -12.0].index.tolist()

    selected_high = high_candidates[:n_high]
    selected_low = low_candidates[:n_low]

    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)

    # Plot low final risk lines (blue/teal)
    for ev_id in selected_low:
        sub = df_valid[df_valid["event_id"] == ev_id].sort_values("time_to_tca", ascending=False)
        ax.plot(
            sub["time_to_tca"],
            sub["risk"],
            color="#2b6cb0",
            alpha=0.35,
            linewidth=1.2,
            marker="o",
            markersize=2.5,
        )

    # Plot high final risk lines (red/coral)
    for ev_id in selected_high:
        sub = df_valid[df_valid["event_id"] == ev_id].sort_values("time_to_tca", ascending=False)
        ax.plot(
            sub["time_to_tca"],
            sub["risk"],
            color="#e53e3e",
            alpha=0.45,
            linewidth=1.4,
            marker="s",
            markersize=3,
        )

    # Add custom legend proxy handles
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color="#e53e3e", lw=2, label=f"High Final Risk (> 1e-5, n={len(selected_high)})"),
        Line2D([0], [0], color="#2b6cb0", lw=2, label=f"Low Final Risk (< 1e-12, n={len(selected_low)})"),
        Line2D([0], [0], color="#d69e2e", lw=1.5, ls="--", label="ESA Critical Threshold (1e-6 / risk=-6)"),
    ]

    # Draw reference line at -6
    ax.axhline(-6.0, color="#d69e2e", linestyle="--", linewidth=1.5, alpha=0.9)

    # Aesthetics
    ax.set_title("ESA Conjunction Evolution: Collision Risk vs Time to TCA", fontsize=14, fontweight="bold", pad=12)
    ax.set_xlabel("Time to Closest Approach (days) -> Approaching Encounter", fontsize=11, labelpad=8)
    ax.set_ylabel("Risk [log10 Collision Probability]", fontsize=11, labelpad=8)
    ax.set_ylim(-32, -1)
    ax.set_xlim(ax.get_xlim()[1], 0)  # Invert x-axis so time flows from e.g. 6 days down to 0 days (TCA)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(handles=legend_elements, loc="lower left", framealpha=0.9)

    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()
    print(f"Risk evolution plot saved to {out_path}")
    return out_path


def main():
    print("Loading ESA dataset...")
    df = load_cdms()
    print_dataset_info(df)
    generate_overview_facts(df)
    plot_risk_evolution(df)


if __name__ == "__main__":
    main()
