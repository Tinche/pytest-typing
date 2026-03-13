"""Tests for ty."""

import subprocess
import textwrap
from typing import Final

import pytest

from pytest_typing._base import Diagnostic
from pytest_typing._ty import _parse_ty_output
from pytest_typing.plugin import CHECKERS

ty: Final = CHECKERS["ty"]


def test_single_error() -> None:
    output = "/out/test_snippet.py:1:10: error[invalid-assignment] Object of type `Literal[1]` is not assignable to `str`\nFound 1 diagnostic"
    diags = _parse_ty_output(output)
    assert diags == [
        Diagnostic(
            "/out/test_snippet.py",
            line=1,
            col=10,
            severity="error",
            rule="invalid-assignment",
            message="Object of type `Literal[1]` is not assignable to `str`",
        )
    ]


def test_warning() -> None:
    output = "lib/utils.py:3:1: warning[deprecated] Function `old_api` is deprecated"
    diags = _parse_ty_output(output)
    assert len(diags) == 1
    assert diags[0].severity == "warning"


def test_multiple_diagnostics() -> None:
    output = textwrap.dedent("""\
            a.py:1:1: error[unresolved-import] Cannot resolve imported module `nonexistent`
            a.py:5:10: warning[possibly-unresolved-reference] Name `x` is possibly unresolved
            b.py:20:3: error[invalid-argument-type] Argument is incompatible
        """)
    diags = _parse_ty_output(output)
    assert len(diags) == 3


def test_empty_output() -> None:
    assert _parse_ty_output("") == []


def test_non_diagnostic_lines_ignored() -> None:
    output = textwrap.dedent("""\
            WARN ty is pre-release software and not ready for production use.
            a.py:1:1: error[unresolved-import] bad import
            Found 1 diagnostic
        """)
    diags = _parse_ty_output(output)
    assert len(diags) == 1


def test_internal_error(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Internal errors running ty should be recognized."""
    pytester.maketoml("""
    [pytest]
    typing_checkers = ["ty"]
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
    assert ty.extract_revealed_type("Revealed type: `int`") == "int"


def test_literal_type() -> None:
    assert ty.extract_revealed_type("Revealed type: `Literal[1]`") == "Literal[1]"


def test_string_literal() -> None:
    assert ty.extract_revealed_type('Revealed type: `Literal["a"]`') == 'Literal["a"]'
