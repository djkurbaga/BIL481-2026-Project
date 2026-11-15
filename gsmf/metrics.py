"""UC3 — Verimlilik metriklerinin hesaplanması (FR-8).

Her GEÇERLİ (VALID) tekrar için iki metrik hesaplanır:

- Görev başına enerji = net enerji / tamamlanan kullanıcı görevi   [J/task]
- Enerji-Gecikme Çarpımı (EDP) = net enerji × ölçülen süre        [J·s]

Başarısız (FAILED) veya geçersiz (INVALID) tekrarlar için metrik hesaplanmaz.
Kaynak ``RepetitionRecord`` nesneleri hiçbir zaman değiştirilmez; sonuçlar
yeni ``EfficiencyMetrics`` nesneleri olarak döndürülür (FR-11).

Komut satırı demosu::

    python -m gsmf.metrics examples/sample_measurements.csv
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

from gsmf.models import (
    UNIT_DURATION,
    UNIT_EDP,
    UNIT_ENERGY,
    UNIT_ENERGY_PER_TASK,
    EfficiencyMetrics,
    PlatformKind,
    RepetitionRecord,
    RepetitionStatus,
)

# ---------------------------------------------------------------------------
# Temel formüller
# ---------------------------------------------------------------------------


def energy_per_task(net_energy_j: float, completed_tasks: int) -> float:
    """Görev başına enerjiyi hesaplar (J/task).

    Formül: net_energy_j / completed_tasks

    Args:
        net_energy_j: Net enerji (J).
        completed_tasks: Tamamen başarılı kullanıcı görevi sayısı.

    Returns:
        Tamamlanan görev başına joule.

    Raises:
        ValueError: Görev sayısı sıfır veya negatifse (sıfıra bölme koruması).
    """
    # Sıfıra bölmeyi ve anlamsız negatif görev sayısını engelle.
    if completed_tasks <= 0:
        raise ValueError(
            f"completed_tasks pozitif olmalıdır, alınan değer: {completed_tasks}"
        )
    return net_energy_j / completed_tasks


def energy_delay_product(net_energy_j: float, duration_s: float) -> float:
    """Enerji-Gecikme Çarpımını (EDP) hesaplar (J·s).

    Formül: net_energy_j × duration_s

    Args:
        net_energy_j: Net enerji (J).
        duration_s: Ölçülen iş yükü aralığı süresi (s).

    Returns:
        Joule × saniye cinsinden EDP.

    Raises:
        ValueError: Süre sıfır veya negatifse.
    """
    # Ölçülen bir aralık her zaman pozitif süreye sahip olmalıdır.
    if duration_s <= 0:
        raise ValueError(f"duration_s pozitif olmalıdır, alınan değer: {duration_s}")
    return net_energy_j * duration_s


# ---------------------------------------------------------------------------
# Kayıt düzeyinde hesaplama
# ---------------------------------------------------------------------------


def _is_finite_number(value: float | None) -> bool:
    """Değerin None olmayan, sonlu (NaN/sonsuz olmayan) bir sayı olup olmadığını döndürür."""
    return value is not None and math.isfinite(value)


def skip_reason(record: RepetitionRecord) -> str | None:
    """Bir kayıt için metrik hesaplanmaması gerekiyorsa sebebini döndürür.

    Kontroller sırasıyla:
        1. Durum VALID değilse (FAILED / INVALID) atlanır.
        2. Net enerji veya süre eksik/sonsuz ise atlanır.
        3. Tamamlanan görev sayısı eksik veya sıfırsa atlanır (sıfıra bölme koruması).
        4. Net enerji negatifse veya süre pozitif değilse atlanır.

    Args:
        record: İncelenecek tekrar kaydı.

    Returns:
        Atlanma sebebi (metin) veya metrik hesaplanabiliyorsa ``None``.
    """
    # 1) FR-8: başarısız ve geçersiz tekrarlar için metrik hesaplanmaz.
    if record.status is not RepetitionStatus.VALID:
        detail = f": {record.reason}" if record.reason else ""
        return f"status={record.status.value}{detail}"

    # 2) Hesap için gerekli ölçüm değerleri eksiksiz ve sonlu olmalı.
    if not _is_finite_number(record.net_energy_j):
        return "net_energy_j eksik veya sayı değil"
    if not _is_finite_number(record.duration_s):
        return "duration_s eksik veya sayı değil"

    # 3) Sıfıra bölme koruması: görev sayısı pozitif olmalı.
    if record.completed_tasks is None or record.completed_tasks <= 0:
        return "tamamlanan görev sayısı sıfır (completed_tasks <= 0)"

    # 4) Fiziksel olarak anlamsız değerler (FR-7 ile tutarlı).
    if record.net_energy_j < 0:  # type: ignore[operator]
        return "net enerji negatif"
    if record.duration_s <= 0:  # type: ignore[operator]
        return "süre pozitif değil"

    return None


def compute_repetition_metrics(record: RepetitionRecord) -> EfficiencyMetrics | None:
    """Tek bir tekrar için verimlilik metriklerini hesaplar.

    Args:
        record: Tekrar kaydı (değiştirilmez).

    Returns:
        Kayıt geçerliyse yeni bir ``EfficiencyMetrics``; atlanması gerekiyorsa ``None``.
    """
    # Kayıt metrik hesabına uygun değilse hiçbir şey hesaplama.
    if skip_reason(record) is not None:
        return None

    # Buraya gelindiyse değerler doğrulanmıştır; tip denetleyicisi için daralt.
    net_energy_j = float(record.net_energy_j)  # type: ignore[arg-type]
    duration_s = float(record.duration_s)  # type: ignore[arg-type]
    completed_tasks = int(record.completed_tasks)  # type: ignore[arg-type]

    # İki metriği ayrı formüllerle hesapla ve yeni bir sonuç nesnesi oluştur.
    return EfficiencyMetrics(
        run_id=record.run_id,
        target=record.target,
        repetition_index=record.repetition_index,
        net_energy_j=net_energy_j,
        duration_s=duration_s,
        completed_tasks=completed_tasks,
        energy_per_task_j=energy_per_task(net_energy_j, completed_tasks),
        edp_js=energy_delay_product(net_energy_j, duration_s),
    )


def compute_metrics(records: Iterable[RepetitionRecord]) -> list[EfficiencyMetrics]:
    """Birden çok tekrar için metrikleri hesaplar, uygun olmayanları atlar.

    Sonuç listesi, girdi kayıtlarının sırasını korur.

    Args:
        records: Tekrar kayıtları (başarısız/geçersiz olanlar dahil olabilir).

    Returns:
        Yalnızca geçerli tekrarlar için ``EfficiencyMetrics`` listesi.
    """
    results: list[EfficiencyMetrics] = []
    # Her kaydı sırayla işle; None dönenler (atlananlar) listeye eklenmez.
    for record in records:
        metrics = compute_repetition_metrics(record)
        if metrics is not None:
            results.append(metrics)
    return results


# ---------------------------------------------------------------------------
# CSV okuma (demo ve testler için)
# ---------------------------------------------------------------------------

#: Demo CSV dosyasında beklenen sütunlar.
CSV_COLUMNS = (
    "run_id",
    "target",
    "repetition_index",
    "status",
    "reason",
    "idle_power_w",
    "gross_energy_j",
    "duration_s",
    "net_energy_j",
    "completed_tasks",
    "workload_errors",
)


def _optional_float(text: str | None) -> float | None:
    """Boş hücreyi None'a, dolu hücreyi float'a çevirir."""
    text = (text or "").strip()
    return float(text) if text else None


def _optional_int(text: str | None) -> int | None:
    """Boş hücreyi None'a, dolu hücreyi int'e çevirir."""
    text = (text or "").strip()
    return int(text) if text else None


def load_records_csv(path: Path) -> list[RepetitionRecord]:
    """Tekrar kayıtlarını bir CSV dosyasından okur.

    ``#`` ile başlayan satırlar yorum kabul edilir ve atlanır (ör. "örnek veri"
    uyarısı). Boş hücreler ``None`` olarak okunur.

    Args:
        path: CSV dosyasının yolu.

    Returns:
        Dosyadaki sırayla ``RepetitionRecord`` listesi.

    Raises:
        ValueError: Zorunlu sütun eksikse veya bir hücre çözümlenemiyorsa.
    """
    with Path(path).open(encoding="utf-8", newline="") as handle:
        # Yorum ve boş satırları ayıkla, kalanını DictReader'a ver.
        lines = [line for line in handle if line.strip() and not line.lstrip().startswith("#")]

    reader = csv.DictReader(lines)
    # Başlık satırında beklenen sütunların hepsi bulunmalı.
    missing = [col for col in CSV_COLUMNS if col not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"CSV dosyasında eksik sütunlar: {', '.join(missing)}")

    records: list[RepetitionRecord] = []
    # Satır numarası, hata mesajında kullanıcıya yol göstermek içindir.
    for line_no, row in enumerate(reader, start=2):
        try:
            records.append(
                RepetitionRecord(
                    run_id=row["run_id"].strip(),
                    target=PlatformKind(row["target"].strip().lower()),
                    repetition_index=int(row["repetition_index"]),
                    status=RepetitionStatus(row["status"].strip().lower()),
                    reason=(row["reason"] or "").strip() or None,
                    idle_power_w=_optional_float(row["idle_power_w"]),
                    gross_energy_j=_optional_float(row["gross_energy_j"]),
                    duration_s=_optional_float(row["duration_s"]),
                    net_energy_j=_optional_float(row["net_energy_j"]),
                    completed_tasks=_optional_int(row["completed_tasks"]),
                    workload_errors=_optional_int(row["workload_errors"]) or 0,
                )
            )
        except (ValueError, KeyError) as exc:
            raise ValueError(f"CSV veri satırı {line_no} çözümlenemedi: {exc}") from exc
    return records


# ---------------------------------------------------------------------------
# Tablo biçimlendirme ve komut satırı
# ---------------------------------------------------------------------------


def format_table(records: Sequence[RepetitionRecord], edp_unit: str = UNIT_EDP) -> str:
    """Her kayıt için metrik veya atlanma sebebini içeren metin tablosu üretir.

    Args:
        records: Tabloya yazılacak tekrar kayıtları.
        edp_unit: Başlıkta gösterilecek EDP birimi (konsol "·" yazamıyorsa "J*s").

    Returns:
        Terminalde yazdırılmaya hazır çok satırlı metin.
    """
    headers = [
        "Target",
        "Rep",
        "Status",
        f"Net energy ({UNIT_ENERGY})",
        f"Duration ({UNIT_DURATION})",
        "Tasks",
        f"Energy/task ({UNIT_ENERGY_PER_TASK})",
        f"EDP ({edp_unit})",
        "Note",
    ]
    rows: list[list[str]] = []

    # Her kayıt için ya hesaplanan metrikleri ya da atlanma sebebini yaz.
    for record in records:
        metrics = compute_repetition_metrics(record)
        if metrics is not None:
            rows.append(
                [
                    record.target.value,
                    str(record.repetition_index),
                    record.status.value,
                    f"{metrics.net_energy_j:,.2f}",
                    f"{metrics.duration_s:,.2f}",
                    str(metrics.completed_tasks),
                    f"{metrics.energy_per_task_j:.4f}",
                    f"{metrics.edp_js:,.1f}",
                    "",
                ]
            )
        else:
            rows.append(
                [
                    record.target.value,
                    str(record.repetition_index),
                    record.status.value,
                    "-",
                    "-",
                    "-" if record.completed_tasks is None else str(record.completed_tasks),
                    "-",
                    "-",
                    f"skipped: {skip_reason(record)}",
                ]
            )

    # Sütun genişliklerini en uzun hücreye göre hesapla.
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)]
    # Sayısal sütunları sağa, metin sütunlarını sola hizala.
    numeric = {1, 3, 4, 5, 6, 7}

    def fmt(cells: Sequence[str]) -> str:
        """Bir satırı hizalanmış sütunlarla birleştirir."""
        return " | ".join(
            cell.rjust(widths[i]) if i in numeric else cell.ljust(widths[i])
            for i, cell in enumerate(cells)
        ).rstrip()

    separator = "-+-".join("-" * w for w in widths)
    lines = [fmt(headers), separator, *(fmt(r) for r in rows)]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Komut satırı giriş noktası: CSV'deki kayıtlar için metrik tablosunu yazdırır.

    Args:
        argv: Komut satırı argümanları (None ise ``sys.argv`` kullanılır).

    Returns:
        Çıkış kodu (0 = başarılı, 1 = dosya/veri hatası).
    """
    parser = argparse.ArgumentParser(
        prog="python -m gsmf.metrics",
        description=(
            "UC3 / FR-8: compute energy per completed user task (J/task) and "
            "EDP (J·s) for each valid repetition in a CSV file. Failed and "
            "invalid repetitions are listed but skipped."
        ),
    )
    parser.add_argument("csv_path", type=Path, help="CSV file with repetition records")
    args = parser.parse_args(argv)

    # Konsol kodlaması "·" karakterini yazamıyorsa (ör. Windows cp1254) ASCII birim kullan.
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        UNIT_EDP.encode(encoding)
        edp_label = UNIT_EDP
    except (UnicodeEncodeError, LookupError):
        edp_label = "J*s"

    # Dosyayı oku; okunamazsa anlaşılır bir hata ile çık.
    try:
        records = load_records_csv(args.csv_path)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # Tabloyu ve kısa bir özet satırını yazdır.
    valid = compute_metrics(records)
    print(format_table(records, edp_unit=edp_label))
    print()
    print(
        f"{len(valid)} of {len(records)} repetitions used for metrics; "
        f"{len(records) - len(valid)} skipped (failed/invalid/zero tasks)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
