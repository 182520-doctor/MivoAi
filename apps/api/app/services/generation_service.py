"""Provider-neutral image and video generation orchestration."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from app.core.exceptions import ProviderConfigurationError
from app.db.repositories import ConversationRepository
from app.models.gateway import GenerationCreate
from app.services.provider_service import ProviderService
from app.services.volcengine import (
    VolcengineImageClient,
    VolcengineVideoClient,
    download_remote_asset,
)


class GenerationService:
    """Create durable generation tasks and execute provider work in the background."""

    def __init__(self, repository: ConversationRepository, provider_service: ProviderService,
                 asset_dir: Path, image_client: VolcengineImageClient | None = None,
                 video_client: VolcengineVideoClient | None = None) -> None:
        self._repository = repository
        self._providers = provider_service
        self._asset_dir = asset_dir
        self._image = image_client or VolcengineImageClient()
        self._video = video_client or VolcengineVideoClient()

    async def create(self, payload: GenerationCreate) -> dict[str, object]:
        model = self._providers.resolve_media_model(payload.model_id, payload.task_type)
        if payload.provider_id != model["provider_id"]:
            raise ProviderConfigurationError("所选模型不属于指定供应商")
        request_id = payload.client_request_id or str(uuid.uuid4())
        normalized = {
            "providerId": model["provider_id"], "modelId": model["id"],
            "modelKey": model["model_key"], "taskType": payload.task_type,
            "prompt": payload.prompt, "inputAssetIds": payload.input_asset_ids,
            "parameters": payload.parameters,
        }
        task_id = self._repository.create_generation_task(
            session_id=payload.session_id, turn_id=payload.turn_id,
            user_id="local-user", provider_id=str(model["provider_id"]),
            model_id=str(model["id"]), task_type=payload.task_type, prompt=payload.prompt,
            original_request=payload.model_dump(by_alias=True), normalized_request=normalized,
            client_request_id=request_id, status="pending",
        )
        self._repository.update_generation_task_status(task_id, status="queued", progress=0)
        asyncio.create_task(self._execute(task_id, payload, model))
        return self._task_view(task_id)

    def get(self, task_id: str) -> dict[str, object]:
        return self._task_view(task_id)

    def _task_view(self, task_id: str) -> dict[str, object]:
        task = self._repository.get_generation_task(task_id)
        if not task:
            raise ProviderConfigurationError("生成任务不存在")
        return {
            "id": task["id"], "sessionId": task["session_id"],
            "providerId": task["provider_id"], "modelId": task["model_id"],
            "taskType": task["task_type"], "prompt": task["prompt"],
            "status": task["status"], "progress": task["progress"],
            "providerTaskId": task["provider_task_id"],
            "resultAssetIds": task["result_asset_ids"],
            "errorMessage": task["error_message"], "createdAt": task["created_at"],
            "updatedAt": task["updated_at"], "completedAt": task["completed_at"],
        }

    async def _execute(self, task_id: str, payload: GenerationCreate,
                       model: dict[str, object]) -> None:
        try:
            self._repository.update_generation_task_status(task_id, status="running", progress=1)
            api_key = str(model.get("api_key") or "")
            config = json.loads(str(model.get("config_json") or "{}"))
            base_url = str(config.get("base_url") or model.get("base_url") or
                           "https://ark.cn-beijing.volces.com/api/v3")
            if payload.task_type == "image_generation":
                await self._execute_image(task_id, payload, model, api_key, base_url)
            else:
                await self._execute_video(task_id, payload, model, api_key, base_url)
        except Exception as exc:  # noqa: BLE001 - task errors are persisted
            self._repository.update_generation_task_status(
                task_id, status="failed", error_code="provider_error", error=str(exc),
                completed=True,
            )

    async def _execute_image(self, task_id: str, payload: GenerationCreate,
                             model: dict[str, object], api_key: str, base_url: str) -> None:
        request = {"model": model["model_key"], "prompt": payload.prompt, **payload.parameters}
        self._repository.update_generation_task_request(task_id, request)
        response = await self._image.generate(api_key=api_key, base_url=base_url,
                                              model=str(model["model_key"]),
                                              prompt=payload.prompt,
                                              parameters=payload.parameters)
        urls = _extract_urls(response)
        if not urls:
            raise RuntimeError("图片任务成功但未返回图片地址")
        asset_ids = []
        for index, url in enumerate(urls):
            destination = self._asset_dir / "image" / task_id / f"{index}.bin"
            local_path, size, mime_type = await download_remote_asset(url, destination)
            asset_ids.append(self._repository.create_asset(
                session_id=payload.session_id, task_id=task_id, asset_type="image",
                source="generated", local_path=local_path, remote_url=url,
                mime_type=mime_type or "image/png", size=size,
                metadata={"model": model["model_key"]},
            ))
        self._repository.set_generation_task_assets(task_id, asset_ids)
        self._repository.update_generation_task_status(
            task_id, status="succeeded", progress=100, response=response, completed=True,
        )

    async def _execute_video(self, task_id: str, payload: GenerationCreate,
                             model: dict[str, object], api_key: str, base_url: str) -> None:
        request = {"model": model["model_key"],
                   "content": [{"type": "text", "text": payload.prompt}],
                   **payload.parameters}
        self._repository.update_generation_task_request(task_id, request)
        response = await self._video.create(api_key=api_key, base_url=base_url,
                                            model=str(model["model_key"]), prompt=payload.prompt,
                                            parameters=payload.parameters)
        provider_task_id = str(response.get("id") or response.get("task_id") or "")
        if not provider_task_id:
            raise RuntimeError("火山引擎未返回视频任务 ID")
        self._repository.update_generation_task_status(
            task_id, status="running", progress=5, provider_task_id=provider_task_id,
            response=response,
        )
        for _ in range(900):
            await asyncio.sleep(2)
            response = await self._video.get_status(api_key=api_key, base_url=base_url,
                                                    provider_task_id=provider_task_id)
            status = str(response.get("status") or "running").lower()
            progress = _coerce_progress(response.get("progress"))
            if status in {"succeeded", "success", "completed", "done"}:
                urls = _extract_urls(response)
                if not urls:
                    raise RuntimeError("视频任务成功但未返回视频地址")
                asset_ids = []
                for index, url in enumerate(urls):
                    destination = self._asset_dir / "video" / task_id / f"{index}.mp4"
                    local_path, size, mime_type = await download_remote_asset(url, destination)
                    asset_ids.append(self._repository.create_asset(
                        session_id=payload.session_id, task_id=task_id, asset_type="video",
                        source="generated", local_path=local_path, remote_url=url,
                        mime_type=mime_type or "video/mp4", size=size,
                        metadata={"model": model["model_key"]},
                    ))
                self._repository.set_generation_task_assets(task_id, asset_ids)
                self._repository.update_generation_task_status(
                    task_id, status="succeeded", progress=100, response=response, completed=True,
                )
                return
            if status in {"failed", "error", "canceled", "cancelled"}:
                raise RuntimeError(str(response.get("error") or "视频生成失败"))
            self._repository.update_generation_task_status(
                task_id, status="running", progress=progress, response=response,
            )
        raise RuntimeError("视频生成轮询超时")


def _extract_urls(value: Any) -> list[str]:
    urls: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            is_url = (
                key in {"url", "video_url", "image_url"}
                and isinstance(item, str)
                and item.startswith("http")
            )
            if is_url:
                urls.append(item)
            else:
                urls.extend(_extract_urls(item))
    elif isinstance(value, list):
        for item in value:
            urls.extend(_extract_urls(item))
    return list(dict.fromkeys(urls))


def _coerce_progress(value: Any) -> int | None:
    try:
        return max(0, min(99, int(float(value))))
    except (TypeError, ValueError):
        return None
