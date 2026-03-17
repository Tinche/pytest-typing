import textwrap

import pytest

from pytest_typing.plugin import InvalidAssertionError, parse_assertions


def test_error_assertion() -> None:
    """Simple inline error assertions are parsed properly."""
    src = 'x: int = "hello" # error: [invalid-assignment]'
    assertions = parse_assertions(src)
    assert len(assertions) == 1
    assert assertions[0].kind == "error"
    assert assertions[0].rule == "invalid-assignment"
    assert assertions[0].checker is None
    assert assertions[0].message is None


def test_checker_specific_error() -> None:
    """Checker-specific inline assertions are parsed properly."""
    src = 'x: int = "hello" # ty-error: [invalid-assignment]'
    assertions = parse_assertions(src)
    assert len(assertions) == 1
    assert assertions[0].checker == "ty"
    assert assertions[0].rule == "invalid-assignment"


def test_multi_checker_specific_error() -> None:
    """Inline checker-specific errors can be stacked."""
    src = 'x: int = "hello" # ty-error: [invalid-assignment]  # mypy-error: [test]'
    assertions = parse_assertions(src)
    assert len(assertions) == 2
    assert assertions[0].checker == "ty"
    assert assertions[0].rule == "invalid-assignment"
    assert assertions[0].message is None
    assert assertions[1].checker == "mypy"
    assert assertions[1].rule == "test"
    assert assertions[1].message is None


def test_error_with_message() -> None:
    """Inline error assertions with messages are parsed properly."""
    src = 'x: int = "hello" # error: [invalid-assignment] not assignable'
    assertions = parse_assertions(src)
    assert assertions[0].message == "not assignable"


def test_revealed() -> None:
    """Simple inline reveal assertions are parsed properly."""
    src = "reveal_type(x) # revealed: int"
    assertions = parse_assertions(src)
    assert assertions[0].kind == "revealed"
    assert assertions[0].message == "int"
    assert assertions[0].rule is None
    assert assertions[0].checker is None


def test_complex_revealed_type() -> None:
    """Complex inline reveal assertions are parsed properly."""
    src = "reveal_type(d) # revealed: dict[str, list[int]]"
    assertions = parse_assertions(src)
    assert assertions[0].message == "dict[str, list[int]]"


def test_no_assertions() -> None:
    """Lines with no assertions are handled properly."""
    assert parse_assertions("x: int = 1") == []


def test_preceding_line_assertions() -> None:
    """Stacked checker-specific errors are parsed properly."""
    src = textwrap.dedent("""\
        # ty-error: [invalid-assignment]
        # mypy-error: [assignment]
        x: int = "hello"
    """)
    assertions = parse_assertions(src)
    assert len(assertions) == 2
    assert assertions[0].checker == "ty"
    assert assertions[0].line_number == 3
    assert assertions[1].checker == "mypy"
    assert assertions[1].line_number == 3


def test_stacked_preceding_and_inline() -> None:
    """Combining stacked and inline assertions works."""
    src = textwrap.dedent("""\
        # mypy-error: [assignment]
        x: int = "hello" # ty-error: [invalid-assignment]
    """)
    assertions = parse_assertions(src)
    assert len(assertions) == 2
    # preceding mypy assertion targets line 2
    assert assertions[0].checker == "mypy"
    assert assertions[0].line_number == 2
    # inline ty assertion targets line 2
    assert assertions[1].checker == "ty"
    assert assertions[1].line_number == 2


def test_preceding_universal() -> None:
    """Stacked non-specific error assertions work."""
    src = textwrap.dedent("""\
        # error: [some-rule]
        x: int = "hello"
    """)
    assertions = parse_assertions(src)
    assert len(assertions) == 1
    assert assertions[0].checker is None
    assert assertions[0].line_number == 2


def test_invalid_warning_assertion_raises() -> None:
    """Unsupported inline assertions error out."""
    src = "old_api() # warning: [deprecated]"
    with pytest.raises(InvalidAssertionError) as exc_info:
        parse_assertions(src)
    assert exc_info.value.line_number == 1
    assert exc_info.value.kind == "warning"
    assert "warning:" in str(exc_info.value)


def test_invalid_info_assertion_raises() -> None:
    """Unsupported inline assertions error out."""
    src = "x = 1 # info: [some-info]"
    with pytest.raises(InvalidAssertionError) as exc_info:
        parse_assertions(src)
    assert exc_info.value.kind == "info"


def test_invalid_checker_specific_warning_raises() -> None:
    """Unsupported inline assertions error out."""
    src = "x = 1 # ty-warning: [some-rule]"
    with pytest.raises(InvalidAssertionError) as exc_info:
        parse_assertions(src)
    assert exc_info.value.checker == "ty"
    assert exc_info.value.kind == "warning"


def test_invalid_warn_typo_raises() -> None:
    """Unsupported inline assertions error out."""
    src = "x = 1 # warn: [typo]"
    with pytest.raises(InvalidAssertionError) as exc_info:
        parse_assertions(src)
    assert exc_info.value.kind == "warn"


def test_invalid_err_typo_raises() -> None:
    """Unsupported inline assertions error out."""
    src = "x = 1 # err: [typo]"
    with pytest.raises(InvalidAssertionError) as exc_info:
        parse_assertions(src)
    assert exc_info.value.kind == "err"


def test_invalid_arbitrary_assertion_raises() -> None:
    """Any # something: [rule] pattern that isn't error: should raise."""
    src = "x = 1 # banana: [fruit]"
    with pytest.raises(InvalidAssertionError) as exc_info:
        parse_assertions(src)
    assert exc_info.value.kind == "banana"
