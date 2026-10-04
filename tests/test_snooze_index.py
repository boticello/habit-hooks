
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from habit_hooks.cli import EXIT_TOOL_ERROR
from habit_hooks.snooze import (
    INDEX_PATH,
    Entry,
    SnoozeError,
    load_index,
    main,
    save_index,
)


def _write_index(project_dir: Path, content: str) -> Path:
    path = project_dir / INDEX_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("content", "why"),
    [
        ("not json", "invalid JSON"),
        ("null", "JSON null"),
        ('"src/a.py"', "a bare string"),
        ('{"src/a.py": "why"}', "an object"),
    ],
)
def test_a_malformed_index_fails_by_name(
    tmp_path: Path, content: str, why: str
) -> None:
    path = _write_index(tmp_path, content)
    with pytest.raises(SnoozeError) as excinfo:
        load_index(tmp_path)
    assert str(path) in str(excinfo.value), why


@pytest.mark.parametrize("index_op", ["--list", "--snooze", "--prune"])
def test_a_corrupt_index_fails_as_a_tool_error(
    index_op: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_index(tmp_path, "not json")
    monkeypatch.setattr(sys, "stdin", io.StringIO("[]"))
    monkeypatch.chdir(tmp_path)
    assert main([index_op]) == EXIT_TOOL_ERROR


def test_an_index_of_bare_keys_still_loads(tmp_path: Path) -> None:
    _write_index(tmp_path, json.dumps(["src/x.ts", "src/y.ts"]))
    assert load_index(tmp_path) == {
        "src/x.ts": Entry(anchors={}),
        "src/y.ts": Entry(anchors={}),
    }


def test_an_index_mixing_both_shapes_loads(tmp_path: Path) -> None:
    recorded = {"key": "src/y.ts", "anchors": {"src/y.ts": "sha256:abc"}}
    _write_index(tmp_path, json.dumps(["src/x.ts", recorded]))
    assert load_index(tmp_path) == {
        "src/x.ts": Entry(anchors={}),
        "src/y.ts": Entry(anchors={"src/y.ts": "sha256:abc"}),
    }


def test_a_smell_scoped_entry_loads(tmp_path: Path) -> None:
    recorded = {"key": "src/y.ts", "smells": ["loose-equality", "var-declaration"]}
    _write_index(tmp_path, json.dumps([recorded]))
    assert load_index(tmp_path) == {
        "src/y.ts": Entry(
            anchors={}, smells=frozenset({"loose-equality", "var-declaration"})
        ),
    }


@pytest.mark.parametrize(
    "smells",
    [[], ["loose-equality", 5], "loose-equality", {"loose-equality": "why"}],
    ids=["empty", "a non string", "a bare string", "an object"],
)
def test_a_smell_list_the_index_cannot_mean_fails_by_name(
    tmp_path: Path, smells: object
) -> None:
    _write_index(tmp_path, json.dumps([{"key": "src/y.ts", "smells": smells}]))
    with pytest.raises(SnoozeError) as excinfo:
        load_index(tmp_path)
    assert "expected each entry" in str(excinfo.value)


def test_an_entry_with_a_field_the_index_cannot_mean_fails_by_name(tmp_path: Path) -> None:
    _write_index(tmp_path, json.dumps([{"key": "src/a.py", "reason": "we discussed it"}]))
    with pytest.raises(SnoozeError) as excinfo:
        load_index(tmp_path)
    assert "expected each entry" in str(excinfo.value)


def test_an_entry_recording_nothing_is_written_as_a_bare_key(tmp_path: Path) -> None:
    save_index(
        {
            "src/x.ts": Entry(anchors={}),
            "src/y.ts": Entry(anchors={"src/y.ts": "sha256:abc"}),
        },
        tmp_path,
    )
    assert json.loads((tmp_path / INDEX_PATH).read_text(encoding="utf-8")) == [
        "src/x.ts",
        {"key": "src/y.ts", "anchors": {"src/y.ts": "sha256:abc"}},
    ]


def test_a_smell_scoped_entry_is_written_with_its_smells(tmp_path: Path) -> None:
    save_index(
        {
            "src/y.ts": Entry(
                anchors={"src/y.ts": "sha256:abc"},
                smells=frozenset({"var-declaration", "loose-equality"}),
            ),
        },
        tmp_path,
    )
    assert json.loads((tmp_path / INDEX_PATH).read_text(encoding="utf-8")) == [
        {
            "key": "src/y.ts",
            "smells": ["loose-equality", "var-declaration"],
            "anchors": {"src/y.ts": "sha256:abc"},
        },
    ]


def test_save_index_writes_atomically_leaving_no_temp_files(tmp_path: Path) -> None:
    save_index({"src/x.ts": Entry(anchors={})}, tmp_path)
    index_dir = tmp_path / INDEX_PATH.parent
    assert [p.name for p in index_dir.iterdir()] == ["snooze.json"]
    assert load_index(tmp_path) == {"src/x.ts": Entry(anchors={})}
