"""Tests for Pyright."""

import subprocess

import pytest

from pytest_typing._pyright import PyrightChecker


def test_empty_output() -> None:
    assert PyrightChecker.parse_output("") == []


def test_internal_error(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Internal errors running pyright should be recognized."""
    pytester.maketoml("""
    [pytest]
    typing_checkers = ["pyright"]
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
    """A missing pyright installation should not be mistaken for type errors."""
    pytester.maketoml("""
    [pytest]
    typing_checkers = ["pyright"]
    """)
    pytester.makefile(".md", test_typing_basics="# Test\n\n```py\nx = 1\n```\n")

    def monkeypatched_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=1,
            stdout="",
            stderr="/usr/bin/python: No module named pyright",
        )

    monkeypatch.setattr(subprocess, "run", monkeypatched_run)
    res = pytester.runpytest_inprocess()

    assert res.ret == 1


def test_extract_revealed_type() -> None:
    assert (
        PyrightChecker.extract_revealed_type('Type of "x" is "Literal[1]"')
        == "Literal[1]"
    )


def test_extract_revealed_type_normalizes_quotes() -> None:
    assert (
        PyrightChecker.extract_revealed_type('Type of "x" is "Literal[\'a\']"')
        == 'Literal["a"]'
    )
