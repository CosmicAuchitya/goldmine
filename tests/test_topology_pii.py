"""
================================================================================
UNIT TESTS: STAGE 1 TOPOLOGY, PRIVACY & CARDINALITY HAZARDS
================================================================================
"""

import pytest
import pandas as pd
from autonomous_engine.pii_scrubber import scrub_text, scrub_sample_values, scrub_schema_payload
from autonomous_engine.composite_key_detector import find_candidate_composite_keys
from autonomous_engine.cardinality_and_bridge_detector import detect_relationship_cardinality


def test_pii_scrubbing_local():
    """Confidential customer identifiers must be masked locally prior to LLM submission."""
    raw_email = "User alice@corporate.com signed up."
    scrubbed = scrub_text(raw_email)
    assert "[REDACTED_EMAIL]" in scrubbed
    assert "alice@corporate.com" not in scrubbed

    raw_phone = "Call direct at 123-456-7890 for verification."
    scrubbed_phone = scrub_text(raw_phone)
    assert "[REDACTED_PHONE]" in scrubbed_phone

    # Test sample values scrubbing
    masked_samples = scrub_sample_values("customer_email", ["bob@test.com", "alice@test.org"])
    assert all("[MASKED_CUSTOMER_EMAIL]" in s for s in masked_samples)


def test_composite_key_detection():
    """Composite key detector must identify combinations that uniquely identify records."""
    df = pd.DataFrame({
        "Store_ID": [1, 1, 2, 2, 3],
        "Dept_ID":  [10, 20, 10, 20, 10],
        "Sales":    [100, 200, 150, 250, 300]
    })
    composites = find_candidate_composite_keys(df)
    # Together (Store_ID, Dept_ID) uniquely identify all 5 rows
    assert any(set(cand) == {"Store_ID", "Dept_ID"} for cand in composites)


def test_cardinality_hazard_scan():
    """Cardinality scanner must flag 1:N relations to prevent Cartesian multiplication."""
    df_parent = pd.DataFrame({"cust_id": [1, 2, 3], "name": ["A", "B", "C"]})
    df_child = pd.DataFrame({"cust_id": [1, 1, 1, 2, 2, 3], "order_id": [101, 102, 103, 104, 105, 106]})
    card = detect_relationship_cardinality(df_parent, "cust_id", df_child, "cust_id")
    # Should identify 1:N relationship
    assert "1:N" in card["cardinality"]
    assert card["danger_level"] in ["LOW", "MEDIUM", "HIGH"]

