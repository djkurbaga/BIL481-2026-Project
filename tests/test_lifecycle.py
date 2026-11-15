"""UC2 durum geçişlerini Docker olmadan, enjekte edilmiş süreçlerle sınar."""

from contextlib import nullcontext
from dataclasses import replace
from http.client import BadStatusLine
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


@pytest.mark.parametrize("timeout", [0, -1, True, "1", float("nan"), float("inf"), 10**400])
def test_invalid_timeout(manager, target, timeout):
    manager.runner = FakeRunner("")
    manager.start(target)
    with pytest.raises(ExecutionFailure, match="timeout_s"):
        manager.wait_until_healthy(target, timeout)


@pytest.mark.parametrize("failure", [URLError("bağlantı yok"), TimeoutError("bekleme doldu"), BadStatusLine("bozuk HTTP")])
def test_http_failure_times_out(manager, target, monkeypatch, clock, failure):
    manager.runner = FakeRunner("", RUNNING, RUNNING)

    def unavailable(url, timeout):
        assert 0 < timeout <= 0.5 - clock.now
        raise failure

    monkeypatch.setattr(lifecycle, "urlopen", unavailable)
    manager.start(target)
    with pytest.raises(ExecutionFailure, match="zaman aşımı"):
        manager.wait_until_healthy(target, 0.5)
    assert clock.now == 0.5
    assert manager.state is StackState.FAILED


def test_http_error_then_recovery(manager, target, monkeypatch, clock):
    manager.runner = FakeRunner("", RUNNING, RUNNING)
    responses = iter([503, 204])
    monkeypatch.setattr(lifecycle, "urlopen", lambda *args, **kwargs: nullcontext(
        SimpleNamespace(status=next(responses)),
    ))
    manager.start(target)
    manager.wait_until_healthy(target, 1)
    assert manager.state is StackState.HEALTHY
    assert clock.now == 0.25


def test_container_health_must_pass_before_http(manager, target, healthy_http, clock):
    manager.runner = FakeRunner("", '[{"State":"running","Health":"starting"}]', RUNNING)
    manager.start(target)
    manager.wait_until_healthy(target, 1)
    assert len(healthy_http) == 1
    assert clock.now == 0.25


def test_late_http_success_is_rejected(manager, target, monkeypatch, clock):
    manager.runner = FakeRunner("", RUNNING)

    def late_response(url, timeout):
        clock.now += 2
        return nullcontext(SimpleNamespace(status=200))

    monkeypatch.setattr(lifecycle, "urlopen", late_response)
    manager.start(target)
    with pytest.raises(ExecutionFailure, match="zaman aşımı"):
        manager.wait_until_healthy(target, 1)


def test_compose_poll_is_bounded_by_health_deadline(manager, target, clock):
    runner = FakeRunner("", subprocess.TimeoutExpired("ps", 0.1))
    manager.runner = runner
    manager.start(target)
    with pytest.raises(ExecutionFailure, match="Komut"):
        manager.wait_until_healthy(target, 0.1)
    assert runner.calls[-1][1]["timeout"] == 0.1


def test_context_cleans_up_normal_exit(manager, target, healthy_http):
    manager.runner = FakeRunner("", RUNNING, "", "")
    with isolated_stack(manager, target) as current:
        assert current is manager
        assert manager.state is StackState.HEALTHY
        manager.mark_running()
    assert manager.state is StackState.STOPPED


def test_context_cleans_up_workload_failure(manager, target, healthy_http):
    manager.runner = FakeRunner("", RUNNING, "", "")
    with pytest.raises(RuntimeError, match="iş yükü"):
        with isolated_stack(manager, target):
            raise RuntimeError("iş yükü başarısız")
    assert manager.state is StackState.STOPPED


@pytest.mark.parametrize("responses", [
    [subprocess.CompletedProcess("up", 1, "", "kısmi başlatma"), "", ""],
    ["", "[]", "", ""],
])
def test_context_cleans_up_start_and_health_failure(manager, target, responses):
    runner = FakeRunner(*responses)
    manager.runner = runner
    with pytest.raises(ExecutionFailure):
        with isolated_stack(manager, target):
            pytest.fail("Başarısız yığında iş yüküne geçilmemeli")
    assert runner.calls[-2][0][-2:] == ["down", "--remove-orphans"]
    assert manager.state is StackState.STOPPED


def test_cleanup_failure_preserves_original_exception(manager, target, healthy_http):
    manager.runner = FakeRunner(
        "", RUNNING, subprocess.CompletedProcess("down", 1, "", "kapanış hatası"),
    )
    with pytest.raises(ExecutionFailure, match="kapanış hatası") as caught:
        with isolated_stack(manager, target):
            raise RuntimeError("asıl iş yükü hatası")
    assert isinstance(caught.value.__context__, RuntimeError)
    assert manager.state is StackState.FAILED


def test_nested_context_does_not_stop_outer_stack(manager, target, healthy_http):
    runner = FakeRunner("", RUNNING, "", "")
    manager.runner = runner
    with isolated_stack(manager, target):
        with pytest.raises(ExecutionFailure, match="boş"):
            with isolated_stack(manager, target):
                pytest.fail("İç içe yığın açılmamalı")
        assert len(runner.calls) == 2
        assert manager.state is StackState.HEALTHY
    assert manager.state is StackState.STOPPED


def test_context_cleans_up_keyboard_interrupt(manager, target, healthy_http):
    manager.runner = FakeRunner("", RUNNING, "", "")
    with pytest.raises(KeyboardInterrupt):
        with isolated_stack(manager, target):
            raise KeyboardInterrupt
    assert manager.state is StackState.STOPPED
