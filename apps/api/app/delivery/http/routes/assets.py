"""HTTP routes for locally stored asset content."""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.modules.assets import AssetService


def create_asset_router(service: AssetService) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["assets"])

    @router.get("/assets")
    async def list_assets(limit: int = 200):
        return service.list(limit=limit)

    @router.get("/assets/{asset_id}")
    async def get_asset(asset_id: str):
        path, mime_type = service.get_content(asset_id)
        return FileResponse(path, media_type=mime_type)

    @router.post("/assets/upload")
    async def upload_assets(files: Annotated[list[UploadFile], File()]):
        asset_ids = []
        for file in files:
            content = await file.read()
            if len(content) > 500 * 1024 * 1024:
                raise HTTPException(413, f"文件过大：{file.filename}")
            asset_ids.append(
                service.import_upload(
                    filename=file.filename or "upload",
                    mime_type=file.content_type,
                    content=content,
                )
            )
        return {"assetIds": asset_ids}

    return router
