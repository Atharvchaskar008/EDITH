from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional
import joblib
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "out", "risk_model_operational.joblib")

_MODEL_BUNDLE: Optional[dict] = None


def get_model_bundle() -> dict:
    global _MODEL_BUNDLE
    if _MODEL_BUNDLE is None:
        if not os.path.isfile(MODEL_PATH):
            raise FileNotFoundError(f"Trained operational model not found at {MODEL_PATH}. Run train.py first.")
        _MODEL_BUNDLE = joblib.load(MODEL_PATH)
    return _MODEL_BUNDLE


def parse_utc_dt(val: Any) -> Optional[datetime]:
    if isinstance(val, datetime):
        return val.astimezone(timezone.utc)
    if isinstance(val, str):
        s = val.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None
    return None


def predict_final_risk(event: dict) -> float | None:
    """Predicts the event's FINAL risk (log10 Pc) using the trained operational model.
    Returns None if any required input field is missing or invalid.
    """
    if not isinstance(event, dict):
        return None

    # Required field validation
    pc = event.get("pc")
    miss_dist_km = event.get("miss_distance_km")
    rel_speed_kms = event.get("relative_speed_kms")
    tca_str = event.get("tca")
    sig_p = event.get("sigma_rtn_primary_km")
    sig_s = event.get("sigma_rtn_secondary_km")

    if pc is None or miss_dist_km is None or rel_speed_kms is None or tca_str is None:
        return None
    if sig_p is None or sig_s is None or len(sig_p) < 3 or len(sig_s) < 3:
        return None

    try:
        # --- UNIT CONVERSIONS ---
        # 1. Collision Probability:
        # Input: dimensionless probability pc in [0, 1]
        # Target/Model unit: base-10 logarithm [log10 Pc]
        # Clamp at 1e-30 to match ESA dataset floor of -30.0
        pc_val = float(pc)
        if pc_val <= 0:
            latest_risk = -30.0
        else:
            latest_risk = float(np.log10(max(pc_val, 1e-30)))

        # 2. Miss Distance:
        # Input: kilometres [km]
        # Dataset/Model unit: metres [m]
        # Conversion: 1 km = 1,000 m
        miss_dist_m = float(miss_dist_km) * 1000.0

        # 3. Relative Speed:
        # Input: kilometres per second [km/s]
        # Dataset/Model unit: metres per second [m/s]
        # Conversion: 1 km/s = 1,000 m/s
        rel_speed_ms = float(rel_speed_kms) * 1000.0

        # 4. Time to TCA:
        # Input: TCA timestamp string
        # Dataset/Model unit: days [days]
        # Conversion: seconds to closest approach / 86,400 s/day
        tca_dt = parse_utc_dt(tca_str)
        if tca_dt is None:
            return None

        # Reference time: check if ref_time / run_time is provided, else use current UTC or first_seen
        ref_str = event.get("run_time") or event.get("first_seen")
        ref_dt = parse_utc_dt(ref_str) if ref_str else None
        if ref_dt is None:
            ref_dt = datetime.now(timezone.utc)

        time_to_tca_days = max(0.0, (tca_dt - ref_dt).total_seconds() / 86400.0)

        # 5. Position standard deviations (RTN sigmas):
        # Input: kilometres [km] for radial (R), transverse (T), normal (N)
        # Dataset/Model unit: metres [m]
        # Conversion: 1 km = 1,000 m
        t_sigma_r = float(sig_p[0]) * 1000.0
        t_sigma_t = float(sig_p[1]) * 1000.0
        t_sigma_n = float(sig_p[2]) * 1000.0

        c_sigma_r = float(sig_s[0]) * 1000.0
        c_sigma_t = float(sig_s[1]) * 1000.0
        c_sigma_n = float(sig_s[2]) * 1000.0

        comb_sigma = float(np.sqrt(
            t_sigma_r**2 + t_sigma_t**2 + t_sigma_n**2 +
            c_sigma_r**2 + c_sigma_t**2 + c_sigma_n**2
        ))
        log_comb_sigma = float(np.log10(max(comb_sigma, 1e-3)))
        log_miss_dist = float(np.log10(max(miss_dist_m, 1.0)))
        mahal_proxy = float(np.log10(max(miss_dist_m / max(comb_sigma, 1e-3), 1e-4)))
        max_sig = float(max(t_sigma_r, t_sigma_t, t_sigma_n, c_sigma_r, c_sigma_t, c_sigma_n))
        log_max_sig = float(np.log10(max(max_sig, 1e-3)))
        log_rel_speed = float(np.log10(max(rel_speed_ms, 1.0)))

        # 6. History stats:
        # Input: list of dicts [{"run_id": ..., "pc_max": ..., "miss_distance_km": ...}]
        history = event.get("history") or []
        num_warnings = max(1, len(history))

        if len(history) >= 2:
            r_last = np.log10(max(float(history[-1].get("pc_max", pc_val)), 1e-30))
            r_prev = np.log10(max(float(history[-2].get("pc_max", pc_val)), 1e-30))
            risk_diff = float(r_last - r_prev)
            hist_risks = [np.log10(max(float(h.get("pc_max", pc_val)), 1e-30)) for h in history]
            mean_risk = float(np.mean(hist_risks))
            std_risk = float(np.std(hist_risks))
            risk_velocity = float(risk_diff / 0.5)
        elif len(history) == 1:
            risk_diff = 0.0
            mean_risk = latest_risk
            std_risk = 0.0
            risk_velocity = 0.0
        else:
            risk_diff = 0.0
            mean_risk = latest_risk
            std_risk = 0.0
            risk_velocity = 0.0

        bundle = get_model_bundle()
        model = bundle["model"]
        feature_names = bundle["features"]

        feature_values = {
            "latest_risk": latest_risk,
            "latest_miss_distance": miss_dist_m,
            "latest_relative_speed": rel_speed_ms,
            "time_to_tca": time_to_tca_days,
            "t_sigma_r": t_sigma_r,
            "t_sigma_t": t_sigma_t,
            "t_sigma_n": t_sigma_n,
            "c_sigma_r": c_sigma_r,
            "c_sigma_t": c_sigma_t,
            "c_sigma_n": c_sigma_n,
            "num_warnings": float(num_warnings),
            "risk_diff": risk_diff,
            "mean_risk": mean_risk,
            "std_risk": std_risk,
            "combined_sigma": comb_sigma,
            "log_combined_sigma": log_comb_sigma,
            "log_miss_distance": log_miss_dist,
            "mahalanobis_proxy": mahal_proxy,
            "log_max_sigma": log_max_sig,
            "log_rel_speed": log_rel_speed,
            "risk_velocity": risk_velocity,
        }

        X_df = pd.DataFrame([[feature_values[f] for f in feature_names]], columns=feature_names)
        pred = model.predict(X_df)[0]
        return float(pred)
    except Exception:
        return None
