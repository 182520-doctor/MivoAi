"""Provider gateway implementation for currently supported media APIs."""

from __future__ import annotations

from app.contexts.providers.infrastructure.comfyui import ComfyUIClient
from app.contexts.providers.infrastructure.volcengine import (
    VolcengineImageClient,
    VolcengineVideoClient,
)
from app.shared.errors import AppServerError
from app.shared.model_routing import MediaModelRoute


class MediaProviderGateway:
    """Adapt resolved routes to concrete vendor media clients."""

    def __init__(
        self,
        image_client: VolcengineImageClient | None = None,
        video_client: VolcengineVideoClient | None = None,
        comfyui_client: ComfyUIClient | None = None,
    ) -> None:
        self._image = image_client or VolcengineImageClient()
        self._video = video_client or VolcengineVideoClient()
        self._comfyui = comfyui_client or ComfyUIClient()

    async def generate_image(
        self,
        route: MediaModelRoute,
        prompt: str,
        parameters: dict[str, object],
        input_asset_paths: list[str],
        input_asset_paths_by_parameter: dict[str, list[str]] | None = None,
    ) -> dict[str, object]:
        if route.provider_id == "comfyui":
            return await self._comfyui.generate_image(
                route,
                prompt,
                parameters,
                input_asset_paths,
                input_asset_paths_by_parameter,
            )
        if input_asset_paths:
            raise AppServerError("当前供应商图片接口尚不支持参考素材")
        return await self._image.generate(
            api_key=route.api_key,
            base_url=route.base_url,
            model=route.model_key,
            prompt=prompt,
            parameters=parameters,
        )

    async def create_video(
        self,
        route: MediaModelRoute,
        prompt: str,
        parameters: dict[str, object],
        input_asset_paths: list[str],
        input_asset_paths_by_parameter: dict[str, list[str]] | None = None,
    ) -> dict[str, object]:
        if route.provider_id == "comfyui":
            return await self._comfyui.create_video(
                route,
                prompt,
                parameters,
                input_asset_paths,
                input_asset_paths_by_parameter,
            )
        if input_asset_paths:
            raise AppServerError("当前供应商视频接口尚不支持参考素材")
        return await self._video.create(
            api_key=route.api_key,
            base_url=route.base_url,
            model=route.model_key,
            prompt=prompt,
            parameters=parameters,
        )

    async def generate_audio(
        self,
        route: MediaModelRoute,
        prompt: str,
        parameters: dict[str, object],
        input_asset_paths: list[str],
        input_asset_paths_by_parameter: dict[str, list[str]] | None = None,
    ) -> dict[str, object]:
        if route.provider_id != "comfyui":
            raise AppServerError("当前供应商尚未接通音频处理能力")
        return await self._comfyui.generate_audio(
            route,
            prompt,
            parameters,
            input_asset_paths,
            input_asset_paths_by_parameter,
        )

    async def generate_transcription(
        self,
        route: MediaModelRoute,
        prompt: str,
        parameters: dict[str, object],
        input_asset_paths: list[str],
        input_asset_paths_by_parameter: dict[str, list[str]] | None = None,
    ) -> dict[str, object]:
        if route.provider_id != "comfyui":
            raise AppServerError("当前供应商尚未接通语音转写能力")
        return await self._comfyui.generate_transcription(
            route,
            prompt,
            parameters,
            input_asset_paths,
            input_asset_paths_by_parameter,
        )

    async def get_video_status(
        self, route: MediaModelRoute, provider_task_id: str
    ) -> dict[str, object]:
        if route.provider_id == "comfyui":
            return await self._comfyui.get_video_status(route, provider_task_id)
        return await self._video.get_status(
            api_key=route.api_key,
            base_url=route.base_url,
            provider_task_id=provider_task_id,
        )


def default_media_provider_gateway() -> MediaProviderGateway:
    """Composition helper for the current built-in provider set."""

    return MediaProviderGateway()
