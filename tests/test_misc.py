"""Small tests for misc things."""

import pytest

from pytest_typing.plugin import _checker_or_none


def test_checker_or_none():
    assert _checker_or_none(None) is None
    assert _checker_or_none("ty") == "ty"
    assert _checker_or_none("mypy") == "mypy"

    with pytest.raises(ValueError):
        _checker_or_none("nonexistent")
