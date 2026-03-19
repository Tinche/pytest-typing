"""Tests matching diagnostics and assertions."""

from pytest_typing.plugin import CHECKERS, Diagnostic, TypeAssertion, match_diagnostics


def test_perfect_match() -> None:
    """Type assertions match to diagnostics properly."""
    assertions = [
        TypeAssertion(
            line_number=1,
            kind="error",
            checker=None,
            rule="invalid-assignment",
            message=None,
        )
    ]
    diagnostics = [
        Diagnostic(
            file="t.py",
            line=1,
            col=1,
            severity="error",
            rule="invalid-assignment",
            message="something",
        )
    ]
    result = match_diagnostics(assertions, diagnostics, CHECKERS["ty"])
    assert result.ok


def test_unmatched_assertion() -> None:
    """Unmatched assertions work properly."""
    assertions = [
        TypeAssertion(
            line_number=5, kind="error", checker=None, rule="bad-thing", message=None
        )
    ]
    result = match_diagnostics(assertions, [], CHECKERS["ty"])
    assert not result.ok
    assert len(result.unmatched_assertions) == 1


def test_unexpected_diagnostic() -> None:
    """Unmatched diagnostics get processed correctly."""
    diagnostics = [
        Diagnostic(
            file="t.py",
            line=3,
            col=1,
            severity="error",
            rule="surprise",
            message="oh no",
        )
    ]
    result = match_diagnostics([], diagnostics, CHECKERS["ty"])
    assert not result.ok
    assert len(result.unexpected_diagnostics) == 1


def test_revealed_type_match() -> None:
    """Reveal diagnostics and assertions match."""
    assertions = [
        TypeAssertion(
            line_number=2, kind="revealed", checker=None, rule=None, message="int"
        )
    ]
    diagnostics = [
        Diagnostic(
            file="t.py",
            line=2,
            col=1,
            severity="error",
            rule="revealed-type",
            message="Revealed type is `int`",
        )
    ]
    result = match_diagnostics(assertions, diagnostics, CHECKERS["ty"])
    assert result.ok


def test_revealed_type_mismatch() -> None:
    """Error when reveal assertions and diagnostics disagree on type."""
    assertions = [
        TypeAssertion(
            line_number=2, kind="revealed", checker=None, rule=None, message="str"
        )
    ]
    diagnostics = [
        Diagnostic(
            file="t.py",
            line=2,
            col=1,
            severity="error",
            rule="revealed-type",
            message="Revealed type is `int`",
        )
    ]
    result = match_diagnostics(assertions, diagnostics, CHECKERS["ty"])
    assert not result.ok


def test_message_substring_match() -> None:
    """Error messages are matched by substring."""
    assertions = [
        TypeAssertion(
            line_number=1,
            kind="error",
            checker=None,
            rule="invalid-assignment",
            message="not assignable",
        )
    ]
    diagnostics = [
        Diagnostic(
            file="t.py",
            line=1,
            col=1,
            severity="error",
            rule="invalid-assignment",
            message="Type `str` is not assignable to `int`",
        )
    ]
    result = match_diagnostics(assertions, diagnostics, CHECKERS["ty"])
    assert result.ok


def test_clean_code() -> None:
    """No assertions and no diagnostics works properly."""
    result = match_diagnostics([], [], CHECKERS["ty"])
    assert result.ok


def test_checker_specific_matched() -> None:
    """A ty-specific assertion should match when running ty."""
    assertions = [
        TypeAssertion(
            line_number=1,
            kind="error",
            checker="ty",
            rule="invalid-assignment",
            message=None,
        )
    ]
    diagnostics = [
        Diagnostic(
            file="t.py",
            line=1,
            col=1,
            severity="error",
            rule="invalid-assignment",
            message="bad",
        )
    ]
    result = match_diagnostics(assertions, diagnostics, CHECKERS["ty"])
    assert result.ok


def test_other_checker_assertions_skipped() -> None:
    """A mypy-specific assertion should be skipped when running ty."""
    assertions = [
        TypeAssertion(
            line_number=1, kind="error", checker="mypy", rule="assignment", message=None
        )
    ]
    diagnostics: list[Diagnostic] = []
    result = match_diagnostics(assertions, diagnostics, CHECKERS["ty"])
    assert result.ok  # mypy assertion ignored, no unexpected diagnostics


def test_pyright_specific_assertions_skipped() -> None:
    """A pyright-specific assertion should be skipped when running ty."""
    assertions = [
        TypeAssertion(
            line_number=1,
            kind="error",
            checker="pyright",
            rule="reportAssignmentType",
            message=None,
        )
    ]
    diagnostics: list[Diagnostic] = []
    result = match_diagnostics(assertions, diagnostics, CHECKERS["ty"])
    assert result.ok


def test_mixed_checker_assertions() -> None:
    """Only the active checker's assertions should be enforced."""
    assertions = [
        TypeAssertion(
            line_number=1,
            kind="error",
            checker="ty",
            rule="invalid-assignment",
            message=None,
        ),
        TypeAssertion(
            line_number=1, kind="error", checker="mypy", rule="assignment", message=None
        ),
    ]
    diagnostics = [
        Diagnostic(
            file="t.py",
            line=1,
            col=1,
            severity="error",
            rule="invalid-assignment",
            message="bad",
        )
    ]
    result = match_diagnostics(assertions, diagnostics, CHECKERS["ty"])
    assert result.ok


def test_has_unexpected_errors_true() -> None:
    """has_unexpected_errors should be True when there are unexpected error diagnostics."""
    diagnostics = [
        Diagnostic(
            file="t.py",
            line=1,
            col=1,
            severity="error",
            rule="some-error",
            message="unexpected error",
        )
    ]
    result = match_diagnostics([], diagnostics, CHECKERS["ty"])
    assert result.has_unexpected_errors


def test_has_unexpected_errors_false_for_warnings() -> None:
    """has_unexpected_errors should be False when only warnings are unexpected."""
    diagnostics = [
        Diagnostic(
            file="t.py",
            line=1,
            col=1,
            severity="warning",
            rule="some-warning",
            message="unexpected warning",
        )
    ]
    result = match_diagnostics([], diagnostics, CHECKERS["ty"])
    assert not result.has_unexpected_errors


def test_has_unexpected_errors_false_when_ok() -> None:
    """has_unexpected_errors should be False when result is ok."""
    result = match_diagnostics([], [], CHECKERS["ty"])
    assert not result.has_unexpected_errors
