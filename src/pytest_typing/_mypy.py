"""mypy type checker backend."""

import re
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from ._base import Diagnostic, InternalCheckerError, TypeChecker

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

            if severity not in ("error", "warning", "info"):  # pragma: no cover
                raise ValueError(severity)

            diagnostics.append(
                Diagnostic(
                    file=m.group("file"),
                    line=int(m.group("line")),
                    col=1,  # mypy doesn't provide column in default output
                    severity=severity,  # type: ignore
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
        # Mypy error codes: https://github.com/python/mypy/issues/6003
        if result.returncode not in (0, 1):
            # Internal error or misconfiguration
            raise InternalCheckerError(result.stderr, "mypy")
        return _parse_mypy_output(result.stdout)

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
