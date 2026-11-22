"""Controlled remote media download used by provider result ingestion."""

from __future__ import annotations

from pathlib import Path

import httpx

from app.shared.errors import AppServerError


class HttpAssetFetcher:
    """Download a provider result into a path chosen by the platform."""

    async def fetch(
        self, url: str, destination: Path
    ) -> tuple[str, int, str | None]:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(180.0, connect=20.0)
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(response.content)
                return (
                    str(destination),
                    len(response.content),
                    response.headers.get("content-type"),
                )
        except httpx.HTTPError as exc:
            raise AppServerError(f"素材下载失败：{exc}") from exc
