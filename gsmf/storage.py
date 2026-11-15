"""UC4 — Sonuçların kalıcı saklanması ve dışa aktarımı (FR-11). ARAYÜZ TASLAĞI.

Bu dosya yalnızca imzaları ve sözleşmeyi içerir; gövdeler UC4 sorumlusu
tarafından doldurulacaktır. Saklanan ölçülen değerler sonradan değiştirilmez.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

from gsmf.models import (  # noqa: F401  (sözleşmede kullanılır)
    BenchmarkConfig,
    EfficiencyMetrics,
    PlatformKind,
    RepetitionRecord,
    StorageError,
    TestbedSettings,
)


class ResultStore:
    """SQLite tabanlı sonuç deposu."""

    def __init__(self, db_path: Path) -> None:
        """Depoyu verilen SQLite dosyasıyla ilişkilendirir.

        Args:
            db_path: SQLite veritabanı dosyasının yolu (yoksa oluşturulur).
        """
        raise NotImplementedError("UC4: ResultStore.__init__ henüz uygulanmadı")

    def initialize_schema(self) -> None:
        """Gerekli tabloları (runs, repetitions, metrics) yoksa oluşturur."""
        raise NotImplementedError("UC4: initialize_schema henüz uygulanmadı")

    def save_run(
        self,
        run_id: str,
        config: BenchmarkConfig,
        target_versions: Mapping[PlatformKind, str],
        testbed: TestbedSettings,
    ) -> None:
        """Bir çalıştırmanın yapılandırmasını, hedef sürümlerini ve testbed ayarlarını kaydeder.

        Raises:
            StorageError: Aynı run_id zaten varsa veya yazma başarısızsa.
        """
        raise NotImplementedError("UC4: save_run henüz uygulanmadı")

    def save_repetition(self, record: RepetitionRecord) -> None:
        """Bir tekrar kaydını (başarısız/geçersiz olanlar dahil) ekler.

        Yalnızca ekleme yapılır; var olan bir kayıt güncellenmez.

        Raises:
            StorageError: Kayıt zaten varsa veya yazma başarısızsa.
        """
        raise NotImplementedError("UC4: save_repetition henüz uygulanmadı")

    def save_metrics(self, metrics: Iterable[EfficiencyMetrics]) -> None:
        """Hesaplanan metrikleri ham kayıtlardan ayrı bir tabloya yazar.

        Raises:
            StorageError: Yazma başarısızsa.
        """
        raise NotImplementedError("UC4: save_metrics henüz uygulanmadı")

    def load_repetitions(self, run_id: str) -> list[RepetitionRecord]:
        """Bir çalıştırmanın tüm tekrar kayıtlarını sırasıyla döndürür."""
        raise NotImplementedError("UC4: load_repetitions henüz uygulanmadı")

    def export_raw_csv(self, run_id: str, out_path: Path) -> Path:
        """Ham tekrar kayıtlarını CSV dosyasına yazar ve dosya yolunu döndürür.

        Raises:
            StorageError: run_id bulunamazsa veya dosya yazılamazsa.
        """
        raise NotImplementedError("UC4: export_raw_csv henüz uygulanmadı")

    def export_aggregates_csv(self, run_id: str, out_path: Path) -> Path:
        """Hedef bazında toplu sonuçları CSV dosyasına yazar ve dosya yolunu döndürür.

        Raises:
            StorageError: run_id bulunamazsa veya dosya yazılamazsa.
        """
        raise NotImplementedError("UC4: export_aggregates_csv henüz uygulanmadı")
