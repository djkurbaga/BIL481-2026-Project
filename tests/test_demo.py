"""Assignment 3 demosunun CI ve yerel kullanım davranışını sınar."""

from dataclasses import replace
import subprocess

import pytest

import gsmf.lifecycle as lifecycle
from scripts import demo


@pytest.mark.parametrize(("args", "exit_code", "status", "totals"), [
    ([], 0, "SKIPPED", "3 passed, 0 failed, 1 skipped"),
    (["--require-docker"], 1, "FAIL", "3 passed, 1 failed, 0 skipped"),
])
def test_unavailable_docker_affects_exit_status(monkeypatch, capsys, tmp_path,
                                               args, exit_code, status, totals):
    monkeypatch.setattr(demo, "_docker_available", lambda: (False, "test daemon unavailable"))

    result = demo.main(["--out", str(tmp_path), *args])

    assert result == exit_code
    output = capsys.readouterr().out
    assert f"{status:<8} UC2 Manage isolated stack lifecycle (FR-3)" in output
    assert "test daemon unavailable" in output
    assert totals in output


def test_demo_uses_a_new_configured_compose_project_per_run(monkeypatch, capsys, tmp_path):
    config = demo.load_config(demo.VALID_CONFIG)
    compose_file = tmp_path / "configured compose.yml"
    config = replace(config, targets=(replace(config.targets[0], compose_file=compose_file),))
    monkeypatch.setattr(demo, "load_config", lambda path: config)
    monkeypatch.setattr(demo, "_docker_available", lambda: (True, ""))
    monkeypatch.setattr(lifecycle, "http_status", lambda url, timeout: 200)
    calls = []

    def compose_run(command, **kwargs):
        calls.append(command)
        status = '[{"State":"running","Health":"healthy"}]' if "--format" in command else ""
        return subprocess.CompletedProcess(command, 0, stdout=status, stderr="")

    monkeypatch.setattr(demo.subprocess, "run", compose_run)

    projects = []
    for _ in range(2):
        calls.clear()
        assert demo.uc2_lifecycle(require_docker=True) == "PASS"
        project = calls[0][3]
        assert project.startswith("gsmf-a3-demo-")
        prefix = ["docker", "compose", "--project-name", project, "-f", str(compose_file)]
        assert calls == [
            prefix + ["build"],
            prefix + ["up", "-d"],
            prefix + ["ps", "--all", "--format", "json"],
            prefix + ["down", "--remove-orphans"],
            prefix + ["ps", "--all", "--quiet"],
        ]
        assert f"project={project}, compose_file={compose_file}" in capsys.readouterr().out
        projects.append(project)

    assert projects[0] != projects[1]
