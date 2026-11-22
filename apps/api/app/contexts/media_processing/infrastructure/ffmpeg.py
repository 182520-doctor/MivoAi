"""FFmpeg adapter for deterministic local media operations."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from pathlib import Path

from app.shared.errors import AppServerError


class FFmpegAudioExtractor:
    def __init__(self, executable: str | None = None) -> None:
        self._executable = executable or shutil.which("ffmpeg")

    def extract_audio(self, source: Path, destination: Path) -> None:
        if not self._executable:
            raise AppServerError("未找到 ffmpeg，无法提取视频音频")
        command = [
            self._executable,
            "-y",
            "-i",
            str(source),
            "-vn",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(destination),
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if result.returncode != 0:
            message = result.stderr.strip().splitlines()
            detail = message[-1] if message else "未知 FFmpeg 错误"
            raise AppServerError(f"音频提取失败：{detail}")
        if not destination.is_file() or destination.stat().st_size == 0:
            raise AppServerError("音频提取失败：未生成有效音频")


class FFmpegAudioNormalizer:
    def __init__(self, executable: str | None = None) -> None:
        self._executable = executable or shutil.which("ffmpeg")

    def normalize_audio(
        self,
        source: Path,
        destination: Path,
        *,
        target_lufs: float,
        true_peak_db: float,
        loudness_range: float,
    ) -> dict[str, object]:
        if not self._executable:
            raise AppServerError("未找到 ffmpeg，无法执行音频响度标准化")
        if not source.is_file():
            raise AppServerError("待标准化的音频文件不存在")
        base_filter = (
            f"loudnorm=I={target_lufs}:TP={true_peak_db}:"
            f"LRA={loudness_range}"
        )
        analysis = subprocess.run(
            [
                self._executable,
                "-hide_banner",
                "-nostats",
                "-i",
                str(source),
                "-vn",
                "-af",
                f"{base_filter}:print_format=json",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if analysis.returncode != 0:
            detail = _last_stderr_line(analysis.stderr)
            raise AppServerError(f"音频响度分析失败：{detail}")
        measured = _parse_loudnorm_json(analysis.stderr)
        finish = subprocess.run(
            [
                self._executable,
                "-y",
                "-i",
                str(source),
                "-vn",
                "-af",
                (
                    f"{base_filter}:"
                    f"measured_I={measured['input_i']}:"
                    f"measured_LRA={measured['input_lra']}:"
                    f"measured_TP={measured['input_tp']}:"
                    f"measured_thresh={measured['input_thresh']}:"
                    f"offset={measured['target_offset']}:"
                    "linear=true:print_format=summary"
                ),
                "-ar",
                "48000",
                "-ac",
                "2",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(destination),
            ],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if finish.returncode != 0:
            detail = _last_stderr_line(finish.stderr)
            raise AppServerError(f"音频响度标准化失败：{detail}")
        if not destination.is_file() or destination.stat().st_size == 0:
            raise AppServerError("音频响度标准化失败：未生成有效音频")
        return measured


class FFmpegWhisperTranscriber:
    def __init__(
        self,
        executable: str | None = None,
        model_path: Path | None = None,
    ) -> None:
        self._executable = executable or shutil.which("ffmpeg")
        self._model_path = model_path or Path(
            os.getenv(
                "ZAOJING_WHISPER_MODEL",
                r"E:\comfyui_decp\models\whisper\ggml-tiny.bin",
            )
        )

    def transcribe(
        self,
        source: Path,
        destination: Path,
        *,
        language: str,
    ) -> list[dict[str, object]]:
        if not self._executable:
            raise AppServerError("未找到 ffmpeg，无法执行语音转写")
        if not source.is_file():
            raise AppServerError("待转写音频不存在")
        if not self._model_path.is_file():
            raise AppServerError(
                f"Whisper 模型不存在：{self._model_path}"
            )
        escaped_model = (
            os.fspath(self._model_path)
            .replace("\\", "/")
            .replace(":", r"\:")
        )
        escaped_destination = (
            os.fspath(destination)
            .replace("\\", "/")
            .replace(":", r"\:")
        )
        whisper_filter = (
            f"whisper=model='{escaped_model}':"
            f"language={language}:"
            f"destination='{escaped_destination}':format=json"
        )
        result = subprocess.run(
            [
                self._executable,
                "-hide_banner",
                "-nostats",
                "-y",
                "-i",
                str(source),
                "-vn",
                "-af",
                whisper_filter,
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        if result.returncode != 0:
            raise AppServerError(
                f"语音转写失败：{_last_stderr_line(result.stderr)}"
            )
        if not destination.is_file():
            raise AppServerError("语音转写失败：未生成时间轴文件")
        cues: list[dict[str, object]] = []
        for line in destination.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            text = str(payload.get("text") or "").strip()
            if not text:
                continue
            start_ms = int(payload.get("start") or 0)
            end_ms = int(payload.get("end") or start_ms)
            cues.append(
                {
                    "startSeconds": round(start_ms / 1000, 3),
                    "endSeconds": round(max(start_ms + 100, end_ms) / 1000, 3),
                    "text": text,
                }
            )
        if not cues:
            raise AppServerError("语音转写完成但未识别到字幕内容")
        return cues


class FFmpegVideoComposer:
    def __init__(
        self,
        ffmpeg: str | None = None,
        ffprobe: str | None = None,
    ) -> None:
        self._ffmpeg = ffmpeg or shutil.which("ffmpeg")
        self._ffprobe = ffprobe or shutil.which("ffprobe")

    def compose_videos(
        self,
        sources: list[Path],
        destination: Path,
        *,
        aspect_ratio: str,
        subtitle_path: Path | None = None,
        subtitle_style: dict[str, object] | None = None,
        audio_sources: list[Path | None] | None = None,
        transition: str = "none",
        transition_duration: float = 0.4,
        music_source: Path | None = None,
        music_volume_db: float = -18,
        ambience_source: Path | None = None,
        ambience_volume_db: float = -22,
        ducking: bool = True,
        sound_effects: list[dict[str, object]] | None = None,
    ) -> None:
        if not self._ffmpeg or not self._ffprobe:
            raise AppServerError("未找到 ffmpeg/ffprobe，无法合成整集")
        if not sources:
            raise AppServerError("没有可合成的镜头视频")
        width, height = _output_dimensions(aspect_ratio)
        probes = [_probe_video(self._ffprobe, source) for source in sources]
        output_fps = max(
            30,
            min(60, max(int(probe["fps"]) for probe in probes)),
        )
        command = [self._ffmpeg, "-y"]
        video_input_indices: list[int] = []
        audio_input_indices: list[int | None] = []
        input_count = 0
        for source in sources:
            command.extend(["-i", str(source)])
            video_input_indices.append(input_count)
            input_count += 1
        normalized_audio = list(audio_sources or [])
        normalized_audio.extend([None] * (len(sources) - len(normalized_audio)))
        for audio_source in normalized_audio[: len(sources)]:
            if audio_source:
                if not audio_source.is_file():
                    raise AppServerError("镜头配音文件不存在")
                command.extend(["-i", str(audio_source)])
                audio_input_indices.append(input_count)
                input_count += 1
            else:
                audio_input_indices.append(None)
        music_input_index: int | None = None
        if music_source:
            command.extend(["-stream_loop", "-1", "-i", str(music_source)])
            music_input_index = input_count
            input_count += 1
        ambience_input_index: int | None = None
        if ambience_source:
            command.extend(["-stream_loop", "-1", "-i", str(ambience_source)])
            ambience_input_index = input_count
            input_count += 1
        effect_input_indices: list[int] = []
        for effect in sound_effects or []:
            effect_source = effect.get("source")
            if not isinstance(effect_source, Path):
                continue
            command.extend(["-stream_loop", "-1", "-i", str(effect_source)])
            effect_input_indices.append(input_count)
            input_count += 1
        filters: list[str] = []
        concat_inputs: list[str] = []
        for index, probe in enumerate(probes):
            duration = probe["duration"]
            video_index = video_input_indices[index]
            filters.append(
                f"[{video_index}:v]"
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
                f"setsar=1,fps={output_fps},format=yuv420p"
                f"[v{index}]"
            )
            audio_index = audio_input_indices[index]
            if audio_index is not None:
                filters.append(
                    f"[{audio_index}:a]"
                    "aresample=48000,aformat=channel_layouts=stereo,"
                    f"apad=whole_dur={duration},atrim=0:{duration},"
                    "asetpts=PTS-STARTPTS"
                    f"[a{index}]"
                )
            elif probe["hasAudio"]:
                filters.append(
                    f"[{video_index}:a]"
                    "aresample=48000,aformat=channel_layouts=stereo,"
                    f"apad=whole_dur={duration},atrim=0:{duration},"
                    "asetpts=PTS-STARTPTS"
                    f"[a{index}]"
                )
            else:
                filters.append(
                    "anullsrc=r=48000:cl=stereo,"
                    f"atrim=0:{duration},asetpts=PTS-STARTPTS[a{index}]"
                )
            concat_inputs.append(f"[v{index}][a{index}]")
        count = len(sources)
        overlap_duration = (
            min(
                max(0.1, transition_duration),
                min(float(probe["duration"]) for probe in probes) / 2,
            )
            if transition == "crossfade" and count > 1
            else 0.0
        )
        program_duration = (
            sum(float(probe["duration"]) for probe in probes)
            - overlap_duration * max(0, count - 1)
        )
        if transition == "crossfade" and count > 1:
            effective_duration = overlap_duration
            video_output = "v0"
            audio_output = "a0"
            current_duration = float(probes[0]["duration"])
            for index in range(1, count):
                offset = max(0.0, current_duration - effective_duration)
                next_video = f"xv{index}"
                next_audio = f"xa{index}"
                filters.append(
                    f"[{video_output}][v{index}]"
                    f"xfade=transition=fade:duration={effective_duration}:"
                    f"offset={offset:.6f}[{next_video}]"
                )
                filters.append(
                    f"[{audio_output}][a{index}]"
                    f"acrossfade=d={effective_duration}:c1=tri:c2=tri"
                    f"[{next_audio}]"
                )
                video_output = next_video
                audio_output = next_audio
                current_duration = (
                    current_duration
                    + float(probes[index]["duration"])
                    - effective_duration
                )
            filters.append(f"[{video_output}]null[outv]")
            filters.append(f"[{audio_output}]anull[outa]")
        else:
            filters.append(
                "".join(concat_inputs)
                + f"concat=n={count}:v=1:a=1[outv][outa]"
            )
        video_output = "outv"
        mixed_audio_output = "outa"
        if music_input_index is not None:
            filters.append(
                f"[{music_input_index}:a]"
                "aresample=48000,aformat=channel_layouts=stereo,"
                f"atrim=0:{program_duration},asetpts=PTS-STARTPTS,"
                f"volume={music_volume_db}dB[musicbed]"
            )
            if ducking:
                filters.append("[outa]asplit=2[mainaudio][sidechain]")
                filters.append(
                    "[musicbed][sidechain]"
                    "sidechaincompress=threshold=0.03:ratio=8:"
                    "attack=20:release=400[duckedmusic]"
                )
                filters.append(
                    "[mainaudio][duckedmusic]"
                    "amix=inputs=2:duration=first:"
                    "dropout_transition=0[musicmix]"
                )
            else:
                filters.append(
                    "[outa][musicbed]"
                    "amix=inputs=2:duration=first:"
                    "dropout_transition=0[musicmix]"
                )
            mixed_audio_output = "musicmix"
        if ambience_input_index is not None:
            filters.append(
                f"[{ambience_input_index}:a]"
                "aresample=48000,aformat=channel_layouts=stereo,"
                f"atrim=0:{program_duration},asetpts=PTS-STARTPTS,"
                f"volume={ambience_volume_db}dB[ambiencebed]"
            )
            filters.append(
                f"[{mixed_audio_output}][ambiencebed]"
                "amix=inputs=2:duration=first:"
                "dropout_transition=0[ambiencemix]"
            )
            mixed_audio_output = "ambiencemix"
        for index, input_index in enumerate(effect_input_indices):
            effect = (sound_effects or [])[index]
            start = max(0.0, float(effect.get("startSeconds") or 0))
            if start >= program_duration:
                continue
            duration = min(
                max(0.05, float(effect.get("durationSeconds") or 0)),
                program_duration - start,
            )
            volume = float(effect.get("volumeDb") or 0)
            delay_ms = round(start * 1000)
            filters.append(
                f"[{input_index}:a]"
                "aresample=48000,aformat=channel_layouts=stereo,"
                f"atrim=0:{duration},asetpts=PTS-STARTPTS,"
                f"volume={volume}dB,adelay={delay_ms}|{delay_ms}"
                f"[sfx{index}]"
            )
            next_output = f"sfxmix{index}"
            filters.append(
                f"[{mixed_audio_output}][sfx{index}]"
                "amix=inputs=2:duration=first:"
                f"dropout_transition=0[{next_output}]"
            )
            mixed_audio_output = next_output
        if subtitle_path:
            force_style = _subtitle_force_style(subtitle_style)
            filters.append(
                f"[outv]subtitles={subtitle_path.name}:"
                f"force_style='{force_style}'"
                "[subtitlev]"
            )
            video_output = "subtitlev"
        command.extend(
            [
                "-filter_complex",
                ";".join(filters),
                "-map",
                f"[{video_output}]",
                "-map",
                f"[{mixed_audio_output}]",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(destination),
            ]
        )
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
            cwd=destination.parent,
        )
        if result.returncode != 0:
            message = result.stderr.strip().splitlines()
            detail = message[-1] if message else "未知 FFmpeg 错误"
            raise AppServerError(f"整集合成失败：{detail}")
        if not destination.is_file() or destination.stat().st_size == 0:
            raise AppServerError("整集合成失败：未生成有效视频")


class FFmpegVideoUpscaler:
    def __init__(self, executable: str | None = None) -> None:
        self._executable = executable or shutil.which("ffmpeg")

    def upscale_video(
        self,
        source: Path,
        destination: Path,
        *,
        width: int,
        height: int,
    ) -> None:
        if not self._executable:
            raise AppServerError("未找到 ffmpeg，无法执行视频超分")
        command = [
            self._executable,
            "-y",
            "-i",
            str(source),
            "-vf",
            (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease:"
                "flags=lanczos,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
                "setsar=1,unsharp=5:5:0.55:5:5:0"
            ),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(destination),
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        if result.returncode != 0:
            message = result.stderr.strip().splitlines()
            detail = message[-1] if message else "未知 FFmpeg 错误"
            raise AppServerError(f"视频超分失败：{detail}")
        if not destination.is_file() or destination.stat().st_size == 0:
            raise AppServerError("视频超分失败：未生成有效视频")


def _probe_video(ffprobe: str, source: Path) -> dict[str, object]:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=avg_frame_rate,r_frame_rate",
            "-of",
            "json",
            str(source),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise AppServerError(f"无法读取视频时长：{source.name}")
    payload = json.loads(result.stdout or "{}")
    duration = float(payload.get("format", {}).get("duration") or 0)
    if duration <= 0:
        raise AppServerError(f"视频时长无效：{source.name}")
    streams = payload.get("streams") or []
    rate = "30/1"
    if streams:
        rate = (
            streams[0].get("avg_frame_rate")
            or streams[0].get("r_frame_rate")
            or rate
        )
    fps = _frame_rate(rate)
    audio = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            str(source),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return {
        "duration": round(duration, 3),
        "fps": fps,
        "hasAudio": bool(audio.stdout.strip()),
    }


def _output_dimensions(aspect_ratio: str) -> tuple[int, int]:
    return {
        "9:16": (1080, 1920),
        "16:9": (1920, 1080),
        "1:1": (1080, 1080),
        "4:3": (1440, 1080),
        "3:4": (1080, 1440),
    }.get(aspect_ratio, (1920, 1080))


def _frame_rate(value: object) -> int:
    text = str(value or "30/1")
    try:
        numerator, denominator = text.split("/", 1)
        result = float(numerator) / max(float(denominator), 1)
    except (TypeError, ValueError, ZeroDivisionError):
        result = 30
    if result <= 0:
        result = 30
    return max(1, round(result))


def _last_stderr_line(stderr: str) -> str:
    lines = stderr.strip().splitlines()
    return lines[-1] if lines else "未知 FFmpeg 错误"


def _parse_loudnorm_json(stderr: str) -> dict[str, float]:
    start = stderr.rfind("{")
    end = stderr.rfind("}")
    if start < 0 or end <= start:
        raise AppServerError("音频响度分析失败：未返回测量数据")
    try:
        payload = json.loads(stderr[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AppServerError("音频响度分析失败：测量数据格式错误") from exc
    values: dict[str, float] = {}
    for key in (
        "input_i",
        "input_lra",
        "input_tp",
        "input_thresh",
        "target_offset",
    ):
        try:
            value = float(payload[key])
        except (KeyError, TypeError, ValueError) as exc:
            raise AppServerError(
                f"音频响度分析失败：缺少 {key}"
            ) from exc
        if not math.isfinite(value):
            raise AppServerError("音频响度分析失败：音频缺少可测量响度")
        values[key] = value
    return values


def _subtitle_force_style(style: dict[str, object] | None) -> str:
    values = style or {}
    font_size = max(12, min(80, int(values.get("fontSize") or 30)))
    outline = max(0.0, min(8.0, float(values.get("outline") or 2)))
    margin_v = max(0, min(600, int(values.get("marginV") or 96)))
    primary = _ass_color(str(values.get("primaryColor") or "#FFFFFF"))
    outline_color = _ass_color(
        str(values.get("outlineColor") or "#101010")
    )
    return (
        f"FontName=SimHei,FontSize={font_size},"
        f"PrimaryColour={primary},OutlineColour={outline_color},"
        f"BorderStyle=1,Outline={outline},Shadow=0,"
        f"MarginV={margin_v},Alignment=2"
    )


def _ass_color(value: str) -> str:
    normalized = value.strip().lstrip("#")
    if len(normalized) != 6:
        normalized = "FFFFFF"
    try:
        red = int(normalized[0:2], 16)
        green = int(normalized[2:4], 16)
        blue = int(normalized[4:6], 16)
    except ValueError:
        red, green, blue = 255, 255, 255
    return f"&H00{blue:02X}{green:02X}{red:02X}"
