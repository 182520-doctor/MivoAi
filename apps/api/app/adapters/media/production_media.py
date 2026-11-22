"""Media-generation adapter used by durable drama production runs."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules.media_generation.application import GenerationService
from app.modules.media_generation.commands import CreateGenerationCommand
from app.shared.errors import ProviderConfigurationError


class GenerationProductionMediaAdapter:
    """Translate a run item's canonical request into a media task."""

    def __init__(self, generation: GenerationService) -> None:
        self._generation = generation

    async def submit(self, request: dict[str, object]) -> dict[str, object]:
        provider_id = str(request.get("providerId") or "")
        model_id = str(request.get("modelId") or "")
        task_type = str(request.get("taskType") or "")
        if not provider_id or not model_id or not task_type:
            raise ProviderConfigurationError(
                "制作项必须提供 providerId、modelId 和 taskType"
            )
        images = _string_list(request.get("images"))
        if not images:
            images = _string_list(request.get("inputAssetIds"))
        parameters = request.get("parameters")
        command = CreateGenerationCommand(
            provider_id=provider_id,
            model_id=model_id,
            task_type=task_type,
            prompt=str(request.get("prompt") or ""),
            session_id=None,
            turn_id=None,
            input_asset_ids=images,
            reference_asset_ids={
                "image": images,
                "video": _string_list(request.get("videos")),
                "audio": _string_list(request.get("audios")),
                "file": _string_list(request.get("files")),
            },
            parameters=(
                dict(parameters) if isinstance(parameters, dict) else {}
            ),
            client_request_id=(
                str(request.get("clientRequestId") or "")
                or f"drama-run-{uuid.uuid4()}"
            ),
            raw_request=dict(request),
        )
        return await self._generation.create(command)

    def get(self, task_id: str) -> dict[str, object]:
        return self._generation.get(task_id)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item]
