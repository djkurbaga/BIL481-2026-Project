"""UC1 — Kıyaslama yapılandırması (FR-1). ARAYÜZ TASLAĞI.

Bu dosya yalnızca imzaları ve sözleşmeyi içerir; gövdeler UC1 sorumlusu
tarafından doldurulacaktır. İmzalar değiştirilmeden önce ekipçe karar
verilmelidir çünkü diğer modüller bunlara göre yazılır.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from gsmf.models import BenchmarkConfig, ConfigError  # noqa: F401  (sözleşmede kullanılır)


def load_config(path: Path) -> BenchmarkConfig:
    """YAML yapılandırma dosyasını okuyup doğrulanmış nesneye çevirir.

    Dosyayı okur, ``validate_config`` ile doğrular ve sonucu döndürür.
    Herhangi bir platform yığını başlatılmadan önce çağrılmalıdır.

    Args:
        path: YAML yapılandırma dosyasının yolu.

    Returns:
        Doğrulanmış ``BenchmarkConfig`` nesnesi.

    Raises:
        ConfigError: Dosya bulunamazsa, YAML bozuksa veya doğrulama başarısızsa.
    """
    raise NotImplementedError("UC1: load_config henüz uygulanmadı")


def validate_config(raw: Mapping[str, Any]) -> BenchmarkConfig:
    """Ham (sözlük) yapılandırmayı FR-1 kurallarına göre doğrular.

    Kurallar:
        - Zorunlu alanlar eksik olmamalıdır.
        - Hedefler yalnızca ``PlatformKind`` değerlerinden olabilir.
        - workload_size, concurrency, repetitions pozitif tam sayı olmalıdır.
        - cooldown_s negatif olmamalıdır.

    Args:
        raw: YAML'dan okunmuş ham sözlük.

    Returns:
        Doğrulanmış ``BenchmarkConfig`` nesnesi.

    Raises:
        ConfigError: Açıklayıcı mesajla, ilk bulunan kural ihlalinde.
    """
    raise NotImplementedError("UC1: validate_config henüz uygulanmadı")
