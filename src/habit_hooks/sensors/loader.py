
from __future__ import annotations

from dataclasses import dataclass, replace

from ..cli import ConfigError, ToolError
from ..config import Config
from ..config_schema import read_toml
from ..resolve import Resolver
from . import inline_spec
from .model import Part, Plugin
from .named_tools import DeclaredTools, files_for


@dataclass(frozen=True)
class PluginLoader:

    resolver: Resolver
    config: Config

    def load_plugin(self, name: str) -> Plugin:
        self.resolver.require_plugin(name)
        path = self.resolver.in_plugin(name, "config.toml")
        spec = read_toml(path) if path else {}
        sensors = [
            self._sensor(name, entry)
            for entry in inline_spec.unique_sensors(name, spec.get("sensors", []))
            if not self._disabled(
                entry if isinstance(entry, str) else inline_spec.name_of(entry)
            )
        ]
        transformers = [
            self.resolve_part([name], "transformers", transformer)
            for transformer in spec.get("transformers", [])
        ]
        return Plugin(name, spec.get("language"), sensors, transformers)

    def _sensor(self, plugin: str, entry: object) -> Part:
        if not isinstance(entry, dict):
            return self.resolve_part([plugin], "sensors", entry)
        part = inline_spec.part_from(
            plugin, self.resolver.in_plugin(plugin, "config.toml"), entry
        )
        part = replace(
            part,
            args=self._project_args(part.name),
            files=self._sensor_setting(part.name, entry, "files"),
            timeout=self._sensor_timeout(part.name, part.timeout),
        )
        inline_spec.refuse_unusable_report(part)
        return self._with_its_tools("sensors", part)

    def resolve_part(self, plugins: list[str], kind: str, name: str) -> Part:
        path = self.resolver.part(plugins, f"{kind}/{name}.toml")
        if path is None:
            raise ToolError(
                f"habit-sensors: no {kind[:-1]} {name!r} in {plugins} or the core"
            )
        spec = read_toml(path)
        command, argv = _recipe(kind, name, spec)
        part = Part(name, path.parent, command, argv)
        if kind == "sensors":
            part = replace(
                part,
                args=self._sensor_setting(name, spec, "args") or [],
                files=self._sensor_setting(name, spec, "files"),
                timeout=self._sensor_timeout(name, spec.get("timeout")),
            )
        return self._with_its_tools(kind, part)

    def _with_its_tools(self, kind: str, part: Part) -> Part:
        tools = DeclaredTools(self.config.plugin_detectors, self.resolver.project_dir)
        return replace(part, detectors=files_for(part, kind[:-1], tools))

    def _sensor_setting(self, name: str, spec: dict, key: str) -> list[str] | None:
        override = self.config.sensors.get(name)
        value = getattr(override, key) if override is not None else None
        return value if value is not None else spec.get(key)

    def _sensor_timeout(self, name: str, declared: object) -> float | None:
        override = self.config.sensors.get(name)
        value = override.timeout if override is not None else None
        if value is None:
            value = declared
        return inline_spec.timeout_of(value, name)

    def _project_args(self, name: str) -> list[str]:
        return self._sensor_setting(name, {}, "args") or []

    def _disabled(self, sensor: str) -> bool:
        override = self.config.sensors.get(sensor)
        return bool(override and override.disabled)


def _recipe(kind: str, name: str, spec: dict) -> tuple[str | None, list[str] | None]:
    command, argv = spec.get("command"), spec.get("argv")
    if argv == []:
        raise ConfigError(
            f"{kind[:-1]} {name!r} spells an empty 'argv' — the first element "
            "of an argv is the program to run, so a list with nothing in it "
            "names no command at all; give it the program and its arguments, "
            "or spell a 'command' string instead"
        )
    _refuse_an_argv_that_is_not_arguments(kind, name, argv)
    if (command is None) != (argv is None):
        return command, argv
    spelled = (
        "spells both 'command' and 'argv'"
        if command is not None
        else "spells neither 'command' nor 'argv'"
    )
    raise ConfigError(
        f"{kind[:-1]} {name!r} {spelled} — a part runs one or the other: 'argv' "
        "is a list of arguments spawned as it stands, which is the only form "
        "there is where no POSIX shell exists; 'command' is a shell string, for "
        "the syntax a list cannot carry, such as a pipe into jq"
    )


def _refuse_an_argv_that_is_not_arguments(
    kind: str, name: str, argv: object
) -> None:
    if argv is None:
        return
    if not isinstance(argv, list):
        raise ConfigError(
            f"{kind[:-1]} {name!r} spells {argv!r} as its 'argv' — an argv is a "
            "list, the program first and one element per argument after it; put "
            "it in brackets, or spell a 'command' string instead"
        )
    unspellable = [element for element in argv if not isinstance(element, str)]
    if not unspellable:
        return
    raise ConfigError(
        f"{kind[:-1]} {name!r} spells {unspellable[0]!r} in its 'argv' — every "
        "element is an argument handed to a program as it stands, so each has "
        "to be a string; quote it, or spell a 'command' string instead"
    )
