"""Integration tests, which run the entire pytest machinery."""

import textwrap

import pytest


def test_collects_matching_files(pytester: pytest.Pytester) -> None:
    pytester.makefile(".md", test_typing_basics="# Test\n\n```py\nx = 1\n```\n")
    result = pytester.runpytest("--collect-only")
    result.stdout.fnmatch_lines(["*Test*"])


def test_ignores_non_prefixed_markdown(pytester: pytest.Pytester) -> None:
    pytester.makefile(".md", readme="# Readme\n\n```py\nx = 1\n```\n")
    result = pytester.runpytest("--collect-only")
    result.stdout.no_fnmatch_line("*Readme*")


def test_ignores_other_test_markdown(pytester: pytest.Pytester) -> None:
    pytester.makefile(".md", test_mypy_stuff="# Mypy\n\n```py\nx = 1\n```\n")
    result = pytester.runpytest("--collect-only")
    result.stdout.no_fnmatch_line("*Mypy*")


def test_marker_filtering(pytester: pytest.Pytester) -> None:
    pytester.makefile(".md", test_typing_basics="# Test\n\n```py\nx = 1\n```\n")
    result = pytester.runpytest("--collect-only", "-m", "typing")
    result.stdout.fnmatch_lines(["*Test*"])


def test_nested_headings_collected(pytester: pytest.Pytester) -> None:
    pytester.makefile(
        ".md",
        test_typing_suite=textwrap.dedent("""\
            # Suite

            ## Part A

            ```py
            x = 1
            ```

            ## Part B

            ```py
            y = 2
            ```
        """),
    )
    result = pytester.runpytest("--collect-only")
    result.stdout.fnmatch_lines(["*suite-part_a*", "*suite-part_b*"])


def test_wrong_error_asserted(pytester: pytest.Pytester) -> None:
    """Asserting the wrong error code leaves the diagnostic to be surfaced."""
    pytester.makefile(
        ".md",
        test_typing_assertions=textwrap.dedent("""\
            # Suite

            ```py
            # error: [nonexistent]
            x: str = 1
            ```
        """),
    )
    result = pytester.runpytest_inprocess()
    result.stdout.fnmatch_lines(
        [" line 2: error[[]invalid-assignment[]]*", " line 2: error: [[]nonexistent[]]"]
    )


def test_no_python_blocks_means_no_items(pytester: pytest.Pytester) -> None:
    """A Markdown file with no Python blocks yields no tests."""
    pytester.makefile(".md", test_typing_empty="# Just prose\n\nNo code here.\n")
    result = pytester.runpytest("--collect-only")
    result.assert_outcomes()


def test_skip_attribute_excludes_block(pytester: pytest.Pytester) -> None:
    pytester.makefile(
        ".md",
        test_typing_skip=textwrap.dedent("""\
            # Suite

            ## Included

            ```py
            x = 1
            ```

            ## Excluded

            ```py skip=ty
            y = 2
            ```
        """),
    )
    result = pytester.runpytest("--collect-only")
    result.stdout.fnmatch_lines(["*suite-included*"])
    result.stdout.no_fnmatch_line("*excluded*")


def test_only_attribute_includes_block(pytester: pytest.Pytester) -> None:
    pytester.makefile(
        ".md",
        test_typing_only=textwrap.dedent("""\
            # Suite

            ## For ty

            ```py only=ty
            x = 1
            ```

            ## For mypy only

            ```py only=mypy
            y = 2
            ```
        """),
    )
    result = pytester.runpytest("--collect-only")
    result.stdout.fnmatch_lines(["*suite-for_ty*"])
    result.stdout.no_fnmatch_line("*for_mypy_only*")


def test_unknown_checker_errors(pytester: pytest.Pytester) -> None:
    pytester.makefile(".md", test_typing_x="# Test\n\n```py\nx = 1\n```\n")
    result = pytester.runpytest("--typing-checkers=nope")
    result.stdout.fnmatch_lines(["*Unknown typing checker*"])


def test_unexpected_errors_shown_before_reveals(pytester: pytest.Pytester) -> None:
    """When there's an unexpected error, it should be shown first, and
    unmatched reveal assertions should be suppressed since the error
    likely caused the reveal to fail."""
    pytester.makefile(
        ".md",
        test_typing_error_priority=textwrap.dedent("""\
            # Error Priority

            ```py
            x: int = undefined_var
            reveal_type(x)  # revealed: int
            ```
        """),
    )
    result = pytester.runpytest("-v")
    # Should show "Unexpected errors" section
    result.stdout.fnmatch_lines(["*Unexpected errors*"])
    # Should NOT show "revealed: int" in unmatched assertions since there
    # are unexpected errors that likely caused the reveal to fail
    result.stdout.no_fnmatch_line("*revealed: int*")


def test_reveals_shown_when_no_unexpected_errors(pytester: pytest.Pytester) -> None:
    """When there are no unexpected errors, mismatched reveal assertions
    should be shown with expected vs actual format."""
    pytester.makefile(
        ".md",
        test_typing_reveal_mismatch=textwrap.dedent("""\
            # Reveal Mismatch

            ```py
            x = 1
            reveal_type(x)  # revealed: str
            ```
        """),
    )
    result = pytester.runpytest("-v")
    # Should show the mismatched reveal with expected vs actual
    result.stdout.fnmatch_lines(["*`str` (expected) vs*"])


def test_diagnostics_used_only_once(pytester: pytest.Pytester) -> None:
    """Diagnostic messages are matched to only one assertion."""
    pytester.makefile(
        ".md",
        test_typing_reveal_multiple=textwrap.dedent("""\
            # Multiple reveals

            ```py
            from typing_extensions import reveal_type

            x = 1
            # revealed: Literal[1]
            # revealed: Literal[1]
            reveal_type(x)
            reveal_type(x)
            reveal_type(x)
            ```
        """),
    )
    result = pytester.runpytest_inprocess()
    assert result.ret == 1
    result.stdout.fnmatch_lines(
        [
            " Unexpected diagnostics:",
            " line 7: info[revealed-type]: Revealed type: `Literal[1]`",
            " line 8: info[revealed-type]: Revealed type: `Literal[1]`",
        ]
    )


def test_err_message_used_only_once(pytester: pytest.Pytester) -> None:
    """Error messages are matched to only one assertion."""
    pytester.makefile(
        ".md",
        test_typing_multiple_errors=textwrap.dedent("""\
            # Multiple errors

            ```py
            # error: [invalid-assignment] Wrong message
            a: str = 1
            ```
        """),
    )
    result = pytester.runpytest_inprocess()
    assert result.ret == 1


def test_unmatched_error_assertion_with_message(pytester: pytest.Pytester) -> None:
    """Unmatched errors with messages are properly displayed"""
    pytester.makefile(
        ".md",
        test_typing_multiple_errors=textwrap.dedent("""\
            # Unmatched errors with messages

            ```py
            # error: [invalid-assignment] Wrong message
            a: int = 1
            ```
        """),
    )
    result = pytester.runpytest_inprocess()
    assert result.ret == 1
    result.stdout.fnmatch_lines("*Wrong message*")
