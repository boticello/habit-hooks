
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .cli import EXIT_TOOL_ERROR, add_version_flag, run_console
from .snooze_index import INDEX_PATH, Entry, SnoozeError, Index, load_index, save_index
from .snooze_lapse import anchor_file, holds, pruned, renewed, reported

__all__ = ["INDEX_PATH", "SnoozeError", "load_index", "main", "save_index"]

SNOOZE_TRANSFORMERS = frozenset({"snooze", "snooze-until-changed"})


def transform(findings: list[dict], index: Index, project_dir: Path) -> list[dict]:
    def still_snoozed(smell: str, issue: dict) -> bool:
        entry = index.get(issue["key"])
        if entry is None:
            return False
        if entry.smells is not None and smell not in entry.smells:
            return False
        return holds(entry.anchors, anchor_file(issue), project_dir)

    kept = []
    for finding in findings:
        smell = finding["smell"]
        issues = [
            issue
            for issue in finding["issues"]
            if not still_snoozed(smell, issue)
        ]
        snoozed_them_all = finding["issues"] and not issues
        if not snoozed_them_all:
            kept.append({**finding, "issues": issues})
    return kept


def read_findings() -> list[dict]:
    raw = sys.stdin.read().strip()
    return json.loads(raw) if raw else []


def run(args: argparse.Namespace, project_dir: Path) -> int:
    if args.list:
        for key, entry in sorted(load_index(project_dir).items()):
            for line in _lines(key, entry):
                sys.stdout.write(line + "\n")
        return 0
    if args.snooze:
        index = load_index(project_dir)
        save_index(renewed(index, read_findings(), project_dir), project_dir)
        return 0
    if args.prune:
        return _prune(project_dir)
    return _write_transformed(project_dir)


def _lines(key: str, entry: Entry) -> list[str]:
    if entry.smells is None:
        return [key]
    return [f"{key} {smell}" for smell in sorted(entry.smells)]


def _prune(project_dir: Path) -> int:
    present = reported(read_findings())
    index = load_index(project_dir)
    if index and not present:
        sys.stderr.write(
            "habit-snooze: --prune read no findings; refusing to empty a "
            "populated index. Nothing was measured — feed it a snooze-free run "
            "(`habit-sensors --no-snooze | habit-snooze --prune`). "
            "Index left unchanged.\n"
        )
        return 1
    kept: Index = {}
    for key, entry in index.items():
        if key in present:
            survivor = pruned(entry, present[key])
            if survivor is not None:
                kept[key] = survivor
    save_index(kept, project_dir)
    return 0


def _write_transformed(project_dir: Path) -> int:
    findings = read_findings()
    index = load_index(project_dir)
    sys.stdout.write(json.dumps(transform(findings, index, project_dir)) + "\n")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="habit-snooze")
    add_version_flag(parser)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--snooze", action="store_true")
    group.add_argument("--prune", action="store_true")
    group.add_argument("--list", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    return run_console("habit-snooze", _run_snooze_command, argv)


def _run_snooze_command(argv: list[str]) -> int:
    try:
        return run(parse_args(argv), Path.cwd())
    except SnoozeError as error:
        sys.stderr.write(f"habit-snooze: {error}\n")
        return EXIT_TOOL_ERROR


if __name__ == "__main__":
    sys.exit(main())
