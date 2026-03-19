"""The Pyright backend."""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, ClassVar, Literal

import pytest

from ._base import Checker, Diagnostic, InternalCheckerError


class PyrightChecker:
    name: ClassVar[Checker] = "pyright"

    @staticmethod
    def parse_output(output: str) -> list[Diagnostic]:
        """Parse pyright JSON output into diagnostics."""
        if not output.strip():
            return []

        payload = json.loads(output)
        diagnostics: list[Diagnostic] = []

        for entry in payload.get("generalDiagnostics", []):
            severity = PyrightChecker._normalize_severity(
                entry.get("severity", "error")
            )
            message = str(entry.get("message", ""))
            rule = str(entry.get("rule", "") or "")

            if (
                severity == "info"
                and message.startswith('Type of "')
                and ' is "' in message
            ):
                rule = "revealed-type"

            start = entry.get("range", {}).get("start", {})
            line = int(start.get("line", 0)) + 1
            col = int(start.get("character", 0)) + 1

            diagnostics.append(
                Diagnostic(
                    file=PyrightChecker._extract_file(entry),
                    line=line,
                    col=col,
                    severity=severity,
                    rule=rule,
                    message=message,
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
            "pyright",
            "--outputjson",
            "--project",
            project_dir,
            str(file_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_dir)  # noqa: S603
        if result.returncode not in (0, 1):
            raise InternalCheckerError(result.stderr, "pyright")
        if (
            result.returncode == 1
            and not result.stdout.strip()
            and result.stderr.strip()
        ):
            raise InternalCheckerError(result.stderr, "pyright")

        return PyrightChecker.parse_output(result.stdout)

    @staticmethod
    def extract_revealed_type(message: str) -> str:
        """Extract the revealed type from a pyright informational message."""
        match = re.search(r' is "([^"]+)"', message)
        assert match is not None
        return match.group(1).replace("'", '"')

    @staticmethod
    def _normalize_severity(raw: str) -> Literal["error", "warning", "info"]:
        normalized = {
            "error": "error",
            "warning": "warning",
            "information": "info",
        }.get(raw, raw)
        if normalized not in ("error", "warning", "info"):  # pragma: no cover
            raise ValueError(raw)
        return normalized  # type: ignore[return-value]

    @staticmethod
    def _extract_file(entry: dict[str, Any]) -> str:
        return str(entry["file"])
