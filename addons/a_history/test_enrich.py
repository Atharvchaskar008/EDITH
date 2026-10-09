import pytest
import pandas as pd
from pathlib import Path
from enrich import enrich_catalog, download_satcat_if_needed

def test_enrich_preserves_count_and_fields(tmp_path):
    csv_path = download_satcat_if_needed()
    
    sample_objs = [
        # Iridium NEXT (41917)
        {"norad_id": 41917, "name": "IRIDIUM 106", "object_type": "PAYLOAD", "custom_field": "test123"},
        # Non-existent NORAD ID
        {"norad_id": 9999999, "name": "UNKNOWN DEB", "object_type": "DEBRIS", "extra": 456}
    ]

    res = enrich_catalog(sample_objs, csv_path)

    assert len(res) == 2
    # Verify extra fields are preserved
    assert res[0]["custom_field"] == "test123"
    assert res[1]["extra"] == 456

    # Iridium 106 (41917) should be PAYLOAD and operational
    iridium = res[0]
    assert iridium["norad_id"] == 41917
    assert iridium["object_type"] == "PAYLOAD"
    assert iridium["operational"] is True
    assert iridium["radius_m"] > 0.0

    # Non-existent ID should keep defaulted radius_m for DEBRIS
    missing = res[1]
    assert missing["norad_id"] == 9999999
    assert missing["radius_m"] == 0.5
