"""Tests for Pyrefly."""

import subprocess

import pytest

from pytest_typing._pyrefly import PyreflyChecker


def test_empty_output() -> None:
    assert PyreflyChecker.parse_output("") == []


def test_internal_error(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Internal errors running pyrefly should be recognized."""
    pytester.maketoml("""
    [pytest]
    typing_checkers = ["pyrefly"]
    """)
    pytester.makefile(".md", test_typing_basics="# Test\n\n```py\nx = 1\n```\n")

    orig_run = subprocess.run

    def monkeypatched_run(*args, **kwargs):
        res = orig_run(*args, **kwargs)
        res.returncode = 2
        return res

    monkeypatch.setattr(subprocess, "run", monkeypatched_run)
    res = pytester.runpytest_inprocess()

    assert res.ret == 1


def test_missing_module_is_internal_error(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing pyrefly installation should not be mistaken for type errors."""
    pytester.maketoml("""
    [pytest]
    typing_checkers = ["pyrefly"]
    """)
    pytester.makefile(".md", test_typing_basics="# Test\n\n```py\nx = 1\n```\n")

    def monkeypatched_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=1,
            stdout="",
            stderr="/usr/bin/python: No module named pyrefly",
        )

    monkeypatch.setattr(subprocess, "run", monkeypatched_run)
    res = pytester.runpytest_inprocess()

    assert res.ret == 1


def test_extract_revealed_type() -> None:
    assert (
        PyreflyChecker.extract_revealed_type("revealed type: Literal[1]")
        == "Literal[1]"
    )


def test_extract_revealed_type_normalizes_quotes() -> None:
    assert (
        PyreflyChecker.extract_revealed_type("revealed type: Literal['a']")
        == 'Literal["a"]'
    )
