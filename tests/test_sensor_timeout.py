
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from habit_hooks.cli import ConfigError
from plugin_fixture import loader_for, one_sensor, write_plugin, write_project_config
from sensor_run import python_sensor, run_sensor_until


def test_a_part_file_declares_a_timeout(tmp_path: Path) -> None:
    part = one_sensor(tmp_path, 'command = "true"\ntimeout = 90\n')
    assert part.timeout == 90.0


def test_an_inline_sensor_declares_a_timeout(tmp_path: Path) -> None:
    write_project_config(tmp_path, 'plugins = ["fixt"]')
    write_plugin(
        tmp_path,
        "fixt",
        {"config.toml": 'sensors = [{ name = "s", tool = "true", timeout = 45 }]\n'},
    )
    part = loader_for(tmp_path).load_plugin("fixt").sensors[0]
    assert part.timeout == 45.0


def test_a_project_overrides_a_plugins_declared_timeout(tmp_path: Path) -> None:
    one_sensor(tmp_path, 'command = "true"\ntimeout = 90\n')
    write_project_config(tmp_path, 'plugins = ["fixt"]\n\n[sensors.s]\ntimeout = 15\n')
    part = loader_for(tmp_path).load_plugin("fixt").sensors[0]
    assert part.timeout == 15.0


@pytest.mark.parametrize(
    "declared",
    ['"later"', "true", "0", "-5"],
    ids=["a string", "a boolean", "zero", "negative"],
)
def test_a_timeout_that_is_no_number_of_seconds_is_refused(
    tmp_path: Path, declared: str
) -> None:
    with pytest.raises(ConfigError) as excinfo:
        one_sensor(tmp_path, f'command = "true"\ntimeout = {declared}\n')
    assert "timeout" in str(excinfo.value)


def test_a_sensor_with_its_own_timeout_outlives_the_run_deadline(
    tmp_path: Path,
) -> None:
    part = replace(
        python_sensor(tmp_path, "import time\ntime.sleep(1.2)\nprint('[]')\n"),
        timeout=30,
    )
    run = run_sensor_until(part, 0.3)
    assert not run.failed
    assert run.findings == []


def test_the_run_deadline_still_applies_without_its_own_timeout(
    tmp_path: Path,
) -> None:
    part = python_sensor(tmp_path, "import time\ntime.sleep(1.2)\nprint('[]')\n")
    run = run_sensor_until(part, 0.3)
    assert run.failed
