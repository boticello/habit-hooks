
from __future__ import annotations

import json
import re
from pathlib import Path

import jq

from .broken_part import run_part
from .chunking import chunked_commands
from .diagnosis import keep_both_ends
from .finding_paths import anchored, malformed
from .inline_report import report_path, report_text
from .model import InlineRecipe, Part, SensorError
from .part_output import COMMAND_NOT_FOUND, part_failure
from .spawn import Spawner

_GLOB_METACHARACTERS = re.compile(r"[*?\[\]{}\\]")


def literal_spelling_of(path: str) -> str:
    if "*" not in path:
        return path
    return _GLOB_METACHARACTERS.sub(r"\\\g<0>", path)


def findings_for(sensor: Part, execution) -> list[dict]:
    findings: list[dict] = []
    for argv in _invocations(sensor, execution, execution.scoped_files(sensor)):
        findings.extend(_invocation_findings(sensor, argv, execution.spawner_for(sensor)))
    return anchored(findings, execution.project_dir, sensor.name)


def _invocations(sensor: Part, execution, files: list[str]) -> list[list[str]]:
    literal = [literal_spelling_of(file) for file in files]
    return chunked_commands(sensor, literal, execution.expander(sensor))


def _invocation_findings(
    sensor: Part, argv: list[str], spawner: Spawner
) -> list[dict]:
    recipe = sensor.inline or InlineRecipe()
    with report_path(recipe) as report:
        runnable = (
            [a.replace("${report}", str(report)) for a in argv] if report else argv
        )
        result = run_part(
            "sensor",
            sensor,
            lambda: spawner.run(
                runnable, tools=sensor.tools_that_read_its_arguments
            ),
        )
        if result.returncode not in recipe.success_exit_codes:
            raise _tool_failure(sensor, result)
        output = report_text(sensor, report) if report else result.stdout
        return _findings_in(sensor, recipe, output)


def _tool_failure(sensor: Part, result) -> SensorError:
    if COMMAND_NOT_FOUND.search(result.stderr):
        return part_failure("sensor", sensor, result)
    words = (result.stderr or result.stdout).strip()
    message = f"sensor {sensor.name!r} failed: {sensor.command_line}"
    return SensorError(message + (f"\n{keep_both_ends(words)}" if words else ""))


def _findings_in(sensor: Part, recipe: InlineRecipe, output: str) -> list[dict]:
    try:
        parsed = json.loads(output)
    except ValueError:
        raise SensorError(
            f"sensor {sensor.name!r} printed output that is not JSON — its "
            f"findings cannot be read\n{keep_both_ends(output.strip())}"
        ) from None
    if recipe.transform is not None:
        parsed = _transformed(sensor, recipe.transform, parsed)
    return _validated(sensor, parsed)


def _transformed(sensor: Part, program_path: Path, parsed: object) -> object:
    program = program_path.read_text(encoding="utf-8")
    try:
        outputs = jq.compile(program).input(parsed).all()
    except ValueError as broken:
        raise SensorError(
            f"sensor {sensor.name!r} transform {program_path.name!r} failed: "
            f"{broken}"
        ) from None
    if len(outputs) != 1:
        raise SensorError(
            f"sensor {sensor.name!r} transform {program_path.name!r} produced "
            f"{len(outputs)} outputs rather than one findings array"
        )
    return outputs[0]


def _validated(sensor: Part, findings: object) -> list[dict]:
    if not isinstance(findings, list):
        raise malformed(sensor.name, "output that is not a findings array", contract=True)
    for finding in findings:
        _validated_finding(sensor, finding)
    return findings


def _validated_finding(sensor: Part, finding: object) -> None:
    if not isinstance(finding, dict):
        raise malformed(sensor.name, "a finding that is not an object", contract=True)
    if not isinstance(finding.get("smell"), str):
        raise malformed(sensor.name, "a finding whose 'smell' is not a string", contract=True)
    if not isinstance(finding.get("details"), dict):
        raise malformed(sensor.name, "a finding whose 'details' is not an object", contract=True)
    issues = finding.get("issues")
    if not isinstance(issues, list):
        raise malformed(sensor.name, "a finding whose 'issues' is not a list", contract=True)
    for issue in issues:
        _validated_issue(sensor, issue)


def _validated_issue(sensor: Part, issue: object) -> None:
    if not isinstance(issue, dict):
        raise malformed(sensor.name, "an issue that is not an object", contract=True)
    if not isinstance(issue.get("key"), str):
        raise malformed(sensor.name, "an issue whose 'key' is not a string", contract=True)
    if not isinstance(issue.get("details"), dict):
        raise malformed(sensor.name, "an issue whose 'details' is not an object", contract=True)
