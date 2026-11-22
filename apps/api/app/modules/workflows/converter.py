"""Convert supported ComfyUI UI workflows into executable API prompt graphs."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from app.modules.workflows.domain import ConvertedWorkflow, WorkflowBindings
from app.shared.errors import ProviderConfigurationError
from app.shared.semantic_parameters import (
    dimensions_for_resolution,
    infer_semantic_key,
    resolution_to_megapixels,
)

_CONTROL_VALUES = {"fixed", "increment", "decrement", "randomize"}
_COMMON_ASPECT_RATIO_LABELS = {
    "1:1": "1:1 (Square)",
    "2:3": "2:3 (Portrait Photo)",
    "3:2": "3:2 (Photo)",
    "3:4": "3:4 (Portrait Standard)",
    "4:3": "4:3 (Standard)",
    "9:16": "9:16 (Portrait Widescreen)",
    "16:9": "16:9 (Widescreen)",
    "21:9": "21:9 (Ultrawide)",
}
_TEXT_NODES = {
    "CLIPTextEncode",
    "CLIPTextEncodeFlux",
    "CLIPTextEncodeSDXL",
    "CLIPTextEncodeSDXL+",
    "CLIPTextEncodeControlnet",
    "CLIPTextEncodeLumina2",
    "CLIPTextEncodePixArtAlpha",
    "TextEncodeQwenImageEdit",
    "TextEncodeQwenImageEditPlus",
    "TextEncodeZImageOmni",
    "WanVideoTextEncode",
}
_SAMPLER_NODES = {
    "KSampler",
    "KSamplerAdvanced",
    "KSampler (Efficient)",
    "KSampler Adv. (Efficient)",
    "WanVideoSampler",
}
_OUTPUT_NODES = {
    "SaveImage",
    "SaveAnimatedWEBP",
    "SaveVideo",
    "SaveWEBM",
    "VHS_VideoCombine",
    "CreateVideo",
    "SaveAudio",
    "SaveAudioMP3",
    "SaveAudioOpus",
    "SaveText",
    "SaveText|pysssss",
}
_VIDEO_OUTPUT_PRIORITY = (
    "SaveVideo",
    "SaveWEBM",
    "VHS_VideoCombine",
    "CreateVideo",
)
_IMAGE_OUTPUT_PRIORITY = ("SaveImage", "SaveAnimatedWEBP")
_AUDIO_OUTPUT_PRIORITY = ("SaveAudio", "SaveAudioMP3", "SaveAudioOpus")
_TEXT_OUTPUT_PRIORITY = ("SaveText", "SaveText|pysssss")
_UI_PSEUDO_INPUT_TYPES = {
    "IMAGEUPLOAD",
    "VIDEOUPLOAD",
    "AUDIOUPLOAD",
}
_LATENT_SIZE_NODES = {
    "EmptySD3LatentImage",
    "EmptyLatentImage",
    "EmptyLTXVLatentVideo",
    "EmptyHunyuanLatentVideo",
    "WanImageToVideo",
}
_ASSET_NODE_TYPES = {
    "LoadImage",
    "LoadImageMask",
    "LoadVideo",
    "VHS_LoadVideo",
    "VHS_LoadVideoPath",
    "LoadAudio",
    "VHS_LoadAudio",
    "VHS_LoadAudioUpload",
}
_SCALAR_TYPES = {
    "INT": "integer",
    "FLOAT": "number",
    "STRING": "string",
    "BOOLEAN": "boolean",
    "COMBO": "string",
    "COMFY_DYNAMICCOMBO_V3": "string",
}


def convert_ui_workflow(
    ui_workflow: dict[str, Any],
    *,
    capability: str,
    object_info: dict[str, Any] | None = None,
) -> ConvertedWorkflow:
    """Convert a UI workflow into an executable graph and editable input catalog."""

    warnings: list[str] = []
    source_workflow = ui_workflow
    ui_workflow = _flatten_subgraphs(ui_workflow, warnings)
    nodes = {
        str(node["id"]): node
        for node in ui_workflow.get("nodes", [])
        if isinstance(node, dict) and node.get("id") is not None
    }
    links = {
        str(link[0]): link
        for link in ui_workflow.get("links", [])
        if isinstance(link, list) and len(link) >= 5
    }
    api_graph: dict[str, Any] = {}

    for node_id, node in nodes.items():
        mode = int(node.get("mode") or 0)
        if mode in {2, 4}:
            warnings.append(
                f"已跳过静音/旁路节点 {node.get('type')} ({node_id})"
            )
            continue
        class_type = str(node.get("type") or "")
        if not class_type or class_type in {"Note", "MarkdownNote"}:
            continue
        inputs: dict[str, Any] = {}
        raw_widget_values = node.get("widgets_values")
        widget_values = (
            list(raw_widget_values)
            if isinstance(raw_widget_values, list)
            else []
        )
        named_widgets = (
            node.get("widgets_values_named")
            if isinstance(node.get("widgets_values_named"), dict)
            else {}
        )
        widget_index = 0
        for input_spec in node.get("inputs") or []:
            if not isinstance(input_spec, dict):
                continue
            name = str(input_spec.get("name") or "")
            if not name:
                continue
            if str(input_spec.get("type") or "").upper() in (
                _UI_PSEUDO_INPUT_TYPES
            ):
                if (
                    input_spec.get("widget") is not None
                    and widget_index < len(widget_values)
                ):
                    widget_index += 1
                continue
            link_id = input_spec.get("link")
            if link_id is not None:
                link = links.get(str(link_id))
                if not link:
                    raise ProviderConfigurationError(
                        f"工作流连线缺失：节点 {node_id} / {name}"
                    )
                inputs[name] = [str(link[1]), int(link[2])]
                if (
                    input_spec.get("widget") is not None
                    and widget_index < len(widget_values)
                ):
                    widget_index += 1
                    if (
                        name in {"seed", "noise_seed"}
                        and widget_index < len(widget_values)
                        and widget_values[widget_index] in _CONTROL_VALUES
                    ):
                        widget_index += 1
                continue
            if input_spec.get("widget") is None:
                continue
            if isinstance(named_widgets, dict) and name in named_widgets:
                named_value = named_widgets[name]
                definition = _input_definition(
                    (object_info or {}).get(class_type) or {},
                    name,
                )
                if _input_value_matches(named_value, definition):
                    inputs[name] = named_value
                    if widget_index < len(widget_values):
                        widget_index += 1
                        if (
                            name in {"seed", "noise_seed"}
                            and widget_index < len(widget_values)
                            and widget_values[widget_index] in _CONTROL_VALUES
                        ):
                            widget_index += 1
                    continue
                if (
                    widget_index < len(widget_values)
                    and _input_value_matches(
                        widget_values[widget_index],
                        definition,
                    )
                ):
                    inputs[name] = widget_values[widget_index]
                    widget_index += 1
                    continue
                default = _input_default(definition)
                if default is not None:
                    inputs[name] = default
                continue
            if widget_index >= len(widget_values):
                continue
            value = widget_values[widget_index]
            widget_index += 1
            if (
                name in {"seed", "noise_seed"}
                and widget_index < len(widget_values)
                and widget_values[widget_index] in _CONTROL_VALUES
            ):
                widget_index += 1
            inputs[name] = value
        widget_index = _fill_missing_widgets(
            class_type,
            inputs,
            widget_values,
            widget_index,
            object_info,
            named_widgets=named_widgets,
        )
        api_graph[node_id] = {"class_type": class_type, "inputs": inputs}

    if not api_graph:
        raise ProviderConfigurationError("工作流没有可执行的节点")

    if capability in {"video_generation", "video_processing"}:
        priority = _VIDEO_OUTPUT_PRIORITY
    elif capability == "audio_processing":
        priority = _AUDIO_OUTPUT_PRIORITY
    elif capability == "transcription":
        priority = _TEXT_OUTPUT_PRIORITY
    else:
        priority = _IMAGE_OUTPUT_PRIORITY
    output_node_id = _select_output_node(api_graph, priority)
    if not output_node_id:
        if capability in {"video_generation", "video_processing"}:
            raise ProviderConfigurationError(
                "未找到启用的 SaveVideo、WebM 或 CreateVideo 视频输出节点"
            )
        if capability == "audio_processing":
            raise ProviderConfigurationError(
                "未找到启用的 SaveAudio、MP3 或 Opus 音频输出节点"
            )
        if capability == "transcription":
            raise ProviderConfigurationError("未找到启用的 SaveText 文本输出节点")
        raise ProviderConfigurationError("没有找到可下载的图片输出节点")

    bindings = _infer_bindings(
        api_graph,
        output_node_id,
        object_info=object_info,
    )
    if not bindings.prompt:
        warnings.append(
            "未自动识别提示词；导入后请在参数配置中手动绑定提示词输入"
        )
    parameter_schema = _build_parameter_schema(
        api_graph,
        bindings,
        object_info=object_info,
    )
    input_catalog = _build_first_layer_input_catalog(
        source_workflow,
        api_graph,
        nodes,
        object_info,
    )
    topology = _build_topology(source_workflow)
    return ConvertedWorkflow(
        api_graph=api_graph,
        output_node_id=output_node_id,
        capability=capability,
        bindings=bindings,
        parameter_schema=tuple(parameter_schema),
        input_catalog=tuple(input_catalog),
        topology=topology,
        warnings=tuple(warnings),
    )


def _select_output_node(
    api_graph: dict[str, Any],
    priority: tuple[str, ...],
) -> str | None:
    for class_type in priority:
        ids = [
            node_id
            for node_id, node in api_graph.items()
            if node.get("class_type") == class_type
        ]
        if ids:
            return ids[-1]
    return None


def build_topology_from_graph(api_graph: dict[str, Any]) -> dict[str, Any]:
    """Create a deterministic fallback layout for legacy workflow records."""

    nodes: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    for index, (node_id, node) in enumerate(api_graph.items()):
        column = index % 8
        row = index // 8
        nodes.append(
            {
                "id": node_id,
                "classType": node.get("class_type"),
                "title": node.get("class_type"),
                "pos": [40 + column * 260, 40 + row * 140],
                "size": [220, 96],
            }
        )
        for field, value in (node.get("inputs") or {}).items():
            if _is_link(value):
                links.append(
                    {
                        "originId": str(value[0]),
                        "originSlot": int(value[1]),
                        "targetId": node_id,
                        "targetField": str(field),
                    }
                )
    return {"nodes": nodes, "links": links, "source": "api_graph"}


def _build_topology(ui_workflow: dict[str, Any]) -> dict[str, Any]:
    definitions = {
        str(definition.get("id")): definition
        for definition in (
            (ui_workflow.get("definitions") or {}).get("subgraphs") or []
        )
        if isinstance(definition, dict) and definition.get("id")
    }
    nodes = [
        {
            "id": str(node["id"]),
            "classType": (
                "Subgraph"
                if str(node.get("type")) in definitions
                else str(node.get("type") or "")
            ),
            "title": str(
                node.get("title")
                or (
                    (definitions.get(str(node.get("type"))) or {}).get("name")
                )
                or node.get("type")
                or ""
            ),
            "pos": _number_pair(node.get("pos"), [0, 0]),
            "size": _number_pair(node.get("size"), [220, 100]),
            "mode": int(node.get("mode") or 0),
            "subgraph": str(node.get("type")) in definitions,
        }
        for node in ui_workflow.get("nodes") or []
        if isinstance(node, dict)
        and node.get("id") is not None
        and node.get("type") not in {"Note", "MarkdownNote"}
    ]
    node_ids = {node["id"] for node in nodes}
    links = []
    for raw in ui_workflow.get("links") or []:
        link = _normalize_ui_link(raw)
        if not link:
            continue
        origin_id = str(link[1])
        target_id = str(link[3])
        if origin_id not in node_ids or target_id not in node_ids:
            continue
        links.append(
            {
                "originId": origin_id,
                "originSlot": int(link[2]),
                "targetId": target_id,
                "targetSlot": int(link[4]),
                "type": str(link[5]) if len(link) > 5 else "*",
            }
        )
    return {"nodes": nodes, "links": links, "source": "ui_workflow"}


def _build_first_layer_input_catalog(
    source_workflow: dict[str, Any],
    api_graph: dict[str, Any],
    flattened_nodes: dict[str, dict[str, Any]],
    object_info: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    definitions = {
        str(definition.get("id")): definition
        for definition in (
            (source_workflow.get("definitions") or {}).get("subgraphs") or []
        )
        if isinstance(definition, dict) and definition.get("id")
    }
    if not definitions:
        return _build_input_catalog(api_graph, flattened_nodes, object_info)

    source_nodes = {
        str(node["id"]): node
        for node in source_workflow.get("nodes") or []
        if isinstance(node, dict) and node.get("id") is not None
    }
    plain_node_ids = {
        node_id
        for node_id, node in source_nodes.items()
        if str(node.get("type")) not in definitions
    }
    catalog = _build_input_catalog(
        api_graph,
        {
            node_id: node
            for node_id, node in flattened_nodes.items()
            if node_id in plain_node_ids
        },
        object_info,
        restrict_to_nodes=True,
    )

    for container_id, container in source_nodes.items():
        definition = definitions.get(str(container.get("type")))
        if not definition:
            continue
        definition_nodes = {
            str(node["id"]): node
            for node in definition.get("nodes") or []
            if isinstance(node, dict) and node.get("id") is not None
        }
        input_node_id = str((definition.get("inputNode") or {}).get("id"))
        definition_links = [
            link
            for raw in definition.get("links") or []
            if (link := _normalize_ui_link(raw)) is not None
        ]
        widget_values = list(container.get("widgets_values") or [])
        named_values = container.get("widgets_values_named") or {}
        for input_index, input_spec in enumerate(
            definition.get("inputs") or []
        ):
            if not isinstance(input_spec, dict):
                continue
            name = str(input_spec.get("name") or "")
            if not name:
                continue
            container_spec = (
                (container.get("inputs") or [])[input_index]
                if input_index < len(container.get("inputs") or [])
                else {}
            )
            if (
                container_spec.get("widget") is None
                or str(input_spec.get("type") or "").upper()
                in _UI_PSEUDO_INPUT_TYPES
            ):
                continue
            bindings: list[dict[str, str]] = []
            target_definition = None
            for link in definition_links:
                if (
                    str(link[1]) != input_node_id
                    or int(link[2]) != input_index
                ):
                    continue
                target_node = definition_nodes.get(str(link[3]))
                if not target_node:
                    continue
                target_specs = list(target_node.get("inputs") or [])
                target_slot = int(link[4])
                if target_slot >= len(target_specs):
                    continue
                field = str(target_specs[target_slot].get("name") or "")
                if not field:
                    continue
                flattened_id = f"{container_id}:{target_node['id']}"
                if flattened_id not in api_graph:
                    continue
                bindings.append({"nodeId": flattened_id, "field": field})
                target_definition = target_definition or _input_definition(
                    (object_info or {}).get(
                        str(target_node.get("type") or "")
                    )
                    or {},
                    field,
                )
            if not bindings:
                continue
            parameter_type = _SCALAR_TYPES.get(
                str(input_spec.get("type") or "").upper()
            ) or _parameter_type(target_definition, None)
            if not parameter_type:
                continue
            default = named_values.get(name)
            if default is None and input_index < len(widget_values):
                default = widget_values[input_index]
            label = str(
                input_spec.get("label")
                or container_spec.get("label")
                or name
            )
            item: dict[str, Any] = {
                "id": f"{container_id}:input:{name}",
                "nodeId": container_id,
                "nodeType": str(container.get("type") or "Subgraph"),
                "nodeTitle": str(
                    container.get("title")
                    or definition.get("name")
                    or "Subgraph"
                ),
                "field": name,
                "fieldLabel": label,
                "label": f"{definition.get('name') or 'Subgraph'} / {label}",
                "type": parameter_type,
                "default": default,
                "linked": container_spec.get("link") is not None,
                "bindings": bindings,
                "subgraph": True,
            }
            options = _input_options(target_definition)
            if options:
                item["options"] = options
            catalog.append(item)
    return catalog


def _number_pair(value: object, fallback: list[int]) -> list[int]:
    if (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        return [int(value[0]), int(value[1])]
    return fallback


def _flatten_subgraphs(
    ui_workflow: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    """Expand ComfyUI subgraph containers into ordinary UI nodes."""

    workflow = deepcopy(ui_workflow)
    definitions = {
        str(definition.get("id")): definition
        for definition in (
            (workflow.get("definitions") or {}).get("subgraphs") or []
        )
        if isinstance(definition, dict) and definition.get("id")
    }
    if not definitions:
        return workflow

    nodes = list(workflow.get("nodes") or [])
    links = [_normalize_ui_link(link) for link in workflow.get("links") or []]
    links = [link for link in links if link is not None]
    expanded = 0
    for _ in range(64):
        container = next(
            (
                node
                for node in nodes
                if isinstance(node, dict)
                and str(node.get("type")) in definitions
            ),
            None,
        )
        if not container:
            break
        definition = definitions[str(container["type"])]
        nodes, links = _expand_subgraph(nodes, links, container, definition)
        expanded += 1
        if expanded > 32:
            raise ProviderConfigurationError("子图展开层数过多，可能存在循环引用")

    if expanded:
        warnings.append(f"已展开 {expanded} 个 ComfyUI 子图")
    workflow["nodes"] = nodes
    workflow["links"] = links
    return workflow


def _expand_subgraph(
    nodes: list[dict[str, Any]],
    links: list[list[Any]],
    container: dict[str, Any],
    definition: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[list[Any]]]:
    container_id = str(container["id"])
    prefix = f"{container_id}:"
    outer_links = {int(link[0]): link for link in links}
    inner_nodes = {
        str(node["id"]): node
        for node in deepcopy(definition.get("nodes") or [])
        if isinstance(node, dict) and node.get("id") is not None
    }
    positioned_nodes = [
        node
        for node in inner_nodes.values()
        if node.get("type") not in {"Note", "MarkdownNote"}
        and isinstance(node.get("pos"), list)
        and len(node["pos"]) >= 2
        and isinstance(node["pos"][0], (int, float))
        and isinstance(node["pos"][1], (int, float))
    ]
    if positioned_nodes:
        min_x = min(float(node["pos"][0]) for node in positioned_nodes)
        min_y = min(float(node["pos"][1]) for node in positioned_nodes)
        container_pos = _number_pair(container.get("pos"), [0, 0])
        container_size = _number_pair(container.get("size"), [240, 120])
        for node in positioned_nodes:
            node["pos"] = [
                container_pos[0] + float(node["pos"][0]) - min_x,
                container_pos[1] + container_size[1] + 130
                + float(node["pos"][1]) - min_y,
            ]
    inner_links = [
        link
        for raw_link in definition.get("links") or []
        if (link := _normalize_ui_link(raw_link)) is not None
    ]
    input_node_id = str((definition.get("inputNode") or {}).get("id"))
    output_node_id = str((definition.get("outputNode") or {}).get("id"))
    container_inputs = list(container.get("inputs") or [])
    widget_values = list(container.get("widgets_values") or [])
    named_widgets = container.get("widgets_values_named") or {}
    max_existing_link = max(
        [int(link[0]) for link in links] + [0]
    )
    next_link = max_existing_link + 1
    output_sources: dict[int, tuple[str, int, str]] = {}
    expanded_links: list[list[Any]] = []

    for link in inner_links:
        target_id = str(link[3])
        target_slot = int(link[4])
        origin_id = str(link[1])
        origin_slot = int(link[2])
        link_type = str(link[5]) if len(link) > 5 else "*"
        if target_id == output_node_id:
            output_sources[target_slot] = (
                f"{prefix}{origin_id}",
                origin_slot,
                link_type,
            )
            continue
        target_node = inner_nodes.get(target_id)
        if not target_node:
            continue
        if origin_id == input_node_id:
            if origin_slot >= len(container_inputs):
                raise ProviderConfigurationError(
                    f"子图 {container.get('type')} 缺少输入槽 {origin_slot}"
                )
            container_input = container_inputs[origin_slot]
            external_link_id = container_input.get("link")
            if external_link_id is not None:
                external = outer_links.get(int(external_link_id))
                if not external:
                    raise ProviderConfigurationError(
                        f"子图输入连线缺失：{container_input.get('name')}"
                    )
                expanded_links.append(
                    [
                        next_link,
                        str(external[1]),
                        int(external[2]),
                        f"{prefix}{target_id}",
                        target_slot,
                        link_type,
                    ]
                )
                _set_node_input_link(target_node, target_slot, next_link)
                next_link += 1
            else:
                name = str(container_input.get("name") or "")
                value = named_widgets.get(name)
                if value is None and origin_slot < len(widget_values):
                    value = widget_values[origin_slot]
                _set_node_widget_value(target_node, target_slot, value)
            continue
        expanded_links.append(
            [
                next_link,
                f"{prefix}{origin_id}",
                origin_slot,
                f"{prefix}{target_id}",
                target_slot,
                link_type,
            ]
        )
        _set_node_input_link(target_node, target_slot, next_link)
        next_link += 1

    remaining_links: list[list[Any]] = []
    for link in links:
        origin_id = str(link[1])
        target_id = str(link[3])
        if origin_id == container_id and target_id == container_id:
            continue
        if target_id == container_id:
            continue
        if origin_id == container_id:
            source = output_sources.get(int(link[2]))
            if not source:
                raise ProviderConfigurationError(
                    f"子图输出槽 {link[2]} 没有内部连线"
                )
            remaining_links.append(
                [
                    next_link,
                    source[0],
                    source[1],
                    target_id,
                    int(link[4]),
                    source[2],
                ]
            )
            target_node = next(
                (node for node in nodes if str(node.get("id")) == target_id),
                None,
            )
            if target_node:
                _set_node_input_link(
                    target_node,
                    int(link[4]),
                    next_link,
                )
            next_link += 1
            continue
        remaining_links.append(link)

    expanded_nodes = [
        node for node in nodes if str(node.get("id")) != container_id
    ]
    for inner_id, inner_node in inner_nodes.items():
        inner_node["id"] = f"{prefix}{inner_id}"
        expanded_nodes.append(inner_node)
    return expanded_nodes, remaining_links + expanded_links


def _normalize_ui_link(link: object) -> list[Any] | None:
    if isinstance(link, list) and len(link) >= 5:
        return list(link)
    if not isinstance(link, dict) or link.get("id") is None:
        return None
    return [
        link["id"],
        link.get("origin_id"),
        link.get("origin_slot"),
        link.get("target_id"),
        link.get("target_slot"),
        link.get("type") or "*",
    ]


def _set_node_widget_value(
    node: dict[str, Any],
    target_slot: int,
    value: object,
) -> None:
    input_specs = list(node.get("inputs") or [])
    if target_slot >= len(input_specs):
        raise ProviderConfigurationError("子图输入槽超出了目标节点输入范围")
    target = input_specs[target_slot]
    widget = target.get("widget")
    if not isinstance(widget, dict):
        raise ProviderConfigurationError(
            f"子图输入 {target.get('name')} 不是可配置控件"
        )
    target["link"] = None
    widget_index = sum(
        1
        for input_spec in input_specs[:target_slot]
        if isinstance(input_spec, dict) and input_spec.get("widget") is not None
    )
    widgets = node.get("widgets_values")
    if not isinstance(widgets, list):
        widgets = []
        node["widgets_values"] = widgets
    while len(widgets) <= widget_index:
        widgets.append(None)
    widgets[widget_index] = value
    named = node.get("widgets_values_named")
    name = str(widget.get("name") or "")
    if isinstance(named, dict) and name:
        named[name] = value


def _set_node_input_link(
    node: dict[str, Any],
    input_slot: int,
    link_id: int,
) -> None:
    input_specs = list(node.get("inputs") or [])
    if 0 <= input_slot < len(input_specs):
        input_specs[input_slot]["link"] = link_id


def apply_bindings(
    api_graph: dict[str, Any],
    bindings: dict[str, dict[str, str] | None],
    *,
    prompt: str,
    parameters: dict[str, object],
) -> dict[str, Any]:
    """Copy a graph and inject validated business values into bound fields."""

    compiled = deepcopy(api_graph)
    values = {
        "prompt": prompt,
        "negativePrompt": parameters.get("negativePrompt"),
        "width": parameters.get("width"),
        "height": parameters.get("height"),
        "seed": parameters.get("seed"),
        "count": parameters.get("count"),
        "length": parameters.get("length"),
        "fps": parameters.get("fps"),
    }
    for key, binding in bindings.items():
        value = values.get(key)
        if value is None or not binding:
            continue
        node = compiled.get(binding["nodeId"])
        if node and binding.get("field"):
            node["inputs"][binding["field"]] = value
    _normalize_public_dimensions(compiled, values)
    _normalize_easy_pixels_outputs(compiled)
    return compiled


def apply_parameter_schema(
    api_graph: dict[str, Any],
    parameter_schema: list[dict[str, Any]],
    *,
    values: dict[str, object],
    uploaded_assets: list[str] | None = None,
    uploaded_assets_by_parameter: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Validate user parameters and inject defaults before ComfyUI submission."""

    if not parameter_schema:
        return apply_bindings(
            api_graph,
            {},
            prompt=str(values.get("prompt") or ""),
            parameters=values,
        )
    asset_parameters = [
        parameter
        for parameter in parameter_schema
        if parameter.get("type") == "assets"
    ]
    has_reference_video = any(
        str(node.get("class_type") or "") == "MiniMaxH3ReferenceToVideo"
        for node in api_graph.values()
    )
    if has_reference_video and asset_parameters:
        supplied = False
        for parameter in asset_parameters:
            key = str(parameter.get("key") or "")
            if uploaded_assets_by_parameter is not None:
                supplied = supplied or bool(uploaded_assets_by_parameter.get(key))
            else:
                supplied = supplied or bool(uploaded_assets)
            if supplied:
                break
        if not supplied:
            raise ProviderConfigurationError("多参考生视频至少需要 1 个参考素材")
    resolved_values = dict(values)
    dimensions = dimensions_for_resolution(
        resolved_values.get("resolution"),
        resolved_values.get("aspectRatio")
        or resolved_values.get("aspect_ratio"),
    )
    if dimensions and resolved_values.get("width") in (None, ""):
        resolved_values["width"] = dimensions[0]
    if dimensions and resolved_values.get("height") in (None, ""):
        resolved_values["height"] = dimensions[1]
    compiled = deepcopy(api_graph)
    for parameter in parameter_schema:
        key = str(parameter.get("key") or "")
        parameter_type = str(parameter.get("type") or "string")
        required = bool(parameter.get("required"))
        if parameter_type == "assets":
            if uploaded_assets_by_parameter is not None:
                assets = list(uploaded_assets_by_parameter.get(key) or [])
            else:
                assets = list(uploaded_assets or [])
            minimum = int(parameter.get("min") or 0)
            maximum = int(parameter.get("max") or len(assets))
            if len(assets) < minimum:
                raise ProviderConfigurationError(
                    f"参数“{parameter.get('label', key)}”至少需要 {minimum} 个素材"
                )
            if maximum >= 0 and len(assets) > maximum:
                raise ProviderConfigurationError(
                    f"参数“{parameter.get('label', key)}”最多支持 {maximum} 个素材"
                )
            unused_node_ids: set[str] = set()
            for binding in parameter.get("bindings") or []:
                index = int(binding.get("assetIndex", 0))
                node = compiled.get(str(binding.get("nodeId")))
                if node and index < len(assets):
                    node["inputs"][str(binding.get("field"))] = assets[index]
                elif index >= len(assets):
                    unused_node_ids.add(str(binding.get("nodeId")))
            _remove_nodes_and_links(compiled, unused_node_ids)
            continue
        first_binding = (
            parameter.get("bindings") or [{}]
        )[0]
        semantic_key = str(
            parameter.get("semanticKey")
            or infer_semantic_key(
                key,
                str(parameter.get("label") or ""),
                str(first_binding.get("field") or ""),
            )
        )
        value = resolved_values.get(key)
        if value in (None, "") and semantic_key != key:
            value = resolved_values.get(semantic_key)
        if value in (None, "") and semantic_key == "prompt":
            value = resolved_values.get("prompt")
        if value in (None, "") and parameter.get("default") not in (None, ""):
            value = parameter.get("default")
        if required and value in (None, ""):
            raise ProviderConfigurationError(
                f"缺少必填参数：{parameter.get('label', key)}"
            )
        if value in (None, ""):
            continue
        if (
            semantic_key == "resolution"
            and parameter_type in {"integer", "number"}
        ):
            megapixels = resolution_to_megapixels(value)
            if megapixels is not None:
                value = megapixels
        if semantic_key == "aspectRatio":
            options = parameter.get("options")
            value = _aspect_ratio_choice(value, options)
        value = _coerce_parameter_value(parameter, value)
        for binding in parameter.get("bindings") or []:
            node = compiled.get(str(binding.get("nodeId")))
            if node:
                node["inputs"][str(binding.get("field"))] = value
    _normalize_public_dimensions(compiled, resolved_values)
    _normalize_easy_pixels_outputs(compiled)
    return compiled


def _aspect_ratio_choice(
    value: object,
    options: object,
) -> object:
    """Map canonical ratios onto verbose ComfyUI combo values."""

    ratio = _aspect_ratio_token(value)
    if isinstance(options, list) and options:
        matching_option = next(
            (
                option
                for option in options
                if _aspect_ratio_token(option) == ratio
            ),
            None,
        )
        if matching_option is not None:
            return matching_option
    return _COMMON_ASPECT_RATIO_LABELS.get(ratio, value)


def _aspect_ratio_token(value: object) -> str:
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)",
        str(value or ""),
    )
    if not match:
        return str(value or "").strip()
    return f"{match.group(1)}:{match.group(2)}"


def _normalize_public_dimensions(
    api_graph: dict[str, Any],
    values: dict[str, object],
) -> None:
    """Map public output pixels onto ComfyUI helper nodes that apply a scale."""

    width = values.get("width")
    height = values.get("height")
    if width in (None, "") or height in (None, ""):
        return
    try:
        public_width = int(width)
        public_height = int(height)
    except (TypeError, ValueError):
        return
    if public_width <= 0 or public_height <= 0:
        return
    for node in api_graph.values():
        if str(node.get("class_type") or "").lower() != "easy pixels":
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        if {"resolution", "width", "height", "scale"} <= set(inputs):
            inputs["resolution"] = "width x height (custom)"
            inputs["width"] = public_width
            inputs["height"] = public_height
            inputs["scale"] = 1


def _normalize_easy_pixels_outputs(api_graph: dict[str, Any]) -> None:
    """Use normalized integer dimensions instead of scaled float outputs."""

    easy_pixel_nodes = {
        node_id
        for node_id, node in api_graph.items()
        if str(node.get("class_type") or "").lower() == "easy pixels"
    }
    if not easy_pixel_nodes:
        return
    for node in api_graph.values():
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        for field, value in list(inputs.items()):
            if not _is_link(value):
                continue
            if str(value[0]) not in easy_pixel_nodes:
                continue
            slot = int(value[1])
            if slot in {2, 3}:
                inputs[field] = [value[0], slot - 2]


def validate_parameter_schema(
    api_graph: dict[str, Any],
    parameters: list[dict[str, Any]],
) -> None:
    """Validate user-designed parameter bindings before they become executable."""

    allowed_types = {"string", "integer", "number", "boolean", "assets"}
    keys: set[str] = set()
    used_bindings: set[tuple[str, str]] = set()
    for parameter in parameters:
        key = str(parameter.get("key") or "").strip()
        if not key:
            raise ProviderConfigurationError("参数 key 不能为空")
        if len(key) > 64:
            raise ProviderConfigurationError(f"参数 key 过长：{key}")
        if key in keys:
            raise ProviderConfigurationError(f"参数 key 重复：{key}")
        keys.add(key)
        parameter_type = str(parameter.get("type") or "")
        if parameter_type not in allowed_types:
            raise ProviderConfigurationError(
                f"参数“{parameter.get('label', key)}”类型不受支持"
            )
        if parameter_type == "assets":
            asset_type = str(parameter.get("assetType") or "image")
            if asset_type not in {"image", "video", "audio", "file"}:
                raise ProviderConfigurationError(
                    f"素材参数“{parameter.get('label', key)}”类型不受支持"
                )
        bindings = parameter.get("bindings")
        if not isinstance(bindings, list) or not bindings:
            raise ProviderConfigurationError(
                f"参数“{parameter.get('label', key)}”至少需要绑定一个输入"
            )
        for binding in bindings:
            if not isinstance(binding, dict):
                raise ProviderConfigurationError("参数绑定格式不正确")
            node_id = str(binding.get("nodeId") or "")
            field = str(binding.get("field") or "")
            node = api_graph.get(node_id)
            if not node or field not in (node.get("inputs") or {}):
                raise ProviderConfigurationError(
                    f"参数“{parameter.get('label', key)}”绑定了不存在的输入 "
                    f"{node_id}/{field}"
                )
            binding_key = (node_id, field)
            if binding_key in used_bindings:
                raise ProviderConfigurationError(
                    f"工作流输入 {node_id}/{field} 被多个参数重复绑定"
                )
            used_bindings.add(binding_key)
            if parameter_type == "assets":
                asset_index = binding.get("assetIndex")
                if not isinstance(asset_index, int) or asset_index < 0:
                    raise ProviderConfigurationError(
                        f"素材参数“{parameter.get('label', key)}”缺少序号"
                    )
        minimum = parameter.get("min")
        maximum = parameter.get("max")
        if (
            isinstance(minimum, (int, float))
            and isinstance(maximum, (int, float))
            and minimum > maximum
        ):
            raise ProviderConfigurationError(
                f"参数“{parameter.get('label', key)}”最小值不能大于最大值"
            )


def _build_parameter_schema(
    api_graph: dict[str, Any],
    bindings: WorkflowBindings,
    *,
    object_info: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    parameters: list[dict[str, Any]] = []

    def add_scalar(
        key: str,
        label: str,
        parameter_type: str,
        binding: dict[str, str] | None,
        *,
        required: bool = False,
        minimum: object = None,
        maximum: object = None,
        options: list[object] | None = None,
    ) -> None:
        if not binding:
            return
        node = api_graph.get(binding["nodeId"], {})
        default = (node.get("inputs") or {}).get(binding["field"])
        if _is_link(default):
            default = None
        parameter: dict[str, Any] = {
            "key": key,
            "label": label,
            "type": parameter_type,
            "required": required,
            "default": default,
            "bindings": [binding],
            "semanticKey": infer_semantic_key(
                key,
                label,
                str(binding.get("field") or ""),
            ),
        }
        if minimum is not None:
            parameter["min"] = minimum
        if maximum is not None:
            parameter["max"] = maximum
        if options:
            parameter["options"] = options
        parameters.append(parameter)

    add_scalar("prompt", "提示词", "string", bindings.prompt, required=True)
    if bindings.negative_prompt and bindings.negative_prompt != bindings.prompt:
        add_scalar(
            "negativePrompt",
            "反向提示词",
            "string",
            bindings.negative_prompt,
        )
    add_scalar("width", "宽度", "integer", bindings.width, required=True, minimum=64)
    add_scalar("height", "高度", "integer", bindings.height, required=True, minimum=64)
    add_scalar("seed", "随机种子", "integer", bindings.seed, minimum=0)
    add_scalar("count", "生成数量", "integer", bindings.count, minimum=1, maximum=4)
    if bindings.length:
        add_scalar(
            "length",
            "视频帧数",
            "integer",
            bindings.length,
            required=True,
            minimum=5,
            maximum=3600,
        )
    if bindings.fps:
        add_scalar(
            "fps",
            "帧率",
            "integer",
            bindings.fps,
            minimum=1,
            maximum=60,
        )

    if not bindings.width and not bindings.height:
        resolution_selector = next(
            (
                (node_id, node)
                for node_id, node in api_graph.items()
                if str(node.get("class_type") or "") == "ResolutionSelector"
                and "aspect_ratio" in (node.get("inputs") or {})
                and "megapixels" in (node.get("inputs") or {})
            ),
            None,
        )
        if resolution_selector:
            node_id, node = resolution_selector
            node_info = (object_info or {}).get("ResolutionSelector") or {}
            aspect_definition = _input_definition(
                node_info,
                "aspect_ratio",
            )
            add_scalar(
                "aspectRatio",
                "画面比例",
                "string",
                {"nodeId": node_id, "field": "aspect_ratio"},
                required=True,
                options=_input_options(aspect_definition),
            )
            add_scalar(
                "resolution",
                "分辨率",
                "number",
                {"nodeId": node_id, "field": "megapixels"},
                required=True,
                minimum=0.1,
                maximum=64,
            )

    asset_groups: dict[str, list[dict[str, Any]]] = {}
    for node_id, node in api_graph.items():
        class_type = str(node.get("class_type") or "")
        for field in (node.get("inputs") or {}):
            asset_type = _asset_type_for_input(class_type, str(field))
            if not asset_type:
                continue
            bindings = asset_groups.setdefault(asset_type, [])
            bindings.append(
                {
                    "assetIndex": len(bindings),
                    "nodeId": node_id,
                    "field": str(field),
                }
            )
    asset_keys = {
        "image": ("assets", "参考图片"),
        "video": ("videos", "参考视频"),
        "audio": ("audios", "参考音频"),
        "file": ("files", "参考文件"),
    }
    for asset_type, asset_bindings in asset_groups.items():
        key, label = asset_keys[asset_type]
        reference_video_workflow = any(
            str(node.get("class_type") or "") == "MiniMaxH3ReferenceToVideo"
            for node in api_graph.values()
        )
        image_reference_workflow = any(
            str(node.get("class_type") or "") == "MiniMaxH3ImageConditioning"
            for node in api_graph.values()
        )
        parameters.append(
            {
                "key": key,
                "label": label,
                "type": "assets",
                "assetType": asset_type,
                "required": not reference_video_workflow,
                "min": (
                    0
                    if reference_video_workflow
                    else 1
                    if image_reference_workflow
                    else len(asset_bindings)
                ),
                "max": len(asset_bindings),
                "bindings": asset_bindings,
            }
        )
    return parameters


def _remove_nodes_and_links(
    api_graph: dict[str, Any],
    node_ids: set[str],
) -> None:
    """Drop optional capacity slots that the caller did not supply."""

    if not node_ids:
        return
    for node_id in node_ids:
        api_graph.pop(node_id, None)
    for node in api_graph.values():
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        for field, value in list(inputs.items()):
            if _is_link(value) and str(value[0]) in node_ids:
                inputs.pop(field, None)


def _build_input_catalog(
    api_graph: dict[str, Any],
    nodes: dict[str, dict[str, Any]],
    object_info: dict[str, Any] | None,
    *,
    restrict_to_nodes: bool = False,
) -> list[dict[str, Any]]:
    """Describe every scalar or asset input that a user can expose as a parameter."""

    catalog: list[dict[str, Any]] = []
    for node_id, graph_node in api_graph.items():
        if restrict_to_nodes and node_id not in nodes:
            continue
        ui_node = nodes.get(node_id) or {
            "id": node_id,
            "type": graph_node.get("class_type"),
            "inputs": [
                {"name": name}
                for name in (graph_node.get("inputs") or {})
            ],
        }
        class_type = str(graph_node.get("class_type") or "")
        node_info = (object_info or {}).get(class_type) or {}
        node_title = (
            str(ui_node.get("title") or "").strip()
            or str(node_info.get("display_name") or "").strip()
            or class_type
        )
        ordered_names = _ordered_input_names(ui_node, node_info)
        input_specs = {
            str(spec.get("name")): spec
            for spec in (ui_node.get("inputs") or [])
            if isinstance(spec, dict) and spec.get("name")
        }
        for name in ordered_names:
            inputs = graph_node.get("inputs") or {}
            if name not in inputs:
                continue
            definition = _input_definition(node_info, name)
            asset_type = _asset_type_for_input(class_type, name)
            parameter_type = asset_type or _parameter_type(definition, inputs[name])
            if not parameter_type:
                continue
            value = inputs[name]
            linked = _is_link(value)
            named_values = ui_node.get("widgets_values_named") or {}
            default = named_values.get(name)
            if default is None and not linked:
                default = value
            options = _input_options(definition)
            spec = input_specs.get(name) or {}
            field_label = str(
                spec.get("localized_name") or spec.get("label") or name
            )
            item: dict[str, Any] = {
                "id": f"{node_id}:{name}",
                "nodeId": node_id,
                "nodeType": class_type,
                "nodeTitle": node_title,
                "field": name,
                "fieldLabel": field_label,
                "label": f"{node_title} / {field_label}",
                "type": parameter_type,
                "default": default,
                "linked": linked,
            }
            if asset_type:
                item["assetType"] = asset_type
            if linked:
                item["linkedTo"] = value
            if options:
                item["options"] = options
            catalog.append(item)
    return catalog


def build_input_catalog(
    api_graph: dict[str, Any],
    object_info: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Rebuild a bindable field catalog from a persisted API graph."""

    return _build_input_catalog(api_graph, {}, object_info)


def _ordered_input_names(
    ui_node: dict[str, Any],
    node_info: dict[str, Any],
) -> list[str]:
    input_order = node_info.get("input_order") or {}
    names = [
        str(name)
        for name in (
            *(input_order.get("required") or []),
            *(input_order.get("optional") or []),
        )
    ]
    names.extend(
        str(spec["name"])
        for spec in (ui_node.get("inputs") or [])
        if isinstance(spec, dict)
        and spec.get("name")
        and str(spec["name"]) not in names
    )
    return names


def _input_definition(
    node_info: dict[str, Any],
    name: str,
) -> object:
    definitions = node_info.get("input") or {}
    return (definitions.get("required") or {}).get(name) or (
        definitions.get("optional") or {}
    ).get(name)


def _parameter_type(
    definition: object,
    value: object,
) -> str | None:
    if isinstance(definition, list) and definition:
        raw_type = definition[0]
        if isinstance(raw_type, list):
            return "string"
        mapped = _SCALAR_TYPES.get(str(raw_type))
        if mapped:
            return mapped
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    return None


def _input_options(definition: object) -> list[object]:
    if not isinstance(definition, list) or not definition:
        return []
    raw_type = definition[0]
    if not isinstance(raw_type, list):
        return []
    return [option for option in raw_type if isinstance(option, (str, int, float))]


def _asset_type_for_input(class_type: str, field: str) -> str | None:
    normalized_class = class_type.lower()
    normalized_field = field.lower()
    if "loadvideo" in normalized_class and normalized_field in {
        "file",
        "video",
        "video_path",
    }:
        return "video"
    if "loadaudio" in normalized_class and normalized_field in {
        "audio",
        "audio_file",
        "file",
    }:
        return "audio"
    if "loadimage" in normalized_class and normalized_field in {
        "image",
        "image_path",
    }:
        return "image"
    if class_type in _ASSET_NODE_TYPES and normalized_field == "image":
        return "image"
    if normalized_field in {"video", "video_path"} and normalized_class.startswith(
        "load"
    ):
        return "video"
    if normalized_field in {"audio", "audio_path"} and normalized_class.startswith(
        "load"
    ):
        return "audio"
    if normalized_field in {"image", "image_path"} and normalized_class.startswith(
        "load"
    ):
        return "image"
    return None


def _coerce_parameter_value(
    parameter: dict[str, Any], value: object
) -> object:
    parameter_type = parameter.get("type")
    try:
        if parameter_type == "integer":
            coerced: object = int(value)
        elif parameter_type == "number":
            coerced = float(value)
        elif parameter_type == "boolean":
            coerced = (
                value
                if isinstance(value, bool)
                else str(value).lower() in {"1", "true", "yes", "on"}
            )
        else:
            coerced = str(value)
    except (TypeError, ValueError) as exc:
        raise ProviderConfigurationError(
            f"参数“{parameter.get('label')}”类型不正确"
        ) from exc
    minimum = parameter.get("min")
    maximum = parameter.get("max")
    if isinstance(coerced, (int, float)):
        if minimum is not None and coerced < minimum:
            raise ProviderConfigurationError(
                f"参数“{parameter.get('label')}”不能小于 {minimum}"
            )
        if maximum is not None and coerced > maximum:
            raise ProviderConfigurationError(
                f"参数“{parameter.get('label')}”不能大于 {maximum}"
            )
    choices = parameter.get("options")
    if isinstance(choices, list) and choices and coerced not in choices:
        raise ProviderConfigurationError(
            f"参数“{parameter.get('label')}”不在允许范围内"
        )
    return coerced


def _infer_bindings(
    api_graph: dict[str, Any],
    output_node_id: str,
    *,
    object_info: dict[str, Any] | None,
) -> WorkflowBindings:
    positive = _find_sampler_text_node(api_graph, "positive", object_info)
    negative = _find_sampler_text_node(api_graph, "negative", object_info)
    size_binding = _find_size_binding(api_graph)
    seed_binding = _find_field(api_graph, {"seed", "noise_seed"})
    count_binding = _find_field(api_graph, {"batch_size"})
    length_binding = _find_field(api_graph, {"length"})
    fps_binding = _find_field(api_graph, {"fps"})
    return WorkflowBindings(
        prompt=_text_ref(positive),
        negative_prompt=_text_ref(negative),
        width=size_binding[0],
        height=size_binding[1],
        seed=seed_binding,
        count=count_binding,
        length=length_binding,
        fps=fps_binding,
    )


def _find_sampler_text_node(
    api_graph: dict[str, Any],
    input_name: str,
    object_info: dict[str, Any] | None,
) -> tuple[str, str] | None:
    source_names = (
        ("positive", "text_embeds")
        if input_name == "positive"
        else ("negative", "text_embeds")
    )
    for node in api_graph.values():
        reference = next(
            (
                node["inputs"].get(name)
                for name in source_names
                if _is_link(node["inputs"].get(name))
            ),
            None,
        )
        if not _is_link(reference):
            continue
        found = _trace_text_node(
            api_graph,
            str(reference[0]),
            int(reference[1]),
            set(),
            input_name,
            object_info,
        )
        if found:
            return found
    for node_id, node in api_graph.items():
        if _is_text_encoder(node, object_info):
            field = _select_text_field(node, input_name, object_info)
            if field:
                return node_id, field
    return None


def _trace_text_node(
    api_graph: dict[str, Any],
    node_id: str,
    output_slot: int,
    visited: set[str],
    conditioning_kind: str,
    object_info: dict[str, Any] | None,
) -> tuple[str, str] | None:
    if node_id in visited:
        return None
    visited.add(node_id)
    node = api_graph.get(node_id)
    if not node:
        return None
    if _is_text_encoder(node, object_info):
        field = _select_text_field(node, conditioning_kind, object_info)
        if field:
            return node_id, field
    if node["class_type"] == "WanImageToVideo" and output_slot in {0, 1}:
        input_name = "positive" if output_slot == 0 else "negative"
        reference = node["inputs"].get(input_name)
        if _is_link(reference):
            return _trace_text_node(
                api_graph,
                str(reference[0]),
                int(reference[1]),
                visited,
                conditioning_kind,
                object_info,
            )
    for value in node["inputs"].values():
        if _is_link(value):
            found = _trace_text_node(
                api_graph,
                str(value[0]),
                int(value[1]),
                visited,
                conditioning_kind,
                object_info,
            )
            if found:
                return found
    return None


def _find_size_binding(
    api_graph: dict[str, Any],
) -> tuple[dict[str, str] | None, dict[str, str] | None]:
    candidates = sorted(
        api_graph.items(),
        key=lambda item: item[1]["class_type"] not in _LATENT_SIZE_NODES,
    )
    for node_id, node in candidates:
        width = node["inputs"].get("width")
        height = node["inputs"].get("height")
        if (
            "width" in node["inputs"]
            and "height" in node["inputs"]
            and not _is_link(width)
            and not _is_link(height)
        ):
            return (
                {"nodeId": node_id, "field": "width"},
                {"nodeId": node_id, "field": "height"},
            )
    return None, None


def _find_field(
    api_graph: dict[str, Any], field_names: set[str]
) -> dict[str, str] | None:
    for node_id, node in api_graph.items():
        for field in field_names:
            if field in node["inputs"] and not _is_link(node["inputs"][field]):
                return {"nodeId": node_id, "field": field}
    return None


def _text_ref(
    reference: tuple[str, str] | None,
) -> dict[str, str] | None:
    if not reference:
        return None
    return {"nodeId": reference[0], "field": reference[1]}


def _is_text_encoder(
    node: dict[str, Any],
    object_info: dict[str, Any] | None,
) -> bool:
    class_type = str(node.get("class_type") or "")
    if class_type in _TEXT_NODES:
        return True
    if not object_info:
        return False
    node_info = object_info.get(class_type) or {}
    for output_type in node_info.get("output") or []:
        normalized = str(output_type).upper()
        if "CONDITIONING" in normalized or "TEXTEMBED" in normalized:
            return True
    return False


def _select_text_field(
    node: dict[str, Any],
    kind: str,
    object_info: dict[str, Any] | None,
) -> str | None:
    inputs = node.get("inputs") or {}
    available = _text_input_names(node, object_info)
    if kind == "negative":
        candidates = (
            "negative_prompt",
            "negative",
            "negative_text",
            "text",
            "prompt",
            "text_g",
        )
    else:
        candidates = (
            "positive_prompt",
            "positive",
            "positive_text",
            "text",
            "prompt",
            "text_g",
            "t5xxl",
            "clip_l",
        )
    by_normalized_name = {
        _normalize_input_name(name): name for name in available if name in inputs
    }
    for candidate in candidates:
        if candidate in by_normalized_name:
            return by_normalized_name[candidate]
    return None


def _text_input_names(
    node: dict[str, Any],
    object_info: dict[str, Any] | None,
) -> list[str]:
    node_info = (object_info or {}).get(str(node.get("class_type") or "")) or {}
    input_order = node_info.get("input_order") or {}
    ordered = [
        *(input_order.get("required") or []),
        *(input_order.get("optional") or []),
    ]
    names = [str(name) for name in ordered]
    names.extend(
        name for name in (node.get("inputs") or {}) if str(name) not in names
    )
    return names


def _normalize_input_name(name: str) -> str:
    return name.strip().lower().replace("-", "_").replace(" ", "_")


def _is_link(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    )


def _fill_missing_widgets(
    class_type: str,
    inputs: dict[str, Any],
    widget_values: list[Any],
    widget_index: int,
    object_info: dict[str, Any] | None,
    *,
    named_widgets: dict[str, Any] | None = None,
) -> int:
    if not object_info:
        return widget_index
    node_info = object_info.get(class_type) or {}
    definitions = node_info.get("input") or {}
    input_order = node_info.get("input_order") or {}
    names = [
        *(input_order.get("required") or []),
        *(input_order.get("optional") or []),
    ]
    for name in names:
        if name in inputs:
            continue
        definition = (definitions.get("required") or {}).get(name)
        if definition is None:
            definition = (definitions.get("optional") or {}).get(name)
        if not _is_scalar_input(definition):
            continue
        if named_widgets and name in named_widgets:
            inputs[name] = named_widgets[name]
            if widget_index < len(widget_values):
                widget_index += 1
            continue
        if widget_index >= len(widget_values):
            continue
        value = widget_values[widget_index]
        widget_index += 1
        if (
            name in {"seed", "noise_seed"}
            and widget_index < len(widget_values)
            and widget_values[widget_index] in _CONTROL_VALUES
        ):
            widget_index += 1
        inputs[name] = value
    return widget_index


def _is_scalar_input(definition: object) -> bool:
    if not isinstance(definition, list) or not definition:
        return False
    value = definition[0]
    return isinstance(value, list) or value in {
        "INT",
        "FLOAT",
        "STRING",
        "BOOLEAN",
        "COMBO",
        "COMFY_DYNAMICCOMBO_V3",
    }


def _input_value_matches(value: object, definition: object) -> bool:
    if not isinstance(definition, list) or not definition:
        return True
    input_type = definition[0]
    options = definition[1].get("options") if (
        len(definition) > 1 and isinstance(definition[1], dict)
    ) else None
    if isinstance(input_type, list):
        options = input_type
        input_type = "COMBO"
    if isinstance(options, list) and value not in options:
        return False
    if input_type == "INT":
        return isinstance(value, int) and not isinstance(value, bool)
    if input_type == "FLOAT":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
        )
    if input_type == "BOOLEAN":
        return isinstance(value, bool)
    if input_type == "STRING":
        return isinstance(value, str)
    if input_type in {"COMBO", "COMFY_DYNAMICCOMBO_V3"}:
        return isinstance(value, (str, int, float, bool))
    return True


def _input_default(definition: object) -> object | None:
    if (
        isinstance(definition, list)
        and len(definition) > 1
        and isinstance(definition[1], dict)
    ):
        return definition[1].get("default")
    return None
