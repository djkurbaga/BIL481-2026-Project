"""UC2 — İzole yığın yaşam döngüsü yönetimi (FR-3). ARAYÜZ TASLAĞI.

Bu dosya yalnızca imzaları ve sözleşmeyi içerir; gövdeler UC2 sorumlusu
tarafından doldurulacaktır. Aynı anda yalnızca bir hedef yığın çalışabilir.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from gsmf.models import ExecutionFailure, StackState, TargetPlatform  # noqa: F401


class StackManager:
    """Docker Compose ile tek bir hedef yığını başlatır, izler ve durdurur.

    Durum makinesi: STARTING → HEALTHY → RUNNING → STOPPING → STOPPED;
    herhangi bir adımda hata olursa FAILED. Önceki yığının kapandığı
    doğrulanmadan yeni yığın başlatılmaz.
    """

    def __init__(self, compose_command: tuple[str, ...] = ("docker", "compose")) -> None:
        """Yöneticiyi oluşturur.

        Args:
            compose_command: Docker Compose'u çağıran komut parçaları.
        """
        raise NotImplementedError("UC2: StackManager.__init__ henüz uygulanmadı")

    @property
    def state(self) -> StackState:
        """Yönetilen yığının mevcut durumunu döndürür."""
        raise NotImplementedError("UC2: StackManager.state henüz uygulanmadı")

    def start(self, target: TargetPlatform) -> None:
        """Hedef yığını ``docker compose up -d`` ile başlatır (durum: STARTING).

        Raises:
            ExecutionFailure: Başka bir yığın hâlâ çalışıyorsa veya başlatma başarısızsa.
        """
        raise NotImplementedError("UC2: StackManager.start henüz uygulanmadı")

    def wait_until_healthy(self, target: TargetPlatform, timeout_s: float) -> None:
        """Sağlık kontrolü geçene kadar bekler (durum: HEALTHY).

        Args:
            target: Beklenen hedef.
            timeout_s: En fazla bekleme süresi (s).

        Raises:
            ExecutionFailure: Süre dolarsa veya yığın çökerse (durum: FAILED).
        """
        raise NotImplementedError("UC2: StackManager.wait_until_healthy henüz uygulanmadı")

    def mark_running(self) -> None:
        """İş yükü başladığında durumu HEALTHY'den RUNNING'e geçirir.

        Raises:
            ExecutionFailure: Yığın HEALTHY durumunda değilse.
        """
        raise NotImplementedError("UC2: StackManager.mark_running henüz uygulanmadı")

    def stop(self, target: TargetPlatform) -> None:
        """Yığını ``docker compose down`` ile durdurur ve kapanışı doğrular.

        Durum STOPPING → STOPPED olur. Kapanış doğrulanmadan dönmez.

        Raises:
            ExecutionFailure: Kapatma başarısızsa veya doğrulanamazsa (durum: FAILED).
        """
        raise NotImplementedError("UC2: StackManager.stop henüz uygulanmadı")


@contextmanager
def isolated_stack(manager: StackManager, target: TargetPlatform) -> Iterator[StackManager]:
    """Yığını başlatıp sağlıklı olmasını bekleyen, çıkışta her durumda durduran bağlam yöneticisi.

    Kullanım::

        with isolated_stack(manager, target):
            ...  # ölçüm

    Raises:
        ExecutionFailure: Başlatma, sağlık kontrolü veya kapatma başarısızsa.
    """
    raise NotImplementedError("UC2: isolated_stack henüz uygulanmadı")
    yield manager  # pragma: no cover  (üreteç imzasını korumak için)
