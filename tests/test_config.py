"""UC1 yapılandırmasının model dönüşümünü ve sınırlarını sınar."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from gsmf.config import load_config, validate_config
from gsmf.models import ConfigError, PlatformKind


@pytest.fixture
def raw_config():
    """Her test için bağımsız, geçerli bir yapılandırma verir."""
    return {
        "title": "UC1 deneyi",
        "targets": [{
            "kind": "fastapi",
            "compose_file": "../apps/fastapi-baseline/docker-compose.yml",
            "base_url": "http://127.0.0.1:8000",
            "health_url": "http://127.0.0.1:8000/health",
        }],
        "workload_size": 100,
        "concurrency": 2,
        "repetitions": 3,
        "cooldown_s": 0,
        "load_generator_host": "loadgen.local",
    }


@pytest.mark.parametrize("kind", list(PlatformKind))
def test_supported_platforms_and_defaults(raw_config, kind):
    raw_config["targets"][0]["kind"] = kind.value
    original = deepcopy(raw_config)
    config = validate_config(raw_config)
    assert config.targets[0].kind is kind
    assert config.targets[0].health_timeout_s == 120.0
    assert config.targets[0].compose_file == Path(original["targets"][0]["compose_file"])
    assert config.grid_carbon_intensity is None
    assert config.cooldown_s == 0.0
    assert raw_config == original


def test_optional_numbers(raw_config):
    raw_config["grid_carbon_intensity"] = 0
    raw_config["cooldown_s"] = 0.25
    raw_config["targets"][0]["health_timeout_s"] = 1.5
    config = validate_config(raw_config)
    assert config.grid_carbon_intensity == 0.0
    assert config.cooldown_s == 0.25
    assert config.targets[0].health_timeout_s == 1.5


def test_multiple_targets_keep_order(raw_config):
    second = dict(raw_config["targets"][0], kind="budibase")
    raw_config["targets"].append(second)
    assert [target.kind for target in validate_config(raw_config).targets] == [
        PlatformKind.FASTAPI, PlatformKind.BUDIBASE,
    ]
