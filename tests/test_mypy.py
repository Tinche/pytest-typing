"""Tests for Mypy."""

import subprocess
import textwrap
from typing import Final

import pytest

from pytest_typing._base import Diagnostic
from pytest_typing._mypy import _parse_mypy_output
from pytest_typing.plugin import CHECKERS

mypy: Final = CHECKERS["mypy"]


def test_single_error() -> None:
    output = 'test.py:1: error: Incompatible types in assignment (expression has type "str", variable has type "int")  [assignment]'
    diags = _parse_mypy_output(output)
    assert diags == [
        Diagnostic(
            "test.py",
            line=1,
            col=1,
            severity="error",
            rule="assignment",
            message='Incompatible types in assignment (expression has type "str", variable has type "int")',
        )
    ]


def test_revealed_type() -> None:
    output = 'test.py:2: note: Revealed type is "builtins.int"'
    diags = _parse_mypy_output(output)
    assert len(diags) == 1
    assert diags[0].severity == "info"
    assert diags[0].rule == "revealed-type"
    assert diags[0].message == 'Revealed type is "builtins.int"'


def test_multiple_diagnostics() -> None:
    output = textwrap.dedent("""\
        a.py:1: error: Cannot find implementation or library stub for module named "nonexistent"  [import]
        a.py:5: error: Incompatible types  [assignment]
        b.py:2: note: Revealed type is "builtins.str"
    """)
    diags = _parse_mypy_output(output)
    assert len(diags) == 3
    assert diags[0].rule == "import"
    assert diags[1].rule == "assignment"
    assert diags[2].rule == "revealed-type"


def test_empty_output() -> None:
    assert _parse_mypy_output("") == []


def test_non_diagnostic_lines_ignored() -> None:
    output = textwrap.dedent("""\
        test.py:1: error: Name "x" is not defined  [name-defined]
        Found 1 error in 1 file (checked 1 source file)
    """)
    diags = _parse_mypy_output(output)
    assert len(diags) == 1


def test_internal_error(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Internal errors running ty should be recognized."""
    pytester.maketoml("""
    [pytest]
    typing_checkers = ["mypy"]
    """)
    pytester.makefile(".md", test_typing_basics="# Test\n\n```py\nx = 1\n```\n")

    # We monkeypatch `subprocess.run` to pretend ty exits with `2`
    orig_run = subprocess.run

    def monkeypatched_run(*args, **kwargs):
        res = orig_run(*args, **kwargs)
        res.returncode = 2
        return res

    monkeypatch.setattr(subprocess, "run", monkeypatched_run)
    res = pytester.runpytest_inprocess()

    # Pytest failure
    assert res.ret == 1


def test_simple_type() -> None:
    mypy = CHECKERS["mypy"]
    assert mypy.extract_revealed_type('Revealed type is "builtins.int"') == "int"


def test_strips_builtins_prefix() -> None:
    mypy = CHECKERS["mypy"]
    assert mypy.extract_revealed_type('Revealed type is "builtins.str"') == "str"


def test_preserves_non_builtins() -> None:
    mypy = CHECKERS["mypy"]
    assert (
        mypy.extract_revealed_type('Revealed type is "typing.List[int]"')
        == "typing.List[int]"
    )


def test_normalizes_quotes() -> None:
    mypy = CHECKERS["mypy"]
    # mypy uses single quotes inside Literal, we normalize to double
    assert (
        mypy.extract_revealed_type("Revealed type is \"Literal['a']\"")
        == 'Literal["a"]'
    )


def test_strips_optional_marker() -> None:
    mypy = CHECKERS["mypy"]
    # mypy adds ? for Optional types
    assert (
        mypy.extract_revealed_type("Revealed type is \"Literal['a']?\"")
        == 'Literal["a"]'
    )


def test_combined_normalizations() -> None:
    mypy = CHECKERS["mypy"]
    # builtins prefix + optional marker
    assert mypy.extract_revealed_type('Revealed type is "builtins.int?"') == "int"
