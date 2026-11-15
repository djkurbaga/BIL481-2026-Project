"""Gerçek HTTP yanıtlarıyla toplam sağlık süresini Docker olmadan sınar."""

from pathlib import Path
import socketserver
import subprocess
import threading
import time
from types import SimpleNamespace

import pytest

from comparisons.lifecycle_subprocess_vs_docker_sdk import SDKBaseline
import gsmf.health as health
from gsmf.lifecycle import StackManager, isolated_stack
from gsmf.models import ExecutionFailure, PlatformKind, StackState, TargetPlatform


@pytest.fixture
def http_server(monkeypatch):
    """Yavaş başlıklar veya normal durum yanıtları üreten yerel sunucu açar."""
    stopped = threading.Event()
    disconnected = threading.Event()
    requested = threading.Event()
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")

    class Handler(socketserver.BaseRequestHandler):
        """Soket bekleme süresini aşmadan uzun süre veri gönderir."""

        def handle(self):
            self.request.settimeout(2)
            try:
                request = self.request.recv(4096)
                requested.set()
                if b"GET /slow " in request:
                    self.request.sendall(b"HTTP/1.1 200 OK\r\n")
                    for index in range(60):
                        self.request.sendall(f"X-Slow-{index}: value\r\n".encode())
                        if stopped.wait(0.03):
                            return
                    self.request.sendall(b"Content-Length: 0\r\n\r\n")
                elif b"GET /malformed " in request:
                    self.request.sendall(b"invalid HTTP response\r\n")
                else:
                    status = b"503 Unavailable" if b"GET /unavailable " in request else b"200 OK"
                    self.request.sendall(b"HTTP/1.1 " + status + b"\r\nContent-Length: 0\r\n\r\n")
            except OSError:
                disconnected.set()

    class Server(socketserver.ThreadingTCPServer):
        """Test çıkışında tüm bağlantı iş parçacıklarının bitmesini bekler."""

        allow_reuse_address = True

    with Server(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
        thread.start()
        try:
            yield SimpleNamespace(
                url=f"http://127.0.0.1:{server.server_address[1]}",
                disconnected=disconnected, requested=requested,
            )
        finally:
            stopped.set()
            server.shutdown()
            thread.join(timeout=2)


def target_for(server, path="/slow"):
    """Yerel HTTP sunucusuna yönelen kısa süreli hedef oluşturur."""
    return TargetPlatform(
        PlatformKind.FASTAPI, Path("/tmp/unused-compose.yml"),
        server.url, server.url + path, 0.35,
    )


def compose_manager():
    """Yalnızca Docker çağrılarını taklit eder; HTTP isteği gerçektir."""
    manager = StackManager()
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        output = '[{"State":"running","Health":"healthy"}]' if "--format" in command else ""
        return subprocess.CompletedProcess(command, 0, output, "")

    manager.runner = runner
    return manager, calls


@pytest.mark.parametrize("backend", ["compose", "sdk"])
def test_slow_headers_respect_total_deadline(http_server, backend, monkeypatch):
    processes = []
    original_popen = subprocess.Popen

    def track_process(*args, **kwargs):
        process = original_popen(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(health.subprocess, "Popen", track_process)
    target = target_for(http_server)
    if backend == "compose":
        manager, _ = compose_manager()
        manager.start(target)
    else:
        manager = SDKBaseline(SimpleNamespace(api=SimpleNamespace(timeout=1)), "test")
        manager.container = SimpleNamespace(
            reload=lambda: None, attrs={"State": {"Status": "running", "Health": {"Status": "healthy"}}},
        )
    started = time.monotonic()
    with pytest.raises(ExecutionFailure, match="zaman aşımı"):
        manager.wait_until_healthy(target, target.health_timeout_s)
    elapsed = time.monotonic() - started
    assert http_server.requested.is_set(), "Regresyon testi gerçek HTTP isteğini çalıştırmalı"
    # Süreç başlatma ve işletim sistemi zamanlaması için pay bırak; eski davranış ~1,8 s sürer.
    assert elapsed < 0.8, f"Toplam süre sınırı aşıldı: {elapsed:.3f} s"
    assert http_server.disconnected.wait(0.4), "Süre dolduktan sonra HTTP bağlantısı açık kaldı"
    assert len(processes) == 1
    assert processes[0].poll() is not None, "HTTP alt süreci sonlandırılıp toplanmalı"
    if backend == "compose":
        assert manager.state is StackState.FAILED


def test_timeout_closes_http_before_stack_cleanup(http_server):
    target = target_for(http_server)
    manager, calls = compose_manager()
    started = time.monotonic()
    with pytest.raises(ExecutionFailure, match="zaman aşımı"):
        with isolated_stack(manager, target):
            pytest.fail("Yavaş sağlık yanıtıyla iş yükü başlamamalı")
    assert time.monotonic() - started < 0.8
    assert manager.state is StackState.STOPPED
    assert calls[-2][-2:] == ["down", "--remove-orphans"]
    assert calls[-1][-3:] == ["ps", "--all", "--quiet"]


@pytest.mark.parametrize("path, expected", [("/ok", 200), ("/unavailable", 503)])
def test_http_probe_returns_real_status(http_server, path, expected):
    assert health.http_status(http_server.url + path, timeout=2) == expected


def test_http_probe_reports_protocol_failure(http_server):
    with pytest.raises(OSError, match="HTTP sağlık kontrolü başarısız"):
        health.http_status(http_server.url + "/malformed", timeout=2)


def test_expired_budget_does_not_start_process(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Süresi dolmuş yoklama için süreç açılmamalı")

    monkeypatch.setattr(health.subprocess, "run", unexpected)
    with pytest.raises(TimeoutError, match="zaman aşımı"):
        health.http_status("http://127.0.0.1/health", timeout=0)
