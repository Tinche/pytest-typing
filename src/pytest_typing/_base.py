"""Base classes and types for type checker backends."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

import pytest

Checker = Literal["ty", "mypy"]


@dataclass(slots=True)
class Diagnostic:
    """A single diagnostic emitted by a type checker."""

    file: str
    line: int
    col: int
    severity: Literal["error", "warning", "info"]
    rule: str  # e.g. "invalid-assignment"
    message: str


class TypeChecker(Protocol):
    """Protocol for a type checker backend."""

    @property
    def name(self) -> Checker: ...

    def check(
        self, file_path: Path, project_dir: str, config: pytest.Config
    ) -> list[Diagnostic]:
        """Run the checker on *file_path* and return parsed diagnostics."""
        ...

    def parse_output(self, output: str) -> list[Diagnostic]:
        """Parse raw checker output into diagnostics."""
        ...

    def extract_revealed_type(self, message: str) -> str:
        """Extract the type from a revealed-type diagnostic message."""
        ...


class InternalCheckerError(Exception):
    """Raised when a type checker encounters an internal error or misconfiguration."""

    def __init__(self, message: str, checker_name: Checker) -> None:
        super().__init__(message)
        self.checker_name = checker_name


def checker_or_none(value: str | None) -> Checker | None:
    """Convert a string to a Checker literal, or return None."""
    if value is None:
        return None
    if value in ("ty", "mypy"):
        return value  # type: ignore[return-value]
    raise ValueError(f"Invalid checker value ({value})")
