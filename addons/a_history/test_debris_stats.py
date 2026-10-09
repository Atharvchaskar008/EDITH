import pytest
import json
from pathlib import Path
from debris_stats import generate_debris_statistics

def test_debris_stats_execution():
    stats = generate_debris_statistics()
    
    out_dir = Path(__file__).parent / "out"
    json_file = out_dir / "debris_stats.json"
    plot_file = out_dir / "debris_altitude.png"

    assert json_file.exists()
    assert plot_file.exists()

    assert "iridium_next_band_km" in stats
    assert "collision_2009_debris" in stats
    assert "fengyun_1c_debris" in stats

    assert stats["collision_2009_debris"]["total_in_orbit"] > 0
    assert stats["fengyun_1c_debris"]["total_in_orbit"] > 0
