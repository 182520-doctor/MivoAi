"""Durable media generation task orchestration."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

from app.modules.media_generation.commands import CreateGenerationCommand
from app.modules.media_generation.ports import (
    GeneratedAssetIngestor,
    GenerationTaskRepositoryPort,
    MediaModelResolver,
    MediaProviderGateway,
)
from app.shared.errors import ProviderConfigurationError
from app.shared.model_routing import MediaModelRoute, TextModelRoute


class GenerationService:
    """Create durable tasks and execute provider work in the background."""

    def __init__(
        self,
        repository: GenerationTaskRepositoryPort,
        providers: MediaModelResolver,
        assets: GeneratedAssetIngestor,
        provider_gateway: MediaProviderGateway,
    ) -> None:
        self._repository = repository
        self._providers = providers
        self._assets = assets
        self._gateway = provider_gateway
        self._recoverable_tasks = self._repository.recoverable_tasks()
        self._repository.recover_interrupted()

    def start_text_task(
        self,
        *,
        conversation_id: str,
        turn_id: str,
        prompt: str,
        original_request: dict[str, object],
        route: TextModelRoute,
        client_request_id: str,
    ) -> str:
        """Create the audit record required before a text request is sent."""

        return self._repository.create(
            session_id=conversation_id,
            turn_id=turn_id,
            user_id="local-user",
            provider_id=route.provider_id,
            model_id=route.model_id,
            prompt=prompt,
            original_request=original_request,
            normalized_request={
                "providerId": route.provider_id,
                "modelId": route.model_id,
                "taskType": "text",
            },
            client_request_id=client_request_id,
        )

    def update_text_task_request(
        self, task_id: str, provider_request: dict[str, object]
    ) -> None:
        self._repository.update_request(task_id, provider_request)

    def finish_text_task(
        self,
        task_id: str,
        *,
        status: str,
        route: TextModelRoute,
        error: str | None = None,
    ) -> None:
        self._repository.finish(
            task_id,
            status=status,
            response={"provider": route.provider_id, "model": route.model_id},
            error=error,
        )

    async def create(self, command: CreateGenerationCommand) -> dict[str, object]:
        route = self._providers.resolve_media_model(
            command.provider_id, command.model_id, command.task_type
        )
        request_id = command.client_request_id or str(uuid.uuid4())
        normalized = {
            "providerId": route.provider_id,
            "modelId": route.id,
            "modelKey": route.model_key,
            "taskType": command.task_type,
            "prompt": command.prompt,
            "inputAssetIds": command.input_asset_ids,
            "references": command.reference_asset_ids,
            "parameters": command.parameters,
        }
        task_id = self._repository.create(
            session_id=command.session_id,
            turn_id=command.turn_id,
            user_id="local-user",
            provider_id=route.provider_id,
            model_id=route.id,
            task_type=command.task_type,
            prompt=command.prompt,
            original_request=command.raw_request,
            normalized_request=normalized,
            client_request_id=request_id,
            status="pending",
        )
        self._repository.update_status(task_id, status="queued", progress=0)
        asyncio.create_task(self._execute(task_id, command, route))
        return self._task_view(task_id)

    def get(self, task_id: str) -> dict[str, object]:
        return self._task_view(task_id)

    def list(
        self,
        *,
        limit: int = 100,
        task_type: str | None = None,
        status: str | None = None,
    ) -> dict[str, object]:
        tasks = self._repository.list(
            limit=limit,
            task_type=task_type,
            status=status,
        )
        return {
            "tasks": [
                self._task_view_from_data(task) for task in tasks
            ],
            "summary": self._repository.summary(),
        }

    async def resume_interrupted(self) -> int:
        """Reconnect async video tasks that survived an API restart."""

        tasks = self._recoverable_tasks
        self._recoverable_tasks = []
        resumed = 0
        for task in tasks:
            task_id = str(task.get("id") or "")
            provider_task_id = str(task.get("provider_task_id") or "")
            task_type = str(task.get("task_type") or "")
            if (
                not task_id
                or not provider_task_id
                or task_type not in {"video_generation", "video_processing"}
            ):
                continue
            try:
                route = self._providers.resolve_media_model(
                    str(task["provider_id"]),
                    str(task["model_id"]),
                    task_type,
                )
            except Exception as exc:  # noqa: BLE001 - persisted task error
                self._repository.update_status(
                    task_id,
                    status="failed",
                    error_code="resume_failed",
                    error=f"无法恢复任务模型路由：{exc}",
                    completed=True,
                )
                continue
            asyncio.create_task(
                self._resume_video_task(
                    task_id,
                    route,
                    provider_task_id,
                    task.get("session_id"),
                )
            )
            resumed += 1
        return resumed

    async def retry(self, task_id: str) -> dict[str, object]:
        task = self._repository.get(task_id)
        if not task:
            raise ProviderConfigurationError("生成任务不存在")
        if task["status"] not in {"failed", "canceled"}:
            raise ProviderConfigurationError("只有失败或已取消的任务可以重试")
        task_type = str(task["task_type"])
        if task_type not in {
            "image_generation",
            "image_processing",
            "video_generation",
            "video_processing",
            "audio_processing",
            "transcription",
        }:
            raise ProviderConfigurationError("该任务类型不能重试")
        normalized = task.get("normalized_request")
        if not isinstance(normalized, dict):
            raise ProviderConfigurationError("任务缺少可重试的规范请求")
        references = normalized.get("references")
        parameters = normalized.get("parameters")
        command = CreateGenerationCommand(
            provider_id=str(task["provider_id"]),
            model_id=str(task["model_id"]),
            task_type=task_type,
            prompt=str(normalized.get("prompt") or task["prompt"] or ""),
            session_id=(
                str(task["session_id"]) if task.get("session_id") else None
            ),
            turn_id=None,
            input_asset_ids=[
                str(value)
                for value in normalized.get("inputAssetIds") or []
            ],
            reference_asset_ids={
                str(key): [
                    str(item) for item in values
                    if isinstance(item, str) and item
                ]
                for key, values in (
                    references.items()
                    if isinstance(references, dict)
                    else []
                )
                if isinstance(values, list)
            },
            parameters=(
                dict(parameters) if isinstance(parameters, dict) else {}
            ),
            client_request_id=f"retry-{uuid.uuid4()}",
            raw_request={
                "agentTool": "zaojing_retry_media_tasks",
                "retryOfTaskId": task_id,
            },
        )
        return await self.create(command)

    async def retry_many(
        self,
        task_ids: list[str],
    ) -> dict[str, object]:
        retried: list[dict[str, object]] = []
        failures: list[dict[str, str]] = []
        for task_id in list(dict.fromkeys(task_ids))[:50]:
            try:
                retried.append(await self.retry(task_id))
            except Exception as exc:  # noqa: BLE001 - batch partial result
                failures.append({"taskId": task_id, "error": str(exc)})
        return {"tasks": retried, "failures": failures}

    def _task_view(self, task_id: str) -> dict[str, object]:
        task = self._repository.get(task_id)
        if not task:
            raise ProviderConfigurationError("生成任务不存在")
        return self._task_view_from_data(task)

    def _task_view_from_data(
        self, task: dict[str, object]
    ) -> dict[str, object]:
        original_request = task.get("original_request")
        origin = (
            original_request.get("origin")
            if isinstance(original_request, dict)
            else None
        )
        return {
            "id": task["id"],
            "sessionId": task["session_id"],
            "providerId": task["provider_id"],
            "providerName": task.get("provider_name") or task["provider_id"],
            "modelId": task["model_id"],
            "modelName": task.get("model_name") or task["model_id"],
            "taskType": task["task_type"],
            "prompt": task["prompt"],
            "status": task["status"],
            "progress": task["progress"],
            "providerTaskId": task["provider_task_id"],
            "resultAssetIds": task["result_asset_ids"],
            "resultAssets": self._result_asset_views(task["result_asset_ids"]),
            "errorMessage": task["error_message"],
            "origin": origin if isinstance(origin, dict) else None,
            "createdAt": task["created_at"],
            "updatedAt": task["updated_at"],
            "completedAt": task["completed_at"],
        }

    def _result_asset_views(self, value: object) -> list[dict[str, object]]:
        if not isinstance(value, list):
            return []
        views: list[dict[str, object]] = []
        for asset_id in value:
            if not isinstance(asset_id, str) or not asset_id:
                continue
            try:
                asset = self._assets.get(asset_id)
            except ProviderConfigurationError:
                continue
            views.append(
                {
                    "id": asset_id,
                    "type": asset.get("type"),
                    "mimeType": asset.get("mime_type"),
                    "size": asset.get("size"),
                    "metadata": asset.get("metadata") or {},
                    "url": f"/api/assets/{asset_id}",
                }
            )
        return views

    async def _execute(
        self, task_id: str, command: CreateGenerationCommand, route: MediaModelRoute
    ) -> None:
        try:
            self._repository.update_status(task_id, status="running", progress=1)
            if command.task_type in {
                "image_generation",
                "image_processing",
            }:
                await self._execute_image(task_id, command, route)
            elif command.task_type == "audio_processing":
                await self._execute_audio(task_id, command, route)
            elif command.task_type == "transcription":
                await self._execute_transcription(task_id, command, route)
            else:
                await self._execute_video(task_id, command, route)
        except Exception as exc:  # noqa: BLE001 - task errors are persisted
            self._repository.update_status(
                task_id,
                status="failed",
                error_code="provider_error",
                error=str(exc),
                completed=True,
            )

    async def _execute_image(
        self,
        task_id: str,
        command: CreateGenerationCommand,
        route: MediaModelRoute,
    ) -> None:
        request = {"model": route.model_key, "prompt": command.prompt, **command.parameters}
        self._repository.update_request(task_id, request)
        input_paths_by_parameter = self._asset_paths_by_parameter(command, route)
        input_paths = [
            path
            for paths in input_paths_by_parameter.values()
            for path in paths
        ]
        response = await self._gateway.generate_image(
            route,
            command.prompt,
            command.parameters,
            input_paths,
            input_paths_by_parameter,
        )
        urls = _extract_urls(response)
        if not urls:
            raise RuntimeError("图片任务成功但未返回图片地址")
        asset_ids = []
        for index, url in enumerate(urls):
            asset_ids.append(
                await self._assets.import_remote(
                    url=url,
                    session_id=command.session_id,
                    task_id=task_id,
                    asset_type="image",
                    filename=_artifact_filename(url, index, "png"),
                    metadata={"model": route.model_key},
                )
            )
        self._repository.set_assets(task_id, asset_ids)
        self._repository.update_status(
            task_id,
            status="succeeded",
            progress=100,
            response=response,
            completed=True,
        )

    async def _execute_audio(
        self,
        task_id: str,
        command: CreateGenerationCommand,
        route: MediaModelRoute,
    ) -> None:
        request = {
            "model": route.model_key,
            "prompt": command.prompt,
            **command.parameters,
        }
        self._repository.update_request(task_id, request)
        input_paths_by_parameter = self._asset_paths_by_parameter(command, route)
        input_paths = [
            path
            for paths in input_paths_by_parameter.values()
            for path in paths
        ]
        response = await self._gateway.generate_audio(
            route,
            command.prompt,
            command.parameters,
            input_paths,
            input_paths_by_parameter,
        )
        urls = _extract_urls(response)
        if not urls:
            raise RuntimeError("音频处理任务成功但未返回音频地址")
        asset_ids = []
        for index, url in enumerate(urls):
            filename = _audio_artifact_filename(url, index)
            asset_ids.append(
                await self._assets.import_remote(
                    url=url,
                    session_id=command.session_id,
                    task_id=task_id,
                    asset_type="audio",
                    filename=filename,
                    metadata={
                        "model": route.model_key,
                        "originalFilename": filename,
                    },
                )
            )
        self._repository.set_assets(task_id, asset_ids)
        self._repository.update_status(
            task_id,
            status="succeeded",
            progress=100,
            response=response,
            completed=True,
        )

    async def _execute_transcription(
        self,
        task_id: str,
        command: CreateGenerationCommand,
        route: MediaModelRoute,
    ) -> None:
        request = {
            "model": route.model_key,
            "prompt": command.prompt,
            **command.parameters,
        }
        self._repository.update_request(task_id, request)
        input_paths_by_parameter = self._asset_paths_by_parameter(command, route)
        input_paths = [
            path
            for paths in input_paths_by_parameter.values()
            for path in paths
        ]
        response = await self._gateway.generate_transcription(
            route,
            command.prompt,
            command.parameters,
            input_paths,
            input_paths_by_parameter,
        )
        urls = _extract_urls(response)
        if not urls:
            raise RuntimeError("转写任务成功但未返回文本文件")
        asset_ids = []
        for index, url in enumerate(urls):
            filename = _text_artifact_filename(url, index)
            asset_ids.append(
                await self._assets.import_remote(
                    url=url,
                    session_id=command.session_id,
                    task_id=task_id,
                    asset_type="file",
                    filename=filename,
                    metadata={
                        "model": route.model_key,
                        "originalFilename": filename,
                    },
                )
            )
        self._repository.set_assets(task_id, asset_ids)
        self._repository.update_status(
            task_id,
            status="succeeded",
            progress=100,
            response=response,
            completed=True,
        )

    async def _execute_video(
        self,
        task_id: str,
        command: CreateGenerationCommand,
        route: MediaModelRoute,
    ) -> None:
        request = {
            "model": route.model_key,
            "content": [{"type": "text", "text": command.prompt}],
            **command.parameters,
        }
        self._repository.update_request(task_id, request)
        input_paths_by_parameter = self._asset_paths_by_parameter(command, route)
        input_paths = [
            path
            for paths in input_paths_by_parameter.values()
            for path in paths
        ]
        response = await self._gateway.create_video(
            route,
            command.prompt,
            command.parameters,
            input_paths,
            input_paths_by_parameter,
        )
        provider_task_id = str(response.get("id") or response.get("task_id") or "")
        if not provider_task_id:
            raise RuntimeError("供应商未返回视频任务 ID")
        self._repository.update_status(
            task_id,
            status="running",
            progress=5,
            provider_task_id=provider_task_id,
            response=response,
        )
        await self._poll_video(
            task_id,
            route,
            provider_task_id,
            command.session_id,
        )

    async def _resume_video_task(
        self,
        task_id: str,
        route: MediaModelRoute,
        provider_task_id: str,
        session_id: object,
    ) -> None:
        try:
            self._repository.update_status(
                task_id,
                status="running",
                progress=5,
            )
            await self._poll_video(
                task_id,
                route,
                provider_task_id,
                str(session_id) if session_id else None,
            )
        except Exception as exc:  # noqa: BLE001 - resumed task is durable
            self._repository.update_status(
                task_id,
                status="failed",
                error_code="resume_failed",
                error=str(exc),
                completed=True,
            )

    async def _poll_video(
        self,
        task_id: str,
        route: MediaModelRoute,
        provider_task_id: str,
        session_id: str | None,
    ) -> None:
        for _ in range(900):
            response = await self._gateway.get_video_status(route, provider_task_id)
            status = str(response.get("status") or "running").lower()
            progress = _coerce_progress(response.get("progress"))
            if status in {"succeeded", "success", "completed", "done"}:
                urls = _extract_urls(response)
                if not urls:
                    raise RuntimeError("视频任务成功但未返回视频地址")
                asset_ids = []
                for index, url in enumerate(urls):
                    asset_ids.append(
                        await self._assets.import_remote(
                            url=url,
                            session_id=session_id,
                            task_id=task_id,
                            asset_type="video",
                            filename=_artifact_filename(url, index, "mp4"),
                            metadata={"model": route.model_key},
                        )
                    )
                self._repository.set_assets(task_id, asset_ids)
                self._repository.update_status(
                    task_id,
                    status="succeeded",
                    progress=100,
                    response=response,
                    completed=True,
                )
                return
            if status in {"failed", "error", "canceled", "cancelled"}:
                raise RuntimeError(str(response.get("error") or "视频生成失败"))
            self._repository.update_status(
                task_id,
                status="running",
                progress=progress,
                response=response,
            )
            await asyncio.sleep(2)
        raise RuntimeError("视频生成轮询超时")

    def _asset_paths_by_parameter(
        self,
        command: CreateGenerationCommand,
        route: MediaModelRoute,
    ) -> dict[str, list[str]]:
        schema = route.config.get("parameters")
        asset_parameters = (
            [
                parameter
                for parameter in schema
                if isinstance(parameter, dict)
                and parameter.get("type") == "assets"
            ]
            if isinstance(schema, list)
            else []
        )
        if not asset_parameters:
            return {
                "assets": [
                    self._assets.get_content(asset_id)[0]
                    for asset_id in command.input_asset_ids
                ]
            }
        result: dict[str, list[str]] = {}
        reference_ids = command.reference_asset_ids
        for asset_type in {"image", "video", "audio", "file"}:
            references = [
                parameter
                for parameter in asset_parameters
                if str(parameter.get("assetType") or "image") == asset_type
            ]
            remaining = list(reference_ids.get(asset_type) or [])
            for position, parameter in enumerate(references):
                key = str(parameter.get("key") or f"{asset_type}_assets")
                bindings = parameter.get("bindings")
                capacity = (
                    len(bindings)
                    if isinstance(bindings, list) and bindings
                    else len(remaining)
                )
                maximum = parameter.get("max")
                if isinstance(maximum, int) and maximum >= 0:
                    capacity = min(capacity, maximum)
                if position == len(references) - 1:
                    selected = remaining
                else:
                    selected = remaining[:capacity]
                    remaining = remaining[capacity:]
                legacy_ids = _asset_ids(command.parameters.get(key))
                result[key] = [
                    self._assets.get_content(asset_id)[0]
                    for asset_id in (selected or legacy_ids)
                ]
        if result:
            return result
        for index, parameter in enumerate(asset_parameters):
            key = str(parameter.get("key") or f"assets_{index}")
            asset_ids = _asset_ids(command.parameters.get(key))
            if not asset_ids and index == 0:
                asset_ids = list(command.input_asset_ids)
            result[key] = [
                self._assets.get_content(asset_id)[0]
                for asset_id in asset_ids
            ]
        return result


def _asset_ids(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str) and item]
    if isinstance(value, str) and value:
        return [value]
    return []


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


def _artifact_filename(url: str, index: int, extension: str) -> str:
    from urllib.parse import urlparse

    suffix = Path(urlparse(url).path).suffix
    return f"{index}{suffix}" if suffix else f"{index}.{extension}"


def _audio_artifact_filename(url: str, index: int) -> str:
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(url)
    name = (parse_qs(parsed.query).get("filename") or [""])[0]
    if name:
        return Path(name).name
    suffix = Path(parsed.path).suffix or ".flac"
    return f"audio-{index}{suffix}"


def _text_artifact_filename(url: str, index: int) -> str:
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(url)
    name = (parse_qs(parsed.query).get("filename") or [""])[0]
    if name:
        return Path(name).name
    suffix = Path(parsed.path).suffix or ".json"
    return f"transcript-{index}{suffix}"
