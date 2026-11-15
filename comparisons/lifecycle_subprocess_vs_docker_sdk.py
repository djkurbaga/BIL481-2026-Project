"""Aynı FastAPI imajının gerçek Compose ve Docker SDK yaşam döngülerini karşılaştırır.

İmaj önceden oluşturulmalıdır. Sonuçlar enerji ölçümü veya istatistiksel
üstünlük iddiası değildir; derleme ve istemci hazırlığı süreye dahil değildir.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from uuid import uuid4

# Betik doğrudan çalıştırıldığında da depo paketini bulabilsin.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsmf.config import load_config
from gsmf.health import http_status
from gsmf.lifecycle import StackManager
from gsmf.models import ExecutionFailure, TargetPlatform


IMAGE = "gsmf-fastapi-baseline:demo"


def cli(*args: str) -> str:
    """Docker ön kontrollerini sonlu süreyle çalıştırır; başarısız çıktıyı saklar."""
    return subprocess.run(
        ["docker", *args], check=True, capture_output=True, text=True, timeout=30,
    ).stdout.strip()


def make_sdk_client():
    """SDK ve Compose'un aynı Docker sunucusunu kullanmasını sağlar."""
    import docker

    if os.environ.get("DOCKER_HOST") and not os.environ.get("DOCKER_CONTEXT"):
        return docker.from_env(timeout=10)
    command = ["context", "inspect"]
    if os.environ.get("DOCKER_CONTEXT"):
        command.append(os.environ["DOCKER_CONTEXT"])
    endpoint = cli(*command, "--format", "{{.Endpoints.docker.Host}}")
    return docker.DockerClient(base_url=endpoint, timeout=10)


class SDKBaseline:
    """Yalnızca depodaki tek servisli baseline için SDK karşılığıdır; Compose ayrıştırmaz."""

    def __init__(self, client, name: str) -> None:
        """Bu çalıştırmaya özgü adı ve temizlenecek konteyneri saklar."""
        self.client = client
        self.name = name
        self.container = None

    def start(self, target: TargetPlatform) -> None:
        """Aynı imajı, portu ve imajdaki sağlık kontrolünü kullanır."""
        # Önce create kullanmak, start başarısız olsa da temizliği mümkün kılar.
        self.container = self.client.containers.create(
            IMAGE, name=self.name, detach=True,
            ports={"8000/tcp": ("127.0.0.1", 8000)},
            labels={"gsmf.lifecycle-comparison": self.name},
        )
        self.container.start()

    def wait_until_healthy(self, target: TargetPlatform, timeout_s: float) -> None:
        """İmajın sağlık kontrolünü ve aynı HTTP adresini bekler."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            # SDK istek süresi de kalan toplam süreyi aşmamalıdır.
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            self.client.api.timeout = min(10.0, remaining)
            self.container.reload()
            state = self.container.attrs["State"]
            health = state.get("Health", {}).get("Status", "")
            if state["Status"] in {"exited", "dead"} or health == "unhealthy":
                raise ExecutionFailure(f"SDK konteyneri sağlıksız: {state}")
            remaining = deadline - time.monotonic()
            if state["Status"] == "running" and health in ("", "healthy") and remaining > 0:
                try:
                    status = http_status(target.health_url, timeout=min(5.0, remaining))
                    if 200 <= status < 300 and time.monotonic() < deadline:
                        return
                except (OSError, ValueError):
                    pass
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(0.25, remaining))
        raise ExecutionFailure("SDK sağlık kontrolü zaman aşımı")

    def stop(self, target: TargetPlatform) -> None:
        """Yalnızca bu denemenin konteynerlerini kapatır ve silindiğini doğrular."""
        self.client.api.timeout = 30
        # Create yanıtı kaybolsa bile etiketten bulunan kısmi kaynakları temizle.
        filters = {"label": f"gsmf.lifecycle-comparison={self.name}"}
        for container in self.client.containers.list(all=True, filters=filters):
            container.stop(timeout=10)
            container.remove()
        if self.client.containers.list(all=True, filters=filters):
            raise ExecutionFailure("SDK kapanışı doğrulanamadı")


def measure(backend: str, manager, target: TargetPlatform) -> dict:
    """Her aşamanın gerçek süresini ve hata varsa hata metnini döndürür."""
    row = {"backend": backend, "status": "ok", "shutdown_confirmed": False}
    started = time.perf_counter()
    try:
        for field, operation in (
            ("start_s", lambda: manager.start(target)),
            ("health_s", lambda: manager.wait_until_healthy(target, target.health_timeout_s)),
        ):
            phase = time.perf_counter()
            try:
                operation()
            finally:
                row[field] = round(time.perf_counter() - phase, 6)
    except Exception as exc:
        row.update(status="failed", error=f"{type(exc).__name__}: {exc}")
    finally:
        phase = time.perf_counter()
        try:
            manager.stop(target)
            row["shutdown_confirmed"] = True
        except Exception as exc:
            row.update(status="failed", shutdown_error=f"{type(exc).__name__}: {exc}")
        row["stop_s"] = round(time.perf_counter() - phase, 6)
        row["total_s"] = round(time.perf_counter() - started, 6)
    return row


def main(argv: list[str] | None = None) -> int:
    """Gerçek denemeleri sırayla çalıştırır; kapanış doğrulanamazsa devam etmez."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=1)
    args = parser.parse_args(argv)
    if args.repetitions <= 0:
        parser.error("--repetitions pozitif olmalıdır")
    client = None
    try:
        import docker

        target = load_config(ROOT / "examples/benchmark.yaml").targets[0]
        metadata = {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "host": platform.platform(), "python": platform.python_version(),
            "compose": cli("compose", "version", "--short"),
            "engine": cli("version", "--format", "{{.Server.Version}}"),
            "sdk": docker.__version__,
            "image_id": cli("image", "inspect", IMAGE, "--format", "{{.Id}}"),
            "build_included": False,
        }
        client = make_sdk_client()
        print(json.dumps({"environment": metadata}, ensure_ascii=False), flush=True)
        failed = False
        for repetition in range(1, args.repetitions + 1):
            name = f"gsmf-compare-{uuid4().hex[:12]}"
            managers = [
                ("subprocess_compose", StackManager(("docker", "compose", "-p", name))),
                ("docker_sdk", SDKBaseline(client, name + "-sdk")),
            ]
            # Sıra etkisini azaltmak için çift tekrarlarda SDK'yı önce çalıştır.
            if repetition % 2 == 0:
                managers.reverse()
            for backend, manager in managers:
                row = measure(backend, manager, target)
                print(json.dumps({"repetition": repetition, **row}, ensure_ascii=False), flush=True)
                failed = failed or row["status"] != "ok"
                if not row["shutdown_confirmed"]:
                    return 1
        return int(failed)
    except Exception as exc:
        detail = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        print(json.dumps({"status": "failed", "error": f"{type(exc).__name__}: {detail}"}, ensure_ascii=False))
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
