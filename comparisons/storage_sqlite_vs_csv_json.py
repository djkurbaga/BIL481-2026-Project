"""Tekrar kayıtlarının SQLite, CSV ve JSON Lines ile saklanmasını karşılaştırır (UC4).

Aynı sentetik kayıt kümesi üç biçime yazılır ve geri okunur. Ölçülenler:
yazma ve okuma süresi (birkaç tekrarın medyanı), dosya boyutu, geri okunan
kayıtların özgün kayıtlarla birebir eşitliği ve bir kaydın sonradan
değiştirilmesine karşı biçimin kendi koruması.

Kayıt değerleri sözde-rastgele üretilir (sabit tohum); gerçek enerji ölçümü
değildir. Süreler yerel makineye özgüdür, genel bir hız sıralaması değildir.

Çalıştırma::

    python comparisons/storage_sqlite_vs_csv_json.py --records 5000 --repeats 5
"""

from __future__ import annotations

import argparse
import contextlib
import json
import platform
import random
import sqlite3
import statistics
import sys
import tempfile
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Betik doğrudan çalıştırıldığında da depo paketini bulabilsin.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsmf.metrics import load_records_csv  # noqa: E402
from gsmf.models import (  # noqa: E402
    BenchmarkConfig,
    PlatformKind,
    RepetitionRecord,
    RepetitionStatus,
    StorageError,
    TargetPlatform,
    TestbedSettings,
)
from gsmf.storage import ResultStore  # noqa: E402

RUN_ID = "comparison"


def make_records(count: int, seed: int = 481) -> list[RepetitionRecord]:
    """Sabit tohumla geçerli, geçersiz ve başarısız kayıtlardan oluşan sentetik küme üretir."""
    rng = random.Random(seed)
    kinds = list(PlatformKind)
    start = datetime(2026, 11, 15, 9, 0, tzinfo=timezone.utc)
    records = []
    for i in range(count):
        kind = kinds[i % len(kinds)]
        index = i // len(kinds) + 1
        roll = rng.random()
        if roll < 0.05:
            # Başarısız tekrar: ölçüm alanları boş, sebep dolu.
            records.append(RepetitionRecord(
                run_id=RUN_ID, target=kind, repetition_index=index,
                status=RepetitionStatus.FAILED, reason="yığın başlatılamadı",
                started_at=start + timedelta(seconds=i),
            ))
            continue
        idle = rng.uniform(8, 15)
        duration = rng.uniform(10, 60)
        gross = idle * duration + rng.uniform(-20, 2000)
        net = gross - idle * duration
        status = RepetitionStatus.VALID if net >= 0 else RepetitionStatus.INVALID
        records.append(RepetitionRecord(
            run_id=RUN_ID, target=kind, repetition_index=index, status=status,
            reason=None if status is RepetitionStatus.VALID else "net enerji negatif",
            idle_power_w=idle, gross_energy_j=gross, duration_s=duration, net_energy_j=net,
            completed_tasks=rng.randint(900, 1000), workload_errors=rng.randint(0, 3),
            started_at=start + timedelta(seconds=i),
        ))
    return records


# ---------------------------------------------------------------------------
# SQLite (gsmf.storage.ResultStore)
# ---------------------------------------------------------------------------


def sqlite_setup(path: Path) -> ResultStore:
    """Şeması kurulmuş ve çalıştırması kaydedilmiş bir depo döndürür."""
    store = ResultStore(path)
    store.initialize_schema()
    targets = tuple(
        TargetPlatform(kind=k, compose_file=Path(f"{k.value}.yml"),
                       base_url="http://x", health_url="http://x/health")
        for k in PlatformKind
    )
    config = BenchmarkConfig(title="karşılaştırma", targets=targets, workload_size=1000,
                             concurrency=10, repetitions=10, cooldown_s=0.0,
                             load_generator_host="loadgen")
    store.save_run(RUN_ID, config, {k: "1.0" for k in PlatformKind},
                   TestbedSettings("host", "performance", True, ("package-0",)))
    return store


def sqlite_write(path: Path, records: list[RepetitionRecord]) -> None:
    """Kayıtları GSMF deposunun save_repetition yöntemiyle tek tek ekler."""
    store = sqlite_setup(path)
    for record in records:
        store.save_repetition(record)


def sqlite_read(path: Path) -> list[RepetitionRecord]:
    """Kayıtları depodan okur."""
    return ResultStore(path).load_repetitions(RUN_ID)


def sqlite_tamper(path: Path) -> str:
    """Saklanan bir net enerji değerini doğrudan SQL ile değiştirmeyi dener."""
    try:
        with contextlib.closing(sqlite3.connect(path)) as conn, conn:
            conn.execute("UPDATE repetitions SET net_energy_j = 0 WHERE id = 1")
        return "değiştirildi"
    except sqlite3.DatabaseError as exc:
        return f"reddedildi ({exc})"


def sqlite_duplicate(path: Path, record: RepetitionRecord) -> str:
    """Aynı anahtarla ikinci kez kayıt eklemeyi dener."""
    try:
        ResultStore(path).save_repetition(record)
        return "eklendi"
    except StorageError:
        return "reddedildi"


# ---------------------------------------------------------------------------
# CSV (UC3 okuyucusuyla uyumlu sütunlar)
# ---------------------------------------------------------------------------

CSV_HEADER = ("run_id,target,repetition_index,status,reason,idle_power_w,gross_energy_j,"
              "duration_s,net_energy_j,completed_tasks,workload_errors,started_at")


def _cell(value) -> str:
    """Değeri CSV hücresine çevirir (float'lar repr ile kayıpsız)."""
    if value is None:
        return ""
    if isinstance(value, float):
        return repr(value)
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def csv_write(path: Path, records: list[RepetitionRecord]) -> None:
    """Kayıtları başlık satırıyla CSV'ye ekleme kipinde yazar (sebeplerde virgül yok)."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(CSV_HEADER + "\n")
    for record in records:
        with path.open("a", encoding="utf-8", newline="") as handle:
            handle.write(",".join(_cell(v) for v in record.__dict__.values()) + "\n")


def csv_read(path: Path) -> list[RepetitionRecord]:
    """Kayıtları UC3'ün CSV okuyucusuyla okur (started_at bu okuyucuda okunmaz)."""
    return load_records_csv(path)


def csv_tamper(path: Path) -> str:
    """İlk veri satırındaki net enerji hücresini düz metin düzenlemesiyle değiştirir."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    cells = lines[1].split(",")
    cells[8] = "0"
    lines[1] = ",".join(cells)
    path.write_text("".join(lines), encoding="utf-8")
    return "değiştirildi"


# ---------------------------------------------------------------------------
# JSON Lines
# ---------------------------------------------------------------------------


def jsonl_write(path: Path, records: list[RepetitionRecord]) -> None:
    """Her kaydı ayrı bir JSON satırı olarak ekleme kipinde yazar."""
    path.write_text("", encoding="utf-8")
    for record in records:
        row = {k: _cell(v) if isinstance(v, (datetime,)) or hasattr(v, "value") else v
               for k, v in record.__dict__.items()}
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def jsonl_read(path: Path) -> list[RepetitionRecord]:
    """JSON satırlarını kayıt nesnelerine geri çevirir."""
    records = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            row["target"] = PlatformKind(row["target"])
            row["status"] = RepetitionStatus(row["status"])
            if row["started_at"] is not None:
                row["started_at"] = datetime.fromisoformat(row["started_at"])
            records.append(RepetitionRecord(**row))
    return records


def jsonl_tamper(path: Path) -> str:
    """İlk satırdaki net enerjiyi düz metin düzenlemesiyle değiştirir."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    row = json.loads(lines[0])
    row["net_energy_j"] = 0
    lines[0] = json.dumps(row, ensure_ascii=False) + "\n"
    path.write_text("".join(lines), encoding="utf-8")
    return "değiştirildi"


def append_duplicate(writer_path: Path, fmt: str, record: RepetitionRecord) -> str:
    """CSV/JSONL dosyasına aynı kaydı tekrar ekler; biçim bunu engellemez."""
    with writer_path.open("a", encoding="utf-8", newline="") as handle:
        if fmt == "csv":
            handle.write(",".join(_cell(v) for v in record.__dict__.values()) + "\n")
        else:
            handle.write("{}\n")
    return "eklendi"


# ---------------------------------------------------------------------------
# Ölçüm
# ---------------------------------------------------------------------------


def timed(fn: Callable[[], object], repeats: int) -> tuple[float, object]:
    """İşlevi birkaç kez çalıştırır; medyan süreyi (s) ve son sonucu döndürür."""
    durations, result = [], None
    for _ in range(repeats):
        start = time.perf_counter()
        result = fn()
        durations.append(time.perf_counter() - start)
    return statistics.median(durations), result


def main(argv: list[str] | None = None) -> int:
    """Karşılaştırmayı çalıştırır ve her biçim için bir JSON satırı yazdırır."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--records", type=int, default=5000)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args(argv)

    records = make_records(args.records)
    without_time = [RepetitionRecord(**{**r.__dict__, "started_at": None}) for r in records]
    print(json.dumps({
        "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
        "platform": platform.platform(), "records": len(records), "repeats": args.repeats,
        "statuses": {s.value: sum(r.status is s for r in records) for s in RepetitionStatus},
    }, ensure_ascii=False))

    formats = {
        "sqlite": (sqlite_write, sqlite_read, sqlite_tamper),
        "csv": (csv_write, csv_read, csv_tamper),
        "jsonl": (jsonl_write, jsonl_read, jsonl_tamper),
    }
    with tempfile.TemporaryDirectory() as tmp:
        for name, (write, read, tamper) in formats.items():
            path = Path(tmp) / f"records.{name}"

            def do_write(path=path, write=write):
                """Her denemeden önce dosyayı silip baştan yazar."""
                path.unlink(missing_ok=True)
                write(path, records)

            write_s, _ = timed(do_write, args.repeats)
            read_s, loaded = timed(lambda path=path, read=read: read(path), args.repeats)
            size = path.stat().st_size
            # CSV okuyucusu started_at okumadığı için o alan hariç karşılaştırılır.
            expected = without_time if name == "csv" else records
            duplicate = (sqlite_duplicate(path, records[0]) if name == "sqlite"
                         else append_duplicate(path, name, records[0]))
            print(json.dumps({
                "format": name,
                "write_s": round(write_s, 6),
                "read_s": round(read_s, 6),
                "bytes": size,
                "round_trip_equal": loaded == expected,
                "started_at_preserved": name != "csv",
                "duplicate_append": duplicate,
                "tamper_existing_value": tamper(path),
            }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
