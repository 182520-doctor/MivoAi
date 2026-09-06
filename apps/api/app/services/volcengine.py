"""Volcengine Ark Chat API adapter.

Ark exposes an OpenAI-compatible Chat Completions endpoint for text and visual
understanding. The adapter normalizes its SSE chunks into the gateway event shape.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.exceptions import AppServerError
from app.models.codex import CodexEvent


class VolcengineChatClient:
    """Call a user-configured Ark endpoint without exposing the API key to clients."""

    async def chat(
        self, *, api_key: str, base_url: str, model: str, message: str
    ) -> AsyncIterator[CodexEvent]:
        if not api_key:
            raise AppServerError("尚未配置火山引擎 API Key，请在模型设置中填写")
        url = base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": message}],
            "stream": True,
        }
        try:
            async with (
                httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=20.0)) as client,
                client.stream(
                    "POST", url, headers={"Authorization": f"Bearer {api_key}"}, json=payload
                ) as response,
            ):
                    if response.status_code >= 400:
                        detail = (await response.aread()).decode("utf-8", errors="replace")
                        raise AppServerError(
                            f"火山引擎请求失败（{response.status_code}）：{_safe_detail(detail)}"
                        )
                    yield {"type": "meta", "provider": "volcengine", "model": model}
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            yield {"type": "done", "status": "completed"}
                            return
                        try:
                            chunk: dict[str, Any] = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = chunk.get("choices") or []
                        delta = (choices[0].get("delta") or {}) if choices else {}
                        reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                        if reasoning:
                            yield {"type": "reasoning_delta", "text": reasoning}
                        text = delta.get("content") or ""
                        if text:
                            yield {"type": "delta", "text": text}
        except httpx.HTTPError as exc:
            raise AppServerError(f"火山引擎网络请求失败：{exc}") from exc


def _safe_detail(value: str) -> str:
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            error = parsed.get("error") or parsed
            return str(error.get("message") or error)[:500]
    except json.JSONDecodeError:
        pass
    return value[:500]


class VolcengineImageClient:
    """Call Ark Image Generation API and normalize URL/base64 results."""

    async def generate(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        prompt: str,
        parameters: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": model,
            "prompt": prompt,
            "response_format": "url",
            "watermark": True,
        }
        payload.update(parameters or {})
        return await _post_json(base_url.rstrip("/") + "/images/generations", api_key, payload)


class VolcengineVideoClient:
    """Call Ark asynchronous video task APIs."""

    async def create(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        prompt: str,
        parameters: dict[str, object] | None = None,
    ) -> dict[str, object]:
        content: list[dict[str, object]] = [{"type": "text", "text": prompt}]
        extra = dict(parameters or {})
        extra.setdefault("model", model)
        extra.setdefault("content", content)
        return await _post_json(
            base_url.rstrip("/") + "/contents/generations/tasks", api_key, extra
        )

    async def get_status(
        self, *, api_key: str, base_url: str, provider_task_id: str
    ) -> dict[str, object]:
        url = base_url.rstrip("/") + "/contents/generations/tasks/" + provider_task_id
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
                response = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
                if response.status_code >= 400:
                    raise AppServerError(
                        f"火山引擎视频任务查询失败（{response.status_code}）：{_safe_detail(response.text)}"
                    )
                return response.json()
        except httpx.HTTPError as exc:
            raise AppServerError(f"火山引擎视频任务查询失败：{exc}") from exc


async def _post_json(url: str, api_key: str, payload: dict[str, object]) -> dict[str, object]:
    if not api_key:
        raise AppServerError("尚未配置火山引擎 API Key，请在模型设置中填写")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=20.0)) as client:
            response = await client.post(
                url, headers={"Authorization": f"Bearer {api_key}"}, json=payload
            )
            if response.status_code >= 400:
                raise AppServerError(
                    f"火山引擎请求失败（{response.status_code}）：{_safe_detail(response.text)}"
                )
            return response.json()
    except httpx.HTTPError as exc:
        raise AppServerError(f"火山引擎网络请求失败：{exc}") from exc


async def download_remote_asset(url: str, destination: Any) -> tuple[str, int, str | None]:
    """Download a temporary provider URL into the local asset directory."""

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=20.0)) as client:
            response = await client.get(url)
            response.raise_for_status()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(response.content)
            return str(destination), len(response.content), response.headers.get("content-type")
    except httpx.HTTPError as exc:
        raise AppServerError(f"素材下载失败：{exc}") from exc
