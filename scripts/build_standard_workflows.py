"""Build Zaojing standard MiniMax H3 ComfyUI workflow files.

The source workflows are ComfyUI-native exports. This script derives stable
variants with fixed reference roles while leaving the original files untouched.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import uuid
from pathlib import Path
from typing import Any

from app.contexts.workflows.converter import _flatten_subgraphs

STANDARD_METADATA = {
    "family": "minimax_h3",
    "version": 1,
    "maintainer": "zaojing",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workflow-dir",
        type=Path,
        default=Path(
            os.getenv(
                "COMFY_WORKFLOW_DIR",
                r"E:\comfyui_decp\user\default\workflows",
            )
        ),
    )
    args = parser.parse_args()
    directory = args.workflow_dir
    if not directory.is_dir():
        raise SystemExit(f"ComfyUI workflow directory not found: {directory}")

    t2i = _read(directory / "image_minimax_h3_image_t2i.json")
    flf2v = _read(directory / "MiniMax首尾帧视频生成.json")
    ref2v = _read(directory / "video_minimax_h3_r2v.json")

    outputs = {
        "mivo_std_minimax_h3_image_t2i.json": _prepare(
            t2i,
            slug="minimax_h3_image_t2i",
            title="MiniMax H3 文生图",
            use_case="Agent 文生图、短剧角色/场景/道具资产生成",
            reference_roles=[],
        ),
        "mivo_std_minimax_h3_image_multiref.json": _build_image_multiref(t2i),
        "mivo_std_minimax_h3_video_t2v.json": _build_video_t2v(flf2v),
        "mivo_std_minimax_h3_video_multiref.json": _build_video_multiref(ref2v),
        "mivo_std_minimax_h3_video_flf2v.json": _prepare(
            flf2v,
            slug="minimax_h3_video_flf2v",
            title="MiniMax H3 首尾帧视频",
            use_case="短剧镜头关键帧插值、首尾动作过渡",
            reference_roles=["first_frame", "last_frame"],
        ),
        "mivo_std_remove_background.json": _build_remove_background(),
        "mivo_std_extract_first_frame.json": _build_extract_frame(
            index="0",
            slug="extract_first_frame",
            title="提取视频首帧",
            prefix="mivo_first_frame",
        ),
        "mivo_std_extract_last_frame.json": _build_extract_frame(
            index="-1",
            slug="extract_last_frame",
            title="提取视频尾帧",
            prefix="mivo_last_frame",
        ),
        "mivo_std_image_upscale.json": _build_image_upscale(),
        "mivo_std_video_interpolate.json": _build_video_interpolate(),
        "mivo_std_audio_separation.json": _build_audio_separation(),
        "mivo_std_transcription.json": _build_transcription(),
        "mivo_std_video_matting.json": _build_video_matting(),
    }

    for filename, workflow in outputs.items():
        target = directory / filename
        target.write_text(
            json.dumps(workflow, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(target)


def _build_image_multiref(source: dict[str, Any]) -> dict[str, Any]:
    return _build_image_variant(
        source,
        capacity=10,
        slug="minimax_h3_image_multiref",
        title="MiniMax H3 多图参考生图",
        use_case="1–10 张参考图：单图编辑、多图融合、角色与场景一致性",
    )


def _build_image_variant(
    source: dict[str, Any],
    *,
    capacity: int,
    slug: str,
    title: str,
    use_case: str,
) -> dict[str, Any]:
    workflow = _flattened(source)
    conditioning = _find_node(workflow, "MiniMaxH3ImageConditioning")
    _remove_unused_generated_inputs(conditioning, "images.")
    next_id = _next_node_id(workflow)
    next_link = _next_link_id(workflow)
    for index in range(capacity):
        image_id = next_id + index
        link_id = next_link + index
        _add_load_image(
            workflow,
            node_id=image_id,
            target_id=str(conditioning["id"]),
            target_field=f"images.image_{index}",
            link_id=link_id,
            filename=f"reference_{index + 1}.png",
            position=[-1900, 4100 + index * 360],
        )
    return _prepare(
        workflow,
        slug=slug,
        title=title,
        use_case=use_case,
        reference_roles=[
            role
            for role in (
                "character",
                "secondary_character",
                "costume_or_prop",
                "scene_or_style",
                "style_reference",
                "composition_reference",
                "additional_prop",
                "additional_reference",
                "additional_reference_2",
                "additional_reference_3",
            )
        ][:capacity],
        flattened=True,
    )


def _build_video_t2v(source: dict[str, Any]) -> dict[str, Any]:
    workflow = _remove_nodes(copy.deepcopy(source), {275, 277})
    definitions = (workflow.get("definitions") or {}).get("subgraphs") or []
    if not definitions:
        raise RuntimeError("Text-to-video source subgraph definition is missing")
    definition = definitions[0]
    conditioner = _find_node(definition, "MiniMaxH3ImageToVideo")
    for input_spec in conditioner.get("inputs") or []:
        if input_spec.get("name") in {"first_frame", "last_frame"}:
            input_spec["link"] = None
    conditioner_id = int(conditioner["id"])
    definition["links"] = [
        link
        for link in definition.get("links") or []
        if not (
            int(link.get("target_id", -1)) == conditioner_id
            and int(link.get("target_slot", -1)) in {2, 3}
        )
    ]
    workflow = _flat(workflow)
    _set_prompt(
        workflow,
        "生成一段连贯的电影感视频，明确描述主体、动作、场景、镜头运动、"
        "光线、风格和声音。人物外观与服装在镜头中保持一致。",
    )
    return _prepare(
        workflow,
        slug="minimax_h3_video_t2v",
        title="MiniMax H3 文生视频",
        use_case="纯文本镜头生成、短剧动态预演、氛围与动作探索",
        reference_roles=[],
        flattened=True,
    )


def _build_remove_background() -> dict[str, Any]:
    workflow: dict[str, Any] = {"nodes": [], "links": []}
    image_node = _load_image_node(
        1,
        filename="portrait.png",
        position=[-600, 0],
    )
    rembg_node = {
        "id": 2,
        "type": "Image Rembg (Remove Background)",
        "pos": [-200, 0],
        "size": [380, 430],
        "flags": {},
        "order": 1,
        "mode": 0,
        "inputs": [
            {"name": "images", "type": "IMAGE", "link": 10},
            {
                "name": "transparency",
                "type": "BOOLEAN",
                "widget": {"name": "transparency"},
                "link": None,
            },
            {
                "name": "model",
                "type": "COMBO",
                "widget": {"name": "model"},
                "link": None,
            },
            {
                "name": "post_processing",
                "type": "BOOLEAN",
                "widget": {"name": "post_processing"},
                "link": None,
            },
            {
                "name": "only_mask",
                "type": "BOOLEAN",
                "widget": {"name": "only_mask"},
                "link": None,
            },
            {
                "name": "alpha_matting",
                "type": "BOOLEAN",
                "widget": {"name": "alpha_matting"},
                "link": None,
            },
            {
                "name": "alpha_matting_foreground_threshold",
                "type": "INT",
                "widget": {"name": "alpha_matting_foreground_threshold"},
                "link": None,
            },
            {
                "name": "alpha_matting_background_threshold",
                "type": "INT",
                "widget": {"name": "alpha_matting_background_threshold"},
                "link": None,
            },
            {
                "name": "alpha_matting_erode_size",
                "type": "INT",
                "widget": {"name": "alpha_matting_erode_size"},
                "link": None,
            },
            {
                "name": "background_color",
                "type": "COMBO",
                "widget": {"name": "background_color"},
                "link": None,
            },
        ],
        "outputs": [{"name": "images", "type": "IMAGE", "links": [20]}],
        "properties": {"Node name for S&R": "Image Rembg (Remove Background)"},
        "widgets_values": [
            True,
            "isnet-general-use",
            True,
            False,
            True,
            240,
            10,
            10,
            "none",
        ],
    }
    save_node = _save_image_node(
        3,
        prefix="mivo_remove_background",
        position=[260, 0],
        link_id=20,
    )
    image_node["outputs"][0]["links"] = [10]
    workflow["nodes"] = [image_node, rembg_node, save_node]
    workflow["links"] = [
        [10, 1, 0, 2, 0, "IMAGE"],
        [20, 2, 0, 3, 0, "IMAGE"],
    ]
    return _prepare(
        workflow,
        slug="image_remove_background",
        title="透明背景抠图",
        use_case="人物、角色、服装和道具透明化，供短剧合成与素材复用",
        reference_roles=["source_image"],
        flattened=True,
    )


def _build_image_upscale() -> dict[str, Any]:
    workflow: dict[str, Any] = {"nodes": [], "links": []}
    image_node = _load_image_node(
        1,
        filename="source.png",
        position=[-700, 0],
    )
    loader_node = {
        "id": 2,
        "type": "UpscaleModelLoader",
        "pos": [-260, -180],
        "size": [320, 90],
        "flags": {},
        "order": 1,
        "mode": 0,
        "inputs": [
            {
                "name": "model_name",
                "type": "COMBO",
                "widget": {"name": "model_name"},
                "link": None,
            }
        ],
        "outputs": [
            {"name": "UPSCALE_MODEL", "type": "UPSCALE_MODEL", "links": [11]}
        ],
        "properties": {"Node name for S&R": "UpscaleModelLoader"},
        "widgets_values": ["4x-UltraSharp.pth"],
    }
    upscale_node = {
        "id": 3,
        "type": "ImageUpscaleWithModel",
        "pos": [120, 0],
        "size": [300, 100],
        "flags": {},
        "order": 2,
        "mode": 0,
        "inputs": [
            {"name": "upscale_model", "type": "UPSCALE_MODEL", "link": 11},
            {"name": "image", "type": "IMAGE", "link": 10},
        ],
        "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [20]}],
        "properties": {"Node name for S&R": "ImageUpscaleWithModel"},
        "widgets_values": [],
    }
    save_node = _save_image_node(
        4,
        prefix="mivo_image_upscale",
        position=[480, 0],
        link_id=20,
    )
    image_node["outputs"][0]["links"] = [10]
    workflow["nodes"] = [image_node, loader_node, upscale_node, save_node]
    workflow["links"] = [
        [10, 1, 0, 3, 1, "IMAGE"],
        [11, 2, 0, 3, 0, "UPSCALE_MODEL"],
        [20, 3, 0, 4, 0, "IMAGE"],
    ]
    return _prepare(
        workflow,
        slug="image_upscale",
        title="图片放大与细节增强",
        use_case="角色定妆、场景概念、海报与关键帧的 4 倍放大",
        reference_roles=["source_image"],
        flattened=True,
    )


def _build_video_interpolate() -> dict[str, Any]:
    workflow: dict[str, Any] = {"nodes": [], "links": []}
    video_node = _add_load_video(
        workflow,
        node_id=1,
        filename="source.mp4",
        position=[-850, 0],
    )
    rife_node = {
        "id": 2,
        "type": "RIFE VFI",
        "pos": [-420, 0],
        "size": [340, 420],
        "flags": {},
        "order": 1,
        "mode": 0,
        "inputs": [
            {"name": "frames", "type": "IMAGE", "link": 10},
            {
                "name": "optional_interpolation_states",
                "type": "INTERPOLATION_STATES",
                "link": None,
            },
            {
                "name": "ckpt_name",
                "type": "COMBO",
                "widget": {"name": "ckpt_name"},
                "link": None,
            },
            {
                "name": "clear_cache_after_n_frames",
                "type": "INT",
                "widget": {"name": "clear_cache_after_n_frames"},
                "link": None,
            },
            {
                "name": "multiplier",
                "type": "INT",
                "widget": {"name": "multiplier"},
                "link": None,
            },
            {
                "name": "fast_mode",
                "type": "BOOLEAN",
                "widget": {"name": "fast_mode"},
                "link": None,
            },
            {
                "name": "ensemble",
                "type": "BOOLEAN",
                "widget": {"name": "ensemble"},
                "link": None,
            },
            {
                "name": "scale_factor",
                "type": "FLOAT",
                "widget": {"name": "scale_factor"},
                "link": None,
            },
            {
                "name": "dtype",
                "type": "COMBO",
                "widget": {"name": "dtype"},
                "link": None,
            },
            {
                "name": "torch_compile",
                "type": "BOOLEAN",
                "widget": {"name": "torch_compile"},
                "link": None,
            },
            {
                "name": "batch_size",
                "type": "INT",
                "widget": {"name": "batch_size"},
                "link": None,
            },
        ],
        "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [20]}],
        "properties": {"Node name for S&R": "RIFE VFI"},
        "widgets_values": [
            "rife47.pth",
            10,
            2,
            True,
            True,
            1.0,
            "float16",
            False,
            1,
        ],
    }
    combine_node = {
        "id": 3,
        "type": "VHS_VideoCombine",
        "pos": [20, 0],
        "size": [320, 520],
        "flags": {},
        "order": 2,
        "mode": 0,
        "inputs": [
            {"name": "images", "type": "IMAGE", "link": 20},
            {"name": "audio", "type": "AUDIO", "link": None},
            {
                "name": "meta_batch",
                "type": "VHS_BatchManager",
                "link": None,
            },
            {"name": "vae", "type": "VAE", "link": None},
            {
                "name": "frame_rate",
                "type": "FLOAT",
                "widget": {"name": "frame_rate"},
                "link": None,
            },
            {
                "name": "loop_count",
                "type": "INT",
                "widget": {"name": "loop_count"},
                "link": None,
            },
            {
                "name": "filename_prefix",
                "type": "STRING",
                "widget": {"name": "filename_prefix"},
                "link": None,
            },
            {
                "name": "format",
                "type": "COMBO",
                "widget": {"name": "format"},
                "link": None,
            },
            {
                "name": "pingpong",
                "type": "BOOLEAN",
                "widget": {"name": "pingpong"},
                "link": None,
            },
            {
                "name": "save_output",
                "type": "BOOLEAN",
                "widget": {"name": "save_output"},
                "link": None,
            },
            {
                "name": "pix_fmt",
                "type": "COMBO",
                "widget": {"name": "pix_fmt"},
                "link": None,
            },
            {
                "name": "crf",
                "type": "INT",
                "widget": {"name": "crf"},
                "link": None,
            },
            {
                "name": "save_metadata",
                "type": "BOOLEAN",
                "widget": {"name": "save_metadata"},
                "link": None,
            },
            {
                "name": "trim_to_audio",
                "type": "BOOLEAN",
                "widget": {"name": "trim_to_audio"},
                "link": None,
            },
        ],
        "outputs": [{"name": "Filenames", "type": "VHS_FILENAMES", "links": []}],
        "properties": {"Node name for S&R": "VHS_VideoCombine"},
        "widgets_values": {
            "frame_rate": 60,
            "loop_count": 0,
            "filename_prefix": "mivo_video_interpolate",
            "format": "video/h264-mp4",
            "pix_fmt": "yuv420p",
            "crf": 18,
            "save_metadata": True,
            "trim_to_audio": False,
            "pingpong": False,
            "save_output": True,
        },
        "widgets_values_named": {
            "frame_rate": 60,
            "loop_count": 0,
            "filename_prefix": "mivo_video_interpolate",
            "format": "video/h264-mp4",
            "pix_fmt": "yuv420p",
            "crf": 18,
            "save_metadata": True,
            "trim_to_audio": False,
            "pingpong": False,
            "save_output": True,
        },
    }
    video_node["outputs"][0]["links"] = [10]
    workflow["nodes"] = [video_node, rife_node, combine_node]
    workflow["links"] = [
        [10, 1, 0, 2, 0, "IMAGE"],
        [20, 2, 0, 3, 0, "IMAGE"],
    ]
    return _prepare(
        workflow,
        slug="video_interpolate",
        title="视频补帧至 60fps",
        use_case="镜头视频平滑补帧、慢动作和动作连续性优化",
        reference_roles=["source_video"],
        flattened=True,
    )


def _build_audio_separation() -> dict[str, Any]:
    workflow: dict[str, Any] = {"nodes": [], "links": []}
    audio_node = {
        "id": 1,
        "type": "LoadAudio",
        "pos": [-900, 0],
        "size": [320, 180],
        "flags": {},
        "order": 0,
        "mode": 0,
        "inputs": [
            {
                "name": "audio",
                "type": "COMBO",
                "widget": {"name": "audio"},
                "link": None,
            }
        ],
        "outputs": [{"name": "AUDIO", "type": "AUDIO", "links": [10]}],
        "properties": {"Node name for S&R": "LoadAudio"},
        "widgets_values": ["source.wav"],
    }
    separation_node = {
        "id": 2,
        "type": "AudioSeparation",
        "pos": [-430, 0],
        "size": [360, 310],
        "flags": {},
        "order": 1,
        "mode": 0,
        "inputs": [
            {"name": "audio", "type": "AUDIO", "link": 10},
            {
                "name": "chunk_fade_shape",
                "type": "COMBO",
                "widget": {"name": "chunk_fade_shape"},
                "link": None,
            },
            {
                "name": "chunk_length",
                "type": "FLOAT",
                "widget": {"name": "chunk_length"},
                "link": None,
            },
            {
                "name": "chunk_overlap",
                "type": "FLOAT",
                "widget": {"name": "chunk_overlap"},
                "link": None,
            },
        ],
        "outputs": [
            {"name": "Bass", "type": "AUDIO", "links": [20]},
            {"name": "Drums", "type": "AUDIO", "links": [30]},
            {"name": "Other", "type": "AUDIO", "links": [40]},
            {"name": "Vocals", "type": "AUDIO", "links": [50]},
        ],
        "properties": {"Node name for S&R": "AudioSeparation"},
        "widgets_values": ["linear", 10.0, 0.1],
    }
    save_nodes: list[dict[str, Any]] = []
    stems = (("bass", 20), ("drums", 30), ("other", 40), ("vocals", 50))
    for index, (stem, link_id) in enumerate(stems):
        save_nodes.append(
            {
                "id": 3 + index,
                "type": "SaveAudio",
                "pos": [60 + index * 340, 0],
                "size": [300, 150],
                "flags": {},
                "order": 2 + index,
                "mode": 0,
                "inputs": [
                    {"name": "audio", "type": "AUDIO", "link": link_id},
                    {
                        "name": "filename_prefix",
                        "type": "STRING",
                        "widget": {"name": "filename_prefix"},
                        "link": None,
                    },
                ],
                "outputs": [{"name": "audio", "type": "AUDIO", "links": []}],
                "properties": {"Node name for S&R": "SaveAudio"},
                "widgets_values": [f"audio/mivo_{stem}"],
            }
        )
    workflow["nodes"] = [
        audio_node,
        separation_node,
        *save_nodes,
    ]
    workflow["links"] = [
        [10, 1, 0, 2, 0, "AUDIO"],
        [20, 2, 0, 3, 0, "AUDIO"],
        [30, 2, 1, 4, 0, "AUDIO"],
        [40, 2, 2, 5, 0, "AUDIO"],
        [50, 2, 3, 6, 0, "AUDIO"],
    ]
    return _prepare(
        workflow,
        slug="audio_separation",
        title="音频四轨分离",
        use_case="将对白、音乐和环境声混合音频分离为贝斯、鼓、其他与 vocals 四轨",
        reference_roles=["source_audio"],
        flattened=True,
    )


def _build_transcription() -> dict[str, Any]:
    workflow: dict[str, Any] = {"nodes": [], "links": []}
    audio_node = {
        "id": 1,
        "type": "LoadAudio",
        "pos": [-1050, 0],
        "size": [320, 180],
        "flags": {},
        "order": 0,
        "mode": 0,
        "inputs": [
            {
                "name": "audio",
                "type": "COMBO",
                "widget": {"name": "audio"},
                "link": None,
            }
        ],
        "outputs": [{"name": "AUDIO", "type": "AUDIO", "links": [10]}],
        "properties": {"Node name for S&R": "LoadAudio"},
        "widgets_values": {"audio": "speech.wav"},
        "widgets_values_named": {"audio": "speech.wav"},
    }
    whisper_node = {
        "id": 2,
        "type": "Load Whisper (mtb)",
        "pos": [-1050, 280],
        "size": [320, 160],
        "flags": {},
        "order": 1,
        "mode": 0,
        "inputs": [
            {
                "name": "model_size",
                "type": "COMBO",
                "widget": {"name": "model_size"},
                "link": None,
            },
            {
                "name": "download_missing",
                "type": "BOOLEAN",
                "widget": {"name": "download_missing"},
                "link": None,
            },
        ],
        "outputs": [
            {"name": "pipeline", "type": "WHISPER_PIPELINE", "links": [20]}
        ],
        "properties": {"Node name for S&R": "Load Whisper (mtb)"},
        "widgets_values": {
            "model_size": "tiny",
            "download_missing": True,
        },
        "widgets_values_named": {
            "model_size": "tiny",
            "download_missing": True,
        },
    }
    transcribe_node = {
        "id": 3,
        "type": "Audio To Text (mtb)",
        "pos": [-650, 0],
        "size": [380, 240],
        "flags": {},
        "order": 2,
        "mode": 0,
        "inputs": [
            {"name": "pipeline", "type": "WHISPER_PIPELINE", "link": 20},
            {"name": "audio", "type": "AUDIO", "link": 10},
            {
                "name": "language",
                "type": "COMBO",
                "widget": {"name": "language"},
                "link": None,
            },
            {
                "name": "return_timestamps",
                "type": "BOOLEAN",
                "widget": {"name": "return_timestamps"},
                "link": None,
            },
        ],
        "outputs": [
            {"name": "STRING", "type": "STRING", "links": [30]},
            {
                "name": "WHISPER_OUTPUT",
                "type": "WHISPER_OUTPUT",
                "links": [31],
            },
        ],
        "properties": {"Node name for S&R": "Audio To Text (mtb)"},
        "widgets_values": {"language": "zh", "return_timestamps": True},
        "widgets_values_named": {
            "language": "zh",
            "return_timestamps": True,
        },
    }
    chunks_node = {
        "id": 4,
        "type": "Process Whisper Output (mtb)",
        "pos": [-220, 0],
        "size": [340, 180],
        "flags": {},
        "order": 3,
        "mode": 0,
        "inputs": [
            {
                "name": "whisper_output",
                "type": "WHISPER_OUTPUT",
                "link": 31,
            },
            {
                "name": "min_chunk_length",
                "type": "FLOAT",
                "widget": {"name": "min_chunk_length"},
                "link": None,
            },
        ],
        "outputs": [
            {"name": "STRING", "type": "STRING", "links": [32]},
            {
                "name": "WHISPER_CHUNKS",
                "type": "WHISPER_CHUNKS",
                "links": [33],
            },
        ],
        "properties": {"Node name for S&R": "Process Whisper Output (mtb)"},
        "widgets_values": {"min_chunk_length": 0.0},
        "widgets_values_named": {"min_chunk_length": 0.0},
    }
    json_node = {
        "id": 5,
        "type": "JsonDumpAnyStructureNode",
        "pos": [170, 0],
        "size": [320, 160],
        "flags": {},
        "order": 4,
        "mode": 0,
        "inputs": [
            {"name": "py_obj", "type": "*", "link": 33},
            {
                "name": "indent",
                "type": "INT",
                "widget": {"name": "indent"},
                "link": None,
            },
        ],
        "outputs": [{"name": "STRING", "type": "STRING", "links": [34]}],
        "properties": {"Node name for S&R": "JsonDumpAnyStructureNode"},
        "widgets_values": {"indent": 2},
        "widgets_values_named": {"indent": 2},
    }
    save_node = {
        "id": 6,
        "type": "SaveText",
        "pos": [540, 0],
        "size": [320, 180],
        "flags": {},
        "order": 5,
        "mode": 0,
        "inputs": [
            {"name": "text", "type": "STRING", "link": 34},
            {
                "name": "filename_prefix",
                "type": "STRING",
                "widget": {"name": "filename_prefix"},
                "link": None,
            },
            {
                "name": "format",
                "type": "COMBO",
                "widget": {"name": "format"},
                "link": None,
            },
        ],
        "outputs": [{"name": "text", "type": "STRING", "links": []}],
        "properties": {"Node name for S&R": "SaveText"},
        "widgets_values": {
            "filename_prefix": "transcripts/mivo_subtitle",
            "format": "json",
        },
        "widgets_values_named": {
            "filename_prefix": "transcripts/mivo_subtitle",
            "format": "json",
        },
    }
    workflow["nodes"] = [
        audio_node,
        whisper_node,
        transcribe_node,
        chunks_node,
        json_node,
        save_node,
    ]
    workflow["links"] = [
        [10, 1, 0, 3, 1, "AUDIO"],
        [20, 2, 0, 3, 0, "WHISPER_PIPELINE"],
        [31, 3, 1, 4, 0, "WHISPER_OUTPUT"],
        [33, 4, 1, 5, 0, "WHISPER_CHUNKS"],
        [34, 5, 0, 6, 0, "STRING"],
    ]
    return _prepare(
        workflow,
        slug="audio_transcription",
        title="语音转字幕时间轴",
        use_case="使用本机 Whisper 将音频转换为带起止时间的 JSON 字幕块",
        reference_roles=["source_audio"],
        flattened=True,
    )


def _build_video_matting() -> dict[str, Any]:
    workflow: dict[str, Any] = {"nodes": [], "links": []}
    video_node = _add_load_video(
        workflow,
        node_id=1,
        filename="source.mp4",
        position=[-950, 0],
    )
    remove_background_node = {
        "id": 2,
        "type": "Image Rembg (Remove Background)",
        "pos": [-480, 0],
        "size": [380, 430],
        "flags": {},
        "order": 1,
        "mode": 0,
        "inputs": [
            {"name": "images", "type": "IMAGE", "link": 10},
            {
                "name": "transparency",
                "type": "BOOLEAN",
                "widget": {"name": "transparency"},
                "link": None,
            },
            {
                "name": "model",
                "type": "COMBO",
                "widget": {"name": "model"},
                "link": None,
            },
            {
                "name": "post_processing",
                "type": "BOOLEAN",
                "widget": {"name": "post_processing"},
                "link": None,
            },
            {
                "name": "only_mask",
                "type": "BOOLEAN",
                "widget": {"name": "only_mask"},
                "link": None,
            },
            {
                "name": "alpha_matting",
                "type": "BOOLEAN",
                "widget": {"name": "alpha_matting"},
                "link": None,
            },
            {
                "name": "alpha_matting_foreground_threshold",
                "type": "INT",
                "widget": {"name": "alpha_matting_foreground_threshold"},
                "link": None,
            },
            {
                "name": "alpha_matting_background_threshold",
                "type": "INT",
                "widget": {"name": "alpha_matting_background_threshold"},
                "link": None,
            },
            {
                "name": "alpha_matting_erode_size",
                "type": "INT",
                "widget": {"name": "alpha_matting_erode_size"},
                "link": None,
            },
            {
                "name": "background_color",
                "type": "COMBO",
                "widget": {"name": "background_color"},
                "link": None,
            },
        ],
        "outputs": [{"name": "images", "type": "IMAGE", "links": [20]}],
        "properties": {
            "Node name for S&R": "Image Rembg (Remove Background)"
        },
        "widgets_values": [
            True,
            "isnet-general-use",
            True,
            False,
            True,
            240,
            10,
            10,
            "none",
        ],
    }
    combine_node = {
        "id": 3,
        "type": "VHS_VideoCombine",
        "pos": [20, 0],
        "size": [340, 540],
        "flags": {},
        "order": 2,
        "mode": 0,
        "inputs": [
            {"name": "images", "type": "IMAGE", "link": 20},
            {"name": "audio", "type": "AUDIO", "link": None},
            {
                "name": "meta_batch",
                "type": "VHS_BatchManager",
                "link": None,
            },
            {"name": "vae", "type": "VAE", "link": None},
            {
                "name": "frame_rate",
                "type": "FLOAT",
                "widget": {"name": "frame_rate"},
                "link": 30,
            },
            {
                "name": "loop_count",
                "type": "INT",
                "widget": {"name": "loop_count"},
                "link": None,
            },
            {
                "name": "filename_prefix",
                "type": "STRING",
                "widget": {"name": "filename_prefix"},
                "link": None,
            },
            {
                "name": "format",
                "type": "COMBO",
                "widget": {"name": "format"},
                "link": None,
            },
            {
                "name": "pingpong",
                "type": "BOOLEAN",
                "widget": {"name": "pingpong"},
                "link": None,
            },
            {
                "name": "save_output",
                "type": "BOOLEAN",
                "widget": {"name": "save_output"},
                "link": None,
            },
            {
                "name": "pix_fmt",
                "type": "COMBO",
                "widget": {"name": "pix_fmt"},
                "link": None,
            },
            {
                "name": "crf",
                "type": "INT",
                "widget": {"name": "crf"},
                "link": None,
            },
            {
                "name": "save_metadata",
                "type": "BOOLEAN",
                "widget": {"name": "save_metadata"},
                "link": None,
            },
            {
                "name": "trim_to_audio",
                "type": "BOOLEAN",
                "widget": {"name": "trim_to_audio"},
                "link": None,
            },
        ],
        "outputs": [
            {"name": "Filenames", "type": "VHS_FILENAMES", "links": []}
        ],
        "properties": {"Node name for S&R": "VHS_VideoCombine"},
        "widgets_values": {
            "frame_rate": 24,
            "loop_count": 0,
            "filename_prefix": "mivo_video_matting",
            "format": "video/webm",
            "pix_fmt": "yuva420p",
            "crf": 20,
            "save_metadata": True,
            "trim_to_audio": False,
            "pingpong": False,
            "save_output": True,
        },
        "widgets_values_named": {
            "frame_rate": 24,
            "loop_count": 0,
            "filename_prefix": "mivo_video_matting",
            "format": "video/webm",
            "pix_fmt": "yuva420p",
            "crf": 20,
            "save_metadata": True,
            "trim_to_audio": False,
            "pingpong": False,
            "save_output": True,
        },
    }
    frame_rate_node = {
        "id": 4,
        "type": "VHS_VideoInfoLoaded",
        "pos": [-480, 500],
        "size": [300, 180],
        "flags": {},
        "order": 2,
        "mode": 0,
        "inputs": [
            {
                "name": "video_info",
                "type": "VHS_VIDEOINFO",
                "link": 12,
            }
        ],
        "outputs": [{"name": "fps", "type": "FLOAT", "links": [30]}],
        "properties": {"Node name for S&R": "VHS_VideoInfoLoaded"},
        "widgets_values": [],
    }
    video_node["outputs"][0]["links"] = [10]
    video_node["outputs"][3]["links"] = [12]
    workflow["nodes"] = [
        video_node,
        remove_background_node,
        combine_node,
        frame_rate_node,
    ]
    workflow["links"] = [
        [10, 1, 0, 2, 0, "IMAGE"],
        [20, 2, 0, 3, 0, "IMAGE"],
        [12, 1, 3, 4, 0, "VHS_VIDEOINFO"],
        [30, 4, 0, 3, 4, "FLOAT"],
    ]
    return _prepare(
        workflow,
        slug="video_matting",
        title="视频透明抠像 WebM",
        use_case="逐帧移除背景并输出带 Alpha 的透明 WebM，音轨由媒体处理链路单独管理",
        reference_roles=["source_video"],
        flattened=True,
    )


def _build_extract_frame(
    *,
    index: str,
    slug: str,
    title: str,
    prefix: str,
) -> dict[str, Any]:
    workflow: dict[str, Any] = {"nodes": [], "links": []}
    video_node = _add_load_video(
        workflow,
        node_id=1,
        filename="source.mp4",
        position=[-800, 0],
    )
    select_node = {
        "id": 2,
        "type": "GetImagesFromBatchIndexed",
        "pos": [-360, 0],
        "size": [300, 180],
        "flags": {},
        "order": 1,
        "mode": 0,
        "inputs": [
            {"name": "images", "type": "IMAGE", "link": 10},
            {
                "name": "indexes",
                "type": "STRING",
                "widget": {"name": "indexes"},
                "link": None,
            },
        ],
        "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [20]}],
        "properties": {"Node name for S&R": "GetImagesFromBatchIndexed"},
        "widgets_values": [index],
    }
    save_node = _save_image_node(
        3,
        prefix=prefix,
        position=[80, 0],
        link_id=20,
    )
    _connect(
        image_node=video_node,
        target=select_node,
        field="images",
        link_id=10,
        workflow=workflow,
    )
    _connect(
        image_node=select_node,
        target=save_node,
        field="images",
        link_id=20,
        workflow=workflow,
    )
    workflow["nodes"] = [video_node, select_node, save_node]
    return _prepare(
        workflow,
        slug=slug,
        title=title,
        use_case="从已有视频中抽取关键画面，作为首尾帧、角色资产或下一镜头参考",
        reference_roles=["source_video"],
        flattened=True,
    )


def _load_image_node(
    node_id: int,
    *,
    filename: str,
    position: list[int],
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "LoadImage",
        "pos": position,
        "size": [320, 420],
        "flags": {},
        "order": 0,
        "mode": 0,
        "inputs": [
            {
                "localized_name": "图像",
                "name": "image",
                "type": "COMBO",
                "widget": {"name": "image"},
                "link": None,
            },
            {
                "localized_name": "选择文件上传",
                "name": "upload",
                "type": "IMAGEUPLOAD",
                "widget": {"name": "upload"},
                "link": None,
            },
        ],
        "outputs": [
            {"name": "IMAGE", "type": "IMAGE", "links": []},
            {"name": "MASK", "type": "MASK", "links": []},
        ],
        "properties": {"Node name for S&R": "LoadImage"},
        "widgets_values": [filename, "image"],
    }


def _save_image_node(
    node_id: int,
    *,
    prefix: str,
    position: list[int],
    link_id: int,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "SaveImage",
        "pos": position,
        "size": [300, 360],
        "flags": {},
        "order": 2,
        "mode": 0,
        "inputs": [
            {"name": "images", "type": "IMAGE", "link": link_id},
            {
                "name": "filename_prefix",
                "type": "STRING",
                "widget": {"name": "filename_prefix"},
                "link": None,
            },
        ],
        "outputs": [],
        "properties": {"Node name for S&R": "SaveImage"},
        "widgets_values": [prefix],
    }


def _build_video_multiref(source: dict[str, Any]) -> dict[str, Any]:
    return _build_video_variant(
        source,
        image_capacity=9,
        video_capacity=3,
        audio_capacity=3,
        slug="minimax_h3_video_multiref",
        title="MiniMax H3 多参考生视频",
        use_case="9 图 / 3 视频 / 3 音频：完整多模态参考视频",
    )


def _build_video_variant(
    source: dict[str, Any],
    *,
    image_capacity: int,
    video_capacity: int,
    audio_capacity: int,
    slug: str,
    title: str,
    use_case: str,
) -> dict[str, Any]:
    workflow = copy.deepcopy(source)
    reference_node = _find_node(workflow, "MiniMaxH3ReferenceToVideo")
    workflow = _remove_nodes(
        workflow,
        {
            int(node["id"])
            for node in workflow["nodes"]
            if node.get("type") in {"LoadImage", "VHS_LoadVideo", "LoadAudio"}
        },
    )
    reference_node = _find_node(workflow, "MiniMaxH3ReferenceToVideo")
    for prefix in (
        "ref_images.",
        "ref_videos.",
        "ref_video_audios.",
        "ref_audios.",
    ):
        _clear_prefixed_inputs(workflow, reference_node, prefix)
        _remove_prefixed_inputs(reference_node, prefix)
    next_node = _next_node_id(workflow)
    next_link = _next_link_id(workflow)
    for index in range(image_capacity):
        _add_load_image(
            workflow,
            node_id=next_node + index,
            target_id=str(reference_node["id"]),
            target_field=f"ref_images.ref_image_{index}",
            link_id=next_link + index,
            filename=f"reference_image_{index + 1}.png",
            position=[-2200, 2500 + index * 300],
        )
    next_node += image_capacity
    next_link += image_capacity
    for index in range(video_capacity):
        video_node = _add_load_video(
            workflow,
            node_id=next_node + index,
            filename=f"reference_video_{index + 1}.mp4",
            position=[-2200, 5400 + index * 360],
        )
        video_link = next_link + index * 2
        _connect(
            image_node=video_node,
            target=reference_node,
            field=f"ref_videos.ref_video_{index}",
            link_id=video_link,
            workflow=workflow,
            output_slot=0,
            link_type="IMAGE",
        )
    next_node += video_capacity
    next_link += video_capacity * 2
    for index in range(audio_capacity):
        audio_node = _add_load_audio(
            workflow,
            node_id=next_node + index,
            filename=f"reference_audio_{index + 1}.wav",
            position=[-1700, 6500 + index * 280],
        )
        _connect(
            image_node=audio_node,
            target=reference_node,
            field=f"ref_audios.ref_audio_{index}",
            link_id=next_link + index,
            workflow=workflow,
            output_slot=0,
            link_type="AUDIO",
        )
    _set_prompt(
        workflow,
        "按顺序使用 <Picture 1..9>、<Video 1..3>、<Audio 1..3> 作为参考。"
        "明确说明每张图片、视频和音频分别约束角色、服装、场景、动作、镜头、"
        "声音或整体风格。保持人物身份和空间关系一致，生成连贯自然的动作与声音。",
    )
    return _prepare(
        workflow,
        slug=slug,
        title=title,
        use_case=use_case,
        reference_roles=[
            "character",
            "secondary_character",
            "costume_or_prop",
            "scene_or_style",
            "style_reference",
            "composition_reference",
            "additional_image_1",
            "additional_image_2",
            "additional_image_3",
            "reference_video_1",
            "reference_video_2",
            "reference_video_3",
            "reference_audio_1",
            "reference_audio_2",
            "reference_audio_3",
        ],
        flattened=True,
    )


def _prepare(
    workflow: dict[str, Any],
    *,
    slug: str,
    title: str,
    use_case: str,
    reference_roles: list[str],
    flattened: bool = False,
) -> dict[str, Any]:
    result = _flat(workflow) if flattened else copy.deepcopy(workflow)
    result["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, f"mivo:{slug}"))
    result["extra"] = {
        **(result.get("extra") or {}),
        "zaojing": {
            **STANDARD_METADATA,
            "slug": slug,
            "title": title,
            "useCase": use_case,
            "referenceRoles": reference_roles,
        },
    }
    return result


def _flat(workflow: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    result = _flatten_subgraphs(copy.deepcopy(workflow), warnings)
    result.pop("definitions", None)
    return result


def _flattened(workflow: dict[str, Any]) -> dict[str, Any]:
    return _flat(workflow)


def _find_node(workflow: dict[str, Any], node_type: str) -> dict[str, Any]:
    for node in workflow["nodes"]:
        if node.get("type") == node_type:
            return node
    raise RuntimeError(f"Workflow node not found: {node_type}")


def _remove_nodes(
    workflow: dict[str, Any],
    node_ids: set[int],
) -> dict[str, Any]:
    if not node_ids:
        return workflow
    workflow["nodes"] = [
        node for node in workflow["nodes"] if int(node["id"]) not in node_ids
    ]
    workflow["links"] = [
        link
        for link in workflow["links"]
        if int(link[1]) not in node_ids and int(link[3]) not in node_ids
    ]
    valid_links = {int(link[0]) for link in workflow["links"]}
    for node in workflow["nodes"]:
        for input_spec in node.get("inputs") or []:
            if input_spec.get("link") not in valid_links:
                input_spec["link"] = None
        for output_spec in node.get("outputs") or []:
            if isinstance(output_spec.get("links"), list):
                output_spec["links"] = [
                    link_id
                    for link_id in output_spec["links"]
                    if int(link_id) in valid_links
                ]
    return workflow


def _add_load_image(
    workflow: dict[str, Any],
    *,
    node_id: int,
    target_id: str,
    target_field: str,
    link_id: int,
    filename: str,
    position: list[int],
) -> None:
    image_node = {
        "id": node_id,
        "type": "LoadImage",
        "pos": position,
        "size": [320, 420],
        "flags": {},
        "order": 0,
        "mode": 0,
        "inputs": [
            {
                "localized_name": "图像",
                "name": "image",
                "type": "COMBO",
                "widget": {"name": "image"},
                "link": None,
            },
            {
                "localized_name": "选择文件上传",
                "name": "upload",
                "type": "IMAGEUPLOAD",
                "widget": {"name": "upload"},
                "link": None,
            },
        ],
        "outputs": [
            {
                "localized_name": "图像",
                "name": "IMAGE",
                "type": "IMAGE",
                "links": [],
            },
            {
                "localized_name": "遮罩",
                "name": "MASK",
                "type": "MASK",
                "links": [],
            },
        ],
        "properties": {"Node name for S&R": "LoadImage"},
        "widgets_values": [filename, "image"],
    }
    workflow["nodes"].append(image_node)
    _connect(
        image_node=image_node,
        target=_node_by_id(workflow, target_id),
        field=target_field,
        link_id=link_id,
        workflow=workflow,
    )


def _add_load_video(
    workflow: dict[str, Any],
    *,
    node_id: int,
    filename: str,
    position: list[int],
) -> dict[str, Any]:
    node = {
        "id": node_id,
        "type": "VHS_LoadVideo",
        "pos": position,
        "size": [320, 500],
        "flags": {},
        "order": 0,
        "mode": 0,
        "inputs": [
            {
                "name": "video",
                "type": "COMBO",
                "widget": {"name": "video"},
                "link": None,
            },
            {
                "name": "force_rate",
                "type": "FLOAT",
                "widget": {"name": "force_rate"},
                "link": None,
            },
            {
                "name": "custom_width",
                "type": "INT",
                "widget": {"name": "custom_width"},
                "link": None,
            },
            {
                "name": "custom_height",
                "type": "INT",
                "widget": {"name": "custom_height"},
                "link": None,
            },
            {
                "name": "frame_load_cap",
                "type": "INT",
                "widget": {"name": "frame_load_cap"},
                "link": None,
            },
            {
                "name": "skip_first_frames",
                "type": "INT",
                "widget": {"name": "skip_first_frames"},
                "link": None,
            },
            {
                "name": "select_every_nth",
                "type": "INT",
                "widget": {"name": "select_every_nth"},
                "link": None,
            },
        ],
        "outputs": [
            {"name": "IMAGE", "type": "IMAGE", "links": []},
            {"name": "frame_count", "type": "INT", "links": []},
            {"name": "audio", "type": "AUDIO", "links": []},
            {"name": "video_info", "type": "VHS_VIDEOINFO", "links": []},
        ],
        "properties": {"Node name for S&R": "VHS_LoadVideo"},
        "widgets_values": {
            "video": filename,
            "force_rate": 0,
            "custom_width": 0,
            "custom_height": 0,
            "frame_load_cap": 0,
            "skip_first_frames": 0,
            "select_every_nth": 1,
            "format": "AnimateDiff",
        },
        "widgets_values_named": {
            "video": filename,
            "force_rate": 0,
            "custom_width": 0,
            "custom_height": 0,
            "frame_load_cap": 0,
            "skip_first_frames": 0,
            "select_every_nth": 1,
            "format": "AnimateDiff",
        },
    }
    workflow["nodes"].append(node)
    return node


def _add_load_audio(
    workflow: dict[str, Any],
    *,
    node_id: int,
    filename: str,
    position: list[int],
) -> dict[str, Any]:
    node = {
        "id": node_id,
        "type": "LoadAudio",
        "pos": position,
        "size": [300, 180],
        "flags": {},
        "order": 0,
        "mode": 0,
        "inputs": [
            {
                "name": "audio",
                "type": "COMBO",
                "widget": {"name": "audio"},
                "link": None,
            }
        ],
        "outputs": [
            {"name": "AUDIO", "type": "AUDIO", "links": []},
        ],
        "properties": {"Node name for S&R": "LoadAudio"},
        "widgets_values": [filename],
    }
    workflow["nodes"].append(node)
    return node


def _connect(
    *,
    image_node: dict[str, Any],
    target: dict[str, Any],
    field: str,
    link_id: int,
    workflow: dict[str, Any],
    output_slot: int = 0,
    link_type: str = "IMAGE",
) -> None:
    target_id = str(target["id"])
    target_inputs = target.setdefault("inputs", [])
    target_slot = len(target_inputs)
    input_spec = next(
        (item for item in target_inputs if item.get("name") == field),
        None,
    )
    if input_spec is None:
        input_spec = {
            "localized_name": field,
            "name": field,
            "type": link_type,
            "link": link_id,
        }
        target_inputs.append(input_spec)
    else:
        input_spec["link"] = link_id
        target_slot = target_inputs.index(input_spec)
    workflow.setdefault("links", []).append(
        [
            link_id,
            int(image_node["id"]),
            output_slot,
            target_id,
            target_slot,
            link_type,
        ]
    )
    outputs = image_node.setdefault("outputs", [])
    if output_slot < len(outputs):
        output_links = outputs[output_slot].setdefault("links", [])
        if isinstance(output_links, list):
            output_links.append(link_id)


def _clear_prefixed_inputs(
    workflow: dict[str, Any],
    node: dict[str, Any],
    prefix: str,
) -> None:
    link_ids = {
        int(input_spec["link"])
        for input_spec in node.get("inputs") or []
        if str(input_spec.get("name") or "").startswith(prefix)
        and input_spec.get("link") is not None
    }
    workflow["links"] = [
        link for link in workflow["links"] if int(link[0]) not in link_ids
    ]
    for candidate in workflow["nodes"]:
        for output_spec in candidate.get("outputs") or []:
            if isinstance(output_spec.get("links"), list):
                output_spec["links"] = [
                    link_id
                    for link_id in output_spec["links"]
                    if int(link_id) not in link_ids
                ]


def _remove_prefixed_inputs(node: dict[str, Any], prefix: str) -> None:
    node["inputs"] = [
        input_spec
        for input_spec in node.get("inputs") or []
        if not str(input_spec.get("name") or "").startswith(prefix)
    ]


def _remove_unused_generated_inputs(
    node: dict[str, Any],
    prefix: str,
) -> None:
    for input_spec in node.get("inputs") or []:
        if str(input_spec.get("name") or "").startswith(prefix):
            input_spec["link"] = None


def _set_prompt(workflow: dict[str, Any], prompt: str) -> None:
    candidates = [
        node
        for node in workflow["nodes"]
        if node.get("type")
        in {
            "PrimitiveStringMultiline",
            "StringReplace",
            "MiniMaxH3ReferenceToVideo",
            "MiniMaxH3ImageToVideo",
        }
    ]
    for node in candidates:
        values = node.get("widgets_values")
        if isinstance(values, list) and values and isinstance(values[0], str):
            values[0] = prompt
            return
    raise RuntimeError("No prompt node found")


def _next_link_id(workflow: dict[str, Any]) -> int:
    return max((int(link[0]) for link in workflow.get("links") or []), default=0) + 1


def _next_node_id(workflow: dict[str, Any]) -> int:
    numeric_ids = [
        int(node["id"])
        for node in workflow["nodes"]
        if str(node["id"]).isdigit()
    ]
    return max(numeric_ids, default=0) + 1


def _node_by_id(workflow: dict[str, Any], node_id: int) -> dict[str, Any]:
    for node in workflow["nodes"]:
        if str(node["id"]) == str(node_id):
            return node
    raise RuntimeError(f"Workflow node not found: {node_id}")


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
