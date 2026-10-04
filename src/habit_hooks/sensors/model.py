
from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path


class SensorError(Exception):
    pass


@dataclass(frozen=True)
class InlineRecipe:

    success_exit_codes: tuple[int, ...] = (0,)
    transform: Path | None = None
    report: bool = False


@dataclass
class Part:

    name: str
    directory: Path
    command: str | None = None
    argv: list[str] | None = None
    args: list[str] = field(default_factory=list)
    files: list[str] | None = None
    timeout: float | None = None
    detectors: dict[str, str | None] = field(default_factory=dict)
    inline: InlineRecipe | None = None

    @property
    def missing_detector(self) -> str | None:
        absent = (name for name, file in self.detectors.items() if file is None)
        return next(absent, None)

    @property
    def tools_that_read_its_arguments(self) -> list[str]:
        if self.argv is None:
            return []
        return [file for file in self.detectors.values() if file is not None]

    @property
    def command_line(self) -> str:
        if self.command is not None:
            return self.command
        return shlex.join(self.argv or [])


@dataclass
class Plugin:
    name: str
    language: str | None
    sensors: list[Part]
    transformers: list[Part]


@dataclass
class Run:
    findings: list[dict] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    active_languages: set[str] = field(default_factory=set)

    @property
    def failed(self) -> bool:
        return bool(self.notices)
