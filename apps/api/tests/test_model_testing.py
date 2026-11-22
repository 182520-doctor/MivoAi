from fastapi.testclient import TestClient

from app.contexts.media_generation.schemas import GenerationCreate
from app.contexts.providers.application import _public_workflow_inputs
from app.main import create_app
from app.shared.semantic_parameters import dimensions_for_resolution
from tests.fakes import FakeCodexClient


def test_image_processing_is_a_valid_media_task_type() -> None:
    command = GenerationCreate(
        providerId="comfyui",
        modelId="image-upscale",
        taskType="image_processing",
        prompt="",
        images=["asset-source"],
    ).to_command()

    assert command.task_type == "image_processing"
    assert command.reference_asset_ids["image"] == ["asset-source"]


def test_local_text_model_can_be_tested(tmp_path) -> None:
    app = create_app(FakeCodexClient(), database_path=tmp_path / "models.db")
    with TestClient(app) as client:
        response = client.post(
            "/api/models/codex-local-default/test",
            json={
                "providerId": "codex_local",
                "prompt": "只回复：模型连接正常",
            },
        )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["providerId"] == "codex_local"
    assert result["modelId"] == "codex-local-default"
    assert "已运行" in result["message"]


def test_model_test_returns_actionable_failure(tmp_path) -> None:
    app = create_app(FakeCodexClient(), database_path=tmp_path / "models.db")
    with TestClient(app) as client:
        response = client.post(
            "/api/models/missing-model/test",
            json={
                "providerId": "missing-provider",
                "prompt": "只回复：模型连接正常",
            },
        )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is False
    assert result["modelId"] == "missing-model"


def test_public_model_contract_hides_workflow_node_bindings() -> None:
    parameters, references = _public_workflow_inputs(
        [
            {
                "key": "prompt",
                "label": "提示词",
                "type": "string",
                "required": True,
                "bindings": [{"nodeId": "12", "field": "text"}],
            },
            {
                "key": "replace",
                "label": "Image prompt",
                "type": "string",
                "required": True,
                "bindings": [{"nodeId": "13", "field": "replace"}],
            },
            {
                "key": "aspect_ratio",
                "label": "宽高比",
                "type": "string",
                "required": True,
                "bindings": [{"nodeId": "14", "field": "aspect_ratio"}],
            },
            {
                "key": "megapixels",
                "label": "像素",
                "type": "number",
                "required": True,
                "default": 4,
                "bindings": [{"nodeId": "14", "field": "megapixels"}],
            },
            {
                "key": "width",
                "label": "宽度",
                "type": "integer",
                "bindings": [{"nodeId": "15", "field": "width"}],
            },
            {
                "key": "height",
                "label": "高度",
                "type": "integer",
                "bindings": [{"nodeId": "15", "field": "height"}],
            },
            {
                "key": "assets",
                "type": "assets",
                "assetType": "image",
                "required": True,
                "min": 2,
                "max": 3,
                "bindings": [
                    {"nodeId": "20", "field": "image"},
                    {"nodeId": "21", "field": "image"},
                ],
            },
        ]
    )

    assert parameters == [
        {
            "key": "prompt",
            "label": "提示词",
            "type": "string",
            "required": True,
            "semanticKey": "prompt",
        },
        {
            "key": "aspectRatio",
            "label": "画面比例",
            "type": "string",
            "required": True,
            "semanticKey": "aspectRatio",
            "default": "1:1",
            "options": ["1:1", "4:3", "3:2", "16:9", "21:9", "3:4", "2:3", "9:16"],
        },
        {
            "key": "resolution",
            "label": "分辨率（1K / 2K / 4K）",
            "type": "string",
            "required": True,
            "default": "2K",
            "semanticKey": "resolution",
            "options": ["1K", "2K", "4K"],
        },
        {
            "key": "width",
            "label": "宽度",
            "type": "integer",
            "semanticKey": "width",
            "derived": True,
        },
        {
            "key": "height",
            "label": "高度",
            "type": "integer",
            "semanticKey": "height",
            "derived": True,
        }
    ]
    assert references == [
        {
            "type": "image",
            "label": "参考图片",
            "required": True,
            "min": 2,
            "max": 3,
        }
    ]


def test_generation_accepts_provider_neutral_reference_arrays() -> None:
    command = GenerationCreate(
        providerId="comfyui",
        modelId="comfy-workflow",
        taskType="image_generation",
        prompt="use these references",
        images=["image-1", "image-2", "image-3"],
        videos=["video-1"],
        audios=["audio-1"],
        parameters={"aspectRatio": "16:9"},
    ).to_command()

    assert command.reference_asset_ids == {
        "image": ["image-1", "image-2", "image-3"],
        "video": ["video-1"],
        "audio": ["audio-1"],
        "file": [],
    }
    assert "nodeId" not in command.parameters


def test_resolution_tier_resolves_to_workflow_dimensions() -> None:
    assert dimensions_for_resolution("2K", "16:9") == (2752, 1536)
    assert dimensions_for_resolution("1K", "1:1") == (1024, 1024)
