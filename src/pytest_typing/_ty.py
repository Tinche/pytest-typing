"""ty type checker backend."""

import re
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from ._base import Diagnostic, InternalCheckerError, TypeChecker

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
            severity = m.group("severity")
            if severity not in ("error", "warning", "info"):  # pragma: no cover
                raise ValueError(severity)
            diagnostics.append(
                Diagnostic(
                    file=m.group("file"),
                    line=int(m.group("line")),
                    col=int(m.group("col")),
                    severity=severity,  # type: ignore
                    rule=m.group("rule"),
                    message=m.group("message"),
                )
            )
    return diagnostics


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
        # Docs on ty status codes: https://docs.astral.sh/ty/reference/exit-codes/
        if result.returncode not in (0, 1):
            # Internal error or misconfiguration
            raise InternalCheckerError(result.stderr, "ty")

        return _parse_ty_output(result.stdout)

    def extract_revealed_type(self, message: str) -> str:
        """Extract the type from a ty revealed-type diagnostic message.

        Example: "Revealed type: `Literal[1]`" -> "Literal[1]"
        """
        match = re.search(r"`([^`]+)`", message)
        assert match is not None
        return match.group(1)
