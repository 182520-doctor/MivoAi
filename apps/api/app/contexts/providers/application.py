"""Provider catalog, credential management, and model routing use cases."""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from app.contexts.conversations.events import CodexEvent
from app.contexts.providers.commands import (
    SaveCredentialCommand,
    UpdatePreferencesCommand,
)
from app.contexts.providers.ports import ProviderRepositoryPort, TextChatPort
from app.shared.errors import ProviderConfigurationError
from app.shared.model_routing import MediaModelRoute, TextModelRoute
from app.shared.secrets import SecretBox
from app.shared.semantic_parameters import (
    ASPECT_RATIO_OPTIONS,
    aspect_ratio_for_dimensions,
    infer_semantic_key,
    megapixels_to_resolution,
    resolution_from_dimensions,
)


class ProviderService:
    """Expose safe provider metadata and resolve text/media execution routes."""

    def __init__(
        self,
        repository: ProviderRepositoryPort,
        secret_box: SecretBox,
        text_client: TextChatPort,
        local_runtime_status: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self._repository = repository
        self._secret_box = secret_box
        self._text_client = text_client
        self._local_runtime_status = local_runtime_status

    def list_models(self) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for row in self._repository.list_models():
            config = json.loads(str(row.get("config_json") or "{}"))
            parameters, references = _public_workflow_inputs(
                config.get("parameters")
            )
            result.append(
                {
                    "id": row["id"],
                    "providerId": row["provider_id"],
                    "providerName": row["provider_name"],
                    "name": row["name"],
                    "modelKey": row["model_key"],
                    "capabilities": json.loads(str(row["capabilities_json"])),
                    "executionMode": row["execution_mode"],
                    "enabled": bool(row["enabled"]),
                    "configured": bool(row["configured"]),
                    "integrationStatus": row["integration_status"],
                    "kind": config.get("kind", "builtin"),
                    "workflowId": config.get("workflowId"),
                    "parameters": parameters,
                    "references": references,
                    "inputSchema": {
                        "parameters": parameters,
                        "references": references,
                    },
                }
            )
        return result

    def upsert_credential(
        self, provider_id: str, command: SaveCredentialCommand
    ) -> dict[str, object]:
        now = datetime.now(UTC).isoformat()
        credential_id = str(uuid.uuid4())
        config = {"base_url": command.base_url} if command.base_url else {}
        saved = self._repository.save_credential(
            provider_id=provider_id,
            credential_id=credential_id,
            encrypted_secret=self._secret_box.encrypt(command.api_key),
            config_json=json.dumps(config, ensure_ascii=False),
            updated_at=now,
            name=f"{provider_id} API Key",
        )
        if not saved:
            raise ProviderConfigurationError("供应商不存在或已停用")
        return {"providerId": provider_id, "configured": True, "updatedAt": now}

    def get_preferences(self) -> dict[str, object]:
        row = self._repository.get_preferences()
        if not row:
            raise ProviderConfigurationError("用户偏好不存在")
        return {
            "defaultTextModelId": row["default_text_model_id"],
            "defaultImageModelId": row["default_image_model_id"],
            "defaultVideoModelId": row["default_video_model_id"],
            "agentImageEnabled": bool(row["agent_image_enabled"]),
            "agentVideoEnabled": bool(row["agent_video_enabled"]),
        }

    def update_preferences(self, command: UpdatePreferencesCommand) -> dict[str, object]:
        self._repository.update_preferences(
            default_text_model_id=command.default_text_model_id,
            default_image_model_id=command.default_image_model_id,
            default_video_model_id=command.default_video_model_id,
            agent_image_enabled=command.agent_image_enabled,
            agent_video_enabled=command.agent_video_enabled,
        )
        return self.get_preferences()

    def resolve_text_route(
        self,
        requested_provider_id: str,
        requested_model_id: str | None,
    ) -> TextModelRoute:
        row = self._repository.resolve_text_model(requested_model_id)
        if not row:
            raise ProviderConfigurationError("模型不存在或已停用")
        if requested_provider_id != row["provider_id"]:
            raise ProviderConfigurationError("所选模型不属于指定供应商")
        capabilities = json.loads(str(row["capabilities_json"]))
        if "text" not in capabilities or row["integration_status"] != "ready":
            raise ProviderConfigurationError("当前模型暂不支持已接入的文本对话能力")
        if row.get("encrypted_secret"):
            row["api_key"] = self._secret_box.decrypt(str(row["encrypted_secret"]))
        elif row["provider_id"] == "volcengine":
            row["api_key"] = os.getenv("ZAOJING_VOLCENGINE_API_KEY")
        runtime = "codex" if row["adapter_key"] == "codex_local" else "http"
        return TextModelRoute(
            provider_id=str(row["provider_id"]),
            model_id=str(row["id"]),
            runtime=runtime,
            provider_model=row,
        )

    async def stream_text(
        self, route: TextModelRoute, message: str
    ) -> AsyncIterator[CodexEvent]:
        if route.runtime != "http":
            raise ProviderConfigurationError("本地 Codex 路由不能交给 HTTP 模型适配器执行")
        model = route.provider_model
        api_key = str(model.get("api_key") or "")
        config = json.loads(str(model.get("config_json") or "{}"))
        base_url = str(
            config.get("base_url")
            or model.get("base_url")
            or "https://ark.cn-beijing.volces.com/api/v3"
        )
        async for event in self._text_client.chat(
            api_key=api_key,
            base_url=base_url,
            model=str(model["model_key"]),
            message=message,
        ):
            yield event

    async def test_text_model(
        self, provider_id: str, model_id: str, prompt: str
    ) -> dict[str, object]:
        started = perf_counter()
        try:
            route = self.resolve_text_route(provider_id, model_id)
            if route.runtime == "codex":
                status = self._local_runtime_status() if self._local_runtime_status else {}
                running = bool(status.get("running"))
                authenticated = bool(status.get("authenticated"))
                if running and authenticated:
                    message = "本地 Codex App Server 已运行并完成认证"
                elif running:
                    message = "Codex App Server 已运行，但未检测到登录账号；请先执行 codex login"
                else:
                    message = "本地 Codex App Server 未运行；请检查 CODEX_BINARY 配置"
                return {
                    "success": running and authenticated,
                    "modelId": route.model_id,
                    "providerId": route.provider_id,
                    "latencyMs": round((perf_counter() - started) * 1000),
                    "message": message,
                    "responsePreview": "",
                }
            response_parts: list[str] = []
            async for event in self.stream_text(route, prompt):
                if event.get("type") == "delta" and event.get("text"):
                    response_parts.append(str(event["text"]))
            preview = "".join(response_parts).strip()[:500]
            return {
                "success": True,
                "modelId": route.model_id,
                "providerId": route.provider_id,
                "latencyMs": round((perf_counter() - started) * 1000),
                "message": "模型测试请求成功",
                "responsePreview": preview,
            }
        except Exception as exc:  # noqa: BLE001 - test result is returned to the UI
            return {
                "success": False,
                "modelId": model_id,
                "providerId": provider_id,
                "latencyMs": round((perf_counter() - started) * 1000),
                "message": str(exc),
                "responsePreview": "",
            }

    def resolve_media_model(
        self, provider_id: str, model_id: str, task_type: str
    ) -> MediaModelRoute:
        row = self._repository.resolve_media_model(model_id)
        if not row:
            raise ProviderConfigurationError("模型不存在或已停用")
        if provider_id != row["provider_id"]:
            raise ProviderConfigurationError("所选模型不属于指定供应商")
        capabilities = json.loads(str(row["capabilities_json"]))
        if task_type not in capabilities or row["integration_status"] != "ready":
            raise ProviderConfigurationError("当前模型尚未接通该生成能力")
        api_key = ""
        if row.get("encrypted_secret"):
            api_key = self._secret_box.decrypt(str(row["encrypted_secret"]))
        elif row["provider_id"] == "volcengine":
            api_key = os.getenv("ZAOJING_VOLCENGINE_API_KEY") or ""
        if not api_key and row["provider_id"] != "comfyui":
            raise ProviderConfigurationError("尚未配置该供应商 API Key")
        config: dict[str, Any] = json.loads(str(row.get("config_json") or "{}"))
        base_url = str(
            config.get("base_url")
            or row.get("base_url")
            or (
                os.getenv("ZAOJING_COMFYUI_URL", "http://127.0.0.1:8000")
                if row["provider_id"] == "comfyui"
                else None
            )
            or "https://ark.cn-beijing.volces.com/api/v3"
        )
        return MediaModelRoute(
            id=str(row["id"]),
            provider_id=str(row["provider_id"]),
            model_key=str(row["model_key"]),
            base_url=base_url,
            api_key=api_key,
            config=config,
        )


def _public_workflow_inputs(
    raw_parameters: object,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Hide ComfyUI node bindings from the provider-neutral API contract."""

    parameters: list[dict[str, object]] = []
    references: dict[str, dict[str, object]] = {}
    seen_semantics: set[str] = set()
    if not isinstance(raw_parameters, list):
        return parameters, []
    for raw in raw_parameters:
        if not isinstance(raw, dict):
            continue
        parameter_type = str(raw.get("type") or "")
        if parameter_type == "assets":
            asset_type = str(raw.get("assetType") or "image")
            aggregate = references.setdefault(
                asset_type,
                {
                    "type": asset_type,
                    "label": {
                        "image": "参考图片",
                        "video": "参考视频",
                        "audio": "参考音频",
                        "file": "参考文件",
                    }.get(asset_type, "参考素材"),
                    "required": False,
                    "min": 0,
                    "max": 0,
                },
            )
            aggregate["required"] = bool(aggregate["required"]) or bool(
                raw.get("required")
            )
            aggregate["min"] = int(aggregate["min"]) + int(raw.get("min") or 0)
            aggregate["max"] = int(aggregate["max"]) + int(
                raw.get("max") or len(raw.get("bindings") or [])
            )
            continue
        bindings = raw.get("bindings")
        first_binding = (
            bindings[0]
            if isinstance(bindings, list) and bindings
            and isinstance(bindings[0], dict)
            else {}
        )
        semantic_key = str(
            raw.get("semanticKey")
            or infer_semantic_key(
                str(raw.get("key") or ""),
                str(raw.get("label") or ""),
                str(first_binding.get("field") or ""),
            )
        )
        if semantic_key in seen_semantics:
            continue
        seen_semantics.add(semantic_key)
        public_parameter = {
            key: value
            for key, value in raw.items()
            if key
            in {
                "label",
                "required",
                "default",
                "min",
                "max",
                "options",
            }
        }
        public_parameter["key"] = semantic_key
        public_parameter["semanticKey"] = semantic_key
        public_parameter["type"] = raw.get("type", "string")
        public_parameter["label"] = {
            "prompt": "提示词",
            "negativePrompt": "反向提示词",
            "aspectRatio": "画面比例",
            "resolution": "分辨率（1K / 2K / 4K）",
            "width": "宽度",
            "height": "高度",
            "seed": "随机种子",
            "count": "生成数量",
            "duration": "时长",
            "length": "帧数",
            "fps": "帧率",
            "quality": "质量",
        }.get(semantic_key, raw.get("label") or semantic_key)
        if semantic_key == "resolution":
            public_parameter["type"] = "string"
            public_parameter["options"] = ["1K", "2K", "4K"]
            public_parameter["default"] = megapixels_to_resolution(
                raw.get("default")
            )
        if semantic_key == "aspectRatio":
            default_ratio = str(raw.get("default") or "")
            if " (" in default_ratio:
                default_ratio = default_ratio.split(" (", 1)[0]
            if ":" not in default_ratio:
                public_parameter["default"] = "1:1"
            else:
                public_parameter["default"] = default_ratio
            public_parameter["options"] = ASPECT_RATIO_OPTIONS
        parameters.append(public_parameter)
    semantic_keys = {
        str(parameter.get("semanticKey") or "") for parameter in parameters
    }
    width_parameter = next(
        (
            parameter
            for parameter in parameters
            if parameter.get("semanticKey") == "width"
        ),
        None,
    )
    height_parameter = next(
        (
            parameter
            for parameter in parameters
            if parameter.get("semanticKey") == "height"
        ),
        None,
    )
    width_default = width_parameter.get("default") if width_parameter else None
    height_default = height_parameter.get("default") if height_parameter else None
    if (
        width_parameter
        and height_parameter
        and "aspectRatio" not in semantic_keys
    ):
        parameters.append(
            {
                "key": "aspectRatio",
                "semanticKey": "aspectRatio",
                "label": "画面比例",
                "type": "string",
                "required": True,
                "default": aspect_ratio_for_dimensions(
                    width_default,
                    height_default,
                ),
                "options": ASPECT_RATIO_OPTIONS,
            }
        )
        semantic_keys.add("aspectRatio")
    if (
        width_parameter
        and height_parameter
        and "resolution" not in semantic_keys
    ):
        parameters.append(
            {
                "key": "resolution",
                "semanticKey": "resolution",
                "label": "分辨率",
                "type": "string",
                "required": True,
                "default": resolution_from_dimensions(
                    width_default,
                    height_default,
                ),
                "options": ["1K", "2K", "4K"],
            }
        )
        semantic_keys.add("resolution")
    if (
        "resolution" in semantic_keys
        and "aspectRatio" in semantic_keys
    ):
        for parameter in parameters:
            if parameter.get("semanticKey") in {"width", "height"}:
                parameter["derived"] = True
    return parameters, list(references.values())
