import pytest
from fastapi.testclient import TestClient

from app.adapters.comfyui.client import (
    _extract_artifacts,
    _flux_image_graph,
    _wan_video_graph,
)
from app.main import create_app
from app.modules.workflows.converter import (
    _fill_missing_widgets,
    apply_parameter_schema,
    convert_ui_workflow,
    validate_parameter_schema,
)
from app.shared.errors import ProviderConfigurationError
from tests.fakes import FakeCodexClient


def test_flux_graph_uses_prompt_and_requested_size() -> None:
    graph = _flux_image_graph(
        "glass flower",
        {"width": 768, "height": 512, "count": 2, "seed": 7},
    )

    assert graph["4"]["inputs"]["text"] == "glass flower"
    assert graph["7"]["inputs"] == {
        "width": 768,
        "height": 512,
        "batch_size": 2,
    }
    assert graph["8"]["inputs"]["seed"] == 7


def test_wan_graph_normalizes_length_to_four_n_plus_one() -> None:
    graph = _wan_video_graph(
        "neon city",
        {"width": 512, "height": 512, "length": 20, "fps": 12, "seed": 9},
    )

    assert graph["7"]["inputs"]["length"] == 17
    assert graph["8"]["inputs"]["positive"] == ["7", 0]
    assert graph["10"]["class_type"] == "SaveWEBM"


def test_save_text_files_are_valid_workflow_artifacts() -> None:
    artifacts = _extract_artifacts(
        "http://127.0.0.1:8000",
        {
            "outputs": {
                "6": {
                    "text": ['{"text": "hello"}'],
                    "files": [
                        {
                            "filename": "subtitle_00001.json",
                            "subfolder": "transcripts",
                            "type": "output",
                        }
                    ],
                }
            }
        },
    )

    assert artifacts == [
        {
            "url": (
                "http://127.0.0.1:8000/view?"
                "filename=subtitle_00001.json&"
                "subfolder=transcripts&type=output"
            ),
            "filename": "subtitle_00001.json",
            "kind": "file",
            "metadata": {},
        }
    ]


def test_comfyui_models_are_exposed_without_api_key(tmp_path) -> None:
    app = create_app(FakeCodexClient(), database_path=tmp_path / "comfy.db")
    with TestClient(app) as client:
        models = client.get("/api/models").json()

    comfy_models = [model for model in models if model["providerId"] == "comfyui"]
    assert {model["id"] for model in comfy_models} == {
        "comfy-flux-image",
        "comfy-wan-video",
    }
    assert all(model["configured"] for model in comfy_models)


def test_ui_workflow_converts_prompt_size_and_output_bindings() -> None:
    workflow = {
        "nodes": [
            {
                "id": 1,
                "type": "CLIPTextEncode",
                "mode": 0,
                "widgets_values": ["positive prompt"],
                "inputs": [
                    {"name": "clip", "link": 10},
                    {"name": "text", "widget": {"name": "text"}, "link": None},
                ],
            },
            {
                "id": 2,
                "type": "EmptySD3LatentImage",
                "mode": 0,
                "widgets_values": [768, 512, 1],
                "inputs": [
                    {"name": "width", "widget": {"name": "width"}, "link": None},
                    {"name": "height", "widget": {"name": "height"}, "link": None},
                    {
                        "name": "batch_size",
                        "widget": {"name": "batch_size"},
                        "link": None,
                    },
                ],
            },
            {
                "id": 3,
                "type": "KSampler",
                "mode": 0,
                "widgets_values": [7, "randomize", 12, 1, "euler", "normal", 1],
                "inputs": [
                    {"name": "seed", "widget": {"name": "seed"}, "link": None},
                    {"name": "steps", "widget": {"name": "steps"}, "link": None},
                    {"name": "cfg", "widget": {"name": "cfg"}, "link": None},
                    {
                        "name": "sampler_name",
                        "widget": {"name": "sampler_name"},
                        "link": None,
                    },
                    {
                        "name": "scheduler",
                        "widget": {"name": "scheduler"},
                        "link": None,
                    },
                    {
                        "name": "positive",
                        "type": "CONDITIONING",
                        "link": 20,
                    },
                    {
                        "name": "negative",
                        "type": "CONDITIONING",
                        "link": 21,
                    },
                ],
            },
            {
                "id": 4,
                "type": "SaveImage",
                "mode": 0,
                "widgets_values": ["Mivo"],
                "inputs": [
                    {
                        "name": "images",
                        "type": "IMAGE",
                        "link": 30,
                    },
                    {
                        "name": "filename_prefix",
                        "widget": {"name": "filename_prefix"},
                        "link": None,
                    },
                ],
            },
        ],
        "links": [
            [10, 5, 0, 1, 0, "CLIP"],
            [20, 1, 0, 3, 5, "CONDITIONING"],
            [21, 1, 0, 3, 6, "CONDITIONING"],
            [30, 6, 0, 4, 0, "IMAGE"],
        ],
    }

    converted = convert_ui_workflow(workflow, capability="image_generation")

    assert converted.output_node_id == "4"
    assert converted.bindings.prompt == {"nodeId": "1", "field": "text"}
    assert converted.bindings.width == {"nodeId": "2", "field": "width"}
    assert converted.bindings.seed == {"nodeId": "3", "field": "seed"}
    assert converted.api_graph["3"]["inputs"]["positive"] == ["1", 0]


def test_named_widget_values_fill_missing_dynamic_combo() -> None:
    inputs = {
        "video": "source.mp4",
        "force_rate": 0,
        "custom_width": 0,
        "custom_height": 0,
        "frame_load_cap": 0,
        "skip_first_frames": 0,
        "select_every_nth": 1,
    }
    object_info = {
        "VHS_LoadVideo": {
            "input": {
                "required": {
                    name: ["COMBO"]
                    for name in (
                        "video",
                        "force_rate",
                        "custom_width",
                        "custom_height",
                        "frame_load_cap",
                        "skip_first_frames",
                        "select_every_nth",
                    )
                },
                "optional": {"format": [["None", "AnimateDiff"]]},
            },
            "input_order": {
                "required": [
                    "video",
                    "force_rate",
                    "custom_width",
                    "custom_height",
                    "frame_load_cap",
                    "skip_first_frames",
                    "select_every_nth",
                ],
                "optional": ["format"],
            },
        }
    }

    _fill_missing_widgets(
        "VHS_LoadVideo",
        inputs,
        [],
        0,
        object_info,
        named_widgets={"format": "AnimateDiff"},
    )

    assert inputs["format"] == "AnimateDiff"


def test_named_dynamic_sampling_mode_is_filled() -> None:
    inputs = {"max_length": 8192}
    object_info = {
        "TextGenerateV2": {
            "input": {
                "required": {
                    "max_length": ["INT"],
                    "sampling_mode": ["COMFY_DYNAMICCOMBO_V3"],
                },
                "optional": {},
            },
            "input_order": {
                "required": ["max_length", "sampling_mode"],
                "optional": [],
            },
        }
    }

    _fill_missing_widgets(
        "TextGenerateV2",
        inputs,
        [],
        0,
        object_info,
        named_widgets={"sampling_mode": "on"},
    )

    assert inputs["sampling_mode"] == "on"


def test_parameter_schema_assigns_assets_and_defaults() -> None:
    graph = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": "old.png"},
        },
        "2": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
        },
    }
    schema = [
        {
            "key": "width",
            "label": "宽度",
            "type": "integer",
            "required": True,
            "default": 768,
            "bindings": [{"nodeId": "2", "field": "width"}],
        },
        {
            "key": "assets",
            "label": "参考图",
            "type": "assets",
            "required": True,
            "min": 1,
            "max": 2,
            "bindings": [{"assetIndex": 0, "nodeId": "1", "field": "image"}],
        },
    ]

    compiled = apply_parameter_schema(
        graph,
        schema,
        values={"prompt": "test"},
        uploaded_assets=["first.png"],
    )

    assert compiled["1"]["inputs"]["image"] == "first.png"
    assert compiled["2"]["inputs"]["width"] == 768

    with pytest.raises(ProviderConfigurationError):
        apply_parameter_schema(
            graph,
            schema,
            values={"prompt": "test"},
            uploaded_assets=[],
        )


def test_dynamic_reference_workflow_prunes_unused_capacity_slots() -> None:
    graph = {
        "10": {
            "class_type": "MiniMaxH3ImageConditioning",
            "inputs": {
                "images.image_0": ["1", 0],
                "images.image_1": ["2", 0],
                "images.image_2": ["3", 0],
            },
        },
        "1": {"class_type": "LoadImage", "inputs": {"image": "one.png"}},
        "2": {"class_type": "LoadImage", "inputs": {"image": "two.png"}},
        "3": {"class_type": "LoadImage", "inputs": {"image": "three.png"}},
        "20": {
            "class_type": "SaveImage",
            "inputs": {"images": ["10", 0], "filename_prefix": "Mivo"},
        },
    }
    schema = [
        {
            "key": "assets",
            "label": "参考图片",
            "type": "assets",
            "assetType": "image",
            "required": False,
            "min": 0,
            "max": 3,
            "bindings": [
                {"assetIndex": 0, "nodeId": "1", "field": "image"},
                {"assetIndex": 1, "nodeId": "2", "field": "image"},
                {"assetIndex": 2, "nodeId": "3", "field": "image"},
            ],
        }
    ]

    compiled = apply_parameter_schema(
        graph,
        schema,
        values={"prompt": "test"},
        uploaded_assets=["first.png", "second.png"],
    )

    assert compiled["1"]["inputs"]["image"] == "first.png"
    assert compiled["2"]["inputs"]["image"] == "second.png"
    assert "3" not in compiled
    assert "images.image_2" not in compiled["10"]["inputs"]


def test_multimodal_reference_video_exposes_optional_media_groups() -> None:
    workflow = {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "mode": 0,
                "widgets_values": ["image.png"],
                "inputs": [
                    {
                        "name": "image",
                        "type": "COMBO",
                        "widget": {"name": "image"},
                        "link": None,
                    }
                ],
            },
            {
                "id": 2,
                "type": "VHS_LoadVideo",
                "mode": 0,
                "widgets_values": ["video.mp4", 24, 0, 0, 360, 0, 1],
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
                    {"name": "IMAGE", "type": "IMAGE"},
                    {"name": "frame_count", "type": "INT"},
                    {"name": "audio", "type": "AUDIO"},
                ],
            },
            {
                "id": 3,
                "type": "LoadAudio",
                "mode": 0,
                "widgets_values": ["audio.wav"],
                "inputs": [
                    {
                        "name": "audio",
                        "type": "COMBO",
                        "widget": {"name": "audio"},
                        "link": None,
                    }
                ],
            },
            {
                "id": 10,
                "type": "MiniMaxH3ReferenceToVideo",
                "mode": 0,
                "widgets_values": ["prompt", 864, 480, 124, "match"],
                "inputs": [
                    {
                        "name": "prompt",
                        "type": "STRING",
                        "widget": {"name": "prompt"},
                        "link": None,
                    },
                    {
                        "name": "width",
                        "type": "INT",
                        "widget": {"name": "width"},
                        "link": None,
                    },
                    {
                        "name": "height",
                        "type": "INT",
                        "widget": {"name": "height"},
                        "link": None,
                    },
                    {
                        "name": "length",
                        "type": "INT",
                        "widget": {"name": "length"},
                        "link": None,
                    },
                    {
                        "name": "ref_image_size",
                        "type": "COMBO",
                        "widget": {"name": "ref_image_size"},
                        "link": None,
                    },
                    {
                        "name": "ref_images.ref_image_0",
                        "type": "IMAGE",
                        "link": 11,
                    },
                    {
                        "name": "ref_videos.ref_video_0",
                        "type": "IMAGE",
                        "link": 12,
                    },
                    {
                        "name": "ref_video_audios.ref_video_audio_0",
                        "type": "AUDIO",
                        "link": 13,
                    },
                    {
                        "name": "ref_audios.ref_audio_0",
                        "type": "AUDIO",
                        "link": 14,
                    },
                ],
                "outputs": [{"name": "positive", "type": "CONDITIONING"}],
            },
            {
                "id": 20,
                "type": "SaveVideo",
                "mode": 0,
                "widgets_values": ["video/Mivo"],
                "inputs": [
                    {"name": "video", "type": "VIDEO", "link": 21},
                    {
                        "name": "filename_prefix",
                        "type": "STRING",
                        "widget": {"name": "filename_prefix"},
                        "link": None,
                    },
                ],
            },
        ],
        "links": [
            [11, 1, 0, 10, 5, "IMAGE"],
            [12, 2, 0, 10, 6, "IMAGE"],
            [13, 2, 2, 10, 7, "AUDIO"],
            [14, 3, 0, 10, 8, "AUDIO"],
            [21, 10, 0, 20, 0, "VIDEO"],
        ],
    }

    converted = convert_ui_workflow(
        workflow,
        capability="video_generation",
    )
    asset_parameters = {
        parameter["assetType"]: parameter
        for parameter in converted.parameter_schema
        if parameter["type"] == "assets"
    }

    assert set(asset_parameters) == {"image", "video", "audio"}
    assert all(
        parameter["required"] is False
        and parameter["min"] == 0
        and parameter["max"] == 1
        for parameter in asset_parameters.values()
    )
    compiled = apply_parameter_schema(
        converted.api_graph,
        list(converted.parameter_schema),
        values={"prompt": "test"},
        uploaded_assets_by_parameter={
            "assets": ["image.png"],
            "videos": [],
            "audios": [],
        },
    )
    assert "2" not in compiled
    assert "3" not in compiled
    assert "ref_videos.ref_video_0" not in compiled["10"]["inputs"]
    assert "ref_audios.ref_audio_0" not in compiled["10"]["inputs"]
    assert compiled["10"]["inputs"]["ref_images.ref_image_0"] == ["1", 0]

    with pytest.raises(ProviderConfigurationError):
        apply_parameter_schema(
            converted.api_graph,
            list(converted.parameter_schema),
            values={"prompt": "test"},
            uploaded_assets_by_parameter={
                "assets": [],
                "videos": [],
                "audios": [],
            },
        )


def test_ui_workflow_detects_custom_text_encoder_from_object_info() -> None:
    workflow = {
        "nodes": [
            {
                "id": 1,
                "type": "CommunityWanPromptEncoder",
                "mode": 0,
                "widgets_values": ["positive prompt", "negative prompt"],
                "inputs": [
                    {"name": "t5", "link": 10},
                    {
                        "name": "positive_prompt",
                        "widget": {"name": "positive_prompt"},
                        "link": None,
                    },
                    {
                        "name": "negative_prompt",
                        "widget": {"name": "negative_prompt"},
                        "link": None,
                    },
                ],
            },
            {
                "id": 2,
                "type": "CommunityVideoSampler",
                "mode": 0,
                "widgets_values": [7],
                "inputs": [
                    {
                        "name": "text_embeds",
                        "type": "WANVIDEOTEXTEMBEDS",
                        "link": 20,
                    },
                    {
                        "name": "seed",
                        "widget": {"name": "seed"},
                        "link": None,
                    },
                ],
            },
            {
                "id": 3,
                "type": "SaveWEBM",
                "mode": 0,
                "widgets_values": ["Mivo"],
                "inputs": [
                    {"name": "images", "type": "IMAGE", "link": 30},
                    {
                        "name": "filename_prefix",
                        "widget": {"name": "filename_prefix"},
                        "link": None,
                    },
                ],
            },
        ],
        "links": [
            [10, 4, 0, 1, 0, "WANTEXTENCODER"],
            [20, 1, 0, 2, 0, "WANVIDEOTEXTEMBEDS"],
            [30, 5, 0, 3, 0, "VIDEO"],
        ],
    }
    object_info = {
        "CommunityWanPromptEncoder": {
            "input_order": {
                "required": ["positive_prompt", "negative_prompt"],
                "optional": ["t5"],
            },
            "output": ["WANVIDEOTEXTEMBEDS"],
        },
        "CommunityVideoSampler": {
            "input_order": {"required": ["text_embeds", "seed"]},
            "output": ["LATENT"],
        },
    }

    converted = convert_ui_workflow(
        workflow,
        capability="video_generation",
        object_info=object_info,
    )

    assert converted.bindings.prompt == {
        "nodeId": "1",
        "field": "positive_prompt",
    }
    assert converted.bindings.negative_prompt == {
        "nodeId": "1",
        "field": "negative_prompt",
    }
    assert converted.parameter_schema[0]["bindings"] == [
        {"nodeId": "1", "field": "positive_prompt"}
    ]


def test_ui_workflow_expands_subgraph_and_exposes_manual_inputs() -> None:
    subgraph_id = "4f5f960b-subgraph"
    workflow = {
        "nodes": [
            {
                "id": 10,
                "type": subgraph_id,
                "mode": 0,
                "widgets_values": ["hello from user", 42],
                "widgets_values_named": {
                    "prompt": "hello from user",
                    "seed": 42,
                },
                "inputs": [
                    {
                        "name": "prompt",
                        "widget": {"name": "prompt"},
                        "link": None,
                    },
                    {
                        "name": "seed",
                        "widget": {"name": "seed"},
                        "link": None,
                    },
                ],
                "outputs": [{"name": "IMAGE", "type": "IMAGE"}],
            },
            {
                "id": 20,
                "type": "SaveImage",
                "mode": 0,
                "widgets_values": ["Mivo"],
                "inputs": [
                    {"name": "images", "link": 100},
                    {
                        "name": "filename_prefix",
                        "widget": {"name": "filename_prefix"},
                        "link": None,
                    },
                ],
            },
        ],
        "links": [[100, 10, 0, 20, 0, "IMAGE"]],
        "definitions": {
            "subgraphs": [
                {
                    "id": subgraph_id,
                    "inputNode": {"id": -10},
                    "outputNode": {"id": -20},
                    "inputs": [
                        {"name": "prompt", "linkIds": [5]},
                        {"name": "seed", "linkIds": [6]},
                    ],
                    "outputs": [{"name": "IMAGE", "linkIds": [9]}],
                    "nodes": [
                        {
                            "id": 1,
                            "type": "PrimitiveStringMultiline",
                            "mode": 0,
                            "title": "Text (user_prompt)",
                            "widgets_values": [""],
                            "inputs": [
                                {
                                    "name": "value",
                                    "widget": {"name": "value"},
                                    "link": 5,
                                }
                            ],
                        },
                        {
                            "id": 2,
                            "type": "CLIPTextEncode",
                            "mode": 0,
                            "widgets_values": ["initial"],
                            "inputs": [
                                {
                                    "name": "text",
                                    "widget": {"name": "text"},
                                    "link": 7,
                                }
                            ],
                        },
                        {
                            "id": 3,
                            "type": "KSampler",
                            "mode": 0,
                            "widgets_values": [1],
                            "inputs": [
                                {"name": "positive", "link": 8},
                                {
                                    "name": "seed",
                                    "widget": {"name": "seed"},
                                    "link": 6,
                                },
                            ],
                        },
                    ],
                    "links": [
                        {
                            "id": 5,
                            "origin_id": -10,
                            "origin_slot": 0,
                            "target_id": 1,
                            "target_slot": 0,
                            "type": "STRING",
                        },
                        {
                            "id": 6,
                            "origin_id": -10,
                            "origin_slot": 1,
                            "target_id": 3,
                            "target_slot": 1,
                            "type": "INT",
                        },
                        {
                            "id": 7,
                            "origin_id": 1,
                            "origin_slot": 0,
                            "target_id": 2,
                            "target_slot": 0,
                            "type": "STRING",
                        },
                        {
                            "id": 8,
                            "origin_id": 2,
                            "origin_slot": 0,
                            "target_id": 3,
                            "target_slot": 0,
                            "type": "CONDITIONING",
                        },
                        {
                            "id": 9,
                            "origin_id": 3,
                            "origin_slot": 0,
                            "target_id": -20,
                            "target_slot": 0,
                            "type": "LATENT",
                        },
                    ],
                }
            ]
        },
    }
    object_info = {
        "PrimitiveStringMultiline": {
            "input_order": {"required": ["value"]},
            "input": {"required": {"value": ["STRING"]}},
        },
        "CLIPTextEncode": {
            "input_order": {"required": ["text"]},
            "input": {"required": {"text": ["STRING"]}},
        },
        "KSampler": {
            "input_order": {"required": ["positive", "seed"]},
            "input": {
                "required": {
                    "positive": ["CONDITIONING"],
                    "seed": ["INT"],
                }
            },
        },
    }

    converted = convert_ui_workflow(
        workflow,
        capability="image_generation",
        object_info=object_info,
    )

    assert converted.output_node_id == "20"
    assert converted.api_graph["20"]["inputs"]["images"] == ["10:3", 0]
    assert converted.api_graph["10:1"]["inputs"]["value"] == "hello from user"
    assert converted.api_graph["10:3"]["inputs"]["seed"] == 42
    assert converted.bindings.prompt == {"nodeId": "10:2", "field": "text"}
    assert any(
        item["nodeId"] == "10"
        and item["field"] == "prompt"
        and item["default"] == "hello from user"
        and item["bindings"]
        == [{"nodeId": "10:1", "field": "value"}]
        for item in converted.input_catalog
    )
    assert any(
        node["id"] == "10" for node in converted.topology["nodes"]
    )
    assert any(
        link["originId"] == "10" and link["targetId"] == "20"
        for link in converted.topology["links"]
    )


def test_user_parameter_bindings_are_validated_generically() -> None:
    graph = {
        "1": {
            "class_type": "PrimitiveStringMultiline",
            "inputs": {"value": ""},
        }
    }
    parameters = [
        {
            "key": "custom_prompt",
            "label": "自定义提示词",
            "type": "string",
            "required": True,
            "bindings": [{"nodeId": "1", "field": "value"}],
        }
    ]

    validate_parameter_schema(graph, parameters)

    with pytest.raises(ProviderConfigurationError):
        validate_parameter_schema(
            graph,
            [
                {
                    **parameters[0],
                    "bindings": [{"nodeId": "missing", "field": "value"}],
                }
            ],
        )


def test_workflow_supports_separate_image_video_and_audio_references() -> None:
    workflow = {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "mode": 0,
                "widgets_values": ["start.png"],
                "inputs": [
                    {
                        "name": "image",
                        "widget": {"name": "image"},
                        "link": None,
                    }
                ],
            },
            {
                "id": 2,
                "type": "VHS_LoadVideo",
                "mode": 0,
                "widgets_values": ["motion.mp4"],
                "inputs": [
                    {
                        "name": "video",
                        "widget": {"name": "video"},
                        "link": None,
                    }
                ],
            },
            {
                "id": 3,
                "type": "VHS_LoadAudio",
                "mode": 0,
                "widgets_values": ["voice.wav"],
                "inputs": [
                    {
                        "name": "audio_file",
                        "widget": {"name": "audio_file"},
                        "link": None,
                    }
                ],
            },
            {
                "id": 4,
                "type": "SaveImage",
                "mode": 0,
                "widgets_values": ["Mivo"],
                "inputs": [
                    {"name": "images", "link": None},
                    {
                        "name": "filename_prefix",
                        "widget": {"name": "filename_prefix"},
                        "link": None,
                    },
                ],
            },
        ],
        "links": [],
    }

    converted = convert_ui_workflow(
        workflow,
        capability="image_generation",
    )
    parameters = {
        parameter["key"]: parameter
        for parameter in converted.parameter_schema
        if parameter["type"] == "assets"
    }

    assert parameters["assets"]["assetType"] == "image"
    assert parameters["videos"]["assetType"] == "video"
    assert parameters["audios"]["assetType"] == "audio"
    compiled = apply_parameter_schema(
        converted.api_graph,
        list(converted.parameter_schema),
        values={"prompt": "test"},
        uploaded_assets_by_parameter={
            "assets": ["uploaded-start.png"],
            "videos": ["uploaded-motion.mp4"],
            "audios": ["uploaded-voice.wav"],
        },
    )
    assert compiled["1"]["inputs"]["image"] == "uploaded-start.png"
    assert compiled["2"]["inputs"]["video"] == "uploaded-motion.mp4"
    assert compiled["3"]["inputs"]["audio_file"] == "uploaded-voice.wav"


def test_upload_widget_is_ignored_and_last_save_video_is_selected() -> None:
    workflow = {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "mode": 0,
                "widgets_values": ["start.png", "image"],
                "inputs": [
                    {
                        "name": "image",
                        "type": "COMBO",
                        "widget": {"name": "image"},
                        "link": None,
                    },
                    {
                        "name": "upload",
                        "type": "IMAGEUPLOAD",
                        "widget": {"name": "upload"},
                        "link": None,
                    },
                ],
            },
            {
                "id": 2,
                "type": "SaveVideo",
                "mode": 0,
                "widgets_values": ["video/part", "auto", "auto", "auto"],
                "inputs": [
                    {"name": "video", "link": None},
                    {
                        "name": "filename_prefix",
                        "widget": {"name": "filename_prefix"},
                        "link": None,
                    },
                ],
            },
            {
                "id": 3,
                "type": "SaveVideo",
                "mode": 0,
                "widgets_values": ["video/final", "auto", "auto", "auto"],
                "inputs": [
                    {"name": "video", "link": None},
                    {
                        "name": "filename_prefix",
                        "widget": {"name": "filename_prefix"},
                        "link": None,
                    },
                ],
            },
        ],
        "links": [],
    }

    converted = convert_ui_workflow(
        workflow,
        capability="video_generation",
    )
    assets = next(
        parameter
        for parameter in converted.parameter_schema
        if parameter["type"] == "assets"
    )

    assert converted.output_node_id == "3"
    assert assets["bindings"] == [
        {"assetIndex": 0, "nodeId": "1", "field": "image"}
    ]


def test_semantic_aliases_map_prompt_and_resolution_values() -> None:
    graph = {
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}},
        "2": {
            "class_type": "PrimitiveString",
            "inputs": {"replace": ""},
        },
        "3": {
            "class_type": "ResolutionSelector",
            "inputs": {"megapixels": 4.0},
        },
    }
    schema = [
        {
            "key": "prompt",
            "label": "提示词",
            "type": "string",
            "required": True,
            "semanticKey": "prompt",
            "bindings": [{"nodeId": "1", "field": "text"}],
        },
        {
            "key": "replace",
            "label": "Image prompt alias",
            "type": "string",
            "required": True,
            "semanticKey": "prompt",
            "bindings": [{"nodeId": "2", "field": "replace"}],
        },
        {
            "key": "megapixels",
            "label": "分辨率",
            "type": "number",
            "required": True,
            "semanticKey": "resolution",
            "bindings": [{"nodeId": "3", "field": "megapixels"}],
        },
    ]

    compiled = apply_parameter_schema(
        graph,
        schema,
        values={"prompt": "same prompt", "resolution": "2K"},
    )

    assert compiled["1"]["inputs"]["text"] == "same prompt"
    assert compiled["2"]["inputs"]["replace"] == "same prompt"
    assert compiled["3"]["inputs"]["megapixels"] == 4.0


def test_linked_widgets_advance_widget_values_without_parameter_shift() -> None:
    workflow = {
        "nodes": [
            {
                "id": 20,
                "type": "KSampler",
                "mode": 0,
                "widgets_values": [
                    42,
                    "randomize",
                    6,
                    1,
                    "euler",
                    "simple",
                    1,
                ],
                "inputs": [
                    {"name": "model", "link": 1},
                    {"name": "positive", "link": 2},
                    {"name": "negative", "link": 3},
                    {"name": "latent_image", "link": 4},
                    {
                        "name": "seed",
                        "widget": {"name": "seed"},
                        "link": 5,
                    },
                    {
                        "name": "steps",
                        "widget": {"name": "steps"},
                        "link": None,
                    },
                    {
                        "name": "cfg",
                        "widget": {"name": "cfg"},
                        "link": None,
                    },
                    {
                        "name": "sampler_name",
                        "widget": {"name": "sampler_name"},
                        "link": 6,
                    },
                    {
                        "name": "scheduler",
                        "widget": {"name": "scheduler"},
                        "link": 7,
                    },
                    {
                        "name": "denoise",
                        "widget": {"name": "denoise"},
                        "link": None,
                    },
                ],
            },
            {
                "id": 21,
                "type": "SaveImage",
                "mode": 0,
                "widgets_values": ["Mivo"],
                "inputs": [
                    {"name": "images", "link": None},
                    {
                        "name": "filename_prefix",
                        "widget": {"name": "filename_prefix"},
                        "link": None,
                    },
                ],
            },
        ],
        "links": [
            [1, 10, 0, 20, 0, "MODEL"],
            [2, 11, 0, 20, 1, "CONDITIONING"],
            [3, 12, 0, 20, 2, "CONDITIONING"],
            [4, 13, 0, 20, 3, "LATENT"],
            [5, 14, 0, 20, 4, "INT"],
            [6, 15, 0, 20, 7, "COMBO"],
            [7, 16, 0, 20, 8, "COMBO"],
        ],
    }
    object_info = {
        "KSampler": {
            "input_order": {
                "required": [
                    "model",
                    "seed",
                    "steps",
                    "cfg",
                    "sampler_name",
                    "scheduler",
                    "positive",
                    "negative",
                    "latent_image",
                    "denoise",
                ]
            }
        }
    }

    converted = convert_ui_workflow(
        workflow,
        capability="image_generation",
        object_info=object_info,
    )
    sampler = converted.api_graph["20"]["inputs"]

    assert sampler["seed"] == ["14", 0]
    assert sampler["steps"] == 6
    assert sampler["cfg"] == 1
    assert sampler["sampler_name"] == ["15", 0]
    assert sampler["scheduler"] == ["16", 0]
    assert sampler["denoise"] == 1


def test_linked_scalar_outputs_are_not_exposed_as_required_parameters() -> None:
    workflow = {
        "nodes": [
            {
                "id": 1,
                "type": "PrimitiveInt",
                "mode": 0,
                "widgets_values": [49],
                "inputs": [
                    {
                        "name": "value",
                        "widget": {"name": "value"},
                        "link": None,
                    }
                ],
            },
            {
                "id": 2,
                "type": "MiniMaxH3ImageToVideo",
                "mode": 0,
                "widgets_values": ["", 768, 1024],
                "inputs": [
                    {
                        "name": "prompt",
                        "widget": {"name": "prompt"},
                        "link": None,
                    },
                    {
                        "name": "width",
                        "widget": {"name": "width"},
                        "link": None,
                    },
                    {
                        "name": "height",
                        "widget": {"name": "height"},
                        "link": None,
                    },
                    {
                        "name": "length",
                        "widget": {"name": "length"},
                        "link": 10,
                    },
                ],
            },
            {
                "id": 3,
                "type": "SaveVideo",
                "mode": 0,
                "widgets_values": ["video/Mivo"],
                "inputs": [
                    {"name": "video", "link": None},
                    {
                        "name": "filename_prefix",
                        "widget": {"name": "filename_prefix"},
                        "link": None,
                    },
                ],
            },
        ],
        "links": [[10, 1, 0, 2, 3, "INT"]],
    }

    converted = convert_ui_workflow(
        workflow,
        capability="video_generation",
        object_info={
            "MiniMaxH3ImageToVideo": {
                "input_order": {
                    "required": ["prompt", "width", "height", "length"]
                }
            }
        },
    )

    assert converted.bindings.length is None
    assert not any(
        parameter.get("semanticKey") == "length"
        for parameter in converted.parameter_schema
    )


def test_easy_pixels_uses_public_output_dimensions() -> None:
    graph = {
        "1": {
            "class_type": "easy pixels",
            "inputs": {
                "resolution": "2560 x 1440",
                "width": 512,
                "height": 512,
                "scale": 2,
                "flip_w/h": False,
            },
        },
        "2": {
            "class_type": "MiniMaxH3ImageToVideo",
            "inputs": {
                "width": ["1", 2],
                "height": ["1", 3],
            },
        },
    }
    schema = [
        {
            "key": "width",
            "label": "宽度",
            "type": "integer",
            "semanticKey": "width",
            "bindings": [{"nodeId": "1", "field": "width"}],
        },
        {
            "key": "height",
            "label": "高度",
            "type": "integer",
            "semanticKey": "height",
            "bindings": [{"nodeId": "1", "field": "height"}],
        },
    ]

    compiled = apply_parameter_schema(
        graph,
        schema,
        values={"width": 768, "height": 1024},
    )

    assert compiled["1"]["inputs"]["resolution"] == "width x height (custom)"
    assert compiled["1"]["inputs"]["width"] == 768
    assert compiled["1"]["inputs"]["height"] == 1024
    assert compiled["1"]["inputs"]["scale"] == 1
    assert compiled["2"]["inputs"]["width"] == ["1", 0]
    assert compiled["2"]["inputs"]["height"] == ["1", 1]


def test_resolution_selector_exposes_ratio_and_resolution() -> None:
    workflow = {
        "nodes": [
            {
                "id": 1,
                "type": "ResolutionSelector",
                "mode": 0,
                "widgets_values": ["3:4 (Portrait)", 4, 32],
                "inputs": [
                    {
                        "name": "aspect_ratio",
                        "type": "COMBO",
                        "widget": {"name": "aspect_ratio"},
                        "link": None,
                    },
                    {
                        "name": "megapixels",
                        "type": "FLOAT",
                        "widget": {"name": "megapixels"},
                        "link": None,
                    },
                    {
                        "name": "multiple",
                        "type": "INT",
                        "widget": {"name": "multiple"},
                        "link": None,
                    },
                ],
            },
            {
                "id": 2,
                "type": "SaveImage",
                "mode": 0,
                "widgets_values": ["Mivo"],
                "inputs": [
                    {"name": "images", "type": "IMAGE", "link": None},
                    {
                        "name": "filename_prefix",
                        "type": "STRING",
                        "widget": {"name": "filename_prefix"},
                        "link": None,
                    },
                ],
            },
        ],
        "links": [],
    }

    converted = convert_ui_workflow(
        workflow,
        capability="image_generation",
        object_info={
            "ResolutionSelector": {
                "input": {
                    "required": {
                        "aspect_ratio": [
                            ["1:1 (Square)", "3:4 (Portrait)", "16:9 (Widescreen)"]
                        ]
                    }
                }
            }
        },
    )
    parameters = {
        parameter["semanticKey"]: parameter
        for parameter in converted.parameter_schema
    }

    assert parameters["aspectRatio"]["bindings"] == [
        {"nodeId": "1", "field": "aspect_ratio"}
    ]
    assert parameters["aspectRatio"]["options"] == [
        "1:1 (Square)",
        "3:4 (Portrait)",
        "16:9 (Widescreen)",
    ]
    assert parameters["resolution"]["bindings"] == [
        {"nodeId": "1", "field": "megapixels"}
    ]

    compiled = apply_parameter_schema(
        converted.api_graph,
        list(converted.parameter_schema),
        values={"aspectRatio": "3:4", "resolution": "2K"},
    )
    assert compiled["1"]["inputs"]["aspect_ratio"] == "3:4 (Portrait)"
    assert compiled["1"]["inputs"]["megapixels"] == 4.0

    fallback_schema = []
    for parameter in converted.parameter_schema:
        copied = dict(parameter)
        if copied.get("semanticKey") == "aspectRatio":
            copied.pop("options", None)
        fallback_schema.append(copied)
    fallback_compiled = apply_parameter_schema(
        converted.api_graph,
        fallback_schema,
        values={"aspectRatio": "9:16", "resolution": "2K"},
    )
    assert (
        fallback_compiled["1"]["inputs"]["aspect_ratio"]
        == "9:16 (Portrait Widescreen)"
    )
