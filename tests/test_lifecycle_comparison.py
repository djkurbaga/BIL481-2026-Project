"""Karşılaştırmanın hata raporlamasını ve temizlik zorunluluğunu sınar."""

import json
import sys
from types import SimpleNamespace

import pytest

from comparisons import lifecycle_subprocess_vs_docker_sdk as comparison
from gsmf.models import ExecutionFailure


class FakeManager:
    """Aşama hatalarını Docker olmadan üretir."""

    def __init__(self, fail_at=None):
        self.fail_at = fail_at
        self.calls = []

    def perform(self, step):
        self.calls.append(step)
        if step == self.fail_at:
            raise ExecutionFailure(f"{step} hatası")

    def start(self, target):
        self.perform("start")

    def wait_until_healthy(self, target, timeout):
        self.perform("health")

    def stop(self, target):
        self.perform("stop")


def test_measure_success_reports_only_completed_phases():
    manager = FakeManager()
    row = comparison.measure("test", manager, SimpleNamespace(health_timeout_s=1))
    assert row["status"] == "ok"
    assert row["shutdown_confirmed"] is True
    assert manager.calls == ["start", "health", "stop"]
    assert all(row[field] >= 0 for field in ("start_s", "health_s", "stop_s", "total_s"))


@pytest.mark.parametrize("phase", ["start", "health", "stop"])
def test_measure_failure_still_attempts_shutdown(phase):
    manager = FakeManager(phase)
    row = comparison.measure("test", manager, SimpleNamespace(health_timeout_s=1))
    assert row["status"] == "failed"
    assert row["shutdown_confirmed"] is (phase != "stop")
    assert manager.calls[-1] == "stop"
    assert phase in row.get("error", row.get("shutdown_error"))
    if phase == "start":
        assert "health_s" not in row


def test_sdk_shutdown_finds_partial_create_by_own_label():
    calls = []
    container = SimpleNamespace(
        stop=lambda **kwargs: calls.append(("stop", kwargs)),
        remove=lambda: calls.append(("remove", {})),
    )
    results = iter([[container], []])

    def containers(**kwargs):
        assert kwargs == {"all": True, "filters": {"label": "gsmf.lifecycle-comparison=test-run"}}
        return next(results)

    client = SimpleNamespace(api=SimpleNamespace(timeout=1), containers=SimpleNamespace(list=containers))
    baseline = comparison.SDKBaseline(client, "test-run")
    baseline.stop(None)
    assert calls == [("stop", {"timeout": 10}), ("remove", {})]


def test_sdk_shutdown_must_be_confirmed():
    container = SimpleNamespace(stop=lambda **kwargs: None, remove=lambda: None)
    client = SimpleNamespace(
        api=SimpleNamespace(timeout=1),
        containers=SimpleNamespace(list=lambda **kwargs: [container]),
    )
    with pytest.raises(ExecutionFailure, match="kapanışı"):
        comparison.SDKBaseline(client, "test-run").stop(None)


def test_main_aborts_after_unconfirmed_shutdown(monkeypatch, capsys):
    closed = []
    client = SimpleNamespace(close=lambda: closed.append(True))
    monkeypatch.setitem(sys.modules, "docker", SimpleNamespace(__version__="test"))
    monkeypatch.setattr(comparison, "cli", lambda *args: "test")
    monkeypatch.setattr(comparison, "make_sdk_client", lambda: client)
    calls = []

    def measure(backend, manager, target):
        calls.append(backend)
        return {"backend": backend, "status": "failed", "shutdown_confirmed": False}

    monkeypatch.setattr(comparison, "measure", measure)
    assert comparison.main(["--repetitions", "3"]) == 1
    assert calls == ["subprocess_compose"]
    assert closed == [True]
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(rows) == 2
    assert rows[-1]["status"] == "failed"


def test_missing_dependency_is_reported(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "docker", None)
    assert comparison.main([]) == 1
    row = json.loads(capsys.readouterr().out)
    assert row["status"] == "failed"
    assert "ModuleNotFoundError" in row["error"]
