from datetime import datetime, timedelta, timezone

import pytest

from fusion.core.sat import object_from_omm

EPOCH = datetime(2026, 10, 9, 3, 0, 0, tzinfo=timezone.utc)


def test_omm(norad_id=90001, name="TEST SAT 1", mean_anomaly=10.0, raan=120.0, inclination=86.4):
    """Made-up elements for an Iridium-like orbit near 780 km. Test data only."""
    return {
        "OBJECT_NAME": name,
        "OBJECT_ID": "2099-900A",
        "EPOCH": "2026-10-09T03:00:00.000000",
        "MEAN_MOTION": 14.34,
        "ECCENTRICITY": 0.0002,
        "INCLINATION": inclination,
        "RA_OF_ASC_NODE": raan,
        "ARG_OF_PERICENTER": 90.0,
        "MEAN_ANOMALY": mean_anomaly,
        "EPHEMERIS_TYPE": 0,
        "CLASSIFICATION_TYPE": "U",
        "NORAD_CAT_ID": norad_id,
        "ELEMENT_SET_NO": 999,
        "REV_AT_EPOCH": 100,
        "BSTAR": 1e-5,
        "MEAN_MOTION_DOT": 0.0,
        "MEAN_MOTION_DDOT": 0.0,
    }


@pytest.fixture
def primary():
    return object_from_omm(test_omm(), is_primary=True, object_type="PAYLOAD", operational=True)


@pytest.fixture
def epoch():
    return EPOCH


@pytest.fixture
def t_tca():
    return EPOCH + timedelta(hours=30)
