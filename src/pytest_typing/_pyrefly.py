"""The Pyrefly backend."""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

import pytest

from ._base import Checker, Diagnostic, InternalCheckerError


class PyreflyChecker:
    name: ClassVar[Checker] = "pyrefly"

    @staticmethod
    def parse_output(output: str) -> list[Diagnostic]:
        """Parse pyrefly JSON output into diagnostics."""
        if not output.strip():
            return []

        payload = json.loads(output)
        diagnostics: list[Diagnostic] = []

        for entry in payload.get("errors", []):
            severity = str(entry.get("severity", "error"))
            if severity not in ("error", "warning", "info"):  # pragma: no cover
                raise ValueError(severity)
            rule = str(entry.get("name", "") or "")
            if rule == "reveal-type":
                rule = "revealed-type"

            diagnostics.append(
                Diagnostic(
                    file=str(entry["path"]),
                    line=int(entry["line"]),
                    col=int(entry["column"]),
                    severity=severity,  # type: ignore[arg-type]
                    rule=rule,
                    message=str(entry.get("description", "") or ""),
                )
            )

        return diagnostics

    @staticmethod
    def check(
        file_path: Path, project_dir: str, config: pytest.Config
    ) -> list[Diagnostic]:
        cmd = [
            sys.executable,
            "-m",
            "pyrefly",
            "check",
            "--output-format=json",
            "--summary=none",
            str(file_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_dir)  # noqa: S603
        if result.returncode not in (0, 1):
            raise InternalCheckerError(result.stderr, "pyrefly")
        if (
            result.returncode == 1
            and not result.stdout.strip()
            and result.stderr.strip()
        ):
            raise InternalCheckerError(result.stderr, "pyrefly")

        return PyreflyChecker.parse_output(result.stdout)

    @staticmethod
    def extract_revealed_type(message: str) -> str:
        """Extract the revealed type from a pyrefly informational message."""
        match = re.search(r"revealed type:\s*(.+)", message)
        assert match is not None
        return match.group(1).replace("'", '"')
