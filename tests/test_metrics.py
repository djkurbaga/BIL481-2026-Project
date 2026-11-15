"""UC3 (FR-8) verimlilik metrikleri için birim testleri.

Beklenen değerler elle hesaplanmıştır; her testin yorumunda hesap gösterilir.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from gsmf.metrics import (
    compute_metrics,
    compute_repetition_metrics,
    energy_delay_product,
    energy_per_task,
    format_table,
    load_records_csv,
    main,
    skip_reason,
)
from gsmf.models import (
    UNIT_EDP,
    UNIT_ENERGY_PER_TASK,
    EfficiencyMetrics,
    PlatformKind,
    RepetitionRecord,
    RepetitionStatus,
)

# Depo kökündeki örnek (gerçek ölçüm olmayan) veri dosyası.
SAMPLE_CSV = Path(__file__).resolve().parent.parent / "examples" / "sample_measurements.csv"


def make_record(**overrides) -> RepetitionRecord:
    """Varsayılan olarak geçerli bir FastAPI tekrar kaydı üretir; alanlar ezilebilir."""
    base = dict(
        run_id="run-test",
        target=PlatformKind.FASTAPI,
        repetition_index=1,
        status=RepetitionStatus.VALID,
        reason=None,
        idle_power_w=12.0,
        gross_energy_j=635.2,
        duration_s=18.1,
        net_energy_j=418.0,
        completed_tasks=1000,
    )
    base.update(overrides)
    return RepetitionRecord(**base)


# ---------------------------------------------------------------------------
# Geçerli kayıt
# ---------------------------------------------------------------------------


def test_valid_record_matches_manual_calculation():
    """418 J / 1000 görev = 0.418 J/task; 418 J × 18.1 s = 7565.8 J·s."""
    metrics = compute_repetition_metrics(make_record())

    assert isinstance(metrics, EfficiencyMetrics)
    assert metrics.energy_per_task_j == pytest.approx(0.418)
    assert metrics.edp_js == pytest.approx(7565.8)
    # Kaynak değerler sonuca aynen taşınmalı.
    assert metrics.net_energy_j == pytest.approx(418.0)
    assert metrics.duration_s == pytest.approx(18.1)
    assert metrics.completed_tasks == 1000
    assert metrics.target is PlatformKind.FASTAPI
    assert metrics.repetition_index == 1


def test_units_are_recorded():
    """FR-8: birimler J/task ve J·s olarak kaydedilmeli."""
    metrics = compute_repetition_metrics(make_record())

    assert metrics.energy_per_task_unit == UNIT_ENERGY_PER_TASK == "J/task"
    assert metrics.edp_unit == UNIT_EDP == "J·s"


def test_source_record_is_not_modified():
    """FR-11: hesaplama ölçülen değerleri değiştirmemeli."""
    record = make_record()
    before = dataclasses.asdict(record)

    compute_metrics([record])

    assert dataclasses.asdict(record) == before


# ---------------------------------------------------------------------------
# Atlanan kayıtlar
# ---------------------------------------------------------------------------


def test_failed_record_is_skipped():
    """FAILED tekrar için metrik hesaplanmaz, sebep raporlanır."""
    record = make_record(
        status=RepetitionStatus.FAILED,
        reason="k6 remote execution failed",
        net_energy_j=None,
        duration_s=None,
        completed_tasks=None,
    )

    assert compute_repetition_metrics(record) is None
    assert compute_metrics([record]) == []
    assert "failed" in skip_reason(record)
    assert "k6 remote execution failed" in skip_reason(record)


def test_invalid_record_is_skipped_even_with_usable_numbers():
    """INVALID tekrar, sayıları hesaplanabilir olsa bile atlanır."""
    record = make_record(status=RepetitionStatus.INVALID, reason="unreadable RAPL counter")

    assert compute_repetition_metrics(record) is None
    assert "invalid" in skip_reason(record)


@pytest.mark.parametrize("tasks", [0, -5, None])
def test_zero_completed_tasks_is_guarded(tasks):
    """Görev sayısı sıfır/negatif/eksikse sıfıra bölme olmadan atlanır."""
    record = make_record(completed_tasks=tasks)

    assert compute_repetition_metrics(record) is None
    assert "completed_tasks" in skip_reason(record)


def test_energy_per_task_rejects_zero_tasks():
    """Alt düzey formül sıfır görevle çağrılırsa ValueError verir."""
    with pytest.raises(ValueError):
        energy_per_task(100.0, 0)


def test_edp_rejects_non_positive_duration():
    """Alt düzey EDP formülü sıfır süreyle çağrılırsa ValueError verir."""
    with pytest.raises(ValueError):
        energy_delay_product(100.0, 0.0)


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"net_energy_j": -27.3}, "negatif"),
        ({"net_energy_j": None}, "net_energy_j"),
        ({"duration_s": None}, "duration_s"),
        ({"duration_s": 0.0}, "süre"),
        ({"net_energy_j": float("nan")}, "net_energy_j"),
    ],
)
def test_valid_status_with_unusable_values_is_skipped(overrides, expected):
    """VALID işaretli ama kullanılamaz değerli kayıtlar da atlanır."""
    record = make_record(**overrides)

    assert compute_repetition_metrics(record) is None
    assert expected in skip_reason(record)


# ---------------------------------------------------------------------------
# Çoklu tekrar
# ---------------------------------------------------------------------------


def test_multiple_repetitions_keep_order_and_skip_unusable():
    """Karışık listede yalnız geçerliler hesaplanır ve sıra korunur."""
    records = [
        make_record(repetition_index=1, net_energy_j=418.0, duration_s=18.1, completed_tasks=1000),
        make_record(repetition_index=2, status=RepetitionStatus.FAILED, reason="startup failure",
                    net_energy_j=None, duration_s=None, completed_tasks=None),
        make_record(repetition_index=3, net_energy_j=400.0, duration_s=20.0, completed_tasks=800),
        make_record(repetition_index=4, status=RepetitionStatus.INVALID, reason="negative net energy",
                    net_energy_j=-5.0),
        make_record(repetition_index=5, completed_tasks=0),
        make_record(repetition_index=6, target=PlatformKind.BUDIBASE,
                    net_energy_j=1862.1, duration_s=43.2, completed_tasks=1000),
    ]

    results = compute_metrics(records)

    assert [m.repetition_index for m in results] == [1, 3, 6]
    # Rep 3: 400 / 800 = 0.5 J/task; 400 × 20 = 8000 J·s
    assert results[1].energy_per_task_j == pytest.approx(0.5)
    assert results[1].edp_js == pytest.approx(8000.0)
    # Rep 6: 1862.1 / 1000 = 1.8621 J/task; 1862.1 × 43.2 = 80442.72 J·s
    assert results[2].target is PlatformKind.BUDIBASE
    assert results[2].energy_per_task_j == pytest.approx(1.8621)
    assert results[2].edp_js == pytest.approx(80442.72)


def test_compute_metrics_accepts_generator_and_empty_input():
    """Herhangi bir iterable kabul edilir; boş girdi boş liste döndürür."""
    assert compute_metrics([]) == []
    assert len(compute_metrics(make_record(repetition_index=i) for i in range(1, 4))) == 3


# ---------------------------------------------------------------------------
# CSV ve demo
# ---------------------------------------------------------------------------


def test_sample_csv_loads_and_matches_manual_values():
    """Örnek CSV: 9 kayıt, 6 geçerli; ilk satır elle doğrulanır."""
    records = load_records_csv(SAMPLE_CSV)
    results = compute_metrics(records)

    assert len(records) == 9
    assert len(results) == 6
    # fastapi rep 1: 418.0 J / 1000 = 0.418 J/task; 418.0 × 18.1 = 7565.8 J·s
    first = results[0]
    assert (first.target, first.repetition_index) == (PlatformKind.FASTAPI, 1)
    assert first.energy_per_task_j == pytest.approx(0.418)
    assert first.edp_js == pytest.approx(7565.8)


def test_csv_missing_column_raises(tmp_path):
    """Eksik sütunlu CSV açık bir hata ile reddedilir."""
    bad = tmp_path / "bad.csv"
    bad.write_text("run_id,target\nr1,fastapi\n", encoding="utf-8")

    with pytest.raises(ValueError, match="eksik sütunlar"):
        load_records_csv(bad)


def test_format_table_lists_metrics_and_skip_reasons():
    """Tabloda birimli başlıklar, değerler ve atlanma sebepleri bulunur."""
    table = format_table(
        [make_record(), make_record(repetition_index=2, completed_tasks=0)]
    )

    assert "Energy/task (J/task)" in table
    assert "EDP (J·s)" in table
    assert "0.4180" in table
    assert "7,565.8" in table
    assert "skipped:" in table


def test_cli_main_prints_table(capsys):
    """``python -m gsmf.metrics <csv>`` tablo ve özet yazdırır, 0 ile çıkar."""
    exit_code = main([str(SAMPLE_CSV)])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "6 of 9 repetitions used for metrics" in out
    assert "budibase" in out


def test_cli_main_missing_file_returns_error(tmp_path, capsys):
    """Olmayan dosya için anlaşılır hata ve 1 çıkış kodu."""
    exit_code = main([str(tmp_path / "missing.csv")])

    assert exit_code == 1
    assert "error:" in capsys.readouterr().err
