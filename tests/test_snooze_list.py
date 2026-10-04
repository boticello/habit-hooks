
from __future__ import annotations

from pathlib import Path

import pytest

from habit_hooks.snooze import INDEX_PATH, parse_args, run
from snooze_project import a_project_with, snooze


def _write_index(project_dir: Path, content: str) -> None:
    path = project_dir / INDEX_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_list_prints_each_approved_smell_on_its_own_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from finding import a_finding, an_issue

    a_project_with(tmp_path, "src/x.ts", "export const a = 1;\n")
    a_project_with(tmp_path, "src/y.ts", "export const b = 2;\n")
    snooze(
        tmp_path,
        monkeypatch,
        [
            a_finding(smell="oversized-file", issues=[an_issue("src/x.ts")]),
            a_finding(smell="unused-import", issues=[an_issue("src/x.ts")]),
            a_finding(smell="loose-equality", issues=[an_issue("src/y.ts")]),
        ],
    )
    assert run(parse_args(["--list"]), tmp_path) == 0
    assert capsys.readouterr().out == (
        "src/x.ts oversized-file\nsrc/x.ts unused-import\nsrc/y.ts loose-equality\n"
    )


def test_list_prints_a_bare_key_for_a_whole_file_approval(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    _write_index(tmp_path, json.dumps(["src/x.ts"]))
    assert run(parse_args(["--list"]), tmp_path) == 0
    assert capsys.readouterr().out == "src/x.ts\n"
