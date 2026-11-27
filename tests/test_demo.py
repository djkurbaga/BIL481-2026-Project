"""Assignment 3 demosunun CI ve yerel kullanım davranışını sınar."""

import pytest

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
