"""Measure where the time goes, to answer "why Python and NumPy?".

    .venv\\Scripts\\python scripts\\why_python.py

Uses the cached real catalogue (run the pipeline once first). Prints how fast
the compiled libraries are compared with the same work written in plain Python,
and how the neighbour search compares with checking every pair.
"""

from __future__ import annotations

import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
from sgp4.api import accelerated, jday
from sgp4.model import Satrec as PythonSatrec

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fusion import addons, config  # noqa: E402
from fusion.core.ingest import load_catalog  # noqa: E402
from fusion.core.propagate import Propagator  # noqa: E402


def main() -> None:
    addons.ADDONS_DIR = Path("no-addons")  # timing only: skip the optional size lookup
    catalog = load_catalog()
    n = len(catalog)
    now = datetime.now(timezone.utc)
    print(f"Catalogue: {n:,} objects. sgp4 compiled backend in use: {accelerated}\n")

    # 1. orbit prediction: compiled SGP4 on arrays, against the same maths in plain Python
    steps = 60
    propagator = Propagator(catalog)
    start = time.perf_counter()
    r, _ = propagator.states(now, np.arange(steps) * config.SCREEN_STEP_S)
    fast = n * steps / (time.perf_counter() - start)

    sample = [o for o in catalog if o.tle_line1 and o.tle_line2][:300]
    slow_sats = [PythonSatrec.twoline2rv(o.tle_line1, o.tle_line2) for o in sample]
    jd, fr = jday(now.year, now.month, now.day, now.hour, now.minute, now.second)
    start = time.perf_counter()
    for sat in slow_sats:
        for k in range(10):
            sat.sgp4(jd, fr + k * config.SCREEN_STEP_S / 86400.0)
    slow = len(slow_sats) * 10 / (time.perf_counter() - start)
    print("1. Orbit prediction (SGP4)")
    print(f"   compiled, on arrays : {fast:12,.0f} positions per second on one core")
    print(f"   plain Python        : {slow:12,.0f} positions per second")
    print(f"   ratio               : {fast / slow:12,.0f} times faster\n")

    # 2. finding neighbours at one moment: KD-tree against checking every pair
    positions = r[:, 0, :]
    positions = positions[np.isfinite(positions[:, 0])]
    m = len(positions)
    radius = config.SCREEN_THRESHOLD_ALL_LEO_KM + config.MAX_CLOSING_SPEED_KMS * config.SCREEN_STEP_S / 2.0
    start = time.perf_counter()
    pairs = cKDTree(positions).query_pairs(radius, output_type="ndarray")
    tree_s = time.perf_counter() - start

    start = time.perf_counter()
    found = 0
    for first in range(0, m, 1000):  # every pair, with NumPy, in blocks that fit in memory
        block = positions[first:first + 1000]
        d2 = ((block[:, None, :] - positions[None, :, :]) ** 2).sum(axis=2)
        found += int((d2 < radius * radius).sum())
    numpy_s = time.perf_counter() - start
    found = (found - m) // 2

    start = time.perf_counter()
    count = 200_000
    a, b = positions[0].tolist(), positions[1].tolist()
    for _ in range(count):  # the same distance test in plain Python, timed on a sample
        math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) < radius
    python_s = (time.perf_counter() - start) / count * (m * (m - 1) / 2)

    steps_per_day = int(86400 / config.SCREEN_STEP_S)
    print(f"2. Finding objects within {radius:.1f} km of each other at one moment ({m * (m - 1) // 2:,} pairs)")
    print(f"   KD-tree (SciPy, compiled)    : {tree_s * 1000:9,.0f} ms   -> {len(pairs):,} pairs to look at")
    print(f"   every pair, NumPy            : {numpy_s * 1000:9,.0f} ms   -> {found:,} pairs (same answer: {found == len(pairs)})")
    print(f"   every pair, plain Python     : {python_s * 1000:9,.0f} ms   (estimated from a timed sample)")
    print(f"   For one day ({steps_per_day:,} moments) on one core: KD-tree {tree_s * steps_per_day / 60:,.0f} min, "
          f"NumPy every pair {numpy_s * steps_per_day / 3600:,.0f} h, plain Python {python_s * steps_per_day / 86400:,.0f} days")


if __name__ == "__main__":
    main()
