"""Integration tests, which run the entire pytest machinery."""

import textwrap

import pytest


def test_collects_matching_files(pytester: pytest.Pytester) -> None:
    """Simple collection works."""
    pytester.makefile(".md", test_typing_basics="# Test\n\n```py\nx = 1\n```\n")
    result = pytester.runpytest("--collect-only")
    result.stdout.fnmatch_lines(["*Test*"])


def test_ignores_non_prefixed_markdown(pytester: pytest.Pytester) -> None:
    """Files not matching the prefix aren't collected."""
    pytester.makefile(".md", readme="# Readme\n\n```py\nx = 1\n```\n")
    result = pytester.runpytest("--collect-only")
    result.stdout.no_fnmatch_line("*Readme*")


def test_ignores_other_test_markdown(pytester: pytest.Pytester) -> None:
    """Files not matching the prefix aren't collected."""
    pytester.makefile(".md", test_mypy_stuff="# Mypy\n\n```py\nx = 1\n```\n")
    result = pytester.runpytest("--collect-only")
    result.stdout.no_fnmatch_line("*mypy*")


def test_marker_filtering(pytester: pytest.Pytester) -> None:
    """Files with the `test_typing` prefix are collected."""
    pytester.makefile(".md", test_typing_basics="# Test\n\n```py\nx = 1\n```\n")
    result = pytester.runpytest("--collect-only", "-m", "typing")
    result.stdout.fnmatch_lines(["*Test*"])


def test_nested_headings_collected(pytester: pytest.Pytester) -> None:
    """Nested headings work correctly."""
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
    """Python blocks can be ignored using `skip`."""
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
    """Code blocks can be filtered using `only`."""
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


def test_pyright_only_attribute_includes_block(pytester: pytest.Pytester) -> None:
    """Code blocks can target pyright specifically."""
    pytester.makefile(
        ".md",
        test_typing_only=textwrap.dedent("""\
            # Suite

            ## For pyright only

            ```py only=pyright
            y = 2
            ```
        """),
    )
    result = pytester.runpytest("--collect-only", "--typing-checkers=pyright")
    result.stdout.fnmatch_lines(["*suite-for_pyright_only*"])


def test_pyright_specific_assertion_matches(pytester: pytest.Pytester) -> None:
    """Pyright-specific error assertions should work end to end."""
    pytester.makefile(
        ".md",
        test_typing_pyright=textwrap.dedent("""\
            # Suite

            ```py
            x: str = 1  # pyright-error: [reportAssignmentType]
            ```
        """),
    )
    result = pytester.runpytest_inprocess("--typing-checkers=pyright")
    assert result.ret == 0


def test_unknown_checker_errors(pytester: pytest.Pytester) -> None:
    """We validate typing checkers."""
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
    """Unmatched errors with messages are properly displayed."""
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


def test_both_skip_and_only(pytester: pytest.Pytester) -> None:
    """Combining both `skip` and `only` results in an error."""
    pytester.makefile(
        ".md",
        test_typing_skip_only=textwrap.dedent("""\
            ```py only=ty skip=mypy
            a: int = 1
            ```
        """),
    )
    result = pytester.runpytest()
    assert result.ret == 2  # Interrupted
    result.stdout.fnmatch_lines("*`only` and `skip` cannot be used together*")


def test_multiple_blocks_concatenated(pytester: pytest.Pytester) -> None:
    """Multiple code blocks in the same section are concatenated."""
    pytester.makefile(
        ".md",
        test_typing_concat=textwrap.dedent("""\
            # Concatenation Test

            ```py
            a: int = 1
            ```

            Some prose between blocks.

            ```py
            b: int = a + 1
            ```
        """),
    )
    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)
    # Should only be one test, not two
    result.stdout.fnmatch_lines(["*concatenation_test*PASSED*"])


def test_multiple_blocks_with_checker_specific(pytester: pytest.Pytester) -> None:
    """Blocks with `only` are concatenated per-checker."""
    pytester.makefile(
        ".md",
        test_typing_per_checker=textwrap.dedent("""\
            # Per-Checker Test

            ```py
            a: int = 1
            ```

            ```py only=mypy
            # This block is mypy-only
            b: str = 1
            ```

            ```py
            c: int = a + 1
            ```
        """),
    )
    # Run with ty only - should work (skips mypy-only block)
    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_blocks_reference_earlier_definitions(pytester: pytest.Pytester) -> None:
    """Variables defined in earlier blocks are available in later blocks."""
    pytester.makefile(
        ".md",
        test_typing_refs=textwrap.dedent("""\
            # Cross-Block References

            ```py
            class MyClass:
                value: int = 42
            ```

            ```py
            obj = MyClass()
            reveal_type(obj.value)  # revealed: int
            ```
        """),
    )
    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)
