"""UC2 — Tek bir yöneticide izole Docker Compose yaşam döngüsü (FR-3)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import json
import math
import subprocess
import time

from gsmf.health import http_status
from gsmf.models import ExecutionFailure, StackState, TargetPlatform


class StackManager:
    """Bir hedefi başlatır, sağlığını izler ve kapanışını doğrular.

    İmzaları korumak için komut çalıştırıcısı ``manager.runner = fake_run``
    ile enjekte edilir. Çalıştırıcı ``subprocess.run`` sözleşmesini izler.
    Aynı kıyaslamanın tüm hedefleri tek yönetici üzerinden yürütülmelidir.
    """

    def __init__(self, compose_command: tuple[str, ...] = ("docker", "compose")) -> None:
        """Compose komutunu ve dış süreçler için sonlu bekleme süresini ayarlar."""
        self.compose_command = compose_command
        self.runner = subprocess.run
        self.command_timeout_s = 120.0
        self._state = StackState.STOPPED
        self._target: TargetPlatform | None = None

    @property
    def state(self) -> StackState:
        """Yönetilen yığının mevcut durumunu döndürür."""
        return self._state

    def _fail(self, message: str) -> None:
        """Hata durumunu kaydeder; kapanmamış hedefin sahipliğini korur."""
        self._state = StackState.FAILED
        raise ExecutionFailure(message)

    def _run(self, target: TargetPlatform, *args: str, timeout: float | None = None) -> str:
        """Kabuk kullanmadan Compose çağırır ve süreç hatalarını raporlar."""
        command = [*self.compose_command, "-f", str(target.compose_file), *args]
        try:
            result = self.runner(
                command, capture_output=True, text=True, check=False,
                encoding="utf-8", errors="replace",
                timeout=self.command_timeout_s if timeout is None else timeout,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self._state = StackState.FAILED
            raise ExecutionFailure(f"Komut çalıştırılamadı ({' '.join(command)}): {exc}") from exc
        if result.returncode:
            self._fail(
                f"Komut başarısız ({' '.join(command)}), çıkış={result.returncode}: "
                f"{(result.stderr or result.stdout or '').strip()}"
            )
        return result.stdout or ""

    def _require_target(self, target: TargetPlatform) -> None:
        """Yanlış hedef üzerinde sağlık kontrolü veya kapatma yapılmasını engeller."""
        if self._target != target:
            self._fail("İşlem hedefi yöneticinin etkin hedefiyle eşleşmiyor")

    def start(self, target: TargetPlatform) -> None:
        """Yığını başlatır; önceki kapanış doğrulanmadıysa yeni hedefi reddeder."""
        if self._target is not None or self._state is not StackState.STOPPED:
            self._fail("Önceki yığının kapanışı doğrulanmadan yeni hedef başlatılamaz")
        # Kısmi başlatma hatasında bile hedefin sonradan temizlenebilmesini sağla.
        self._target = target
        self._state = StackState.STARTING
        self._run(target, "up", "-d")

    def _containers_ready(self, output: str) -> bool:
        """Compose sürümlerinin JSON dizisi ve JSON satırlarını okuyup çöküşü yakalar."""
        try:
            try:
                containers = json.loads(output)
            except json.JSONDecodeError:
                containers = [json.loads(line) for line in output.splitlines() if line.strip()]
            if isinstance(containers, dict):
                containers = [containers]
            if not isinstance(containers, list) or any(
                not isinstance(item, dict) or not isinstance(item.get("State"), str)
                for item in containers
            ):
                raise ValueError("konteyner durum alanları eksik")
        except (ValueError, TypeError) as exc:
            self._state = StackState.FAILED
            raise ExecutionFailure(f"Compose durum çıktısı çözümlenemedi: {exc}") from exc
        if not containers:
            self._fail("Yığın çöktü veya konteyner bulunamadı")
        for item in containers:
            if item["State"] in {"exited", "dead", "removing"} or item.get("Health") == "unhealthy":
                self._fail(f"Konteyner sağlıksız veya durmuş: {item}")
        return all(
            item["State"] == "running" and item.get("Health", "") in ("", "healthy")
            for item in containers
        )

    def wait_until_healthy(self, target: TargetPlatform, timeout_s: float) -> None:
        """Konteynerleri ve HTTP sağlık adresini sonlu süre boyunca yoklar."""
        self._require_target(target)
        if self._state is not StackState.STARTING:
            self._fail("Sağlık kontrolü yalnızca STARTING durumunda yapılabilir")
        try:
            valid = type(timeout_s) in (int, float) and math.isfinite(timeout_s) and timeout_s > 0
        except OverflowError:
            valid = False
        if not valid:
            self._fail("timeout_s sonlu ve pozitif bir sayı olmalıdır")
        deadline = time.monotonic() + timeout_s
        last_error = "Sağlık denetimi henüz geçmedi"
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            ready = self._containers_ready(self._run(
                target, "ps", "--all", "--format", "json",
                timeout=min(self.command_timeout_s, remaining),
            ))
            remaining = deadline - time.monotonic()
            if ready and remaining > 0:
                try:
                    status = http_status(target.health_url, timeout=min(5.0, remaining))
                    if 200 <= status < 300 and time.monotonic() < deadline:
                        self._state = StackState.HEALTHY
                        return
                    last_error = f"HTTP {status}"
                except (OSError, ValueError) as exc:
                    last_error = str(exc)
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(0.25, remaining))
        self._fail(f"Sağlık kontrolü zaman aşımı ({timeout_s} s, {target.health_url}): {last_error}")

    def mark_running(self) -> None:
        """İş yükünün yalnızca sağlıklı bir yığında başlamasına izin verir."""
        if self._state is not StackState.HEALTHY:
            self._fail("İş yükü yalnızca HEALTHY durumunda başlatılabilir")
        self._state = StackState.RUNNING

    def stop(self, target: TargetPlatform) -> None:
        """Yığını kapatır; durmuş konteynerler dahil hiçbir konteyner kalmadığını doğrular."""
        if self._target is None and self._state is StackState.STOPPED:
            return
        self._require_target(target)
        self._state = StackState.STOPPING
        self._run(target, "down", "--remove-orphans")
        remaining = self._run(target, "ps", "--all", "--quiet").strip()
        if remaining:
            self._fail(f"Yığın kapanışı doğrulanamadı; kalan konteynerler: {remaining}")
        self._target = None
        self._state = StackState.STOPPED


@contextmanager
def isolated_stack(manager: StackManager, target: TargetPlatform) -> Iterator[StackManager]:
    """Başlatma, sağlık veya iş yükü hatasında bile kendi yığınını kapatır.

    İç içe kullanım mevcut yığının sahipliğini devralmaz. Temizlik de hata
    verirse Python istisna zinciri asıl hatayı korur; yeni hedef engellenir.
    """
    if manager._target is not None or manager.state is not StackState.STOPPED:
        raise ExecutionFailure("Bağlam için boş ve kapanışı doğrulanmış yönetici gerekiyor")
    try:
        manager.start(target)
        manager.wait_until_healthy(target, target.health_timeout_s)
        yield manager
    finally:
        manager.stop(target)
