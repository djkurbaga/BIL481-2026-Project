"""UC4 — Sonuçların kalıcı saklanması ve dışa aktarımı (FR-11).

Her tekrar kaydı (başarısız ve geçersiz olanlar dahil, durum ve sebebiyle
birlikte), çalıştırmanın yapılandırması, hedef sürümleri ve testbed ayarları
tek bir SQLite veritabanında saklanır. Seçilen bir çalıştırmanın ham kayıtları
ve hedef bazında toplu sonuçları CSV olarak dışa aktarılabilir.

Değişmezlik kuralı: saklanan ölçülen değerler sonradan değiştirilmez. Depo
yalnızca ``INSERT`` yapar; ayrıca veritabanındaki tetikleyiciler (trigger)
``runs``, ``run_targets``, ``repetitions`` ve ``metrics`` tablolarında her
``UPDATE`` ve ``DELETE`` girişimini reddeder. Hesaplanan metrikler ham
kayıtlardan ayrı ``metrics`` tablosunda tutulur.

Tablolar:
    runs         — çalıştırma başına yapılandırma ve testbed ayarları
    run_targets  — çalıştırmanın hedefleri (sıra, tür, sürüm, adresler)
    repetitions  — ham tekrar kayıtları (VALID / INVALID / FAILED)
    metrics      — geçerli tekrarlar için hesaplanan metrikler (FR-8)
"""

from __future__ import annotations

import csv
import json
import math
import re
import sqlite3
import statistics
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from gsmf.models import (
    UNIT_EDP,
    UNIT_ENERGY_PER_TASK,
    BenchmarkConfig,
    EfficiencyMetrics,
    PlatformKind,
    RepetitionRecord,
    RepetitionStatus,
    StorageError,
    TestbedSettings,
)

# ---------------------------------------------------------------------------
# Şema
# ---------------------------------------------------------------------------

#: Şema sürümü; ileride yapılacak geçişler (migration) için ``user_version``'a yazılır.
SCHEMA_VERSION = 1

#: Değiştirilemez tablolar; her biri için UPDATE ve DELETE tetikleyicisi oluşturulur.
_IMMUTABLE_TABLES = ("runs", "run_targets", "repetitions", "metrics")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id                TEXT PRIMARY KEY CHECK (length(run_id) > 0),
    created_at            TEXT NOT NULL,
    title                 TEXT NOT NULL,
    workload_size         INTEGER NOT NULL,
    concurrency           INTEGER NOT NULL,
    repetitions           INTEGER NOT NULL,
    cooldown_s            REAL NOT NULL,
    load_generator_host   TEXT NOT NULL,
    grid_carbon_intensity REAL,
    config_json           TEXT NOT NULL,
    testbed_hostname      TEXT NOT NULL,
    cpu_governor          TEXT NOT NULL,
    turbo_boost_disabled  INTEGER NOT NULL CHECK (turbo_boost_disabled IN (0, 1)),
    rapl_domains_json     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS run_targets (
    run_id           TEXT NOT NULL REFERENCES runs(run_id),
    position         INTEGER NOT NULL,
    kind             TEXT NOT NULL CHECK (kind IN ('budibase', 'appsmith', 'fastapi')),
    version          TEXT NOT NULL,
    compose_file     TEXT NOT NULL,
    base_url         TEXT NOT NULL,
    health_url       TEXT NOT NULL,
    health_timeout_s REAL NOT NULL,
    PRIMARY KEY (run_id, position)
);

CREATE TABLE IF NOT EXISTS repetitions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id           TEXT NOT NULL REFERENCES runs(run_id),
    target           TEXT NOT NULL CHECK (target IN ('budibase', 'appsmith', 'fastapi')),
    repetition_index INTEGER NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('valid', 'invalid', 'failed')),
    reason           TEXT,
    idle_power_w     REAL,
    gross_energy_j   REAL,
    duration_s       REAL,
    net_energy_j     REAL,
    completed_tasks  INTEGER,
    workload_errors  INTEGER NOT NULL,
    started_at       TEXT,
    UNIQUE (run_id, target, repetition_index),
    CHECK (status = 'valid' OR length(trim(coalesce(reason, ''))) > 0)
);

CREATE TABLE IF NOT EXISTS metrics (
    run_id               TEXT NOT NULL,
    target               TEXT NOT NULL,
    repetition_index     INTEGER NOT NULL,
    net_energy_j         REAL NOT NULL,
    duration_s           REAL NOT NULL,
    completed_tasks      INTEGER NOT NULL,
    energy_per_task_j    REAL NOT NULL,
    edp_js               REAL NOT NULL,
    energy_per_task_unit TEXT NOT NULL,
    edp_unit             TEXT NOT NULL,
    PRIMARY KEY (run_id, target, repetition_index),
    FOREIGN KEY (run_id, target, repetition_index)
        REFERENCES repetitions(run_id, target, repetition_index)
);
"""

# ---------------------------------------------------------------------------
# CSV sütunları
# ---------------------------------------------------------------------------

#: Ham CSV sütunları. İlk 11 sütun ``gsmf.metrics.CSV_COLUMNS`` ile aynıdır;
#: böylece dışa aktarılan dosya ``gsmf.metrics.load_records_csv`` ile okunabilir.
RAW_CSV_COLUMNS = (
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
    "started_at",
)

#: Toplu sonuçlarda istatistiği hesaplanan metrik alanları.
AGGREGATE_FIELDS = ("net_energy_j", "duration_s", "energy_per_task_j", "edp_js")

#: Her metrik alanı için yazılan istatistikler.
AGGREGATE_STATS = ("mean", "median", "stdev", "min", "max")

#: Toplu sonuç CSV sütunları (hedef başına bir satır).
AGGREGATE_CSV_COLUMNS = (
    "run_id",
    "target",
    "target_version",
    "repetitions_total",
    "valid_count",
    "invalid_count",
    "failed_count",
    "metrics_count",
    *(f"{name}_{stat}" for name in AGGREGATE_FIELDS for stat in AGGREGATE_STATS),
    "energy_per_task_unit",
    "edp_unit",
)

# Dosya adında yalnızca güvenli karakterler kalsın (ör. "/" ile dizin dışına çıkılmasın).
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]")


# ---------------------------------------------------------------------------
# Yardımcı dönüştürmeler
# ---------------------------------------------------------------------------


def _to_jsonable(value: Any) -> Any:
    """Dataclass alanlarını JSON'a yazılabilir türlere (Path→str, Enum→değer) çevirir."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    return value


def _checked_float(name: str, value: float | None) -> float | None:
    """Ölçülen değeri olduğu gibi döndürür; SQLite'ın saklayamadığı NaN'ı reddeder.

    SQLite NaN değerini sessizce NULL'a çevirir; bu, ölçülen değerin
    değişmesi demektir (FR-11). Bu yüzden NaN yazılmaz, hata verilir.
    ±sonsuz değerler REAL olarak birebir saklanabildiği için kabul edilir.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StorageError(f"{name} sayı olmalıdır, alınan değer: {value!r}")
    if math.isnan(value):
        raise StorageError(
            f"{name} NaN olamaz: SQLite NaN değerini NULL'a çevirir ve ölçülen değer "
            "değişir; okunamayan değeri None olarak ve sebebini reason alanında kaydedin"
        )
    return value


def _checked_int(name: str, value: int | None) -> int | None:
    """Tam sayı alanını doğrular (bool kabul edilmez)."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise StorageError(f"{name} tam sayı olmalıdır, alınan değer: {value!r}")
    return value


def _csv_cell(value: Any) -> str:
    """Bir değeri CSV hücresine çevirir; float'lar ``repr`` ile kayıpsız yazılır."""
    if value is None:
        return ""
    if isinstance(value, float):
        # repr() en kısa ve geri dönüşümü birebir olan ondalık gösterimi verir.
        return repr(value)
    return str(value)


def _safe_filename_part(run_id: str) -> str:
    """run_id'yi dosya adında güvenle kullanılabilir hale getirir."""
    return _UNSAFE_FILENAME_CHARS.sub("_", run_id)


def _resolve_out_path(out_path: Path, prefix: str, run_id: str) -> Path:
    """Çıktı yolunu belirler: dizinse içine ``<prefix>_<run_id>.csv`` yazılır.

    Var olan bir dizin veya sonu ayraçla biten bir yol dizin kabul edilir;
    aksi halde ``out_path`` doğrudan dosya yolu olarak kullanılır.
    """
    raw = str(out_path)
    path = Path(out_path)
    if path.is_dir() or raw.endswith(("/", "\\")):
        return path / f"{prefix}_{_safe_filename_part(run_id)}.csv"
    return path


def _write_csv(path: Path, header: Sequence[str], rows: Iterable[Sequence[Any]]) -> Path:
    """CSV dosyasını UTF-8 olarak yazar; dosya sistemi hatalarını StorageError'a çevirir."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            for row in rows:
                writer.writerow([_csv_cell(cell) for cell in row])
    except OSError as exc:
        raise StorageError(f"CSV dosyası yazılamadı ({path}): {exc}") from exc
    return path


def _describe(values: Sequence[float]) -> list[float | None]:
    """Değerler için ortalama, medyan, örneklem standart sapması, en küçük ve en büyük değeri döndürür.

    Değer yoksa tüm istatistikler None; tek değer varsa standart sapma None olur.
    """
    if not values:
        return [None] * len(AGGREGATE_STATS)
    stdev = statistics.stdev(values) if len(values) >= 2 else None
    return [statistics.fmean(values), statistics.median(values), stdev, min(values), max(values)]


# ---------------------------------------------------------------------------
# Depo
# ---------------------------------------------------------------------------


class ResultStore:
    """SQLite tabanlı sonuç deposu.

    Her işlem kendi kısa ömürlü bağlantısını açar ve tek bir işlem (transaction)
    içinde çalışır; hata olursa değişiklik geri alınır. Tüm SQLite hataları
    ``StorageError`` olarak yükseltilir.
    """

    def __init__(self, db_path: Path) -> None:
        """Depoyu verilen SQLite dosyasıyla ilişkilendirir.

        Dosya ilk bağlantıda (ör. ``initialize_schema`` çağrısında) oluşturulur.

        Args:
            db_path: SQLite veritabanı dosyasının yolu (yoksa oluşturulur).
        """
        self.db_path = Path(db_path)

    # -- bağlantı ---------------------------------------------------------

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Yabancı anahtar denetimi açık bir bağlantı verir; işlemi tamamlar veya geri alır."""
        try:
            connection = sqlite3.connect(self.db_path)
        except sqlite3.Error as exc:
            raise StorageError(f"SQLite veritabanı açılamadı ({self.db_path}): {exc}") from exc
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:  # başarıda COMMIT, hatada ROLLBACK
                yield connection
        except sqlite3.Error as exc:
            raise StorageError(f"SQLite işlemi başarısız ({self.db_path}): {exc}") from exc
        finally:
            connection.close()

    # -- şema -------------------------------------------------------------

    def initialize_schema(self) -> None:
        """Gerekli tabloları (runs, run_targets, repetitions, metrics) yoksa oluşturur.

        Tekrar çağrılması güvenlidir; var olan veriye dokunmaz. Ayrıca her tablo
        için UPDATE ve DELETE girişimlerini reddeden tetikleyicileri kurar.

        Raises:
            StorageError: Veritabanı oluşturulamaz veya şema yazılamazsa.
        """
        with self._connect() as connection:
            connection.executescript(_SCHEMA_SQL)
            # Saklanan değerler değiştirilemesin (FR-11): UPDATE/DELETE engellenir.
            for table in _IMMUTABLE_TABLES:
                for action in ("UPDATE", "DELETE"):
                    connection.execute(
                        f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} "
                        f"BEFORE {action} ON {table} BEGIN "
                        f"SELECT RAISE(ABORT, '{table} kayıtları değiştirilemez (FR-11)'); END"
                    )
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    # -- yazma ------------------------------------------------------------

    def save_run(
        self,
        run_id: str,
        config: BenchmarkConfig,
        target_versions: Mapping[PlatformKind, str],
        testbed: TestbedSettings,
    ) -> None:
        """Bir çalıştırmanın yapılandırmasını, hedef sürümlerini ve testbed ayarlarını kaydeder.

        Her yapılandırma hedefi için boş olmayan bir sürüm verilmelidir;
        yapılandırmada olmayan bir hedefin sürümü kabul edilmez.

        Raises:
            StorageError: Aynı run_id zaten varsa, sürümler eksik/fazlaysa veya yazma başarısızsa.
        """
        if not isinstance(run_id, str) or not run_id.strip():
            raise StorageError("run_id boş olmayan bir metin olmalıdır")

        # Hedef sürümleri, yapılandırmadaki hedeflerle birebir örtüşmeli.
        config_kinds = {target.kind for target in config.targets}
        missing = [k.value for k in PlatformKind if k in config_kinds and k not in target_versions]
        if missing:
            raise StorageError(f"hedef sürümü eksik: {', '.join(missing)}")
        extra = sorted(str(getattr(k, "value", k)) for k in target_versions if k not in config_kinds)
        if extra:
            raise StorageError(f"yapılandırmada olmayan hedef için sürüm verildi: {', '.join(extra)}")
        for kind in config_kinds:
            version = target_versions[kind]
            if not isinstance(version, str) or not version.strip():
                raise StorageError(f"{kind.value} için sürüm boş olmayan bir metin olmalıdır")

        config_json = json.dumps(_to_jsonable(asdict(config)), ensure_ascii=False, sort_keys=True)
        created_at = datetime.now(timezone.utc).isoformat()

        with self._connect() as connection:
            # Aynı run_id ile ikinci kayıt reddedilir; var olan kayıt güncellenmez.
            if connection.execute("SELECT 1 FROM runs WHERE run_id = ?", (run_id,)).fetchone():
                raise StorageError(f"run_id zaten kayıtlı: {run_id!r}")
            connection.execute(
                "INSERT INTO runs (run_id, created_at, title, workload_size, concurrency, "
                "repetitions, cooldown_s, load_generator_host, grid_carbon_intensity, "
                "config_json, testbed_hostname, cpu_governor, turbo_boost_disabled, "
                "rapl_domains_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    created_at,
                    config.title,
                    config.workload_size,
                    config.concurrency,
                    config.repetitions,
                    config.cooldown_s,
                    config.load_generator_host,
                    config.grid_carbon_intensity,
                    config_json,
                    testbed.hostname,
                    testbed.cpu_governor,
                    int(bool(testbed.turbo_boost_disabled)),
                    json.dumps(list(testbed.rapl_domains), ensure_ascii=False),
                ),
            )
            # Hedefler yapılandırmadaki sırayla, sürümleriyle birlikte yazılır.
            connection.executemany(
                "INSERT INTO run_targets (run_id, position, kind, version, compose_file, "
                "base_url, health_url, health_timeout_s) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        run_id,
                        position,
                        target.kind.value,
                        target_versions[target.kind],
                        str(target.compose_file),
                        target.base_url,
                        target.health_url,
                        target.health_timeout_s,
                    )
                    for position, target in enumerate(config.targets, start=1)
                ],
            )

    def save_repetition(self, record: RepetitionRecord) -> None:
        """Bir tekrar kaydını (başarısız/geçersiz olanlar dahil) ekler.

        Yalnızca ekleme yapılır; var olan bir kayıt güncellenmez. Kaydın
        çalıştırması önceden ``save_run`` ile kaydedilmiş olmalı ve hedefi o
        çalıştırmanın hedeflerinden biri olmalıdır. INVALID ve FAILED kayıtlarda
        sebep (reason) zorunludur.

        Raises:
            StorageError: Kayıt zaten varsa veya yazma başarısızsa.
        """
        # Durum ve sebep: başarısız/geçersiz kayıt sebebi olmadan saklanmaz.
        status = RepetitionStatus(record.status)
        if status is not RepetitionStatus.VALID and not (record.reason or "").strip():
            raise StorageError(f"{status.value} durumundaki tekrar için reason zorunludur")

        values = (
            record.run_id,
            PlatformKind(record.target).value,
            _checked_int("repetition_index", record.repetition_index),
            status.value,
            record.reason,
            _checked_float("idle_power_w", record.idle_power_w),
            _checked_float("gross_energy_j", record.gross_energy_j),
            _checked_float("duration_s", record.duration_s),
            _checked_float("net_energy_j", record.net_energy_j),
            _checked_int("completed_tasks", record.completed_tasks),
            _checked_int("workload_errors", record.workload_errors),
            record.started_at.isoformat() if record.started_at is not None else None,
        )

        with self._connect() as connection:
            self._require_run(connection, record.run_id)
            kinds = {row[0] for row in connection.execute(
                "SELECT kind FROM run_targets WHERE run_id = ?", (record.run_id,)
            )}
            if values[1] not in kinds:
                raise StorageError(
                    f"{values[1]} hedefi {record.run_id!r} çalıştırmasının yapılandırmasında yok"
                )
            # Yinelenen kayıt açık bir hata ile reddedilir (UPDATE yapılmaz).
            if connection.execute(
                "SELECT 1 FROM repetitions WHERE run_id = ? AND target = ? AND repetition_index = ?",
                values[:3],
            ).fetchone():
                raise StorageError(
                    f"tekrar kaydı zaten var: run_id={record.run_id!r}, "
                    f"target={values[1]}, repetition_index={record.repetition_index}"
                )
            connection.execute(
                "INSERT INTO repetitions (run_id, target, repetition_index, status, reason, "
                "idle_power_w, gross_energy_j, duration_s, net_energy_j, completed_tasks, "
                "workload_errors, started_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                values,
            )

    def save_metrics(self, metrics: Iterable[EfficiencyMetrics]) -> None:
        """Hesaplanan metrikleri ham kayıtlardan ayrı bir tabloya yazar.

        Her metrik, kayıtlı ve VALID durumundaki bir tekrara ait olmalı ve o
        tekrarın saklanan net enerji, süre ve görev sayısıyla aynı değerleri
        kullanmalıdır. Tüm liste tek işlemde yazılır: biri hatalıysa hiçbiri yazılmaz.

        Raises:
            StorageError: Yazma başarısızsa (yinelenen metrik veya tutarsız kaynak dahil).
        """
        items = list(metrics)
        with self._connect() as connection:
            for item in items:
                target = PlatformKind(item.target).value
                key = (item.run_id, target, item.repetition_index)
                source = connection.execute(
                    "SELECT status, net_energy_j, duration_s, completed_tasks FROM repetitions "
                    "WHERE run_id = ? AND target = ? AND repetition_index = ?",
                    key,
                ).fetchone()
                label = f"run_id={item.run_id!r}, target={target}, repetition_index={item.repetition_index}"
                if source is None:
                    raise StorageError(f"metriğin kaynak tekrarı bulunamadı: {label}")
                if source[0] != RepetitionStatus.VALID.value:
                    raise StorageError(f"{source[0]} durumundaki tekrar için metrik saklanamaz: {label}")
                # Metrik, saklanan ham değerlerden türetilmiş olmalı (ham değerler değiştirilmez).
                if (source[1], source[2], source[3]) != (
                    item.net_energy_j, item.duration_s, item.completed_tasks
                ):
                    raise StorageError(f"metrik değerleri saklanan ham kayıtla uyuşmuyor: {label}")
                if connection.execute(
                    "SELECT 1 FROM metrics WHERE run_id = ? AND target = ? AND repetition_index = ?",
                    key,
                ).fetchone():
                    raise StorageError(f"metrik zaten kayıtlı: {label}")
                connection.execute(
                    "INSERT INTO metrics (run_id, target, repetition_index, net_energy_j, "
                    "duration_s, completed_tasks, energy_per_task_j, edp_js, "
                    "energy_per_task_unit, edp_unit) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        *key,
                        _checked_float("net_energy_j", item.net_energy_j),
                        _checked_float("duration_s", item.duration_s),
                        _checked_int("completed_tasks", item.completed_tasks),
                        _checked_float("energy_per_task_j", item.energy_per_task_j),
                        _checked_float("edp_js", item.edp_js),
                        item.energy_per_task_unit,
                        item.edp_unit,
                    ),
                )

    # -- okuma ------------------------------------------------------------

    @staticmethod
    def _require_run(connection: sqlite3.Connection, run_id: str) -> None:
        """run_id kayıtlı değilse StorageError yükseltir."""
        if not connection.execute("SELECT 1 FROM runs WHERE run_id = ?", (run_id,)).fetchone():
            raise StorageError(f"run_id bulunamadı: {run_id!r}")

    @staticmethod
    def _fetch_repetition_rows(connection: sqlite3.Connection, run_id: str) -> list[tuple]:
        """Bir çalıştırmanın tekrar satırlarını ekleme sırasıyla döndürür."""
        return connection.execute(
            "SELECT run_id, target, repetition_index, status, reason, idle_power_w, "
            "gross_energy_j, duration_s, net_energy_j, completed_tasks, workload_errors, "
            "started_at FROM repetitions WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()

    def load_repetitions(self, run_id: str) -> list[RepetitionRecord]:
        """Bir çalıştırmanın tüm tekrar kayıtlarını sırasıyla döndürür.

        Sıra, kayıtların eklenme sırasıdır. Kayıt yoksa (veya run_id
        bilinmiyorsa) boş liste döner.
        """
        with self._connect() as connection:
            rows = self._fetch_repetition_rows(connection, run_id)
        return [
            RepetitionRecord(
                run_id=row[0],
                target=PlatformKind(row[1]),
                repetition_index=row[2],
                status=RepetitionStatus(row[3]),
                reason=row[4],
                idle_power_w=row[5],
                gross_energy_j=row[6],
                duration_s=row[7],
                net_energy_j=row[8],
                completed_tasks=row[9],
                workload_errors=row[10],
                started_at=datetime.fromisoformat(row[11]) if row[11] is not None else None,
            )
            for row in rows
        ]

    # -- dışa aktarma -----------------------------------------------------

    def export_raw_csv(self, run_id: str, out_path: Path) -> Path:
        """Ham tekrar kayıtlarını CSV dosyasına yazar ve dosya yolunu döndürür.

        ``out_path`` bir dizinse dosya ``raw_<run_id>.csv`` adıyla içine yazılır.
        Başarısız ve geçersiz kayıtlar durum ve sebepleriyle birlikte yazılır;
        değerler veritabanındakiyle birebir aynıdır (float'lar kayıpsız).

        Raises:
            StorageError: run_id bulunamazsa veya dosya yazılamazsa.
        """
        with self._connect() as connection:
            self._require_run(connection, run_id)
            rows = self._fetch_repetition_rows(connection, run_id)
        path = _resolve_out_path(out_path, "raw", run_id)
        return _write_csv(path, RAW_CSV_COLUMNS, rows)

    def export_aggregates_csv(self, run_id: str, out_path: Path) -> Path:
        """Hedef bazında toplu sonuçları CSV dosyasına yazar ve dosya yolunu döndürür.

        Her hedef için (yapılandırma sırasıyla) sürüm, durum sayıları ve
        ``metrics`` tablosunda saklanan metriklerin ortalama, medyan, örneklem
        standart sapması, en küçük ve en büyük değeri yazılır. İstatistikler
        yalnızca saklanmış metriklerden hesaplanır; ham kayıtlar değiştirilmez.
        ``out_path`` bir dizinse dosya ``aggregates_<run_id>.csv`` adıyla yazılır.

        Raises:
            StorageError: run_id bulunamazsa veya dosya yazılamazsa.
        """
        with self._connect() as connection:
            self._require_run(connection, run_id)
            targets = connection.execute(
                "SELECT kind, version FROM run_targets WHERE run_id = ? ORDER BY position",
                (run_id,),
            ).fetchall()
            counts = {
                (row[0], row[1]): row[2]
                for row in connection.execute(
                    "SELECT target, status, COUNT(*) FROM repetitions WHERE run_id = ? "
                    "GROUP BY target, status",
                    (run_id,),
                )
            }
            metric_rows = connection.execute(
                "SELECT target, net_energy_j, duration_s, energy_per_task_j, edp_js, "
                "energy_per_task_unit, edp_unit FROM metrics WHERE run_id = ? "
                "ORDER BY target, repetition_index",
                (run_id,),
            ).fetchall()

        rows: list[list[Any]] = []
        seen: set[str] = set()
        for kind, version in targets:
            # Aynı tür yapılandırmada iki kez geçse bile tek satır yazılır.
            if kind in seen:
                continue
            seen.add(kind)
            own = [m for m in metric_rows if m[0] == kind]
            valid = counts.get((kind, RepetitionStatus.VALID.value), 0)
            invalid = counts.get((kind, RepetitionStatus.INVALID.value), 0)
            failed = counts.get((kind, RepetitionStatus.FAILED.value), 0)
            row: list[Any] = [run_id, kind, version, valid + invalid + failed, valid, invalid, failed, len(own)]
            for column, _name in enumerate(AGGREGATE_FIELDS, start=1):
                row.extend(_describe([m[column] for m in own]))
            # Birimler saklanan metriklerden alınır; metrik yoksa model varsayılanı yazılır.
            row.append(own[0][5] if own else UNIT_ENERGY_PER_TASK)
            row.append(own[0][6] if own else UNIT_EDP)
            rows.append(row)

        path = _resolve_out_path(out_path, "aggregates", run_id)
        return _write_csv(path, AGGREGATE_CSV_COLUMNS, rows)
