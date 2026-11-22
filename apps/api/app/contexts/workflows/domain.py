"""Workflow catalog values and persisted workflow records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class WorkflowBindings:
    """Business fields mapped to ComfyUI API graph inputs."""

    prompt: dict[str, str] | None
    negative_prompt: dict[str, str] | None
    width: dict[str, str] | None
    height: dict[str, str] | None
    seed: dict[str, str] | None
    count: dict[str, str] | None
    length: dict[str, str] | None
    fps: dict[str, str] | None

    def to_dict(self) -> dict[str, dict[str, str] | None]:
        return {
            "prompt": self.prompt,
            "negativePrompt": self.negative_prompt,
            "width": self.width,
            "height": self.height,
            "seed": self.seed,
            "count": self.count,
            "length": self.length,
            "fps": self.fps,
        }


@dataclass(frozen=True, slots=True)
class ConvertedWorkflow:
    """API prompt graph plus model-facing input metadata."""

    api_graph: dict[str, Any]
    output_node_id: str
    capability: str
    bindings: WorkflowBindings
    parameter_schema: tuple[dict[str, Any], ...]
    input_catalog: tuple[dict[str, Any], ...]
    topology: dict[str, Any]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ComfyWorkflowRecord:
    """An imported ComfyUI workflow that can back a media model."""

    id: str
    source_filename: str
    name: str
    capability: str
    status: str
    api_graph: dict[str, Any]
    bindings: dict[str, dict[str, str] | None]
    parameter_schema: list[dict[str, Any]]
    input_catalog: list[dict[str, Any]]
    topology: dict[str, Any]
    output_node_id: str
    model_id: str
    test_asset_id: str | None
    test_message: str | None
