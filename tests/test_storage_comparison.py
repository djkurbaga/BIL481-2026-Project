"""Depolama karşılaştırma betiğinin küçük bir kümede doğru çıktı verdiğini sınar."""

import json

from comparisons import storage_sqlite_vs_csv_json as comparison


def test_comparison_reports_all_formats(capsys):
    """Üç biçim de kayıpsız geri okunur; yalnızca SQLite değişikliği ve yinelemeyi reddeder."""
    assert comparison.main(["--records", "30", "--repeats", "1"]) == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    header, *rows = lines
    assert header["records"] == 30 and sum(header["statuses"].values()) == 30
    by_format = {row["format"]: row for row in rows}
    assert set(by_format) == {"sqlite", "csv", "jsonl"}
    assert all(row["round_trip_equal"] for row in rows)
    assert by_format["sqlite"]["duplicate_append"] == "reddedildi"
    assert by_format["sqlite"]["tamper_existing_value"].startswith("reddedildi")
    assert by_format["csv"]["tamper_existing_value"] == "değiştirildi"
    assert by_format["jsonl"]["duplicate_append"] == "eklendi"
