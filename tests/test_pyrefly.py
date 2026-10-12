"""Tests for Pyrefly."""

import subprocess

import pytest

from pytest_typing._pyrefly import PyreflyChecker


def test_default_preset(pytester: pytest.Pytester) -> None:
    """The default preset checks assignments and reveals without configuration."""
    pytester.makefile(
        ".md",
        test_typing_preset="""# Test

```py
from typing_extensions import reveal_type

x: str = 1  # pyrefly-error: [bad-assignment]
reveal_type(1)  # revealed: Literal[1]
```
""",
    )

    result = pytester.runpytest_inprocess("--typing-checkers=pyrefly")

    result.assert_outcomes(passed=1)


def test_empty_preset(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty preset leaves selection to Pyrefly, supporting older versions."""
    pytester.maketoml("""
    [pytest]
    typing_checkers = ["pyrefly"]
    typing_pyrefly_preset = ""
    """)
    pytester.makefile(".md", test_typing_preset="# Test\n\n```py\nx = 1\n```\n")
    commands = []

    def run(cmd, **kwargs):
        commands.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout='{"errors": []}')

    monkeypatch.setattr(subprocess, "run", run)

    result = pytester.runpytest_inprocess()

    result.assert_outcomes(passed=1)
    assert len(commands) == 1
    assert "--preset" not in commands[0]


@pytest.mark.parametrize("preset", ["default", "basic"])
def test_configured_preset(pytester: pytest.Pytester, preset: str) -> None:
    """The configured preset controls assignment diagnostics in snippets."""
    pytester.maketoml(f'''
    [pytest]
    typing_checkers = ["pyrefly"]
    typing_pyrefly_preset = "{preset}"
    ''')
    pytester.makefile(
        ".md",
        test_typing_preset="# Test\n\n```py\nx: str = 1  # pyrefly-error: [bad-assignment]\n```\n",
    )

    result = pytester.runpytest_inprocess()

    result.assert_outcomes(
        passed=int(preset == "default"), failed=int(preset == "basic")
    )


@pytest.mark.parametrize("preset", ["default", "basic"])
def test_cli_preset_overrides_config(pytester: pytest.Pytester, preset: str) -> None:
    """The CLI preset takes precedence over the configured preset."""
    configured = "basic" if preset == "default" else "default"
    pytester.maketoml(f'''
    [pytest]
    typing_checkers = ["pyrefly"]
    typing_pyrefly_preset = "{configured}"
    ''')
    pytester.makefile(
        ".md",
        test_typing_preset="# Test\n\n```py\nx: str = 1  # pyrefly-error: [bad-assignment]\n```\n",
    )

    result = pytester.runpytest_inprocess(f"--typing-pyrefly-preset={preset}")

    result.assert_outcomes(
        passed=int(preset == "default"), failed=int(preset == "basic")
    )


def test_invalid_preset(pytester: pytest.Pytester) -> None:
    """An unsupported preset is reported as a checker error."""
    pytester.makefile(".md", test_typing_preset="# Test\n\n```py\nx = 1\n```\n")

    result = pytester.runpytest_inprocess(
        "--typing-checkers=pyrefly", "--typing-pyrefly-preset=nonexistent"
    )

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*invalid value 'nonexistent'*--preset*"])


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
