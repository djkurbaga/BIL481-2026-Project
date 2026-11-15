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


@pytest.mark.parametrize("field", [
    "title", "targets", "workload_size", "concurrency", "repetitions",
    "cooldown_s", "load_generator_host",
])
def test_missing_fields(raw_config, field):
    del raw_config[field]
    with pytest.raises(ConfigError, match=field):
        validate_config(raw_config)


@pytest.mark.parametrize("field", ["kind", "compose_file", "base_url", "health_url"])
def test_missing_target_fields(raw_config, field):
    del raw_config["targets"][0][field]
    with pytest.raises(ConfigError, match=field):
        validate_config(raw_config)


@pytest.mark.parametrize("field", ["workload_size", "concurrency", "repetitions"])
@pytest.mark.parametrize("value", [0, -1, 1.5, 1.0, True, False, "2", None, float("inf")])
def test_invalid_integers(raw_config, field, value):
    raw_config[field] = value
    with pytest.raises(ConfigError, match=field):
        validate_config(raw_config)


@pytest.mark.parametrize("field", ["cooldown_s", "grid_carbon_intensity", "health_timeout_s"])
@pytest.mark.parametrize("value", [-1, True, "2", float("nan"), float("inf"), 10**400])
def test_invalid_real_numbers(raw_config, field, value):
    destination = raw_config["targets"][0] if field == "health_timeout_s" else raw_config
    destination[field] = value
    with pytest.raises(ConfigError, match=field):
        validate_config(raw_config)


def test_zero_health_timeout(raw_config):
    raw_config["targets"][0]["health_timeout_s"] = 0
    with pytest.raises(ConfigError, match="health_timeout_s"):
        validate_config(raw_config)


@pytest.mark.parametrize("value", ["django", None, [], {}])
def test_unsupported_targets(raw_config, value):
    raw_config["targets"][0]["kind"] = value
    with pytest.raises(ConfigError, match="desteklenmeyen hedef"):
        validate_config(raw_config)


@pytest.mark.parametrize("value", [[], {}, "fastapi", ["fastapi"], None])
def test_invalid_target_list(raw_config, value):
    raw_config["targets"] = value
    with pytest.raises(ConfigError, match="targets"):
        validate_config(raw_config)


@pytest.mark.parametrize("value", [None, [], "title", 5])
def test_non_mapping_root(value):
    with pytest.raises(ConfigError, match="sözlük"):
        validate_config(value)


@pytest.mark.parametrize("field", ["title", "load_generator_host"])
@pytest.mark.parametrize("value", [None, 1, "", "   "])
def test_invalid_text(raw_config, field, value):
    raw_config[field] = value
    with pytest.raises(ConfigError, match=field):
        validate_config(raw_config)


@pytest.mark.parametrize("field", ["base_url", "health_url"])
@pytest.mark.parametrize("value", ["", "localhost", "file:///tmp/a", "http://[", "http://x:bad", "http://a b"])
def test_invalid_urls(raw_config, field, value):
    raw_config["targets"][0][field] = value
    with pytest.raises(ConfigError, match=field):
        validate_config(raw_config)


@pytest.mark.parametrize("value", [None, "", "\x00"])
def test_invalid_compose_path(raw_config, value):
    raw_config["targets"][0]["compose_file"] = value
    with pytest.raises(ConfigError, match="compose_file"):
        validate_config(raw_config)
