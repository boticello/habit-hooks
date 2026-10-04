
from __future__ import annotations

from pathlib import Path

from ..cli import ConfigError
from ..config_schema import reject_unknown
from .model import InlineRecipe, Part

ENTRY_KEYS = frozenset(
    {"name", "tool", "args", "files", "timeout", "success_exit_codes", "transform", "report"}
)

_PLACEHOLDER_OR_PATH = ("$", "/", "\\")


def name_of(entry: dict) -> str:
    tool = _a_string("tool", entry.get("tool"))
    name = entry.get("name", tool)
    if not isinstance(name, str) or not name:
        raise _invalid("name", name)
    if name == tool and any(mark in tool for mark in _PLACEHOLDER_OR_PATH):
        raise ConfigError(
            f"an inline sensor spells {tool!r} as its tool, which cannot name the "
            f"sensor — give it a 'name' of its own"
        )
    return name


def unique_sensors(plugin: str, entries: list) -> list:
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = name_of(entry)
        if name in seen:
            raise ConfigError(
                f"the {plugin!r} plugin enables sensor {name!r} twice in its "
                "sensors list"
            )
        seen.add(name)
    return entries


def part_from(plugin: str, config_path: Path, entry: dict) -> Part:
    name = name_of(entry)
    where = f"sensor {name!r} in the {plugin!r} plugin config"
    reject_unknown(ENTRY_KEYS, entry, where)
    tool = _a_string("tool", entry.get("tool"))
    args = entry.get("args", [])
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        raise _invalid("args", args, "a list of strings")
    recipe = InlineRecipe(
        success_exit_codes=_exit_codes(entry.get("success_exit_codes", [0])),
        transform=_transform(entry.get("transform"), config_path.parent, where),
        report=_a_flag(entry.get("report", False)),
    )
    return Part(
        name,
        config_path.parent,
        argv=[tool, *args],
        timeout=timeout_of(entry.get("timeout"), name),
        inline=recipe,
    )


def timeout_of(value: object, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ConfigError(
            f"sensor {name!r} spells {value!r} as its 'timeout' — a timeout is "
            "a number of seconds greater than zero"
        )
    return float(value)


def refuse_unusable_report(part: Part) -> None:
    if part.inline is None:
        return
    argv = part.argv or []
    if part.inline.report and "${report}" not in argv:
        raise ConfigError(
            f"sensor {part.name!r} asks for a report path but spells no "
            "'${report}' argument to receive it"
        )
    if not part.inline.report and "${report}" in argv:
        raise ConfigError(
            f"sensor {part.name!r} spells '${{report}}' as an argument but does "
            "not set 'report' — the tool would receive the placeholder as a "
            "literal argument; set 'report = true', or remove the argument"
        )


def _exit_codes(codes: object) -> tuple[int, ...]:
    if not isinstance(codes, list) or not codes or not all(
        isinstance(code, int) and not isinstance(code, bool) for code in codes
    ):
        raise _invalid("success_exit_codes", codes, "a list of exit-code numbers")
    return tuple(codes)


def _transform(program: object, plugin_dir: Path, where: str) -> Path | None:
    if program is None:
        return None
    if not isinstance(program, str):
        raise _invalid("transform", program, "a path relative to the plugin's config")
    path = plugin_dir / program
    if not path.is_file():
        raise ConfigError(
            f"{where} spells a 'transform' of {program!r}, which is not a file "
            f"the plugin ships"
        )
    return path


def _a_flag(flag: object) -> bool:
    if not isinstance(flag, bool):
        raise _invalid("report", flag, "true or false")
    return flag


def _a_string(key: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise _invalid(key, value, "a string")
    return value


def _invalid(key: str, value: object, expected: str) -> ConfigError:
    return ConfigError(
        f"an inline sensor spells {value!r} as its {key!r} — {expected} "
        "is expected there"
    )
