"""FastAPI sağlık sözleşmesini ve UC1 demo bağlantısını Docker olmadan sınar."""

import asyncio
import importlib.util
from pathlib import Path

import httpx
import yaml

from gsmf.config import load_config
from gsmf.models import PlatformKind


ROOT = Path(__file__).resolve().parents[1]


def test_health_endpoint():
    spec = importlib.util.spec_from_file_location(
        "fastapi_baseline", ROOT / "apps/fastapi-baseline/main.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    async def request():
        """ASGI uygulamasına ağ soketi açmadan gerçek bir HTTP isteği yollar."""
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=module.app), base_url="http://test",
        ) as client:
            return await client.get("/health")

    response = asyncio.run(request())
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_example_points_to_baseline():
    config = load_config(ROOT / "examples/benchmark.yaml")
    target = config.targets[0]
    assert target.kind is PlatformKind.FASTAPI
    assert target.compose_file.is_file()
    assert target.health_url == target.base_url + "/health"
    compose = yaml.safe_load(target.compose_file.read_text(encoding="utf-8"))
    assert compose["services"]["api"]["ports"] == ["127.0.0.1:8000:8000"]
