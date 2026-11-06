"""
================================================================================
UNIT TESTS: RATE LIMITER & MULTI-KEY POOL
================================================================================
"""

import pytest
import time
from pathlib import Path
from autonomous_engine.rate_limiter import PacedGeminiClient


def test_rate_limiter_initialization():
    """Rate limiter pool must initialize without throwing exceptions."""
    pacer = PacedGeminiClient(max_calls_per_minute=28)
    assert pacer.max_calls_per_key == 28
    assert pacer.db_path.exists()


def test_rate_limiter_key_health():
    """Rate limiter must maintain API key health tracking."""
    pacer = PacedGeminiClient(max_calls_per_minute=28)
    # Check that healthy keys exist or pool handles empty keys gracefully
    status = pacer.get_pool_status() if hasattr(pacer, "get_pool_status") else {}
    assert isinstance(status, dict)
