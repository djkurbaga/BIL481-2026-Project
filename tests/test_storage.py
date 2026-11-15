"""UC4 (FR-11) SQLite sonuç deposu ve CSV dışa aktarımı için testler.

Testler geçici dizinde gerçek bir SQLite dosyası kullanır; Docker gerekmez.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path, PureWindowsPath
import pytest

from gsmf.metrics import compute_metrics, compute_repetition_metrics, load_records_csv
from gsmf.models import (
    UNIT_EDP,
    UNIT_ENERGY_PER_TASK,
    BenchmarkConfig,
    PlatformKind,
    RepetitionRecord,
    RepetitionStatus,
    StorageError,
    TargetPlatform,
    TestbedSettings,
)
from gsmf.storage import AGGREGATE_CSV_COLUMNS, RAW_CSV_COLUMNS, ResultStore

RUN = "run-1"


def make_target(kind: PlatformKind) -> TargetPlatform:
    """Verilen tür için örnek bir hedef tanımı üretir."""
    return TargetPlatform(
        kind=kind,
        compose_file=Path(f"apps/{kind.value}/docker-compose.yml"),
        base_url=f"http://{kind.value}.local",
        health_url=f"http://{kind.value}.local/health",
        health_timeout_s=60.0,
    )


CONFIG = BenchmarkConfig(
    title="Örnek kıyaslama — ğüşıöç",
    targets=(make_target(PlatformKind.FASTAPI), make_target(PlatformKind.BUDIBASE)),
    workload_size=1000,
    concurrency=10,
    repetitions=3,
    cooldown_s=30.0,
    load_generator_host="loadgen.local",
    grid_carbon_intensity=420.5,
)
VERSIONS = {PlatformKind.FASTAPI: "0.115.0", PlatformKind.BUDIBASE: "3.2.1"}
TESTBED = TestbedSettings(
    hostname="testbed-01",
    cpu_governor="performance",
    turbo_boost_disabled=True,
    rapl_domains=("package-0", "dram"),
)


def make_record(**overrides) -> RepetitionRecord:
    """Varsayılan olarak geçerli bir FastAPI tekrar kaydı üretir; alanlar ezilebilir."""
    base = dict(
        run_id=RUN,
        target=PlatformKind.FASTAPI,
        repetition_index=1,
        status=RepetitionStatus.VALID,
        reason=None,
        idle_power_w=12.0,
        gross_energy_j=635.2,
        duration_s=18.1,
        net_energy_j=418.0,
        completed_tasks=1000,
        workload_errors=0,
        started_at=datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return RepetitionRecord(**base)


@pytest.fixture()
def store(tmp_path: Path) -> ResultStore:
    """Şeması kurulmuş ve RUN çalıştırması kaydedilmiş boş bir depo."""
    result = ResultStore(tmp_path / "results.db")
    result.initialize_schema()
    result.save_run(RUN, CONFIG, VERSIONS, TESTBED)
    return result


def mixed_records() -> list[RepetitionRecord]:
    """Geçerli, geçersiz ve başarısız kayıtlardan oluşan karışık bir liste."""
    return [
        make_record(repetition_index=1),
        make_record(repetition_index=2, gross_energy_j=640.0, duration_s=18.4,
                    net_energy_j=417.36, idle_power_w=12.1),
        make_record(repetition_index=3, status=RepetitionStatus.INVALID,
                    reason="net enerji negatif", net_energy_j=-5.0),
        make_record(target=PlatformKind.BUDIBASE, repetition_index=1,
                    gross_energy_j=2000.0, duration_s=40.0, net_energy_j=1500.0),
        make_record(target=PlatformKind.BUDIBASE, repetition_index=2,
                    status=RepetitionStatus.FAILED, reason="yığın başlatılamadı",
                    idle_power_w=None, gross_energy_j=None, duration_s=None,
                    net_energy_j=None, completed_tasks=None, started_at=None),
    ]


def read_csv(path: Path) -> list[dict[str, str]]:
    """CSV dosyasını sözlük satırları olarak okur."""
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


# ---------------------------------------------------------------------------
# Şema ve çalıştırma kaydı
# ---------------------------------------------------------------------------


def test_initialize_schema_creates_tables_and_is_idempotent(tmp_path: Path):
    """İki kez çağrılması veri kaybına yol açmaz; dört tablo oluşur."""
    db = tmp_path / "sub" / "x.db"
    db.parent.mkdir()
    s = ResultStore(db)
    s.initialize_schema()
    s.save_run(RUN, CONFIG, VERSIONS, TESTBED)
    s.initialize_schema()
    with sqlite3.connect(db) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"runs", "run_targets", "repetitions", "metrics"} <= tables
        assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1


def test_save_run_stores_config_versions_and_testbed(store: ResultStore):
    """Yapılandırma, hedef sürümleri ve testbed ayarları eksiksiz saklanır."""
    with sqlite3.connect(store.db_path) as conn:
        run = conn.execute(
            "SELECT title, workload_size, concurrency, repetitions, cooldown_s, "
            "load_generator_host, grid_carbon_intensity, config_json, testbed_hostname, "
            "cpu_governor, turbo_boost_disabled, rapl_domains_json FROM runs WHERE run_id=?",
            (RUN,),
        ).fetchone()
        targets = conn.execute(
            "SELECT position, kind, version, compose_file, health_timeout_s "
            "FROM run_targets WHERE run_id=? ORDER BY position",
            (RUN,),
        ).fetchall()
    assert run[:7] == (CONFIG.title, 1000, 10, 3, 30.0, "loadgen.local", 420.5)
    config_json = json.loads(run[7])
    assert config_json["title"] == CONFIG.title
    assert config_json["targets"][1]["kind"] == "budibase"
    assert config_json["targets"][0]["compose_file"] == "apps/fastapi/docker-compose.yml"
    assert run[8:] == ("testbed-01", "performance", 1, '["package-0", "dram"]')
    assert targets == [
        (1, "fastapi", "0.115.0", "apps/fastapi/docker-compose.yml", 60.0),
        (2, "budibase", "3.2.1", "apps/budibase/docker-compose.yml", 60.0),
    ]

def test_compose_path_stored_with_forward_slashes(tmp_path: Path):
    """Windows yolu (ters eğik çizgi) her işletim sisteminde "/" ayracıyla saklanır."""
    target = TargetPlatform(
        kind=PlatformKind.FASTAPI,
        compose_file=PureWindowsPath(r"apps\fastapi\docker-compose.yml"),
        base_url="http://fastapi.local",
        health_url="http://fastapi.local/health",
    )
    config = BenchmarkConfig(
        title="windows", targets=(target,), workload_size=1, concurrency=1,
        repetitions=1, cooldown_s=0.0, load_generator_host="loadgen",
    )
    s = ResultStore(tmp_path / "w.db")
    s.initialize_schema()
    s.save_run("w", config, {PlatformKind.FASTAPI: "1"}, TESTBED)
    with sqlite3.connect(s.db_path) as conn:
        stored = conn.execute("SELECT compose_file FROM run_targets").fetchone()[0]
        config_json = json.loads(conn.execute("SELECT config_json FROM runs").fetchone()[0])
    conn.close()
    assert stored == "apps/fastapi/docker-compose.yml"
    assert config_json["targets"][0]["compose_file"] == "apps/fastapi/docker-compose.yml"


def test_save_run_rejects_duplicate_run_id(store: ResultStore):
    """Aynı run_id ikinci kez kaydedilemez."""
    with pytest.raises(StorageError, match="zaten kayıtlı"):
        store.save_run(RUN, CONFIG, VERSIONS, TESTBED)


@pytest.mark.parametrize(
    ("versions", "message"),
    [
        ({PlatformKind.FASTAPI: "1.0"}, "sürümü eksik: budibase"),
        ({**VERSIONS, PlatformKind.APPSMITH: "1.0"}, "yapılandırmada olmayan hedef"),
        ({PlatformKind.FASTAPI: " ", PlatformKind.BUDIBASE: "3"}, "boş olmayan"),
    ],
)
def test_save_run_validates_target_versions(tmp_path: Path, versions, message):
    """Her hedef için boş olmayan bir sürüm gerekir; fazladan hedef kabul edilmez."""
    s = ResultStore(tmp_path / "v.db")
    s.initialize_schema()
    with pytest.raises(StorageError, match=message):
        s.save_run("r", CONFIG, versions, TESTBED)
    assert s.load_repetitions("r") == []


def test_save_run_rejects_empty_run_id(tmp_path: Path):
    """Boş run_id reddedilir."""
    s = ResultStore(tmp_path / "e.db")
    s.initialize_schema()
    with pytest.raises(StorageError, match="run_id"):
        s.save_run("  ", CONFIG, VERSIONS, TESTBED)


def test_operations_without_schema_raise_storage_error(tmp_path: Path):
    """Şema kurulmadan yapılan işlem SQLite hatası yerine StorageError verir."""
    s = ResultStore(tmp_path / "bos.db")
    with pytest.raises(StorageError, match="SQLite"):
        s.save_run(RUN, CONFIG, VERSIONS, TESTBED)


def test_unopenable_database_raises_storage_error(tmp_path: Path):
    """Açılamayan veritabanı yolu StorageError verir."""
    s = ResultStore(tmp_path / "yok" / "x.db")
    with pytest.raises(StorageError):
        s.initialize_schema()


# ---------------------------------------------------------------------------
# Tekrar kayıtları
# ---------------------------------------------------------------------------


def test_all_statuses_round_trip_unchanged(store: ResultStore):
    """VALID, INVALID ve FAILED kayıtlar durum ve sebepleriyle birebir geri okunur."""
    records = mixed_records()
    for record in records:
        store.save_repetition(record)
    assert store.load_repetitions(RUN) == records
    loaded = store.load_repetitions(RUN)
    assert [r.status for r in loaded] == [
        RepetitionStatus.VALID, RepetitionStatus.VALID, RepetitionStatus.INVALID,
        RepetitionStatus.VALID, RepetitionStatus.FAILED,
    ]
    assert loaded[4].reason == "yığın başlatılamadı"


def test_load_repetitions_keeps_insertion_order(store: ResultStore):
    """Kayıtlar eklendikleri sırayla döner."""
    order = [3, 1, 2]
    for index in order:
        store.save_repetition(make_record(repetition_index=index))
    assert [r.repetition_index for r in store.load_repetitions(RUN)] == order


def test_load_repetitions_unknown_run_returns_empty(store: ResultStore):
    """Bilinmeyen çalıştırma için boş liste döner."""
    assert store.load_repetitions("yok") == []


def test_float_precision_and_timezone_preserved(store: ResultStore):
    """Float değerler bit düzeyinde, zaman damgası saat dilimiyle korunur."""
    started = datetime(2026, 11, 15, 12, 30, 1, 123456, tzinfo=timezone(timedelta(hours=3)))
    record = make_record(net_energy_j=0.1 + 0.2, duration_s=1e-12, gross_energy_j=float("inf"),
                         started_at=started)
    store.save_repetition(record)
    loaded = store.load_repetitions(RUN)[0]
    assert loaded.net_energy_j == 0.30000000000000004
    assert loaded.duration_s == 1e-12
    assert loaded.gross_energy_j == float("inf")
    assert loaded.started_at == started and loaded.started_at.utcoffset() == timedelta(hours=3)


def test_duplicate_repetition_rejected_and_original_kept(store: ResultStore):
    """Yinelenen kayıt reddedilir; ilk saklanan değerler değişmez."""
    store.save_repetition(make_record())
    with pytest.raises(StorageError, match="zaten var"):
        store.save_repetition(make_record(net_energy_j=1.0))
    assert store.load_repetitions(RUN) == [make_record()]


def test_repetition_requires_known_run(store: ResultStore):
    """Kaydedilmemiş çalıştırmaya tekrar eklenemez."""
    with pytest.raises(StorageError, match="bulunamadı"):
        store.save_repetition(make_record(run_id="baska"))


def test_repetition_target_must_belong_to_run(store: ResultStore):
    """Çalıştırmanın yapılandırmasında olmayan hedef reddedilir."""
    with pytest.raises(StorageError, match="appsmith"):
        store.save_repetition(make_record(target=PlatformKind.APPSMITH))


@pytest.mark.parametrize("status", [RepetitionStatus.INVALID, RepetitionStatus.FAILED])
@pytest.mark.parametrize("reason", [None, "", "   "])
def test_failed_or_invalid_requires_reason(store: ResultStore, status, reason):
    """Başarısız/geçersiz kayıt sebep olmadan saklanmaz."""
    with pytest.raises(StorageError, match="reason"):
        store.save_repetition(make_record(status=status, reason=reason))
    assert store.load_repetitions(RUN) == []


def test_nan_measurement_rejected(store: ResultStore):
    """NaN, SQLite'ta NULL'a dönüşeceği için (değer değişir) reddedilir."""
    with pytest.raises(StorageError, match="NaN"):
        store.save_repetition(make_record(gross_energy_j=float("nan")))
    assert store.load_repetitions(RUN) == []


@pytest.mark.parametrize(
    "overrides",
    [{"completed_tasks": True}, {"completed_tasks": 1.5}, {"net_energy_j": "418"}],
)
def test_wrong_value_types_rejected(store: ResultStore, overrides):
    """Yanlış türdeki ölçüm değerleri sessizce dönüştürülmez."""
    with pytest.raises(StorageError):
        store.save_repetition(make_record(**overrides))


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE repetitions SET net_energy_j = 1.0",
        "DELETE FROM repetitions",
        "UPDATE runs SET title = 'x'",
        "DELETE FROM run_targets",
        "UPDATE metrics SET edp_js = 0",
    ],
)
def test_database_triggers_block_modification(store: ResultStore, sql):
    """Doğrudan SQL ile bile saklanan değerler değiştirilemez veya silinemez."""
    store.save_repetition(make_record())
    store.save_metrics(compute_metrics([make_record()]))
    with sqlite3.connect(store.db_path) as conn:
        with pytest.raises(sqlite3.DatabaseError, match="değiştirilemez"):
            conn.execute(sql)
    assert store.load_repetitions(RUN) == [make_record()]


# ---------------------------------------------------------------------------
# Metrikler
# ---------------------------------------------------------------------------


def test_save_metrics_writes_separate_table(store: ResultStore):
    """Metrikler ayrı tabloya yazılır; ham kayıt değişmez."""
    records = mixed_records()
    for record in records:
        store.save_repetition(record)
    computed = compute_metrics(records)
    store.save_metrics(computed)
    with sqlite3.connect(store.db_path) as conn:
        rows = conn.execute(
            "SELECT target, repetition_index, energy_per_task_j, edp_js, energy_per_task_unit, "
            "edp_unit FROM metrics ORDER BY target, repetition_index"
        ).fetchall()
    # 418 / 1000 = 0.418 J/task; 418 × 18.1 = 7565.8 J·s (yalnızca geçerli 3 kayıt).
    assert len(rows) == 3
    assert rows[1][:2] == ("fastapi", 1)
    assert rows[1][2] == pytest.approx(0.418) and rows[1][3] == pytest.approx(7565.8)
    assert rows[1][4:] == (UNIT_ENERGY_PER_TASK, UNIT_EDP)
    assert store.load_repetitions(RUN) == records


def test_save_metrics_is_atomic(store: ResultStore):
    """Listedeki bir metrik hatalıysa hiçbiri yazılmaz."""
    store.save_repetition(make_record())
    good = compute_repetition_metrics(make_record())
    orphan = compute_repetition_metrics(make_record(repetition_index=9))
    with pytest.raises(StorageError, match="kaynak tekrarı bulunamadı"):
        store.save_metrics([good, orphan])
    with sqlite3.connect(store.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0] == 0


def test_save_metrics_rejects_duplicates(store: ResultStore):
    """Aynı tekrarın metriği ikinci kez yazılamaz."""
    store.save_repetition(make_record())
    store.save_metrics(compute_metrics([make_record()]))
    with pytest.raises(StorageError, match="zaten kayıtlı"):
        store.save_metrics(compute_metrics([make_record()]))


def test_save_metrics_rejects_non_valid_source(store: ResultStore):
    """Geçersiz tekrar için metrik saklanamaz."""
    store.save_repetition(make_record(status=RepetitionStatus.INVALID, reason="sayaç okunamadı"))
    metric = compute_repetition_metrics(make_record())
    with pytest.raises(StorageError, match="invalid"):
        store.save_metrics([metric])


def test_save_metrics_rejects_values_not_matching_raw(store: ResultStore):
    """Metrik, saklanan ham değerlerden farklı bir net enerjiyle yazılamaz."""
    store.save_repetition(make_record())
    metric = compute_repetition_metrics(make_record(net_energy_j=500.0))
    with pytest.raises(StorageError, match="uyuşmuyor"):
        store.save_metrics([metric])


# ---------------------------------------------------------------------------
# CSV dışa aktarma
# ---------------------------------------------------------------------------


def test_export_raw_csv_includes_all_records(store: ResultStore, tmp_path: Path):
    """Ham CSV tüm durumları sebepleriyle içerir ve UC3 okuyucusuyla geri okunur."""
    records = mixed_records()
    for record in records:
        store.save_repetition(record)
    out = store.export_raw_csv(RUN, tmp_path / "out" / "raw.csv")
    assert out == tmp_path / "out" / "raw.csv"
    rows = read_csv(out)
    assert list(rows[0].keys()) == list(RAW_CSV_COLUMNS)
    assert [r["status"] for r in rows] == ["valid", "valid", "invalid", "valid", "failed"]
    assert rows[2]["reason"] == "net enerji negatif"
    assert rows[4]["net_energy_j"] == "" and rows[4]["reason"] == "yığın başlatılamadı"
    assert rows[0]["started_at"] == "2026-11-15T10:00:00+00:00"
    # UC3 CSV okuyucusu zaman damgası dışında aynı kayıtları üretmelidir.
    reloaded = load_records_csv(out)
    assert reloaded == [
        RepetitionRecord(**{**r.__dict__, "started_at": None}) for r in records
    ]


def test_export_raw_csv_to_directory_uses_default_name(store: ResultStore, tmp_path: Path):
    """Çıktı yolu dizinse raw_<run_id>.csv adı kullanılır; güvensiz karakterler temizlenir."""
    store.save_run("2026/11 ölçüm", CONFIG, VERSIONS, TESTBED)
    out = store.export_raw_csv("2026/11 ölçüm", tmp_path)
    assert out.parent == tmp_path
    assert out.name == "raw_2026_11__l__m.csv"
    assert read_csv(out) == []


@pytest.mark.parametrize("name", ["results/", "results", "out.v2"])
def test_export_to_new_directory_creates_it(store: ResultStore, tmp_path: Path, monkeypatch, name):
    """Henüz var olmayan ve .csv ile bitmeyen yol dizin olarak oluşturulur."""
    monkeypatch.chdir(tmp_path)
    raw = store.export_raw_csv(RUN, Path(name))
    agg = store.export_aggregates_csv(RUN, Path(name))
    folder = tmp_path / name.rstrip("/")
    assert folder.is_dir()
    assert raw.resolve() == folder / f"raw_{RUN}.csv"
    assert agg.resolve() == folder / f"aggregates_{RUN}.csv"


def test_export_to_existing_directory_named_like_csv(store: ResultStore, tmp_path: Path):
    """.csv ile biten ama var olan bir dizin yine dizin olarak kullanılır."""
    folder = tmp_path / "eski.csv"
    folder.mkdir()
    assert store.export_raw_csv(RUN, folder) == folder / f"raw_{RUN}.csv"


def test_export_empty_run_writes_header_only(store: ResultStore, tmp_path: Path):
    """Kaydı olmayan çalıştırma için yalnızca başlık satırı yazılır."""
    out = store.export_raw_csv(RUN, tmp_path / "raw.csv")
    assert out.read_text(encoding="utf-8").strip() == ",".join(RAW_CSV_COLUMNS)


@pytest.mark.parametrize("method", ["export_raw_csv", "export_aggregates_csv"])
def test_export_unknown_run_raises(store: ResultStore, tmp_path: Path, method):
    """Bilinmeyen run_id için dosya oluşturulmaz ve StorageError verilir."""
    with pytest.raises(StorageError, match="bulunamadı"):
        getattr(store, method)("yok", tmp_path / "x.csv")
    assert not (tmp_path / "x.csv").exists()


@pytest.mark.parametrize("method", ["export_raw_csv", "export_aggregates_csv"])
def test_export_unwritable_path_raises(store: ResultStore, tmp_path: Path, method):
    """Yazılamayan yol (dosyanın altında dizin) StorageError verir."""
    blocker = tmp_path / "dosya"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(StorageError, match="yazılamadı"):
        getattr(store, method)(RUN, blocker / "alt" / "x.csv")


def test_export_aggregates_from_stored_metrics(store: ResultStore, tmp_path: Path):
    """Toplu sonuçlar hedef başına sayımlar ve saklanan metriklerin istatistiklerini içerir."""
    records = mixed_records()
    for record in records:
        store.save_repetition(record)
    store.save_metrics(compute_metrics(records))
    out = store.export_aggregates_csv(RUN, tmp_path)
    assert out.name == f"aggregates_{RUN}.csv"
    rows = read_csv(out)
    assert list(rows[0].keys()) == list(AGGREGATE_CSV_COLUMNS)
    fastapi, budibase = rows
    assert (fastapi["target"], fastapi["target_version"]) == ("fastapi", "0.115.0")
    assert (fastapi["repetitions_total"], fastapi["valid_count"], fastapi["invalid_count"],
            fastapi["failed_count"], fastapi["metrics_count"]) == ("3", "2", "1", "0", "2")
    # (418 + 417.36) / 2 = 417.68 J; stdev = |418 − 417.36| / √2 ≈ 0.452548 J.
    assert float(fastapi["net_energy_j_mean"]) == pytest.approx(417.68)
    assert float(fastapi["net_energy_j_median"]) == pytest.approx(417.68)
    assert float(fastapi["net_energy_j_stdev"]) == pytest.approx(0.64 / 2 ** 0.5)
    assert float(fastapi["net_energy_j_min"]) == 417.36
    assert float(fastapi["net_energy_j_max"]) == 418.0
    # EDP: 418 × 18.1 = 7565.8 ve 417.36 × 18.4 = 7679.424 → ortalama 7622.612 J·s.
    assert float(fastapi["edp_js_mean"]) == pytest.approx(7622.612)
    assert fastapi["energy_per_task_unit"] == "J/task" and fastapi["edp_unit"] == "J·s"
    # Budibase: 1 geçerli, 1 başarısız; tek değer için stdev boş.
    assert (budibase["valid_count"], budibase["failed_count"], budibase["metrics_count"]) == ("1", "1", "1")
    assert float(budibase["energy_per_task_j_mean"]) == pytest.approx(1.5)
    assert budibase["net_energy_j_stdev"] == ""


def test_export_aggregates_without_metrics_leaves_values_blank(store: ResultStore, tmp_path: Path):
    """Metrik saklanmamışsa sayımlar yazılır, istatistik hücreleri boş kalır."""
    store.save_repetition(make_record(status=RepetitionStatus.FAILED, reason="k6 hatası",
                                      net_energy_j=None))
    rows = read_csv(store.export_aggregates_csv(RUN, tmp_path / "agg.csv"))
    assert [r["target"] for r in rows] == ["fastapi", "budibase"]
    assert rows[0]["failed_count"] == "1" and rows[0]["metrics_count"] == "0"
    assert rows[0]["net_energy_j_mean"] == "" and rows[1]["repetitions_total"] == "0"


def test_exports_do_not_modify_stored_values(store: ResultStore, tmp_path: Path):
    """Dışa aktarma ve metrik hesabından sonra ham kayıtlar aynı kalır."""
    records = mixed_records()
    for record in records:
        store.save_repetition(record)
    store.save_metrics(compute_metrics(store.load_repetitions(RUN)))
    store.export_raw_csv(RUN, tmp_path)
    store.export_aggregates_csv(RUN, tmp_path)
    assert store.load_repetitions(RUN) == records
