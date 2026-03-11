"""Tests for the pytest-typing plugin."""

import textwrap

import pytest

from pytest_typing.plugin import (
    CHECKERS,
    Diagnostic,
    InvalidAssertionError,
    TypeAssertion,
    match_diagnostics,
    parse_assertions,
    parse_markdown,
)

# ═══════════════════════════════════════════════════════════════════════
# Inline assertion parser
# ═══════════════════════════════════════════════════════════════════════


class TestParseInlineAssertions:
    def test_error_assertion(self) -> None:
        src = 'x: int = "hello" # error: [invalid-assignment]'
        assertions = parse_assertions(src)
        assert len(assertions) == 1
        assert assertions[0].kind == "error"
        assert assertions[0].rule == "invalid-assignment"
        assert assertions[0].checker is None
        assert assertions[0].message is None

    def test_checker_specific_error(self) -> None:
        src = 'x: int = "hello" # ty-error: [invalid-assignment]'
        assertions = parse_assertions(src)
        assert len(assertions) == 1
        assert assertions[0].checker == "ty"
        assert assertions[0].rule == "invalid-assignment"

    def test_error_with_message(self) -> None:
        src = 'x: int = "hello" # error: [invalid-assignment] "not assignable"'
        assertions = parse_assertions(src)
        assert assertions[0].message == "not assignable"

    def test_revealed(self) -> None:
        src = "reveal_type(x) # revealed: int"
        assertions = parse_assertions(src)
        assert assertions[0].kind == "revealed"
        assert assertions[0].message == "int"
        assert assertions[0].rule is None
        assert assertions[0].checker is None

    def test_complex_revealed_type(self) -> None:
        src = "reveal_type(d) # revealed: dict[str, list[int]]"
        assertions = parse_assertions(src)
        assert assertions[0].message == "dict[str, list[int]]"

    def test_no_assertions(self) -> None:
        assert parse_assertions("x: int = 1") == []

    def test_preceding_line_assertions(self) -> None:
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

    def test_stacked_preceding_and_inline(self) -> None:
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

    def test_preceding_universal(self) -> None:
        src = textwrap.dedent("""\
            # error: [some-rule]
            x: int = "hello"
        """)
        assertions = parse_assertions(src)
        assert len(assertions) == 1
        assert assertions[0].checker is None
        assert assertions[0].line_number == 2

    def test_invalid_warning_assertion_raises(self) -> None:
        src = "old_api() # warning: [deprecated]"
        with pytest.raises(InvalidAssertionError) as exc_info:
            parse_assertions(src)
        assert exc_info.value.line_number == 1
        assert exc_info.value.kind == "warning"
        assert "warning:" in str(exc_info.value)

    def test_invalid_info_assertion_raises(self) -> None:
        src = "x = 1 # info: [some-info]"
        with pytest.raises(InvalidAssertionError) as exc_info:
            parse_assertions(src)
        assert exc_info.value.kind == "info"

    def test_invalid_checker_specific_warning_raises(self) -> None:
        src = "x = 1 # ty-warning: [some-rule]"
        with pytest.raises(InvalidAssertionError) as exc_info:
            parse_assertions(src)
        assert exc_info.value.checker == "ty"
        assert exc_info.value.kind == "warning"

    def test_invalid_warn_typo_raises(self) -> None:
        src = "x = 1 # warn: [typo]"
        with pytest.raises(InvalidAssertionError) as exc_info:
            parse_assertions(src)
        assert exc_info.value.kind == "warn"

    def test_invalid_err_typo_raises(self) -> None:
        src = "x = 1 # err: [typo]"
        with pytest.raises(InvalidAssertionError) as exc_info:
            parse_assertions(src)
        assert exc_info.value.kind == "err"

    def test_invalid_arbitrary_assertion_raises(self) -> None:
        """Any # something: [rule] pattern that isn't error: should raise."""
        src = "x = 1 # banana: [fruit]"
        with pytest.raises(InvalidAssertionError) as exc_info:
            parse_assertions(src)
        assert exc_info.value.kind == "banana"


# ═══════════════════════════════════════════════════════════════════════
# Markdown parser
# ═══════════════════════════════════════════════════════════════════════


class TestParseMarkdown:
    def test_single_block(self) -> None:
        md = textwrap.dedent("""\
            # My Test

            ```py
            x: int = 1
            ```
        """)
        blocks = parse_markdown(md)
        assert len(blocks) == 1
        assert blocks[0].source == "x: int = 1"
        assert blocks[0].section == "My Test"
        assert blocks[0].only_checkers is None
        assert blocks[0].skip_checkers == set()
        md = textwrap.dedent("""\
            # Suite

            ## Integers

            ```py
            x: int = 1
            ```

            ## Strings

            ```py
            y: str = "hi"
            ```
        """)
        blocks = parse_markdown(md)
        assert len(blocks) == 2
        assert blocks[0].section == "Suite - Integers"
        assert blocks[1].section == "Suite - Strings"

    def test_non_python_blocks_ignored(self) -> None:
        md = textwrap.dedent("""\
            ```toml
            [tool.ty]
            ```

            ```py
            x = 1
            ```
        """)
        blocks = parse_markdown(md)
        assert len(blocks) == 1

    def test_empty_markdown(self) -> None:
        assert parse_markdown("") == []

    def test_only_attribute(self) -> None:
        md = textwrap.dedent("""\
            ```py only=ty,pyright
            x = 1
            ```
        """)
        blocks = parse_markdown(md)
        assert len(blocks) == 1
        assert blocks[0].only_checkers == {"ty", "pyright"}

    def test_skip_attribute(self) -> None:
        md = textwrap.dedent("""\
            ```py skip=mypy
            x = 1
            ```
        """)
        blocks = parse_markdown(md)
        assert len(blocks) == 1
        assert blocks[0].skip_checkers == {"mypy"}

    def test_combined_attributes(self) -> None:
        md = textwrap.dedent("""\
            ```py only=ty skip=mypy
            x = 1
            ```
        """)
        blocks = parse_markdown(md)
        assert blocks[0].only_checkers == {"ty"}
        assert blocks[0].skip_checkers == {"mypy"}

    def test_attributes_are_per_block(self) -> None:
        md = textwrap.dedent("""\
            ```py only=ty
            x = 1
            ```

            ```py
            y = 2
            ```
        """)
        blocks = parse_markdown(md)
        assert len(blocks) == 2
        assert blocks[0].only_checkers == {"ty"}
        assert blocks[1].only_checkers is None


# ═══════════════════════════════════════════════════════════════════════
# Assertion matcher
# ═══════════════════════════════════════════════════════════════════════


class TestMatchDiagnostics:
    def test_perfect_match(self) -> None:
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

    def test_unmatched_assertion(self) -> None:
        assertions = [
            TypeAssertion(
                line_number=5,
                kind="error",
                checker=None,
                rule="bad-thing",
                message=None,
            )
        ]
        result = match_diagnostics(assertions, [], CHECKERS["ty"])
        assert not result.ok
        assert len(result.unmatched_assertions) == 1

    def test_unexpected_diagnostic(self) -> None:
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

    def test_revealed_type_match(self) -> None:
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

    def test_revealed_type_mismatch(self) -> None:
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

    def test_undefined_reveal_suppressed(self) -> None:
        assertions = [
            TypeAssertion(
                line_number=1, kind="revealed", checker=None, rule=None, message="int"
            )
        ]
        diagnostics = [
            Diagnostic(
                file="t.py",
                line=1,
                col=1,
                severity="error",
                rule="revealed-type",
                message="Revealed type is `int`",
            ),
            Diagnostic(
                file="t.py",
                line=1,
                col=1,
                severity="warning",
                rule="undefined-reveal",
                message="reveal_type used without importing",
            ),
        ]
        result = match_diagnostics(assertions, diagnostics, CHECKERS["ty"])
        assert result.ok

    def test_message_substring_match(self) -> None:
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

    def test_clean_code(self) -> None:
        result = match_diagnostics([], [], CHECKERS["ty"])
        assert result.ok

    def test_checker_specific_matched(self) -> None:
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

    def test_other_checker_assertions_skipped(self) -> None:
        """A mypy-specific assertion should be skipped when running ty."""
        assertions = [
            TypeAssertion(
                line_number=1,
                kind="error",
                checker="mypy",  # type: ignore
                rule="assignment",
                message=None,
            )
        ]
        diagnostics: list[Diagnostic] = []
        result = match_diagnostics(assertions, diagnostics, CHECKERS["ty"])
        assert result.ok  # mypy assertion ignored, no unexpected diagnostics

    def test_mixed_checker_assertions(self) -> None:
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
                line_number=1,
                kind="error",
                checker="mypy",  # type: ignore
                rule="assignment",
                message=None,
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

    def test_has_unexpected_errors_true(self) -> None:
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

    def test_has_unexpected_errors_false_for_warnings(self) -> None:
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

    def test_has_unexpected_errors_false_when_ok(self) -> None:
        """has_unexpected_errors should be False when result is ok."""
        result = match_diagnostics([], [], CHECKERS["ty"])
        assert not result.has_unexpected_errors


# ═══════════════════════════════════════════════════════════════════════
# Integration tests via pytester
# ═══════════════════════════════════════════════════════════════════════


class TestIntegration:
    def test_collects_matching_files(self, pytester: pytest.Pytester) -> None:
        pytester.makefile(".md", test_typing_basics="# Test\n\n```py\nx = 1\n```\n")
        result = pytester.runpytest("--collect-only")
        result.stdout.fnmatch_lines(["*Test*"])

    def test_ignores_non_prefixed_markdown(self, pytester: pytest.Pytester) -> None:
        pytester.makefile(".md", readme="# Readme\n\n```py\nx = 1\n```\n")
        result = pytester.runpytest("--collect-only")
        result.stdout.no_fnmatch_line("*Readme*")

    def test_ignores_other_test_markdown(self, pytester: pytest.Pytester) -> None:
        pytester.makefile(".md", test_mypy_stuff="# Mypy\n\n```py\nx = 1\n```\n")
        result = pytester.runpytest("--collect-only")
        result.stdout.no_fnmatch_line("*Mypy*")

    def test_marker_filtering(self, pytester: pytest.Pytester) -> None:
        pytester.makefile(".md", test_typing_basics="# Test\n\n```py\nx = 1\n```\n")
        result = pytester.runpytest("--collect-only", "-m", "typing")
        result.stdout.fnmatch_lines(["*Test*"])

    def test_nested_headings_collected(self, pytester: pytest.Pytester) -> None:
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

    def test_no_python_blocks_means_no_items(self, pytester: pytest.Pytester) -> None:
        """A Markdown file with no Python blocks yields no tests."""
        pytester.makefile(".md", test_typing_empty="# Just prose\n\nNo code here.\n")
        result = pytester.runpytest("--collect-only")
        result.assert_outcomes()

    def test_skip_attribute_excludes_block(self, pytester: pytest.Pytester) -> None:
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

    def test_only_attribute_includes_block(self, pytester: pytest.Pytester) -> None:
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

    def test_unknown_checker_errors(self, pytester: pytest.Pytester) -> None:
        pytester.makefile(".md", test_typing_x="# Test\n\n```py\nx = 1\n```\n")
        result = pytester.runpytest("--typing-checkers=nope")
        result.stdout.fnmatch_lines(["*Unknown typing checker*"])

    def test_unexpected_errors_shown_before_reveals(
        self, pytester: pytest.Pytester
    ) -> None:
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

    def test_reveals_shown_when_no_unexpected_errors(
        self, pytester: pytest.Pytester
    ) -> None:
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

    def test_diagnostics_used_only_once(self, pytester: pytest.Pytester) -> None:
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
