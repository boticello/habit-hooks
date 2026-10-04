
from __future__ import annotations

import json
import os
from pathlib import Path

from attrs import frozen

INDEX_PATH = Path(".habit-hooks") / "snooze.json"

Anchors = dict[str, str]

Index = dict[str, "Entry"]


@frozen
class Entry:

    anchors: Anchors
    smells: frozenset[str] | None = None


class SnoozeError(Exception):
    pass


def load_index(project_dir: Path) -> Index:
    path = project_dir / INDEX_PATH
    if not path.exists():
        return {}
    return _parse_index(path)


def _parse_index(path: Path) -> Index:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SnoozeError(f"{path}: not valid JSON ({exc})") from exc
    if not isinstance(data, list):
        raise SnoozeError(
            f"{path}: expected a JSON list of snoozed entries, got {_describe(data)}"
        )
    return dict(_entry(path, item) for item in data)


def _entry(path: Path, item: object) -> tuple[str, Entry]:
    if isinstance(item, str):
        return item, Entry(anchors={})
    if isinstance(item, dict) and isinstance(item.get("key"), str):
        anchors = item.get("anchors", {})
        smells = item.get("smells")
        if (
            _is_anchors(anchors)
            and _is_smells(smells)
            and not set(item) - {"key", "anchors", "smells"}
        ):
            return item["key"], Entry(
                anchors=anchors, smells=None if smells is None else frozenset(smells)
            )
    raise SnoozeError(
        f"{path}: expected each entry to be a snoozed key, or an object with "
        f'"key", an optional "smells" and an optional "anchors", got '
        f"{_describe(item)}"
    )


def _is_anchors(anchors: object) -> bool:
    return isinstance(anchors, dict) and all(
        isinstance(anchor, str) and isinstance(content, str)
        for anchor, content in anchors.items()
    )


def _is_smells(smells: object) -> bool:
    if smells is None:
        return True
    return isinstance(smells, list) and all(
        isinstance(smell, str) for smell in smells
    ) and bool(smells)


def _describe(data: object) -> str:
    if isinstance(data, list):
        return "a list with a malformed entry"
    return {dict: "an object", str: "a bare string", type(None): "null"}.get(
        type(data), type(data).__name__
    )


def save_index(entries: Index, project_dir: Path) -> None:
    path = project_dir / INDEX_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    written = [_written(key, entries[key]) for key in sorted(entries)]
    _replace_atomically(path, json.dumps(written) + "\n")


def _written(key: str, entry: Entry) -> str | dict:
    if entry.smells is None and not entry.anchors:
        return key
    written: dict[str, object] = {"key": key}
    if entry.smells is not None:
        written["smells"] = sorted(entry.smells)
    if entry.anchors:
        written["anchors"] = dict(sorted(entry.anchors.items()))
    return written


def _replace_atomically(path: Path, content: str) -> None:
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)
