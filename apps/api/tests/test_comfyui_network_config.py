import asyncio
import json
from pathlib import Path
from typing import Any

from app.modules.providers.application import ProviderService
from app.modules.workflows.application import WorkflowService
from app.shared.config import DEFAULT_COMFYUI_URL, Settings
from app.shared.secrets import SecretBox


class _MediaProviderRepository:
    def resolve_media_model(self, model_id: str) -> dict[str, object]:
        return {
            "id": model_id,
            "provider_id": "comfyui",
            "model_key": "flux-test",
            "base_url": DEFAULT_COMFYUI_URL,
            "encrypted_secret": None,
            "config_json": json.dumps({"base_url": DEFAULT_COMFYUI_URL}),
            "capabilities_json": '["image_generation"]',
            "integration_status": "ready",
        }


class _WorkflowRepository:
    def list(self) -> list[Any]:
        return []


class _ComfyCatalog:
    def __init__(self) -> None:
        self.seen_url: str | None = None

    async def list_workflows(self, base_url: str) -> list[str]:
        self.seen_url = base_url
        return []


def test_settings_reads_comfyui_url_from_environment(monkeypatch) -> None:
    monkeypatch.setenv(
        "ZAOJING_COMFYUI_URL",
        "http://192.168.1.20:8000/",
    )

    settings = Settings.from_env()

    assert settings.comfyui_url == "http://192.168.1.20:8000"


def test_media_route_uses_configured_comfyui_url(tmp_path: Path) -> None:
    service = ProviderService(
        _MediaProviderRepository(),
        SecretBox(tmp_path / "master.key"),
        None,
        comfyui_url="http://192.168.1.20:8000/",
    )

    route = service.resolve_media_model(
        "comfyui",
        "flux-test",
        "image_generation",
    )

    assert route.base_url == "http://192.168.1.20:8000"


def test_workflow_discovery_uses_same_configured_comfyui_url() -> None:
    comfyui = _ComfyCatalog()
    service = WorkflowService(
        _WorkflowRepository(),
        comfyui,
        None,
        comfyui_url="http://192.168.1.20:8000/",
    )

    result = asyncio.run(service.discover())

    assert comfyui.seen_url == "http://192.168.1.20:8000"
    assert result["comfyuiUrl"] == "http://192.168.1.20:8000"
