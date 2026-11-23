"""ComfyUI execution adapter for local generation workflows."""

from __future__ import annotations

import asyncio
import os
import random
import uuid
from typing import Any
from urllib.parse import urlencode

import httpx

from app.modules.workflows.converter import apply_bindings, apply_parameter_schema
from app.shared.errors import AppServerError
from app.shared.model_routing import MediaModelRoute


class ComfyUIClient:
    """Submit curated API-format graphs and retrieve generated artifacts."""

    def __init__(
        self,
        *,
        image_timeout: float = 600,
        video_timeout: float = 1800,
    ) -> None:
        self._image_timeout = image_timeout
        self._video_timeout = video_timeout

    async def generate_image(
        self,
        route: MediaModelRoute,
        prompt: str,
        parameters: dict[str, object],
        input_asset_paths: list[str],
        input_asset_paths_by_parameter: dict[str, list[str]] | None = None,
    ) -> dict[str, object]:
        uploaded_by_parameter = await self._upload_assets_by_parameter(
            route.base_url,
            input_asset_paths,
            input_asset_paths_by_parameter,
        )
        uploaded = [
            item for values in uploaded_by_parameter.values() for item in values
        ]
        graph = _route_graph(
            route,
            prompt,
            parameters,
            uploaded,
            uploaded_by_parameter,
        ) or _flux_image_graph(prompt, parameters)
        if uploaded and route.config.get("kind") != "comfy_workflow":
            raise AppServerError("内置 ComfyUI 图片模型不支持参考素材")
        prompt_id = await self._submit(route.base_url, graph)
        history = await self._wait(route.base_url, prompt_id, self._image_timeout)
        artifacts = _extract_artifacts(route.base_url, history)
        return {
            "task_id": prompt_id,
            "status": "succeeded",
            "data": [{"url": artifact["url"]} for artifact in artifacts],
            "artifacts": artifacts,
        }

    async def create_video(
        self,
        route: MediaModelRoute,
        prompt: str,
        parameters: dict[str, object],
        input_asset_paths: list[str],
        input_asset_paths_by_parameter: dict[str, list[str]] | None = None,
    ) -> dict[str, object]:
        uploaded_by_parameter = await self._upload_assets_by_parameter(
            route.base_url,
            input_asset_paths,
            input_asset_paths_by_parameter,
        )
        uploaded = [
            item for values in uploaded_by_parameter.values() for item in values
        ]
        graph = _route_graph(
            route,
            prompt,
            parameters,
            uploaded,
            uploaded_by_parameter,
        ) or _wan_video_graph(prompt, parameters)
        if uploaded and route.config.get("kind") != "comfy_workflow":
            raise AppServerError("内置 ComfyUI 视频模型不支持参考素材")
        prompt_id = await self._submit(route.base_url, graph)
        return {"id": prompt_id, "status": "running"}

    async def generate_audio(
        self,
        route: MediaModelRoute,
        prompt: str,
        parameters: dict[str, object],
        input_asset_paths: list[str],
        input_asset_paths_by_parameter: dict[str, list[str]] | None = None,
    ) -> dict[str, object]:
        uploaded_by_parameter = await self._upload_assets_by_parameter(
            route.base_url,
            input_asset_paths,
            input_asset_paths_by_parameter,
        )
        uploaded = [
            item for values in uploaded_by_parameter.values() for item in values
        ]
        graph = _route_graph(
            route,
            prompt,
            parameters,
            uploaded,
            uploaded_by_parameter,
        )
        if not graph:
            raise AppServerError("音频处理必须使用已注册的 ComfyUI 工作流")
        prompt_id = await self._submit(route.base_url, graph)
        history = await self._wait(route.base_url, prompt_id, self._image_timeout)
        artifacts = _extract_artifacts(route.base_url, history)
        return {
            "task_id": prompt_id,
            "status": "succeeded",
            "data": [{"url": artifact["url"]} for artifact in artifacts],
            "artifacts": artifacts,
        }

    async def generate_transcription(
        self,
        route: MediaModelRoute,
        prompt: str,
        parameters: dict[str, object],
        input_asset_paths: list[str],
        input_asset_paths_by_parameter: dict[str, list[str]] | None = None,
    ) -> dict[str, object]:
        return await self.generate_audio(
            route,
            prompt,
            parameters,
            input_asset_paths,
            input_asset_paths_by_parameter,
        )

    async def get_video_status(
        self, route: MediaModelRoute, provider_task_id: str
    ) -> dict[str, object]:
        base_url = route.base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = await client.get(f"{base_url}/history/{provider_task_id}")
            response.raise_for_status()
            payload = response.json()
        entry = payload.get(provider_task_id)
        if not entry:
            return {"status": "running", "id": provider_task_id}
        status = entry.get("status") or {}
        if status.get("status_str") == "error" or status.get("completed") is False:
            return {
                "status": "failed",
                "error": _execution_error(status),
                "id": provider_task_id,
            }
        artifacts = _extract_artifacts(base_url, entry)
        if not artifacts:
            return {"status": "failed", "error": "ComfyUI 未返回视频文件"}
        return {
            "status": "succeeded",
            "video_url": artifacts[0]["url"],
            "artifacts": artifacts,
            "id": provider_task_id,
        }

    async def _submit(self, base_url: str, graph: dict[str, Any]) -> str:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=15.0)
            ) as client:
                response = await client.post(
                    base_url.rstrip("/") + "/prompt",
                    json={"prompt": graph, "client_id": f"mivo-{uuid.uuid4()}"},
                )
                payload = response.json()
                if response.status_code >= 400 or payload.get("node_errors"):
                    detail = payload.get("node_errors") or payload
                    raise AppServerError(f"ComfyUI 工作流校验失败：{detail}")
                prompt_id = str(payload.get("prompt_id") or "")
                if not prompt_id:
                    raise AppServerError("ComfyUI 未返回 prompt_id")
                return prompt_id
        except httpx.HTTPError as exc:
            raise AppServerError(f"ComfyUI 提交失败：{exc}") from exc

    async def _wait(
        self, base_url: str, prompt_id: str, timeout: float
    ) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0)
            ) as client:
                response = await client.get(
                    base_url.rstrip("/") + f"/history/{prompt_id}"
                )
                response.raise_for_status()
                payload = response.json()
            entry = payload.get(prompt_id)
            if entry:
                status = entry.get("status") or {}
                if status.get("status_str") == "success":
                    return entry
                if status.get("status_str") == "error":
                    raise AppServerError(_execution_error(status))
            await asyncio.sleep(1)
        raise AppServerError("ComfyUI 生成超时")

    async def list_workflows(self, base_url: str) -> list[str]:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0)
            ) as client:
                response = await client.get(
                    base_url.rstrip("/") + "/userdata",
                    params={"dir": "workflows"},
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise AppServerError(f"无法读取 ComfyUI 工作流目录：{exc}") from exc
        return sorted(
            item
            for item in payload
            if isinstance(item, str) and item.lower().endswith(".json")
        )

    async def upload_image(self, base_url: str, path: str) -> str:
        file_path = os.fspath(path)
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=15.0)
            ) as client:
                with open(file_path, "rb") as handle:
                    response = await client.post(
                        base_url.rstrip("/") + "/upload/image",
                        data={"type": "input", "overwrite": "false"},
                        files={
                            "image": (
                                os.path.basename(file_path),
                                handle,
                                "application/octet-stream",
                            )
                        },
                    )
                response.raise_for_status()
                payload = response.json()
        except (OSError, httpx.HTTPError, ValueError) as exc:
            raise AppServerError(f"上传参考素材到 ComfyUI 失败：{exc}") from exc
        name = str(payload.get("name") or "")
        if not name:
            raise AppServerError("ComfyUI 未返回上传文件名")
        subfolder = str(payload.get("subfolder") or "")
        return f"{subfolder}/{name}" if subfolder else name

    async def load_ui_workflow(
        self, base_url: str, filename: str
    ) -> dict[str, Any]:
        encoded = f"workflows/{filename}".replace("/", "%2F")
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0)
            ) as client:
                response = await client.get(
                    base_url.rstrip("/") + "/userdata/" + encoded
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AppServerError(f"无法读取 ComfyUI 工作流：{exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("nodes"), list):
            raise AppServerError("该文件不是 ComfyUI UI 格式工作流")
        return payload

    async def get_object_info(self, base_url: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=15.0)
            ) as client:
                response = await client.get(base_url.rstrip("/") + "/object_info")
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AppServerError(f"无法读取 ComfyUI 节点信息：{exc}") from exc

    async def execute_graph(
        self,
        base_url: str,
        graph: dict[str, Any],
        *,
        timeout: float = 600,
    ) -> list[dict[str, object]]:
        prompt_id = await self._submit(base_url, graph)
        history = await self._wait(base_url, prompt_id, timeout)
        artifacts = _extract_artifacts(base_url, history)
        if not artifacts:
            raise AppServerError("工作流执行成功，但没有找到图片或视频输出")
        return artifacts

    async def _upload_assets(
        self, base_url: str, input_asset_paths: list[str]
    ) -> list[str]:
        return [
            await self.upload_image(base_url, path)
            for path in input_asset_paths
        ]

    async def _upload_assets_by_parameter(
        self,
        base_url: str,
        input_asset_paths: list[str],
        paths_by_parameter: dict[str, list[str]] | None,
    ) -> dict[str, list[str]]:
        if not paths_by_parameter:
            return {"assets": await self._upload_assets(base_url, input_asset_paths)}
        return {
            key: [
                await self.upload_image(base_url, path)
                for path in paths
            ]
            for key, paths in paths_by_parameter.items()
        }


def _flux_image_graph(
    prompt: str, parameters: dict[str, object]
) -> dict[str, Any]:
    width = _int(parameters.get("width"), 1024)
    height = _int(parameters.get("height"), 1024)
    steps = _int(parameters.get("steps"), 12)
    guidance = _float(parameters.get("guidance"), 3.5)
    seed = _seed(parameters.get("seed"))
    count = max(1, min(_int(parameters.get("count"), 1), 4))
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": os.getenv(
                    "ZAOJING_COMFY_IMAGE_UNET",
                    r"flux\flux1-dev-fp8.safetensors",
                ),
                "weight_dtype": "default",
            },
        },
        "2": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": os.getenv(
                    "ZAOJING_COMFY_IMAGE_T5",
                    "t5xxl_fp8_e4m3fn.safetensors",
                ),
                "clip_name2": os.getenv(
                    "ZAOJING_COMFY_IMAGE_CLIP",
                    "clip_l.safetensors",
                ),
                "type": "flux",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": os.getenv("ZAOJING_COMFY_IMAGE_VAE", "ae.sft")
            },
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["2", 0]},
        },
        "5": {
            "class_type": "FluxGuidance",
            "inputs": {"conditioning": ["4", 0], "guidance": guidance},
        },
        "6": {
            "class_type": "ConditioningZeroOut",
            "inputs": {"conditioning": ["4", 0]},
        },
        "7": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": width, "height": height, "batch_size": count},
        },
        "8": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "seed": seed,
                "steps": steps,
                "cfg": 1,
                "sampler_name": "euler",
                "scheduler": "normal",
                "positive": ["5", 0],
                "negative": ["6", 0],
                "latent_image": ["7", 0],
                "denoise": 1,
            },
        },
        "9": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["8", 0], "vae": ["3", 0]},
        },
        "10": {
            "class_type": "SaveImage",
            "inputs": {"images": ["9", 0], "filename_prefix": "Mivo"},
        },
    }


def _route_graph(
    route: MediaModelRoute,
    prompt: str,
    parameters: dict[str, object],
    uploaded_assets: list[str],
    uploaded_assets_by_parameter: dict[str, list[str]] | None = None,
) -> dict[str, Any] | None:
    if route.config.get("kind") != "comfy_workflow":
        return None
    api_graph = route.config.get("apiGraph")
    bindings = route.config.get("bindings")
    if not isinstance(api_graph, dict) or not isinstance(bindings, dict):
        raise AppServerError("已导入的 ComfyUI 工作流配置不完整")
    parameter_schema = route.config.get("parameters")
    if isinstance(parameter_schema, list) and parameter_schema:
        return apply_parameter_schema(
            api_graph,
            parameter_schema,
            values={**parameters, "prompt": prompt},
            uploaded_assets=uploaded_assets,
            uploaded_assets_by_parameter=uploaded_assets_by_parameter,
        )
    return apply_bindings(
        api_graph,
        bindings,
        prompt=prompt,
        parameters=parameters,
    )


def _wan_video_graph(
    prompt: str, parameters: dict[str, object]
) -> dict[str, Any]:
    width = _int(parameters.get("width"), 512)
    height = _int(parameters.get("height"), 512)
    length = _video_length(_int(parameters.get("length"), 9))
    fps = _int(parameters.get("fps"), 12)
    steps = _int(parameters.get("steps"), 12)
    seed = _seed(parameters.get("seed"))
    negative = str(
        parameters.get("negativePrompt")
        or "blurry, low quality, static, text, watermark"
    )
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": os.getenv(
                    "ZAOJING_COMFY_VIDEO_UNET",
                    r"wan\Wan2_1-I2V-14B-480P_fp8_e4m3fn.safetensors",
                ),
                "weight_dtype": "default",
            },
        },
        "2": {
            "class_type": "ModelSamplingSD3",
            "inputs": {"model": ["1", 0], "shift": 8},
        },
        "3": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": os.getenv(
                    "ZAOJING_COMFY_VIDEO_CLIP",
                    "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                ),
                "type": "wan",
                "device": "default",
            },
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["3", 0]},
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": ["3", 0]},
        },
        "6": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": os.getenv(
                    "ZAOJING_COMFY_VIDEO_VAE", "wan_2.1_vae.safetensors"
                )
            },
        },
        "7": {
            "class_type": "WanImageToVideo",
            "inputs": {
                "positive": ["4", 0],
                "negative": ["5", 0],
                "vae": ["6", 0],
                "width": width,
                "height": height,
                "length": length,
                "batch_size": 1,
            },
        },
        "8": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["2", 0],
                "seed": seed,
                "steps": steps,
                "cfg": 6,
                "sampler_name": "uni_pc",
                "scheduler": "simple",
                "positive": ["7", 0],
                "negative": ["7", 1],
                "latent_image": ["7", 2],
                "denoise": 1,
            },
        },
        "9": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["8", 0], "vae": ["6", 0]},
        },
        "10": {
            "class_type": "SaveWEBM",
            "inputs": {
                "images": ["9", 0],
                "filename_prefix": "Mivo",
                "codec": "vp9",
                "fps": fps,
                "crf": 32,
            },
        },
    }


def _extract_artifacts(
    base_url: str, history: dict[str, Any]
) -> list[dict[str, object]]:
    artifacts: list[dict[str, object]] = []
    for output in (history.get("outputs") or {}).values():
        for key in ("images", "gifs", "videos", "audio", "files", "text"):
            values = output.get(key)
            if not isinstance(values, list):
                continue
            for value in values:
                if not isinstance(value, dict) or not value.get("filename"):
                    continue
                query = urlencode(
                    {
                        "filename": value["filename"],
                        "subfolder": value.get("subfolder", ""),
                        "type": value.get("type", "output"),
                    }
                )
                metadata = value.get("metadata") or {}
                kind = str(
                    metadata.get("kind")
                    or (
                        "audio"
                        if key == "audio"
                        else "file"
                        if key in {"text", "files"}
                        else "image"
                    )
                )
                artifacts.append(
                    {
                        "url": base_url.rstrip("/") + "/view?" + query,
                        "filename": value["filename"],
                        "kind": kind,
                        "metadata": metadata,
                    }
                )
    return artifacts


def _execution_error(status: dict[str, Any]) -> str:
    for message in status.get("messages") or []:
        if (
            isinstance(message, list)
            and len(message) > 1
            and message[0] == "execution_error"
        ):
            detail = message[1] or {}
            return str(detail.get("exception_message") or "ComfyUI 执行失败")
    return "ComfyUI 执行失败"


def _seed(value: object) -> int:
    try:
        return int(value) if value not in (None, "") else random.randint(0, 2**31 - 1)
    except (TypeError, ValueError):
        return random.randint(0, 2**31 - 1)


def _int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _video_length(value: int) -> int:
    clamped = max(5, min(value, 81))
    return clamped - ((clamped - 1) % 4)
