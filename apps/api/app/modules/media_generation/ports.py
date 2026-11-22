"""Ports used by media generation to call other bounded contexts."""

from __future__ import annotations

from typing import Protocol

from app.shared.model_routing import MediaModelRoute


class MediaModelResolver(Protocol):
    """Resolve a media model and enforce its declared capability."""

    def resolve_media_model(
        self, provider_id: str, model_id: str, task_type: str
    ) -> MediaModelRoute: ...


class MediaProviderGateway(Protocol):
    """Provider-specific media execution hidden behind one gateway."""

    async def generate_image(
        self,
        route: MediaModelRoute,
        prompt: str,
        parameters: dict[str, object],
        input_asset_paths: list[str],
        input_asset_paths_by_parameter: dict[str, list[str]] | None = None,
    ) -> dict[str, object]: ...

    async def create_video(
        self,
        route: MediaModelRoute,
        prompt: str,
        parameters: dict[str, object],
        input_asset_paths: list[str],
        input_asset_paths_by_parameter: dict[str, list[str]] | None = None,
    ) -> dict[str, object]: ...

    async def generate_audio(
        self,
        route: MediaModelRoute,
        prompt: str,
        parameters: dict[str, object],
        input_asset_paths: list[str],
        input_asset_paths_by_parameter: dict[str, list[str]] | None = None,
    ) -> dict[str, object]: ...

    async def generate_transcription(
        self,
        route: MediaModelRoute,
        prompt: str,
        parameters: dict[str, object],
        input_asset_paths: list[str],
        input_asset_paths_by_parameter: dict[str, list[str]] | None = None,
    ) -> dict[str, object]: ...

    async def get_video_status(
        self, route: MediaModelRoute, provider_task_id: str
    ) -> dict[str, object]: ...


class GeneratedAssetIngestor(Protocol):
    """Persist a provider artifact as an application-owned asset."""

    async def import_remote(
        self,
        *,
        url: str,
        session_id: str | None,
        task_id: str | None,
        asset_type: str,
        filename: str,
        metadata: dict[str, object] | None = None,
    ) -> str: ...

    def get_content(self, asset_id: str) -> tuple[str, str | None]: ...

    def get(self, asset_id: str) -> dict[str, object]: ...


class GenerationTaskRepositoryPort(Protocol):
    """Persistence operations required by media generation."""

    def create(
        self,
        *,
        session_id: str | None,
        turn_id: str | None,
        user_id: str,
        provider_id: str,
        model_id: str,
        prompt: str,
        original_request: dict[str, object],
        normalized_request: dict[str, object],
        client_request_id: str,
        task_type: str = "text",
        status: str = "running",
    ) -> str: ...

    def update_status(
        self,
        task_id: str,
        *,
        status: str,
        progress: int | None = None,
        provider_task_id: str | None = None,
        response: dict[str, object] | None = None,
        error_code: str | None = None,
        error: str | None = None,
        completed: bool = False,
    ) -> None: ...

    def set_assets(self, task_id: str, asset_ids: list[str]) -> None: ...

    def get(self, task_id: str) -> dict[str, object] | None: ...

    def list(
        self,
        *,
        limit: int = 100,
        task_type: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, object]]: ...

    def summary(self) -> dict[str, int]: ...

    def recover_interrupted(self) -> int: ...

    def recoverable_tasks(self) -> list[dict[str, object]]: ...

    def update_request(self, task_id: str, provider_request: dict[str, object]) -> None: ...

    def finish(
        self,
        task_id: str,
        *,
        status: str,
        response: dict[str, object] | None = None,
        error: str | None = None,
    ) -> None: ...
