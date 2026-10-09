import pytest
import json
from pathlib import Path
from out.testkit.check import check, brute_force_screen

def test_testkit_cases_exist():
    cases_file = Path(__file__).parent / "out" / "testkit" / "cases.json"
    assert cases_file.exists()
    with open(cases_file, "r", encoding="utf-8") as f:
        cases = json.load(f)
    assert len(cases) == 7

def test_testkit_checker_passes():
    result = check(brute_force_screen)
    assert result is True
