
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from attrs import evolve

from .snooze_index import Anchors, Entry, Index

CONTENT_ALGORITHM = "sha256"


def anchor_file(issue: dict) -> str:
    file = issue.get("details", {}).get("file")
    return file if isinstance(file, str) and file else issue["key"]


@dataclass(frozen=True)
class Reported:

    smells: set[str]
    anchors: set[str]


def reported(findings: list[dict]) -> dict[str, Reported]:
    reported_by_key: dict[str, Reported] = {}
    for finding in findings:
        for issue in finding["issues"]:
            entry = reported_by_key.setdefault(issue["key"], Reported(set(), set()))
            entry.smells.add(finding["smell"])
            entry.anchors.add(anchor_file(issue))
    return reported_by_key


def content_hash(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    digest = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    return f"{CONTENT_ALGORITHM}:{digest}"


def holds(recorded: Anchors, anchor: str, project_dir: Path) -> bool:
    if not recorded:
        return True
    if anchor not in recorded:
        return False
    return recorded[anchor] == content_hash(project_dir / anchor)


def renewed(index: Index, findings: list[dict], project_dir: Path) -> Index:
    fresh = dict(index)
    for key, current in reported(findings).items():
        entry = fresh.get(key, Entry(anchors={}, smells=frozenset()))
        smells = (
            entry.smells
            if entry.smells is None
            else entry.smells | frozenset(current.smells)
        )
        fresh[key] = evolve(entry, anchors=_recorded(entry, current, project_dir), smells=smells)
    return fresh


def _recorded(entry: Entry, current: Reported, project_dir: Path) -> Anchors:
    fresh = {anchor: content_hash(project_dir / anchor) for anchor in current.anchors}
    return {**entry.anchors, **{
        anchor: content for anchor, content in fresh.items() if content is not None
    }}


def pruned(entry: Entry, current: Reported) -> Entry | None:
    smells = entry.smells
    if smells is not None:
        smells = frozenset(smell for smell in smells if smell in current.smells)
        if not smells:
            return None
    anchors = {
        anchor: content
        for anchor, content in entry.anchors.items()
        if anchor in current.anchors
    }
    return Entry(anchors=anchors, smells=smells)
