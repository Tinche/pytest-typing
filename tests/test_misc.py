"""Small tests for misc things."""

import pytest

from pytest_typing._base import checker_or_none


def test_checker_or_none():
    """Checker names can be structured."""
    assert checker_or_none(None) is None
    assert checker_or_none("ty") == "ty"
    assert checker_or_none("mypy") == "mypy"

    with pytest.raises(ValueError):
        checker_or_none("nonexistent")
