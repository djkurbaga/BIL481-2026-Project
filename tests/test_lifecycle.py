"""UC2 durum geçişlerini Docker olmadan, enjekte edilmiş süreçlerle sınar."""

from contextlib import nullcontext
from dataclasses import replace
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from urllib.error import URLError

import pytest

import gsmf.lifecycle as lifecycle
from gsmf.lifecycle import StackManager, isolated_stack
from gsmf.models import ExecutionFailure, PlatformKind, StackState, TargetPlatform


RUNNING = json.dumps([{"State": "running", "Health": "healthy"}])


class FakeRunner:
    """Sıralı yanıtları döndürür; bütün komutları ve süre sınırlarını kaydeder."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        assert self.responses, f"Beklenmeyen komut: {command}"
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if isinstance(response, subprocess.CompletedProcess):
            return response
        return subprocess.CompletedProcess(command, 0, stdout=response, stderr="")


@pytest.fixture
def target():
    """Boşluk içeren Compose yoluyla kabuksuz çağrıyı da sınar."""
    return TargetPlatform(
        PlatformKind.FASTAPI, Path("/tmp/demo stack/compose.yml"),
        "http://localhost:8000", "http://localhost:8000/health", 1.0,
    )


@pytest.fixture
def manager():
    """Varsayılan komut imzasını kullanan boş bir yönetici oluşturur."""
    return StackManager()


@pytest.fixture
def healthy_http(monkeypatch):
    """Gerçek ağa çıkmadan başarılı sağlık yanıtı verir."""
    calls = []

    def get(url, timeout):
        calls.append((url, timeout))
        return nullcontext(SimpleNamespace(status=200))

    monkeypatch.setattr(lifecycle, "urlopen", get)
    return calls


@pytest.fixture
def clock(monkeypatch):
    """Beklemeleri sanal saatte ilerleterek zaman aşımını hızlı ve kesin sınar."""
    value = SimpleNamespace(now=0.0)

    def sleep(seconds):
        value.now += seconds

    monkeypatch.setattr(lifecycle, "time", SimpleNamespace(
        monotonic=lambda: value.now, sleep=sleep,
    ))
    return value


def test_full_lifecycle(manager, target, healthy_http):
    runner = FakeRunner("", RUNNING, "", "")
    manager.runner = runner
    assert manager.state is StackState.STOPPED
    manager.start(target)
    assert manager.state is StackState.STARTING
    manager.wait_until_healthy(target, 1.0)
    assert manager.state is StackState.HEALTHY
    manager.mark_running()
    assert manager.state is StackState.RUNNING
    manager.stop(target)
    assert manager.state is StackState.STOPPED
    prefix = ["docker", "compose", "-f", str(target.compose_file)]
    assert [call[0] for call in runner.calls] == [
        prefix + ["up", "-d"], prefix + ["ps", "--all", "--format", "json"],
        prefix + ["down", "--remove-orphans"], prefix + ["ps", "--all", "--quiet"],
    ]
    assert all(call[1]["timeout"] > 0 for call in runner.calls)
    assert all("shell" not in call[1] for call in runner.calls)
    assert healthy_http[0][0] == target.health_url


@pytest.mark.parametrize("output", [
    RUNNING, '{"State":"running","Health":""}',
    '{"State":"running"}\n{"State":"running","Health":"healthy"}\n',
])
def test_compose_json_formats(manager, target, healthy_http, output):
    manager.runner = FakeRunner("", output)
    manager.start(target)
    manager.wait_until_healthy(target, 1.0)
    assert manager.state is StackState.HEALTHY


def test_next_target_only_after_shutdown(manager, target):
    manager.runner = FakeRunner("", "", "", "")
    manager.start(target)
    manager.stop(target)
    manager.start(replace(target, kind=PlatformKind.BUDIBASE))
    assert manager.state is StackState.STARTING


def test_custom_compose_command(target):
    manager = StackManager(("custom-compose",))
    runner = FakeRunner("")
    manager.runner = runner
    manager.start(target)
    assert runner.calls[0][0][0] == "custom-compose"


def test_stop_is_idempotent(manager, target):
    runner = FakeRunner("", "", "")
    manager.runner = runner
    manager.stop(target)
    manager.start(target)
    manager.stop(target)
    manager.stop(target)
    assert len(runner.calls) == 3
