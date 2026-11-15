"""UC1 — YAML kıyaslama yapılandırmasını yükler ve doğrular (FR-1)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
import math
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from gsmf.models import BenchmarkConfig, ConfigError, PlatformKind, TargetPlatform


def _required(raw: Mapping[str, Any], fields: tuple[str, ...], location: str) -> None:
    """Eksik alanları ait oldukları bölümle birlikte bildirir."""
    missing = [field for field in fields if field not in raw]
    if missing:
        raise ConfigError(f"{location}: zorunlu alanlar eksik: {', '.join(missing)}")


def _text(value: Any, field: str) -> str:
    """Boş olmayan bir metin bekler."""
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{field}: boş olmayan bir metin olmalıdır")
    return value.strip()


def _number(value: Any, field: str, *, positive: bool = False) -> float:
    """Mantıksal değerleri ve sonlu olmayan sayıları reddeder."""
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
        valid = valid and (value > 0 if positive else value >= 0)
        if valid:
            return float(value)
    except OverflowError:
        pass
    boundary = "pozitif" if positive else "negatif olmayan"
    raise ConfigError(f"{field}: sonlu, {boundary} bir sayı olmalıdır")


def _url(value: Any, field: str) -> str:
    """Sağlık ve uygulama adreslerinde mutlak HTTP(S) adresi bekler."""
    value = _text(value, field)
    try:
        parsed = urlsplit(value)
        if parsed.scheme in ("http", "https") and parsed.hostname and not any(
            char.isspace() for char in value
        ):
            parsed.port  # Geçersiz portları da ayrıştırma sırasında yakala.
            return value
    except ValueError:
        pass
    raise ConfigError(f"{field}: geçerli bir HTTP(S) adresi olmalıdır")


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
    path = Path(path)
    try:
        with path.open(encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"Yapılandırma okunamadı ({path}): {exc}") from exc
    config = validate_config(raw)
    # Göreli Compose yolları çalışma dizinine değil YAML dosyasına bağlıdır.
    return replace(config, targets=tuple(
        replace(target, compose_file=(path.parent / target.compose_file).resolve())
        for target in config.targets
    ))


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
    if not isinstance(raw, Mapping):
        raise ConfigError("Yapılandırmanın kökü bir sözlük olmalıdır")
    _required(raw, (
        "title", "targets", "workload_size", "concurrency", "repetitions",
        "cooldown_s", "load_generator_host",
    ), "Yapılandırma")
    for field in ("workload_size", "concurrency", "repetitions"):
        if type(raw[field]) is not int or raw[field] <= 0:
            raise ConfigError(f"{field}: pozitif tam sayı olmalıdır")
    if not isinstance(raw["targets"], list) or not raw["targets"]:
        raise ConfigError("targets: en az bir hedef içeren liste olmalıdır")

    targets = []
    for index, item in enumerate(raw["targets"]):
        location = f"targets[{index}]"
        if not isinstance(item, Mapping):
            raise ConfigError(f"{location}: sözlük olmalıdır")
        _required(item, ("kind", "compose_file", "base_url", "health_url"), location)
        try:
            kind = PlatformKind(item["kind"])
        except (ValueError, TypeError) as exc:
            supported = ", ".join(kind.value for kind in PlatformKind)
            raise ConfigError(
                f"{location}.kind: desteklenmeyen hedef {item['kind']!r}; "
                f"desteklenenler: {supported}"
            ) from exc
        compose_file = _text(item["compose_file"], f"{location}.compose_file")
        if "\x00" in compose_file:
            raise ConfigError(f"{location}.compose_file: geçersiz dosya yolu")
        targets.append(TargetPlatform(
            kind=kind,
            compose_file=Path(compose_file),
            base_url=_url(item["base_url"], f"{location}.base_url"),
            health_url=_url(item["health_url"], f"{location}.health_url"),
            health_timeout_s=_number(
                item.get("health_timeout_s", 120.0),
                f"{location}.health_timeout_s", positive=True,
            ),
        ))
    carbon = raw.get("grid_carbon_intensity")
    return BenchmarkConfig(
        title=_text(raw["title"], "title"),
        targets=tuple(targets),
        workload_size=raw["workload_size"],
        concurrency=raw["concurrency"],
        repetitions=raw["repetitions"],
        cooldown_s=_number(raw["cooldown_s"], "cooldown_s"),
        load_generator_host=_text(raw["load_generator_host"], "load_generator_host"),
        grid_carbon_intensity=(
            None if carbon is None else _number(carbon, "grid_carbon_intensity")
        ),
    )
