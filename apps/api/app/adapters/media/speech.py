"""Windows speech adapter for offline speech synthesis."""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path

from app.shared.errors import AppServerError


class WindowsSapiSpeechSynthesizer:
    def __init__(self, script_path: Path) -> None:
        self._script_path = script_path
        self._powershell = shutil.which("powershell.exe")

    def list_voices(self) -> list[dict[str, object]]:
        result = self._run(["-ListVoices"])
        try:
            payload = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as exc:
            raise AppServerError("无法解析本机语音列表") from exc
        if isinstance(payload, dict):
            payload = [payload]
        return [item for item in payload if isinstance(item, dict)]

    def synthesize(
        self,
        text: str,
        destination: Path,
        *,
        voice_name: str,
        rate: int,
    ) -> None:
        if not text.strip():
            raise AppServerError("配音文本不能为空")
        destination.parent.mkdir(parents=True, exist_ok=True)
        text_path = destination.parent / f"{uuid.uuid4()}.txt"
        text_path.write_text(text, encoding="utf-8")
        try:
            self._run(
                [
                    "-TextFile",
                    str(text_path),
                    "-OutputFile",
                    str(destination),
                    "-VoiceName",
                    voice_name,
                    "-Rate",
                    str(max(-10, min(10, rate))),
                ]
            )
        finally:
            text_path.unlink(missing_ok=True)
        if not destination.is_file() or destination.stat().st_size == 0:
            raise AppServerError("本机语音合成未生成有效音频")

    def _run(self, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        if not self._powershell:
            raise AppServerError("未找到 Windows PowerShell，无法使用本机 TTS")
        if not self._script_path.is_file():
            raise AppServerError("本机 TTS 脚本不存在")
        result = subprocess.run(
            [
                self._powershell,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self._script_path),
                *arguments,
            ],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise AppServerError(f"本机 TTS 失败：{detail or '未知错误'}")
        return result
