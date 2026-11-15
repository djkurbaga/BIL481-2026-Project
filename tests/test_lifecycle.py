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


@pytest.mark.parametrize("failure", [
    FileNotFoundError("docker bulunamadı"),
    subprocess.TimeoutExpired("docker", 1),
    subprocess.CompletedProcess("docker", 1, "", "başlatma hatası"),
])
def test_start_failure_blocks_next_target_until_cleanup(manager, target, failure):
    runner = FakeRunner(failure, "", "", "")
    manager.runner = runner
    with pytest.raises(ExecutionFailure, match="Komut"):
        manager.start(target)
    assert manager.state is StackState.FAILED
    with pytest.raises(ExecutionFailure, match="kapanışı"):
        manager.start(replace(target, kind=PlatformKind.APPSMITH))
    assert len(runner.calls) == 1
    manager.stop(target)
    manager.start(target)
    assert manager.state is StackState.STARTING


@pytest.mark.parametrize("responses", [
    [subprocess.CompletedProcess("down", 1, "", "kapatılamadı")],
    ["", "kalan-konteyner\n"],
    ["", subprocess.TimeoutExpired("ps", 1)],
    ["", subprocess.CompletedProcess("ps", 1, "", "erişim reddedildi")],
])
def test_shutdown_failure_blocks_next_target(manager, target, responses):
    runner = FakeRunner("", *responses)
    manager.runner = runner
    manager.start(target)
    with pytest.raises(ExecutionFailure):
        manager.stop(target)
    assert manager.state is StackState.FAILED
    count = len(runner.calls)
    with pytest.raises(ExecutionFailure, match="kapanışı"):
        manager.start(replace(target, kind=PlatformKind.APPSMITH))
    assert len(runner.calls) == count


@pytest.mark.parametrize("output", [
    "", "[]", '[{"State":"exited"}]', '[{"State":"dead"}]',
    '[{"State":"running","Health":"unhealthy"}]',
    'bozuk JSON', '{}', 'null', '[42]',
])
def test_crashed_or_unreadable_stack_fails(manager, target, output, healthy_http):
    manager.runner = FakeRunner("", output)
    manager.start(target)
    with pytest.raises(ExecutionFailure):
        manager.wait_until_healthy(target, 1)
    assert manager.state is StackState.FAILED
    assert healthy_http == []


def test_wrong_target_cannot_stop_active_stack(manager, target):
    runner = FakeRunner("", "", "")
    manager.runner = runner
    manager.start(target)
    with pytest.raises(ExecutionFailure, match="eşleşmiyor"):
        manager.stop(replace(target, kind=PlatformKind.APPSMITH))
    assert len(runner.calls) == 1
    manager.stop(target)
    assert manager.state is StackState.STOPPED


def test_mark_running_requires_health(manager, target):
    manager.runner = FakeRunner("")
    manager.start(target)
    with pytest.raises(ExecutionFailure, match="HEALTHY"):
        manager.mark_running()
    assert manager.state is StackState.FAILED


def test_double_start_does_not_issue_another_command(manager, target):
    runner = FakeRunner("")
    manager.runner = runner
    manager.start(target)
    with pytest.raises(ExecutionFailure, match="kapanışı"):
        manager.start(target)
    assert len(runner.calls) == 1
