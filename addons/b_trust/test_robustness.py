import numpy as np
import pytest

from pc_reference import pc_max
from robustness import against, guessed_sigma, level, worst_case


@pytest.mark.parametrize("m, Cp, hbr", [
    ([0.30, 0.00], np.diag([0.25**2, 0.25**2]), 0.010),
    ([0.05, 0.02], np.diag([2.0**2, 0.1**2]), 0.010),
    ([0.02, 0.06], np.array([[1.0, 0.3], [0.3, 0.2]]), 0.005),
])
def test_the_lighter_worst_case_search_matches_the_reference(m, Cp, hbr):
    assert worst_case(np.array(m), Cp, hbr) == pytest.approx(pc_max(m, Cp, hbr), rel=0.01)


def test_worst_case_is_one_when_the_objects_overlap_at_the_predicted_miss():
    assert worst_case(np.array([0.004, 0.0]), np.eye(2), 0.010) == 1.0


def test_levels_and_the_guessed_table():
    assert [level(p) for p in (2e-4, 1e-4, 5e-5, 1e-5, 9e-6)] == ["RED", "RED", "AMBER", "AMBER", "GREEN"]
    assert guessed_sigma("PAYLOAD", 2.0) == pytest.approx([0.2, 2.5, 0.2])
    assert guessed_sigma("DEBRIS", 2.0) == pytest.approx([0.2, 4.5, 0.2])


def test_comparison_with_the_baseline_counts_what_changed():
    baseline = [{"pc": 10.0 ** -(i + 3), "pc_max": 10.0 ** -(i / 4 + 3)} for i in range(20)]
    same = against(baseline, baseline)
    assert same == {"spearman_pc": 1.0, "spearman_pc_max": 1.0, "top10_still_in_top10": 10, "events_changing_risk_level": 0}
    reversed_rows = list(reversed(baseline))
    flipped = against(baseline, reversed_rows)
    assert flipped["spearman_pc_max"] == pytest.approx(-1.0) and flipped["top10_still_in_top10"] == 0
    assert flipped["events_changing_risk_level"] > 0
