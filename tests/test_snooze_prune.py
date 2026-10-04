
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from habit_hooks.snooze import INDEX_PATH, Entry, load_index, parse_args, run
from snooze_project import a_project_with, feed_stdin, finding, snooze


def _write_index(project_dir: Path, content: str) -> None:
    path = project_dir / INDEX_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _finding(*keys: str) -> dict:
    return {
        "smell": "loose-equality",
        "details": {},
        "issues": [{"key": key, "details": {"file": key}} for key in keys],
    }


def _prune(tmp_path: Path, monkeypatch, findings: object) -> None:
    feed_stdin(monkeypatch, findings)
    assert run(parse_args(["--prune"]), tmp_path) == 0


def test_prune_drops_a_key_that_no_longer_appears(
    tmp_path: Path, monkeypatch
) -> None:
    _write_index(tmp_path, json.dumps(["src/x.ts", "src/y.ts"]))
    _prune(tmp_path, monkeypatch, [_finding("src/x.ts")])
    assert load_index(tmp_path) == {"src/x.ts": Entry(anchors={})}


def test_prune_refuses_to_empty_a_populated_index_on_no_findings(
    tmp_path: Path, monkeypatch
) -> None:
    _write_index(tmp_path, json.dumps(["src/x.ts", "src/y.ts"]))
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    assert run(parse_args(["--prune"]), tmp_path) == 1
    assert load_index(tmp_path) == {
        "src/x.ts": Entry(anchors={}),
        "src/y.ts": Entry(anchors={}),
    }


def test_prune_still_clears_an_index_it_was_asked_to_when_findings_exist(
    tmp_path: Path, monkeypatch
) -> None:
    _write_index(tmp_path, json.dumps(["src/x.ts"]))
    _prune(tmp_path, monkeypatch, [_finding("src/other.ts")])
    assert load_index(tmp_path) == {}


def test_prune_keeps_the_recordings_of_a_key_it_keeps(
    tmp_path: Path, monkeypatch
) -> None:
    a_project_with(tmp_path, "src/x.ts", "export const a = 1;\n")
    snooze(tmp_path, monkeypatch, [finding("src/x.ts", "src/x.ts")])
    recorded = load_index(tmp_path)["src/x.ts"]

    _prune(tmp_path, monkeypatch, [finding("src/x.ts", "src/x.ts")])
    assert load_index(tmp_path) == {"src/x.ts": recorded}


def test_prune_drops_an_anchor_the_run_no_longer_reports(
    tmp_path: Path, monkeypatch
) -> None:
    from habit_hooks.snooze_lapse import content_hash
    from snooze_project import aliased

    a_project_with(tmp_path, "src/a.py", "import requests\n")
    a_project_with(tmp_path, "src/b.py", "import requests\nrequests.get()\n")
    snooze(tmp_path, monkeypatch, aliased("src/a.py", "src/b.py"))

    _prune(tmp_path, monkeypatch, aliased("src/b.py"))
    assert load_index(tmp_path) == {
        "requests": Entry(
            anchors={"src/b.py": content_hash(tmp_path / "src/b.py")},
            smells=frozenset({"unused-dependency"}),
        ),
    }


def test_prune_drops_a_smell_the_run_no_longer_reports(
    tmp_path: Path, monkeypatch
) -> None:
    from finding import a_finding, an_issue
    from habit_hooks.snooze_lapse import content_hash

    a_project_with(tmp_path, "src/x.ts", "export const a = 1;\n")
    snooze(tmp_path, monkeypatch, [finding("src/x.ts", "src/x.ts")])
    snooze(
        tmp_path,
        monkeypatch,
        [a_finding(smell="unused-import", issues=[an_issue("src/x.ts")])],
    )

    _prune(tmp_path, monkeypatch, [finding("src/x.ts", "src/x.ts")])
    assert load_index(tmp_path) == {
        "src/x.ts": Entry(
            anchors={"src/x.ts": content_hash(tmp_path / "src/x.ts")},
            smells=frozenset({"oversized-file"}),
        ),
    }


def test_prune_drops_a_key_whose_every_smell_is_no_longer_reported(
    tmp_path: Path, monkeypatch
) -> None:
    from finding import a_finding, an_issue

    a_project_with(tmp_path, "src/x.ts", "export const a = 1;\n")
    snooze(tmp_path, monkeypatch, [finding("src/x.ts", "src/x.ts")])

    _prune(
        tmp_path, monkeypatch, [a_finding(smell="unused-import", issues=[an_issue("src/y.ts")])]
    )
    assert load_index(tmp_path) == {}
