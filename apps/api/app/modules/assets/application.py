"""Asset ingestion and content lookup use cases."""

from __future__ import annotations

import shutil
import uuid
from mimetypes import guess_type
from pathlib import Path

from app.modules.assets.ports import AssetFileFetcher, AssetRepositoryPort
from app.shared.errors import ProviderConfigurationError


class AssetService:
    """Own local file placement and asset metadata registration."""

    def __init__(
        self,
        repository: AssetRepositoryPort,
        asset_dir: Path,
        fetcher: AssetFileFetcher,
    ) -> None:
        self._repository = repository
        self._asset_dir = asset_dir
        self._fetcher = fetcher

    async def import_remote(
        self,
        *,
        url: str,
        session_id: str | None,
        task_id: str | None,
        asset_type: str,
        filename: str,
        metadata: dict[str, object] | None = None,
    ) -> str:
        destination = (
            self._asset_dir
            / asset_type
            / (task_id or "workflow-tests")
            / filename
        )
        local_path, size, mime_type = await self._fetcher.fetch(url, destination)
        return self._repository.create(
            session_id=session_id,
            task_id=task_id,
            asset_type=asset_type,
            source="generated",
            local_path=local_path,
            remote_url=url,
            mime_type=mime_type or _default_mime_type(asset_type),
            size=size,
            metadata=metadata,
        )

    def get_content(self, asset_id: str) -> tuple[str, str | None]:
        asset = self._repository.get(asset_id)
        if not asset or not asset.get("local_path"):
            raise ProviderConfigurationError("素材不存在")
        return str(asset["local_path"]), asset.get("mime_type")

    def import_local(
        self,
        *,
        source_path: Path,
        asset_type: str,
        filename: str,
        metadata: dict[str, object] | None = None,
    ) -> str:
        """Copy a locally produced artifact into the managed asset store."""

        if not source_path.is_file():
            raise ProviderConfigurationError("待入库的本地素材不存在")
        suffix = source_path.suffix.lower()
        destination = (
            self._asset_dir
            / asset_type
            / "processing"
            / f"{uuid.uuid4()}{suffix}"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        mime_type, _ = guess_type(filename)
        return self._repository.create(
            session_id=None,
            task_id=None,
            asset_type=asset_type,
            source="generated",
            local_path=str(destination),
            remote_url=None,
            mime_type=mime_type or _default_mime_type(asset_type),
            size=destination.stat().st_size,
            metadata=metadata or {"originalFilename": filename},
        )

    def get(self, asset_id: str) -> dict[str, object]:
        asset = self._repository.get(asset_id)
        if not asset:
            raise ProviderConfigurationError("素材不存在")
        return asset

    def list(self, *, limit: int = 200) -> dict[str, object]:
        assets = [
            {
                "id": asset["id"],
                "type": asset["type"],
                "source": asset["source"],
                "mimeType": asset.get("mime_type"),
                "size": asset.get("size"),
                "width": asset.get("width"),
                "height": asset.get("height"),
                "duration": asset.get("duration"),
                "taskId": asset.get("task_id"),
                "sessionId": asset.get("session_id"),
                "metadata": asset.get("metadata") or {},
                "createdAt": asset["created_at"],
                "url": f"/api/assets/{asset['id']}",
            }
            for asset in self._repository.list(limit=limit)
        ]
        return {
            "assets": assets,
            "summary": self._repository.summary(),
        }

    def import_upload(
        self,
        *,
        filename: str,
        mime_type: str | None,
        content: bytes,
    ) -> str:
        suffix = Path(filename).suffix.lower()
        guessed_mime, _ = guess_type(filename)
        effective_mime = (
            mime_type
            if mime_type and mime_type != "application/octet-stream"
            else guessed_mime
        )
        asset_type = _asset_type_for_mime(effective_mime)
        if asset_type == "file":
            asset_type = _asset_type_for_suffix(suffix)
        if suffix not in {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".bmp",
            ".gif",
            ".mp4",
            ".webm",
            ".mov",
            ".mkv",
            ".avi",
            ".mp3",
            ".wav",
            ".flac",
            ".ogg",
            ".m4a",
            ".txt",
            ".json",
            ".csv",
            ".pdf",
            ".srt",
            ".ass",
        }:
            suffix = ""
        relative = (
            self._asset_dir
            / asset_type
            / "uploads"
            / f"{uuid.uuid4()}{suffix}"
        )
        relative.parent.mkdir(parents=True, exist_ok=True)
        relative.write_bytes(content)
        return self._repository.create(
            session_id=None,
            task_id=None,
            asset_type=asset_type,
            source="upload",
            local_path=str(relative),
            remote_url=None,
            mime_type=effective_mime or mime_type,
            size=len(content),
            metadata={"originalFilename": Path(filename).name},
        )


def _default_mime_type(asset_type: str) -> str | None:
    return {
        "image": "image/png",
        "video": "video/mp4",
        "audio": "audio/mpeg",
    }.get(asset_type)


def _asset_type_for_mime(mime_type: str | None) -> str:
    if mime_type and mime_type.startswith("video/"):
        return "video"
    if mime_type and mime_type.startswith("audio/"):
        return "audio"
    if mime_type and mime_type.startswith("image/"):
        return "image"
    return "file"


def _asset_type_for_suffix(suffix: str) -> str:
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}:
        return "image"
    if suffix in {".mp4", ".webm", ".mov", ".mkv", ".avi"}:
        return "video"
    if suffix in {".mp3", ".wav", ".flac", ".ogg", ".m4a"}:
        return "audio"
    return "file"
