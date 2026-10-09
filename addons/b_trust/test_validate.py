import pytest

from socrates import _name_and_status, download, parse
from validate import compare

CSV = (
    "NORAD_CAT_ID_1,OBJECT_NAME_1,DSE_1,NORAD_CAT_ID_2,OBJECT_NAME_2,DSE_2,TCA,TCA_RANGE,TCA_RELATIVE_SPEED,MAX_PROB,DILUTION\n"
    "59300,STARLINK-31489 [+],5.508,44531,CZ-4B R/B [-],5.704,2026-10-13 10:05:00.379,0.008,12.248,1.000E+00,0.000\n"
    "55973,TIANMU-1 03 [+],2.019,33687,FENGYUN 1C DEB [-],5.998,2026-10-09 22:38:13.848,0.012,12.126,2.075E-02,0.004\n"
    "41920,IRIDIUM 102 [+],4.055,61130,CZ-6A DEB"  # a line cut by the byte limit
)


def event(primary, secondary, tca, miss, speed=12.0, ages=(1.0, 1.0)):
    return {
        "primary_id": primary, "secondary_id": secondary, "tca": tca, "miss_distance_km": miss,
        "relative_speed_kms": speed, "primary_tle_age_days": ages[0], "secondary_tle_age_days": ages[1],
    }


def test_parse_reads_documented_columns_and_skips_a_cut_line():
    rows = parse(CSV)
    assert len(rows) == 2
    first = rows[0]
    assert (first["id_1"], first["name_1"], first["status_1"]) == (59300, "STARLINK-31489", "+")
    assert (first["id_2"], first["name_2"], first["status_2"]) == (44531, "CZ-4B R/B", "-")
    assert first["tca"] == "2026-10-13T10:05:00.379Z" and first["min_range_km"] == 0.008
    assert first["days_since_epoch_2"] == 5.704 and first["max_probability"] == 1.0
    assert _name_and_status("OBJECT WITHOUT STATUS") == ("OBJECT WITHOUT STATUS", "")


def test_compare_matches_either_order_and_respects_the_time_tolerance():
    socrates = parse(CSV)
    events = [
        event(44531, 59300, "2026-10-13T10:05:01.379Z", 0.010, 12.25, ages=(5.704, 5.508)),  # ids reversed, 1 s later
        event(55973, 33687, "2026-10-09T22:39:14.848Z", 0.012),                             # 61 s away: no match
        event(1, 2, "2026-10-13T10:05:00Z", 0.5),                                            # not in SOCRATES
    ]
    result = compare(events, socrates)
    assert result["all_matches"]["matched"] == 1
    pair = result["pairs"][0]
    assert pair["tca_difference_s"] == pytest.approx(1.0) and pair["miss_difference_m"] == pytest.approx(2.0)
    assert pair["relative_speed_difference_ms"] == pytest.approx(2.0) and pair["same_element_sets"] is True
    assert result["same_element_sets"]["matched"] == 1 and result["newer_element_sets"]["matched"] == 0


def test_compare_tells_same_data_from_newer_data_and_reports_coverage():
    socrates = parse(CSV)
    events = [
        event(59300, 44531, "2026-10-13T10:05:00.379Z", 0.9, ages=(0.4, 5.704)),   # first object has a newer element set
        event(55973, 33687, "2026-10-09T22:38:13.848Z", 0.012, ages=(2.019, 5.9985)),
    ]
    result = compare(events, socrates, window=("2026-10-09T00:00:00Z", "2026-10-10T00:00:00Z"), max_range_km=1.0)
    assert result["newer_element_sets"]["matched"] == 1 and result["same_element_sets"]["matched"] == 1
    assert result["newer_element_sets"]["miss_difference_m"]["median"] == pytest.approx(892.0)
    coverage = result["coverage"]
    assert coverage["socrates_rows_in_window_and_range"] == 1 and coverage["of_those_found_by_us"] == 1
    assert coverage["our_events_in_window"] == 1 and coverage["of_those_in_socrates"] == 1


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, content):
        self.content, self.calls = content, []

    def get(self, url, headers=None, timeout=None):
        self.calls.append(headers)
        return FakeResponse(self.content)


def test_download_asks_for_the_first_part_only_and_drops_the_cut_line(tmp_path):
    body = CSV.encode()
    session = FakeSession(body)
    path = download(max_bytes=len(body), path=tmp_path / "socrates.csv", session=session)
    assert session.calls == [{"Range": f"bytes=0-{len(body) - 1}"}]
    assert path.read_text().count("\n") == 3 and "IRIDIUM 102" not in path.read_text()
    download(max_bytes=len(body), path=path, session=session)  # fresh copy: no second request
    assert len(session.calls) == 1
