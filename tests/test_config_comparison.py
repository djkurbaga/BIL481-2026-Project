"""Bağımsız doğrulayıcıların sözleşmesini ve karşılaştırma raporunu sınar."""
from copy import deepcopy
import json

import pytest

from comparisons.config_manual_vs_pydantic import (
    cases, main, outcome, validate_config, validate_pydantic,
)


@pytest.mark.parametrize("name,raw,expected", cases(), ids=[case[0] for case in cases()])
def test_validators_follow_expected_contract(name, raw, expected):
    """İki uygulamanın uzlaşması yanında beklenen kabul kararını da denetler."""
    manual = outcome(validate_config, raw)
    model = outcome(validate_pydantic, raw)
    assert manual[0] is expected, name
    assert model[0] is expected, name
    assert manual[1] == model[1]


def test_report_and_input_preservation(capsys):
    """Raporun sayımlarını doğrular; karşılaştırma girdisi değişmemelidir."""
    raw = cases()[0][1]
    original = deepcopy(raw)
    validate_pydantic(raw)
    assert raw == original
    assert main(["--iterations", "2", "--repeats", "2"]) == 0
    header, *rows, summary = map(json.loads, capsys.readouterr().out.splitlines())
    assert header["cases"] == len(rows) == len(cases())
    assert summary["mismatches"] == 0
    assert all(row["equivalent"] for row in rows)
    assert all(len(samples) == 2 for samples in summary["samples_seconds"].values())
