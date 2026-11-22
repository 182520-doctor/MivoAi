"""Ports used by asset application services."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class AssetRepositoryPort(Protocol):
    """Persistence operations required by asset ingestion."""

    def create(
        self,
        *,
        session_id: str | None,
        task_id: str | None,
        asset_type: str,
        source: str,
        local_path: str | None,
        remote_url: str | None,
        mime_type: str | None,
        size: int | None,
        metadata: dict[str, object] | None = None,
    ) -> str: ...

    def get(self, asset_id: str) -> dict[str, object] | None: ...

    def list(self, *, limit: int = 200) -> list[dict[str, object]]: ...

    def summary(self) -> dict[str, int]: ...


class AssetFileFetcher(Protocol):
    """Download a remote artifact into a platform-selected destination."""

    async def fetch(
        self, url: str, destination: Path
    ) -> tuple[str, int, str | None]: ...
