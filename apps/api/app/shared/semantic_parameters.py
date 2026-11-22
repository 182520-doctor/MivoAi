"""Provider-neutral parameter names shared by workflow and provider contexts."""

from __future__ import annotations

import math
import re
from typing import Any

SEMANTIC_KEYS = {
    "prompt",
    "negativePrompt",
    "aspectRatio",
    "resolution",
    "width",
    "height",
    "seed",
    "count",
    "duration",
    "length",
    "fps",
    "quality",
}

RESOLUTION_MEGAPIXELS = {
    "1K": 1.0,
    "2K": 4.0,
    "4K": 16.0,
}
ASPECT_RATIO_OPTIONS = [
    "1:1",
    "4:3",
    "3:2",
    "16:9",
    "21:9",
    "3:4",
    "2:3",
    "9:16",
]


def infer_semantic_key(
    key: str,
    label: str = "",
    field: str = "",
) -> str:
    """Map workflow-specific aliases to a stable public parameter name."""

    aliases = f"{key} {label} {field}".lower()
    if "negative" in aliases or "反向" in aliases or "负面" in aliases:
        return "negativePrompt"
    if (
        "prompt" in aliases
        or "提示词" in aliases
        or key in {"replace", "text", "string"}
    ):
        return "prompt"
    if (
        "aspect_ratio" in aliases
        or "aspectratio" in aliases
        or "ratio" in aliases
        or "宽高比" in aliases
    ):
        return "aspectRatio"
    if (
        "megapixel" in aliases
        or "resolution" in aliases
        or "像素" in aliases
        or "分辨率" in aliases
    ):
        return "resolution"
    if key in {"width", "w"} or "宽度" in aliases:
        return "width"
    if key in {"height", "h"} or "高度" in aliases:
        return "height"
    if "noise_seed" in aliases or key == "seed" or "随机种子" in aliases:
        return "seed"
    if "batch" in aliases or key in {"count", "n"} or "数量" in aliases:
        return "count"
    if key in {"fps", "frame_rate"} or "帧率" in aliases:
        return "fps"
    if "duration" in aliases or key == "value_1" or "时长" in aliases:
        return "duration"
    if "length" in aliases or "帧数" in aliases:
        return "length"
    if "quality" in aliases or "质量" in aliases:
        return "quality"
    return key


def resolution_to_megapixels(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    normalized = str(value or "").strip().upper()
    return RESOLUTION_MEGAPIXELS.get(normalized)


def megapixels_to_resolution(value: Any) -> str:
    try:
        megapixels = float(value)
    except (TypeError, ValueError):
        return "2K"
    if megapixels <= 1.5:
        return "1K"
    if megapixels <= 6:
        return "2K"
    return "4K"


def dimensions_for_resolution(
    resolution: object,
    aspect_ratio: object,
) -> tuple[int, int] | None:
    megapixels = RESOLUTION_MEGAPIXELS.get(
        str(resolution or "").strip().upper()
    )
    if not megapixels:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)", str(aspect_ratio))
    if not match:
        return None
    ratio_width = float(match.group(1))
    ratio_height = float(match.group(2))
    if ratio_width <= 0 or ratio_height <= 0:
        return None
    ratio = ratio_width / ratio_height
    total_pixels = megapixels * 1024 * 1024
    width = math.sqrt(total_pixels * ratio)
    height = width / ratio
    return (round(width / 64) * 64, round(height / 64) * 64)


def aspect_ratio_for_dimensions(width: object, height: object) -> str:
    try:
        width_value = float(width)
        height_value = float(height)
    except (TypeError, ValueError):
        return "1:1"
    if width_value <= 0 or height_value <= 0:
        return "1:1"
    target = width_value / height_value
    best = min(
        ASPECT_RATIO_OPTIONS,
        key=lambda option: abs(
            _ratio_value(option) - target
        ),
    )
    return best


def resolution_from_dimensions(width: object, height: object) -> str:
    try:
        megapixels = float(width) * float(height) / (1024 * 1024)
    except (TypeError, ValueError):
        return "2K"
    return megapixels_to_resolution(megapixels)


def _ratio_value(value: str) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)", value)
    if not match:
        return 1.0
    return float(match.group(1)) / max(float(match.group(2)), 1e-9)
