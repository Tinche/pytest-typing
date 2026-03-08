"""pytest plugin for Markdown-based type checker tests.

Collects ``test_typing_*.md`` files containing fenced Python code blocks with
inline assertion comments, runs a configured type checker on them, and
verifies that the actual diagnostics match the assertions.

Assertion comments (inspired by Astral's mdtest framework):

* ``# revealed: <type>`` — expects ``reveal_type()`` on that line to
  produce the given type.
* ``# error: [rule-name]`` — expects an error diagnostic with that rule.
* ``# error: [rule-name] "optional message substring"`` — also checks
  that the diagnostic message contains the given text.

Markdown headings define nested test names. Each fenced
``\\`\\`\\`py`` block is a separate test item.
"""

import abc
import re
import subprocess
import sys
import tempfile
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

import pytest
from _pytest.nodes import TerminalRepr, TracebackStyle

# ───────────────────────────────────────────────────────────────────────
# Diagnostic model
# ───────────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class Diagnostic:
    """A single diagnostic emitted by a type checker."""

    file: str
    line: int
    col: int
    severity: str  # "error" | "warning"
    rule: str  # e.g. "invalid-assignment"
    message: str


# ───────────────────────────────────────────────────────────────────────
# Type checker backend interface
# ───────────────────────────────────────────────────────────────────────

Checker = Literal["ty", "mypy"]


def _checker_or_none(value: str | None) -> Checker | None:
    """A poor man's `cattrs.structure`."""
    if value is None:
        return None
    if value in ("ty", "mypy"):
        return value  # type: ignore[return-value]
    raise ValueError(f"Invalid checker value ({value})")


class TypeChecker(abc.ABC):
    """Abstract interface for a type checker backend."""

    name: Checker

    @abc.abstractmethod
    def check(
        self, file_path: Path, project_dir: str, config: pytest.Config
    ) -> list[Diagnostic]:
        """Run the checker on *file_path* and return parsed diagnostics."""

    @abc.abstractmethod
    def extract_revealed_type(self, message: str) -> str:
        """Extract the type from a revealed-type diagnostic message."""


# ───────────────────────────────────────────────────────────────────────
# ty backend
# ───────────────────────────────────────────────────────────────────────

_CONCISE_RE: Final = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+): "
    r"(?P<severity>error|warning|info)\[(?P<rule>[^\]]+)\] "
    r"(?P<message>.+)$"
)


def _parse_ty_output(output: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        m = _CONCISE_RE.match(line)
        if m:
            diagnostics.append(
                Diagnostic(
                    file=m.group("file"),
                    line=int(m.group("line")),
                    col=int(m.group("col")),
                    severity=m.group("severity"),
                    rule=m.group("rule"),
                    message=m.group("message"),
                )
            )
    return diagnostics


def _opt(config: pytest.Config, cli_name: str, ini_name: str) -> Any:
    val = config.getoption(cli_name, default=None)
    if val is None or val is False:
        val = config.getini(ini_name)
    return val


class TyChecker(TypeChecker):
    name = "ty"

    def check(
        self, file_path: Path, project_dir: str, config: pytest.Config
    ) -> list[Diagnostic]:
        cmd = [
            sys.executable,
            "-m",
            "ty",
            "check",
            "--output-format",
            "concise",
            "--no-progress",
            "--project",
            project_dir,
        ]

        cmd.append(str(file_path))

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_dir)  # noqa: S603
        diagnostics = _parse_ty_output(result.stdout)
        if not diagnostics and result.returncode not in (0, 1):
            diagnostics = _parse_ty_output(result.stderr)
        return diagnostics

    def extract_revealed_type(self, message: str) -> str:
        """Extract the type from a ty revealed-type diagnostic message.

        Example: "Revealed type: `Literal[1]`" -> "Literal[1]"
        """
        match = re.search(r"`([^`]+)`", message)
        assert match is not None
        return match.group(1)


# ───────────────────────────────────────────────────────────────────────
# mypy backend
# ───────────────────────────────────────────────────────────────────────

# mypy error format: file:line: error: message [rule]
# mypy note format: file:line: note: message
_MYPY_DIAG_RE: Final = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+): (?P<severity>error|warning|note): "
    r"(?P<message>.+?)(?:\s+\[(?P<rule>[^\]]+)\])?$"
)


def _parse_mypy_output(output: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        m = _MYPY_DIAG_RE.match(line)
        if m:
            severity = m.group("severity")
            message = m.group("message")
            rule = m.group("rule") or ""

            # mypy uses "note" for reveal_type, map it to a rule we recognize
            if severity == "note" and message.startswith("Revealed type is "):
                rule = "revealed-type"
                severity = "info"

            diagnostics.append(
                Diagnostic(
                    file=m.group("file"),
                    line=int(m.group("line")),
                    col=1,  # mypy doesn't provide column in default output
                    severity=severity,
                    rule=rule,
                    message=message,
                )
            )
    return diagnostics


class MypyChecker(TypeChecker):
    name = "mypy"

    def check(
        self, file_path: Path, project_dir: str, config: pytest.Config
    ) -> list[Diagnostic]:
        cmd = [
            sys.executable,
            "-m",
            "mypy",
            "--no-color-output",
            "--show-error-codes",
            "--no-error-summary",
            str(file_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_dir)  # noqa: S603
        diagnostics = _parse_mypy_output(result.stdout)
        if not diagnostics and result.returncode not in (0, 1):
            diagnostics = _parse_mypy_output(result.stderr)
        return diagnostics

    def extract_revealed_type(self, message: str) -> str:
        """Extract the type from a mypy revealed-type diagnostic message.

        Example: 'Revealed type is "builtins.int"' -> "int"

        Normalizations applied:
        - Strip "builtins." prefix
        - Convert single quotes to double quotes (for Literal types)
        - Strip trailing "?" (mypy's optional marker)
        """
        match = re.search(r'"([^"]+)"', message)
        assert match is not None
        revealed = match.group(1)
        # mypy uses fully qualified names like "builtins.int", simplify common ones
        if revealed.startswith("builtins."):
            revealed = revealed[len("builtins.") :]
        # Normalize single quotes to double quotes for consistency with ty
        revealed = revealed.replace("'", '"')
        # Strip trailing "?" (mypy's way of indicating Optional)
        if revealed.endswith("?"):
            revealed = revealed[:-1]
        return revealed


# ── Registry ─────────────────────────────────────────────────────────

CHECKERS: dict[Checker, TypeChecker] = {
    "ty": TyChecker(),
    "mypy": MypyChecker(),
}


# ───────────────────────────────────────────────────────────────────────
# Inline-assertion parser
# ───────────────────────────────────────────────────────────────────────


class InvalidAssertionError(Exception):
    """Raised when an invalid assertion comment is found."""

    def __init__(
        self, line_number: int, kind: str, checker: Checker | None = None
    ) -> None:
        prefix = f"{checker}-" if checker else ""
        super().__init__(
            f"Line {line_number}: unsupported assertion type '{prefix}{kind}:'. "
            f"Only 'error:' and 'revealed:' are supported."
        )
        self.line_number = line_number
        self.kind = kind
        self.checker = checker


@dataclass(slots=True)
class TypeAssertion:
    """An assertion embedded as a comment in a Python code block.

    Assertions can be:

    * **Inline** (same line as code): ``x = 1 # revealed: int``
    * **Preceding-line** (comment-only line above the target):

      .. code-block:: python

          # ty-error: [invalid-assignment]
          # mypy-error: [assignment]
          x: int = "hello"

    The ``checker`` field is ``None`` for universal assertions
    (``# error:``, ``# revealed:``) and a checker name for
    checker-specific ones (``# ty-error:``).
    """

    line_number: int  # the *code* line the assertion applies to
    kind: str  # "error" | "revealed"
    checker: Checker | None  # None = universal, "ty" / "mypy" / … = specific
    rule: str | None
    message: str | None
    matched: bool = False


# ``# error: [rule]``, ``# ty-error: [rule]``, ``# error: [rule] "msg"``
_DIAG_ASSERTION_RE = re.compile(
    r"#\s*(?:(?P<checker>\w+)-)?(?P<severity>error):\s*"
    r"\[(?P<rule>[^\]]+)\]"
    r'(?:\s*"(?P<message>[^"]*)")?'
)

# ``# revealed: <type>``
_REVEALED_RE: Final = re.compile(r"#\s*revealed:\s*(?P<type>.+)")

# Matches any assertion-like pattern: ``# something: [`` or ``# checker-something: [``
# Used to detect invalid assertions (anything that's not error: or revealed:)
_ASSERTION_LIKE_RE = re.compile(r"#\s*(?:(?P<checker>\w+)-)?(?P<kind>\w+):\s*\[")

# A line that is *only* an assertion comment (possibly with leading whitespace).
_COMMENT_ONLY_RE: Final = re.compile(r"^\s*#")


def parse_assertions(source: str) -> list[TypeAssertion]:
    """Extract assertion comments from a Python source string.

    Assertions can appear in two positions:

    1. **Inline** — a trailing comment on a code line. The assertion
       applies to that line.
    2. **Preceding** — a comment-only line immediately above a code line
       (or above another preceding assertion). The assertion applies to
       the next non-comment line. This allows stacking checker-specific
       assertions.
    """
    lines = source.splitlines()
    assertions: list[TypeAssertion] = []
    # Pending assertions from comment-only lines that haven't been
    # anchored to a code line yet.
    pending: list[tuple[str, TypeAssertion]] = []  # ("raw line", assertion)

    for lineno, line in enumerate(lines, start=1):
        is_comment_only = bool(_COMMENT_ONLY_RE.match(line))

        # Check for invalid assertion types - any "# something: [" pattern
        # that isn't a valid "error:" assertion
        assertion_like_match = _ASSERTION_LIKE_RE.search(line)
        if assertion_like_match:
            kind = assertion_like_match.group("kind")
            checker = _checker_or_none(assertion_like_match.group("checker"))
            # Only "error" is valid for bracket-style assertions
            if kind != "error":
                raise InvalidAssertionError(
                    line_number=lineno,
                    kind=kind,
                    checker=checker,
                )

        # Try to parse assertions from this line (supports multiple per line).
        diag_matches = list(_DIAG_ASSERTION_RE.finditer(line))
        revealed_matches = list(_REVEALED_RE.finditer(line)) if not diag_matches else []

        if is_comment_only and (diag_matches or revealed_matches):
            # This is a preceding-line assertion — don't anchor yet.
            for diag_match in diag_matches:
                pending.append(
                    (
                        "diag",
                        TypeAssertion(
                            line_number=-1,  # will be set when anchored
                            kind=diag_match.group("severity"),
                            checker=_checker_or_none(
                                diag_match.group("checker") or None
                            ),
                            rule=diag_match.group("rule"),
                            message=diag_match.group("message"),
                        ),
                    )
                )
            for revealed_match in revealed_matches:
                pending.append(
                    (
                        "revealed",
                        TypeAssertion(
                            line_number=-1,
                            kind="revealed",
                            checker=None,
                            rule=None,
                            message=revealed_match.group("type").strip(),
                        ),
                    )
                )
            continue

        # This is a code line (or a comment line with no assertion).
        # Anchor any pending assertions to this line.
        if pending:
            for _, assertion in pending:
                assertion.line_number = lineno
                assertions.append(assertion)
            pending.clear()

        # Also check for inline assertions on this code line.
        for diag_match in diag_matches:
            assertions.append(
                TypeAssertion(
                    line_number=lineno,
                    kind=diag_match.group("severity"),
                    checker=_checker_or_none(diag_match.group("checker") or None),
                    rule=diag_match.group("rule"),
                    message=diag_match.group("message"),
                )
            )
        for revealed_match in revealed_matches:
            assertions.append(
                TypeAssertion(
                    line_number=lineno,
                    kind="revealed",
                    checker=None,
                    rule=None,
                    message=revealed_match.group("type").strip(),
                )
            )

    return assertions


# ───────────────────────────────────────────────────────────────────────
# Markdown parser
# ───────────────────────────────────────────────────────────────────────


@dataclass
class MdCodeBlock:
    source: str
    start_line: int
    section: str
    only_checkers: set[str] | None  # None = all checkers
    skip_checkers: set[str]  # empty = skip none


_FENCE_OPEN_RE = re.compile(
    r"^```(?:py|python)"
    r"(?P<attrs>(?:\s+\w+=\S+)*)"
    r"\s*$"
)
_FENCE_CLOSE_RE = re.compile(r"^```\s*$")
_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+)$")
_ATTR_RE = re.compile(r"(?P<key>\w+)=(?P<value>\S+)")


def _parse_name_list(raw: str) -> set[str]:
    return {n.strip() for n in raw.split(",") if n.strip()}


def _parse_fence_attrs(attrs_str: str) -> dict[str, str]:
    return {m.group("key"): m.group("value") for m in _ATTR_RE.finditer(attrs_str)}


def parse_markdown(text: str) -> list[MdCodeBlock]:
    blocks: list[MdCodeBlock] = []
    heading_stack: list[tuple[int, str]] = []
    lines = text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]

        hm = _HEADING_RE.match(line)
        if hm:
            level = len(hm.group("hashes"))
            title = hm.group("title").strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
            i += 1
            continue

        fm = _FENCE_OPEN_RE.match(line)
        if fm:
            attrs = _parse_fence_attrs(fm.group("attrs") or "")
            start_line = i + 1
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not _FENCE_CLOSE_RE.match(lines[i]):
                code_lines.append(lines[i])
                i += 1
            section = " - ".join(t for _, t in heading_stack) if heading_stack else ""
            blocks.append(
                MdCodeBlock(
                    source="\n".join(code_lines),
                    start_line=start_line + 1,
                    section=section,
                    only_checkers=_parse_name_list(attrs["only"])
                    if "only" in attrs
                    else None,
                    skip_checkers=_parse_name_list(attrs["skip"])
                    if "skip" in attrs
                    else set(),
                )
            )
            i += 1
            continue

        i += 1
    return blocks


# ───────────────────────────────────────────────────────────────────────
# Assertion matcher
# ───────────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class MismatchedReveal:
    """A reveal_type assertion that matched a diagnostic but with a different type."""

    line_number: int
    expected: str  # from the assertion
    actual: str  # from the diagnostic


@dataclass
class MatchResult:
    unmatched_assertions: list[TypeAssertion]
    unexpected_diagnostics: list[Diagnostic]
    mismatched_reveals: list[MismatchedReveal]

    @property
    def ok(self) -> bool:
        return (
            not self.unmatched_assertions
            and not self.unexpected_diagnostics
            and not self.mismatched_reveals
        )

    @property
    def has_unexpected_errors(self) -> bool:
        """True if there are unexpected error diagnostics (not reveals)."""
        return any(d.severity == "error" for d in self.unexpected_diagnostics)


def match_diagnostics(
    assertions: list[TypeAssertion],
    diagnostics: list[Diagnostic],
    checker: TypeChecker,
) -> MatchResult:
    """Match diagnostics against inline assertions.

    Only universal assertions (``checker is None``) and assertions whose
    ``checker`` matches *checker.name* are considered. Assertions for
    other checkers are silently skipped.
    """
    # Filter to assertions relevant to this checker.
    active = [a for a in assertions if a.checker is None or a.checker == checker.name]

    used_diags: set[int] = set()
    mismatched_reveals: list[MismatchedReveal] = []

    for assertion in active:
        for idx, diag in enumerate(diagnostics):
            if idx in used_diags:
                continue
            if diag.line != assertion.line_number:
                continue

            if assertion.kind == "revealed":
                if diag.rule != "revealed-type":
                    continue
                # Found a revealed-type diagnostic on the same line
                # Extract and normalize the revealed type for comparison
                actual = checker.extract_revealed_type(diag.message)
                if assertion.message and assertion.message != actual:
                    # Type mismatch - record it
                    mismatched_reveals.append(
                        MismatchedReveal(
                            line_number=assertion.line_number,
                            expected=assertion.message,
                            actual=actual,
                        )
                    )
                assertion.matched = True
                used_diags.add(idx)
                break
            if diag.severity != assertion.kind:
                continue
            if assertion.rule and diag.rule != assertion.rule:
                continue
            if assertion.message and assertion.message not in diag.message:
                continue
            assertion.matched = True
            used_diags.add(idx)
            break

    # Suppress ``undefined-reveal`` on lines with a ``# revealed:`` assertion.
    revealed_lines = {a.line_number for a in active if a.kind == "revealed"}
    for idx, diag in enumerate(diagnostics):
        if idx in used_diags:
            continue
        if diag.rule == "undefined-reveal" and diag.line in revealed_lines:
            used_diags.add(idx)

    unmatched = [a for a in active if not a.matched]
    unexpected = [d for i, d in enumerate(diagnostics) if i not in used_diags]
    return MatchResult(
        unmatched_assertions=unmatched,
        unexpected_diagnostics=unexpected,
        mismatched_reveals=mismatched_reveals,
    )


# ───────────────────────────────────────────────────────────────────────
# pytest hooks
# ───────────────────────────────────────────────────────────────────────


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("typing", "type checker tests")
    group.addoption(
        "--typing-checkers",
        default=None,
        help="Type checker backends to use (comma-separated, default: ty). Available: "
        + ", ".join(CHECKERS),
    )

    parser.addini(
        "typing_checkers",
        "Type checker backends (default: ty). Available: " + ", ".join(CHECKERS),
        type="args",
        default=["ty"],
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "typing: mark test as a type checker Markdown test."
    )


def _get_checkers(config: pytest.Config) -> list[TypeChecker]:
    """Get the list of type checkers to use."""
    # CLI option takes precedence (comma-separated string)
    cli_val = config.getoption("typing_checkers", default=None)
    if cli_val:
        names = [n.strip() for n in cli_val.split(",") if n.strip()]
    else:
        # Read from pyproject.toml [tool.pytest] section (native TOML array)
        names = config.getini("typing_checkers") or ["ty"]

    checkers: list[TypeChecker] = []
    for name in names:
        if name not in CHECKERS:
            available = ", ".join(CHECKERS)
            raise pytest.UsageError(
                f"Unknown typing checker {name!r}. Available: {available}"
            )
        checkers.append(CHECKERS[name])
    return checkers


# ───────────────────────────────────────────────────────────────────────
# Collector and test item
# ───────────────────────────────────────────────────────────────────────


def _normalize_test_name(section: str) -> str:
    """Normalize a section name for use as a pytest test name.

    Lowercases and replaces spaces/dashes with underscores for easier CLI use.
    """
    return section.lower().replace(" - ", "-").replace(" ", "_")


class MdTestItem(pytest.Item):
    def __init__(
        self, *, code_block: MdCodeBlock, checker: TypeChecker, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self.code_block = code_block
        self.checker = checker
        self.add_marker(pytest.mark.typing)

    def runtest(self) -> None:
        block = self.code_block
        assertions = parse_assertions(block.source)
        checker = self.checker

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_snippet.py"
            filepath.write_text(block.source, encoding="utf-8")

            diagnostics = checker.check(filepath, tmpdir, self.config)

        for d in diagnostics:
            d.file = Path(d.file).name

        match = match_diagnostics(assertions, diagnostics, checker)

        if not match.ok:
            raise MdTestError(
                match_result=match,
                md_file=str(self.path),
                md_line=block.start_line,
                section=block.section,
                checker_name=checker.name,
            )

    def repr_failure(
        self,
        excinfo: pytest.ExceptionInfo[BaseException],
        style: TracebackStyle | None = None,
    ) -> str | TerminalRepr:
        if not isinstance(excinfo.value, MdTestError):
            return super().repr_failure(excinfo, style)

        err: MdTestError = excinfo.value
        lines: list[str] = []
        if err.section:
            lines.append(f"{err.checker_name}: {err.section}")
        lines.append(f" in {err.md_file}:{err.md_line}\n")

        # Separate unexpected diagnostics into errors and non-errors (reveals, warnings)
        unexpected_errors = [
            d for d in err.match_result.unexpected_diagnostics if d.severity == "error"
        ]
        unexpected_other = [
            d for d in err.match_result.unexpected_diagnostics if d.severity != "error"
        ]

        # Show unexpected errors first - these are the most important
        if unexpected_errors:
            lines.append(" Unexpected errors:")
            for d in unexpected_errors:
                lines.append(f" line {d.line}: {d.severity}[{d.rule}]: {d.message}")

        # Show mismatched reveals with a clear expected vs actual format
        if err.match_result.mismatched_reveals:
            lines.append(" Mismatched revealed types:")
            for m in err.match_result.mismatched_reveals:
                lines.append(
                    f" line {m.line_number}: `{m.expected}` (expected) vs `{m.actual}` (actual)"
                )

        # When there are unexpected errors, only show unmatched error/warning
        # assertions, not reveal assertions (since reveals likely failed due
        # to the errors)
        if err.match_result.unmatched_assertions:
            if unexpected_errors:
                # Filter to only non-reveal assertions when there are unexpected errors
                unmatched_non_reveals = [
                    a
                    for a in err.match_result.unmatched_assertions
                    if a.kind != "revealed"
                ]
                if unmatched_non_reveals:
                    lines.append(" Unmatched assertions (expected but not produced):")
                    for a in unmatched_non_reveals:
                        msg = f" line {a.line_number}: {a.kind}: [{a.rule}]"
                        if a.message:
                            msg += f' "{a.message}"'
                        lines.append(msg)
            else:
                # No unexpected errors - show all unmatched assertions
                lines.append(" Unmatched assertions (expected but not produced):")
                for a in err.match_result.unmatched_assertions:
                    if a.kind == "revealed":
                        lines.append(f" line {a.line_number}: revealed: {a.message}")
                    else:
                        msg = f" line {a.line_number}: {a.kind}: [{a.rule}]"
                        if a.message:
                            msg += f' "{a.message}"'
                        lines.append(msg)

        # Show other unexpected diagnostics (warnings, revealed-type) last
        if unexpected_other:
            lines.append(" Unexpected diagnostics:")
            for d in unexpected_other:
                lines.append(f" line {d.line}: {d.severity}[{d.rule}]: {d.message}")

        return "\n".join(lines)

    def reportinfo(self) -> tuple[Path, int | None, str]:
        section = self.code_block.section
        label = f"typing {section}" if section else "typing"
        return self.path, self.code_block.start_line - 1, label


class MdTestFile(pytest.File):
    def collect(self) -> Generator[MdTestItem, None, None]:
        text = self.path.read_text(encoding="utf-8")
        blocks = parse_markdown(text)
        checkers = _get_checkers(self.config)
        for idx, block in enumerate(blocks):
            base_name = (
                _normalize_test_name(block.section) if block.section else f"block-{idx}"
            )
            for checker in checkers:
                if (
                    block.only_checkers is not None
                    and checker.name not in block.only_checkers
                ):
                    continue
                if checker.name in block.skip_checkers:
                    continue
                # Include checker name in test name when multiple checkers are used
                if len(checkers) > 1:
                    name = f"{base_name}[{checker.name}]"
                else:
                    name = base_name
                yield MdTestItem.from_parent(
                    self, name=name, code_block=block, checker=checker
                )


def pytest_collect_file(
    parent: pytest.Collector,
    file_path: Path,
) -> MdTestFile | None:
    if file_path.suffix.casefold() == ".md" and file_path.stem.startswith(
        "test_typing_"
    ):
        return MdTestFile.from_parent(parent, path=file_path)
    return None


class MdTestError(Exception):
    def __init__(
        self,
        match_result: MatchResult,
        md_file: str,
        md_line: int,
        section: str,
        checker_name: str,
    ) -> None:
        super().__init__("type checker assertion mismatch")
        self.match_result = match_result
        self.md_file = md_file
        self.md_line = md_line
        self.section = section
        self.checker_name = checker_name
