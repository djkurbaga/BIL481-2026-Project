"""FR-1 kurallarını elle doğrulama ve bağımsız Pydantic modeliyle karşılaştırır."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import platform
import statistics
import sys
import time
from typing import Annotated, Literal
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pydantic
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError
from gsmf.config import validate_config
from gsmf.models import BenchmarkConfig, ConfigError, PlatformKind, TargetPlatform


def text_value(value):
    """Metni kırpar; örtük tür dönüşümünü engeller."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("boş olmayan metin gerekli")
    return value.strip()


def number_value(value):
    """Mantıksal değerleri, metinleri ve taşan sayıları reddeder."""
    try:
        if type(value) in (int, float) and math.isfinite(value):
            return float(value)
    except OverflowError:
        pass
    raise ValueError("sonlu sayı gerekli")


def url_value(value):
    """Üretim sözleşmesindeki HTTP(S) adres sınırlarını bağımsız uygular."""
    value = text_value(value)
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or any(c.isspace() for c in value):
        raise ValueError("geçerli HTTP(S) adresi gerekli")
    parsed.port  # Geçersiz port numarasını da denetle.
    return value


def path_value(value):
    value = text_value(value)
    if "\x00" in value:
        raise ValueError("geçersiz dosya yolu")
    return value


Text = Annotated[str, BeforeValidator(text_value)]
Number = Annotated[float, BeforeValidator(number_value)]
Count = Annotated[int, Field(strict=True, gt=0)]


class TargetSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kind: Literal["budibase", "appsmith", "fastapi"]
    compose_file: Annotated[str, BeforeValidator(path_value)]
    base_url: Annotated[str, BeforeValidator(url_value)]
    health_url: Annotated[str, BeforeValidator(url_value)]
    health_timeout_s: Annotated[Number, Field(gt=0)] = 120.0


class ConfigSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: Text
    targets: Annotated[list[TargetSchema], Field(strict=True, min_length=1)]
    workload_size: Count
    concurrency: Count
    repetitions: Count
    cooldown_s: Annotated[Number, Field(ge=0)]
    load_generator_host: Text
    grid_carbon_intensity: Annotated[Number, Field(ge=0)] | None = None


def validate_pydantic(raw):
    """Adil karşılaştırma için aynı donmuş veri modelini üretir."""
    value = ConfigSchema.model_validate(raw)
    return BenchmarkConfig(
        title=value.title,
        targets=tuple(TargetPlatform(PlatformKind(t.kind), Path(t.compose_file),
                                    t.base_url, t.health_url, t.health_timeout_s)
                      for t in value.targets),
        workload_size=value.workload_size, concurrency=value.concurrency,
        repetitions=value.repetitions, cooldown_s=value.cooldown_s,
        load_generator_host=value.load_generator_host,
        grid_carbon_intensity=value.grid_carbon_intensity,
    )


def cases():
    """Sabit sentetik girdiler üretir; bunlar enerji ölçümü değildir."""
    base = dict(title=" QA deneyi ", targets=[dict(kind="fastapi", compose_file="compose.yml",
                base_url="http://localhost:8000", health_url="http://localhost:8000/health")],
                workload_size=100, concurrency=2, repetitions=3, cooldown_s=0,
                load_generator_host="loadgen.local")
    result = [("valid_defaults", base, True)]
    for kind in ("budibase", "appsmith"):
        raw = deepcopy(base)
        raw["targets"][0]["kind"] = kind
        result.append((f"valid_{kind}", raw, True))
    for field in base:
        raw = deepcopy(base)
        del raw[field]
        result.append((f"missing_{field}", raw, False))
    changes = {
        "workload_size": [0, -1, True, "2", 1.0, None],
        "concurrency": [0, False, "2"], "repetitions": [0, True, "3"],
        "cooldown_s": [-1, True, "2", float("nan"), float("inf"), 10**400],
        "grid_carbon_intensity": [-1, True, float("inf")],
        "title": ["", "  ", None], "targets": [[], (), "fastapi", ["fastapi"]],
    }
    for field, values in changes.items():
        for index, value in enumerate(values):
            raw = deepcopy(base)
            raw[field] = value
            result.append((f"invalid_{field}_{index}", raw, False))
    for field, values in {
        "kind": ["django", None, []], "compose_file": ["", "\x00"],
        "base_url": ["localhost", "http://[", "http://x:bad", "http://a b"],
        "health_timeout_s": [0, -1, True, float("nan")],
    }.items():
        for index, value in enumerate(values):
            raw = deepcopy(base)
            raw["targets"][0][field] = value
            result.append((f"invalid_target_{field}_{index}", raw, False))
    for field in ("kind", "compose_file", "base_url", "health_url"):
        raw = deepcopy(base)
        del raw["targets"][0][field]
        result.append((f"missing_target_{field}", raw, False))
    for index, raw in enumerate((None, [], 5)):
        result.append((f"invalid_root_{index}", raw, False))
    for field, value in (("cooldown_s", 0.25), ("grid_carbon_intensity", 0),
                         ("grid_carbon_intensity", None), ("extra_field", "ignored")):
        raw = deepcopy(base)
        raw[field] = value
        result.append((f"valid_{field}_{value}", raw, True))
    return result


def outcome(validator, raw):
    try:
        return True, validator(raw), None
    except (ConfigError, ValidationError) as exc:
        return False, None, str(exc)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args(argv)
    if args.iterations < 1 or args.repeats < 1:
        parser.error("iterations ve repeats pozitif olmalıdır")
    corpus = cases()
    print(json.dumps(dict(python=platform.python_version(), platform=platform.platform(),
                         pydantic=pydantic.__version__, cases=len(corpus),
                         iterations=args.iterations, repeats=args.repeats)))
    mismatches = 0
    for name, raw, expected in corpus:
        manual = outcome(validate_config, raw)
        model = outcome(validate_pydantic, raw)
        equal = manual[0] == model[0] == expected and manual[1] == model[1]
        mismatches += not equal
        print(json.dumps(dict(case=name, expected_accepted=expected, manual_accepted=manual[0],
                             pydantic_accepted=model[0], equivalent=equal,
                             manual_error=manual[2], pydantic_error=model[2]), ensure_ascii=False))
    # Yalnızca geçerli girdinin doğrulanmasını ve ortak modele dönüşümünü zamanla.
    timings = {"manual": [], "pydantic": []}
    validators = [("manual", validate_config), ("pydantic", validate_pydantic)]
    for _, validator in validators:
        validator(corpus[0][1])
    for repeat in range(args.repeats):
        for name, validator in validators[::1 if repeat % 2 == 0 else -1]:
            start = time.perf_counter()
            for _ in range(args.iterations):
                validator(corpus[0][1])
            timings[name].append(time.perf_counter() - start)
    print(json.dumps(dict(summary=True, mismatches=mismatches,
                         median_seconds={name: statistics.median(values) for name, values in timings.items()},
                         samples_seconds=timings)))
    return int(mismatches != 0)


if __name__ == "__main__":
    raise SystemExit(main())
