"use client";

import {
  ArrowRight,
  CheckCircle2,
  FileText as FileReferenceIcon,
  FlaskConical,
  Image as ImageIcon,
  Link2,
  LoaderCircle,
  Music2 as Music2Icon,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  Trash2,
  Video as VideoIcon,
  Workflow,
  X,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  loadAssets,
  uploadAssets as uploadLibraryAssets,
} from "../../_features/assets/api";
import type { LibraryAsset } from "../../_features/assets/types";
import {
  deleteWorkflow,
  importWorkflow,
  loadWorkflowInputs,
  loadWorkflowCatalog,
  setWorkflowEnabled,
  testWorkflow,
  updateWorkflowParameters,
} from "../../_features/workflows/api";
import type {
  ImportedWorkflow,
  WorkflowCatalogItem,
  WorkflowInput,
  WorkflowParameter,
  WorkflowTopology,
} from "../../_features/workflows/types";
import { backendResourceUrl } from "../../../shared/ui/backend-resource";

type WorkflowManagerProps = {
  onModelsChanged: () => Promise<void> | void;
};

type Draft = {
  name: string;
  capability:
    | "image_generation"
    | "image_processing"
    | "video_generation"
    | "video_processing"
    | "audio_processing"
    | "transcription";
};

const filters = [
  { id: "standard", label: "标准能力" },
  { id: "all", label: "全部" },
  { id: "available", label: "未导入" },
  { id: "imported", label: "已导入" },
] as const;

const standardWorkflowSpecs = [
  {
    title: "MiniMax 文生图",
    description: "无参考图，生成角色、场景、道具与关键帧资产。",
    capability: "image_generation" as const,
    references: "0 张参考",
    filenames: ["MiniMax文生图.json", "mivo_std_minimax_h3_image_t2i.json"],
  },
  {
    title: "MiniMax 多图参考生图",
    description: "传入 1–10 张图，按人物、服装、场景、风格顺序自适应裁剪。",
    capability: "image_generation" as const,
    references: "1–10 张参考",
    filenames: ["mivo_std_minimax_h3_image_multiref.json"],
  },
  {
    title: "MiniMax 文生视频",
    description: "纯文本驱动动作、镜头、氛围与声音，适合预演。",
    capability: "video_generation" as const,
    references: "0 张参考",
    filenames: ["mivo_std_minimax_h3_video_t2v.json"],
  },
  {
    title: "MiniMax 首尾帧视频",
    description: "固定两张首尾帧，生成平滑动作与镜头过渡。",
    capability: "video_generation" as const,
    references: "严格 2 张",
    filenames: [
      "MiniMax首尾帧视频生成.json",
      "mivo_std_minimax_h3_video_flf2v.json",
    ],
  },
  {
    title: "MiniMax 多参考生视频",
    description: "混合传入 9 图、3 视频、3 音频，保持角色、动作、场景与声音连续。",
    capability: "video_generation" as const,
    references: "9 图 / 3 视频 / 3 音频",
    filenames: ["mivo_std_minimax_h3_video_multiref.json"],
  },
  {
    title: "音频四轨分离",
    description: "把混合音频拆成贝斯、鼓、其他与 vocals，用于对白提取、伴奏和后期混音。",
    capability: "audio_processing" as const,
    references: "1 条音频 → 4 轨",
    filenames: ["mivo_std_audio_separation.json"],
  },
  {
    title: "视频透明抠像 WebM",
    description: "逐帧移除背景，输出带 Alpha 的 VP9 WebM，并自动沿用源视频帧率。",
    capability: "video_processing" as const,
    references: "1 个源视频",
    filenames: ["mivo_std_video_matting.json"],
  },
];

const testAssetTypeConfig = {
  image: { label: "测试参考图片", noun: "图片", accept: "image/*" },
  video: { label: "测试参考视频", noun: "视频", accept: "video/*" },
  audio: { label: "测试参考音频", noun: "音频", accept: "audio/*" },
  file: { label: "测试参考文件", noun: "文件", accept: "*/*" },
} as const;

const utilityWorkflowSpecs = [
  {
    title: "透明背景抠图",
    description: "人物或道具透明化",
    capability: "image_processing" as const,
    filenames: ["mivo_std_remove_background.json"],
  },
  {
    title: "提取视频首帧",
    description: "从视频提取起始画面",
    capability: "image_processing" as const,
    filenames: ["mivo_std_extract_first_frame.json"],
  },
  {
    title: "提取视频尾帧",
    description: "从视频提取结束画面",
    capability: "image_processing" as const,
    filenames: ["mivo_std_extract_last_frame.json"],
  },
  {
    title: "图片放大与细节增强",
    description: "4× 放大并补充纹理细节",
    capability: "image_processing" as const,
    filenames: ["mivo_std_image_upscale.json"],
  },
  {
    title: "视频补帧至 60fps",
    description: "RIFE 补齐中间帧，保留镜头时长",
    capability: "video_processing" as const,
    filenames: ["mivo_std_video_interpolate.json"],
  },
  {
    title: "语音转字幕时间轴",
    description: "Whisper 转写并返回分段 cue",
    capability: "transcription" as const,
    filenames: ["mivo_std_transcription.json"],
  },
];

export function WorkflowManager({ onModelsChanged }: WorkflowManagerProps) {
  const [items, setItems] = useState<WorkflowCatalogItem[]>([]);
  const [comfyuiUrl, setComfyuiUrl] = useState("");
  const [catalogError, setCatalogError] = useState("");
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] =
    useState<(typeof filters)[number]["id"]>("standard");
  const [search, setSearch] = useState("");
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [busyFile, setBusyFile] = useState<string | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testPrompt, setTestPrompt] = useState(
    "A cinematic scene with soft natural lighting, highly detailed",
  );
  const [results, setResults] = useState<Record<string, ImportedWorkflow>>({});
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [editingId, setEditingId] = useState<string | null>(null);
  const [parameterDrafts, setParameterDrafts] = useState<
    Record<string, WorkflowParameter[]>
  >({});
  const [inputCatalogs, setInputCatalogs] = useState<
    Record<string, WorkflowInput[]>
  >({});
  const [inputTopologies, setInputTopologies] = useState<
    Record<string, WorkflowTopology>
  >({});
  const [loadingInputsId, setLoadingInputsId] = useState<string | null>(null);
  const [inputSearch, setInputSearch] = useState("");
  const [testLibraryAssets, setTestLibraryAssets] = useState<LibraryAsset[]>([]);
  const [testAssetIds, setTestAssetIds] = useState<Record<string, string[]>>(
    {},
  );
  const [uploadingTestAssets, setUploadingTestAssets] = useState(false);

  async function refresh() {
    setLoading(true);
    setCatalogError("");
    try {
      const catalog = await loadWorkflowCatalog();
      setComfyuiUrl(catalog.comfyuiUrl);
      setItems(catalog.workflows);
      if (!catalog.available) setCatalogError(catalog.error || "ComfyUI 不可用");
      setDrafts((current) => {
        const next = { ...current };
        for (const item of catalog.workflows) {
          if (!next[item.filename]) {
            const standard = [
              ...standardWorkflowSpecs,
              ...utilityWorkflowSpecs,
            ].find((spec) => spec.filenames.includes(item.filename));
            next[item.filename] = {
              name: standard?.title ?? item.name,
              capability:
                standard?.capability === "audio_processing" ||
                item.capability === "audio_processing"
                  ? "audio_processing"
                  : standard?.capability === "image_processing" ||
                      item.capability === "image_processing"
                    ? "image_processing"
                  : item.capability === "transcription"
                    ? "transcription"
                  : standard?.capability === "video_processing" ||
                      item.capability === "video_processing"
                    ? "video_processing"
                    : standard?.capability === "video_generation" ||
                      item.capability === "video_generation"
                    ? "video_generation"
                    : "image_generation",
            };
          }
        }
        return next;
      });
    } catch (error) {
      setCatalogError((error as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    void refreshTestAssets();
  }, []);

  useEffect(() => {
    if (!editingId) return;
    const frame = window.requestAnimationFrame(() => {
      document
        .getElementById("workflow-configurator")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [editingId]);

  const visibleItems = useMemo(() => {
    const query = search.trim().toLowerCase();
    return items.filter((item) => {
      if (
        filter === "standard" &&
        !standardWorkflowSpecs.some((spec) =>
          spec.filenames.includes(item.filename),
        )
      ) {
        return false;
      }
      if (filter === "available" && item.imported) return false;
      if (filter === "imported" && !item.imported) return false;
      return !query || item.filename.toLowerCase().includes(query);
    });
  }, [filter, items, search]);

  const standardItems = useMemo(
    () =>
      standardWorkflowSpecs.map((spec) => ({
        spec,
        item:
          spec.filenames
            .map((filename) =>
              items.find((item) => item.filename === filename),
            )
            .find(Boolean) ?? null,
      })),
    [items],
  );
  const utilityItems = useMemo(
    () =>
      utilityWorkflowSpecs.map((spec) => ({
        spec,
        item:
          spec.filenames
            .map((filename) =>
              items.find((item) => item.filename === filename),
            )
            .find(Boolean) ?? null,
      })),
    [items],
  );

  const editingItem = useMemo(
    () =>
      editingId
        ? items.find((item) => item.workflowId === editingId) ?? null
        : null,
    [editingId, items],
  );
  const editingInputs = useMemo(() => {
    const query = inputSearch.trim().toLowerCase();
    const inputs = editingId ? inputCatalogs[editingId] ?? [] : [];
    if (!query) return inputs;
    return inputs.filter((input) =>
      [
        input.nodeId,
        input.nodeType,
        input.nodeTitle,
        input.field,
        input.fieldLabel,
        input.type,
        input.assetType,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(query),
    );
  }, [editingId, inputCatalogs, inputSearch]);

  async function importItem(item: WorkflowCatalogItem) {
    const draft = drafts[item.filename];
    if (!draft) return;
    setBusyFile(item.filename);
    setRowErrors((current) => ({ ...current, [item.filename]: "" }));
    try {
      await importWorkflow(item.filename, draft.name, draft.capability);
      await refresh();
      await onModelsChanged();
    } catch (error) {
      setRowErrors((current) => ({
        ...current,
        [item.filename]: (error as Error).message,
      }));
    } finally {
      setBusyFile(null);
    }
  }

  async function refreshTestAssets() {
    try {
      const library = await loadAssets(200);
      setTestLibraryAssets(library.assets);
    } catch {
      // The workflow test remains available for workflows without references.
    }
  }

  function addTestAsset(workflowId: string, assetId: string) {
    if (!assetId) return;
    setTestAssetIds((current) => {
      const selected = current[workflowId] ?? [];
      if (selected.includes(assetId)) return current;
      return { ...current, [workflowId]: [...selected, assetId] };
    });
  }

  function removeTestAsset(workflowId: string, assetId: string) {
    setTestAssetIds((current) => ({
      ...current,
      [workflowId]: (current[workflowId] ?? []).filter(
        (item) => item !== assetId,
      ),
    }));
  }

  async function uploadTestAssets(workflowId: string, files: File[]) {
    if (!files.length) return;
    setUploadingTestAssets(true);
    setRowErrors((current) => ({ ...current, [workflowId]: "" }));
    try {
      const uploaded = await uploadLibraryAssets(files);
      await refreshTestAssets();
      setTestAssetIds((current) => ({
        ...current,
        [workflowId]: [
          ...(current[workflowId] ?? []),
          ...uploaded.assetIds,
        ],
      }));
    } catch (error) {
      setRowErrors((current) => ({
        ...current,
        [workflowId]: (error as Error).message,
      }));
    } finally {
      setUploadingTestAssets(false);
    }
  }

  async function runTest(item: WorkflowCatalogItem) {
    if (!item.workflowId) return;
    const referenceParameters = item.parameters.filter(
      (parameter) => parameter.type === "assets",
    );
    const selectedAssets = testAssetIds[item.workflowId] ?? [];
    const selectedByType = selectedAssets.reduce<Record<string, number>>(
      (counts, assetId) => {
        const type = testLibraryAssets.find(
          (asset) => asset.id === assetId,
        )?.type;
        if (type) counts[type] = (counts[type] ?? 0) + 1;
        return counts;
      },
      {},
    );
    const insufficient = referenceParameters.find(
      (parameter) =>
        (parameter.min ?? 0) >
        (selectedByType[parameter.assetType ?? "image"] ?? 0),
    );
    if (insufficient) {
      setRowErrors((current) => ({
        ...current,
        [item.filename]: `${insufficient.label}至少需要 ${
          insufficient.min ?? 0
        } 个素材`,
      }));
      return;
    }
    if (
      referenceParameters.length > 0 &&
      selectedAssets.length === 0
    ) {
      setRowErrors((current) => ({
        ...current,
        [item.filename]: "测试至少需要 1 个参考素材",
      }));
      return;
    }
    setTestingId(item.workflowId);
    setRowErrors((current) => ({ ...current, [item.filename]: "" }));
    try {
      const result = await testWorkflow(
        item.workflowId,
        testPrompt,
        selectedAssets,
      );
      setResults((current) => ({ ...current, [item.filename]: result }));
      await refresh();
      await onModelsChanged();
    } catch (error) {
      setRowErrors((current) => ({
        ...current,
        [item.filename]: (error as Error).message,
      }));
    } finally {
      setTestingId(null);
    }
  }

  async function toggle(item: WorkflowCatalogItem) {
    if (!item.workflowId) return;
    setBusyFile(item.filename);
    try {
      const enabled = item.status === "disabled";
      await setWorkflowEnabled(item.workflowId, enabled);
      await refresh();
      await onModelsChanged();
    } catch (error) {
      setRowErrors((current) => ({
        ...current,
        [item.filename]: (error as Error).message,
      }));
    } finally {
      setBusyFile(null);
    }
  }

  async function removeWorkflow(item: WorkflowCatalogItem) {
    if (!item.workflowId) return;
    const confirmed = window.confirm(
      `删除已导入的工作流“${item.name}”？\n\nComfyUI 原始 JSON 文件不会被删除，只删除造境中的模型注册和参数配置。`,
    );
    if (!confirmed) return;
    setBusyFile(item.filename);
    setRowErrors((current) => ({ ...current, [item.filename]: "" }));
    try {
      await deleteWorkflow(item.workflowId);
      if (editingId === item.workflowId) setEditingId(null);
      await refresh();
      await onModelsChanged();
    } catch (error) {
      setRowErrors((current) => ({
        ...current,
        [item.filename]: (error as Error).message,
      }));
    } finally {
      setBusyFile(null);
    }
  }

  async function editParameters(item: WorkflowCatalogItem) {
    if (!item.workflowId) return;
    setEditingId(item.workflowId);
    setInputSearch("");
    setLoadingInputsId(item.workflowId);
    setRowErrors((current) => ({ ...current, [item.filename]: "" }));
    try {
      const catalog = await loadWorkflowInputs(item.workflowId);
      setInputCatalogs((current) => ({
        ...current,
        [item.workflowId!]: catalog.inputs,
      }));
      setInputTopologies((current) => ({
        ...current,
        [item.workflowId!]: catalog.topology,
      }));
      setParameterDrafts((current) => ({
        ...current,
        [item.workflowId!]: structuredClone(
          catalog.parameters ?? [],
        ).map((parameter) => ({
          ...parameter,
          semanticKey:
            parameter.semanticKey ?? inferSemanticRole(parameter),
        })),
      }));
    } catch (error) {
      setEditingId(null);
      setRowErrors((current) => ({
        ...current,
        [item.filename]: (error as Error).message,
      }));
    } finally {
      setLoadingInputsId(null);
    }
  }

  async function saveParameters(item: WorkflowCatalogItem) {
    if (!item.workflowId) return;
    const parameters = parameterDrafts[item.workflowId] ?? [];
    const invalid = parameters.find(
      (parameter) => !parameter.key.trim() || !parameter.bindings?.length,
    );
    if (invalid) {
      setRowErrors((current) => ({
        ...current,
        [item.filename]: `参数“${invalid.label || invalid.key || "未命名"}”必须先绑定一个工作流输入`,
      }));
      return;
    }
    setBusyFile(item.filename);
    setRowErrors((current) => ({ ...current, [item.filename]: "" }));
    try {
      await updateWorkflowParameters(
        item.workflowId,
        parameters,
      );
      setEditingId(null);
      await refresh();
      await onModelsChanged();
    } catch (error) {
      setRowErrors((current) => ({
        ...current,
        [item.filename]: (error as Error).message,
      }));
    } finally {
      setBusyFile(null);
    }
  }

  function updateParameterDraft(
    workflowId: string,
    index: number,
    update: (parameter: WorkflowParameter) => void,
  ) {
    setParameterDrafts((current) => {
      const next = structuredClone(current[workflowId] ?? []);
      if (!next[index]) return current;
      update(next[index]);
      return { ...current, [workflowId]: next };
    });
  }

  function addParameter(item: WorkflowCatalogItem) {
    if (!item.workflowId) return;
    setParameterDrafts((current) => {
      const next = structuredClone(current[item.workflowId!] ?? []);
      const sequence = next.length + 1;
      next.push({
        key: `parameter_${sequence}`,
        label: `参数 ${sequence}`,
        type: "string",
        semanticKey: `parameter_${sequence}`,
        required: false,
        bindings: [],
      });
      return { ...current, [item.workflowId!]: next };
    });
  }

  function addInputAsParameter(
    item: WorkflowCatalogItem,
    input: WorkflowInput,
  ) {
    if (!item.workflowId) return;
    setParameterDrafts((current) => {
      const next = structuredClone(current[item.workflowId!] ?? []);
      const inputBindings =
        input.bindings && input.bindings.length
          ? input.bindings
          : [{ nodeId: input.nodeId, field: input.field }];
      if (
        next.some((parameter) =>
          (parameter.bindings ?? []).some(
            (binding) =>
              inputBindings.some(
                (candidate) =>
                  binding.nodeId === candidate.nodeId &&
                  binding.field === candidate.field,
              ),
          ),
        )
      ) {
        return current;
      }
      const baseKey =
        input.field
          .trim()
          .replace(/[^\w]+/g, "_")
          .replace(/^_+|_+$/g, "") || "parameter";
      let key = baseKey;
      let suffix = 2;
      while (next.some((parameter) => parameter.key === key)) {
        key = `${baseKey}_${suffix}`;
        suffix += 1;
      }
      next.push({
        key,
        label:
          input.fieldLabel && input.fieldLabel !== input.field
            ? `${input.nodeTitle} · ${input.fieldLabel}`
            : `${input.nodeTitle} · ${input.field}`,
        type: input.type,
        semanticKey: inferSemanticRole({
          key,
          label: input.fieldLabel,
        }),
        assetType: input.type === "assets" ? input.assetType ?? "image" : undefined,
        required: false,
        default: input.type === "assets" ? undefined : input.default,
        options: input.options,
        bindings: inputBindings.map((binding, index) => ({
          ...binding,
          ...(input.type === "assets" ? { assetIndex: index } : {}),
        })),
      });
      return { ...current, [item.workflowId!]: next };
    });
  }

  function addReference(
    item: WorkflowCatalogItem,
    assetType: NonNullable<WorkflowParameter["assetType"]>,
  ) {
    if (!item.workflowId) return;
    const labels = {
      image: "图片参考",
      video: "视频参考",
      audio: "音频 / 语音参考",
      file: "文件参考",
    };
    setParameterDrafts((current) => {
      const next = structuredClone(current[item.workflowId!] ?? []);
      const sequence = next.filter(
        (parameter) => parameter.type === "assets",
      ).length + 1;
      next.push({
        key: `${assetType}References${sequence}`,
        label: `${labels[assetType]} ${sequence}`,
        type: "assets",
        assetType,
        required: true,
        min: 1,
        max: 1,
        bindings: [],
      });
      return { ...current, [item.workflowId!]: next };
    });
  }

  function addParameterBinding(
    item: WorkflowCatalogItem,
    parameterIndex: number,
  ) {
    if (!item.workflowId) return;
    const inputs = inputCatalogs[item.workflowId] ?? [];
    updateParameterDraft(item.workflowId, parameterIndex, (parameter) => {
      const used = new Set(
        (parameter.bindings ?? []).map(
          (binding) => `${binding.nodeId}:${binding.field}`,
        ),
      );
      const input =
        inputs.find(
          (candidate) =>
            !used.has(candidate.id) &&
            parameter.type === "assets" &&
            candidate.assetType === parameter.assetType,
        ) ??
        inputs.find((candidate) => !used.has(candidate.id)) ??
        inputs[0];
      if (!input) return;
      parameter.bindings = [
        ...(parameter.bindings ?? []),
        {
          nodeId: input.nodeId,
          field: input.field,
          ...(parameter.type === "assets"
            ? { assetIndex: countAssetBindings(parameter.bindings) }
            : {}),
        },
      ];
      applyInputMetadata(parameter, input);
    });
  }

  function selectParameterBinding(
    item: WorkflowCatalogItem,
    parameterIndex: number,
    bindingIndex: number,
    inputId: string,
  ) {
    if (!item.workflowId) return;
    const input = (inputCatalogs[item.workflowId] ?? []).find(
      (candidate) => candidate.id === inputId,
    );
    if (!input) return;
    updateParameterDraft(item.workflowId, parameterIndex, (parameter) => {
      const bindings = parameter.bindings ?? [];
      bindings[bindingIndex] = {
        nodeId: input.nodeId,
        field: input.field,
        ...(input.type === "assets"
          ? { assetIndex: countAssetBindings(bindings) }
          : {}),
      };
      parameter.bindings = bindings;
      applyInputMetadata(parameter, input);
    });
  }

  function removeParameterBinding(
    item: WorkflowCatalogItem,
    parameterIndex: number,
    bindingIndex: number,
  ) {
    if (!item.workflowId) return;
    updateParameterDraft(item.workflowId, parameterIndex, (parameter) => {
      parameter.bindings = (parameter.bindings ?? []).filter(
        (_, index) => index !== bindingIndex,
      );
      reindexAssetBindings(parameter);
    });
  }

  function removeParameter(item: WorkflowCatalogItem, parameterIndex: number) {
    if (!item.workflowId) return;
    setParameterDrafts((current) => ({
      ...current,
      [item.workflowId!]: (current[item.workflowId!] ?? []).filter(
        (_, index) => index !== parameterIndex,
      ),
    }));
  }

  return (
    <section
      className={`workbench-panel workflow-manager${
        editingItem ? " is-editing" : ""
      }`}
    >
      <div className="workflow-manager-head">
        <div>
          <span className="eyebrow">ComfyUI 工作流模型</span>
          <h2>扫描、导入和测试本机工作流</h2>
          <p>
            来源：{loading ? "正在连接 ComfyUI…" : comfyuiUrl || "未连接"}。导入后从工作流全部输入中手动选择提示词、
            尺寸、种子、模型文件和素材槽位，组成你自己的模型参数。
          </p>
        </div>
        <button type="button" onClick={() => void refresh()} disabled={loading}>
          <RefreshCw className={loading ? "spin" : ""} size={15} />
          重新扫描
        </button>
      </div>

      <div className="workflow-standard-section">
        <div className="workflow-standard-head">
          <div>
            <span className="eyebrow">推荐入口</span>
            <h3>{standardWorkflowSpecs.length} 种标准创作能力</h3>
            <p>先选任务类型，再进入参数和参考素材配置。</p>
          </div>
          <span>
            {loading
              ? "正在扫描"
              : `${standardItems.filter(({ item }) => item?.imported).length} / ${standardWorkflowSpecs.length} 已导入`}
          </span>
        </div>
        <div className="workflow-standard-grid">
          {standardItems.map(({ spec, item }) => {
            const Icon =
              spec.capability === "video_generation" ||
              spec.capability === "video_processing"
                ? VideoIcon
                : spec.capability === "audio_processing"
                  ? Music2Icon
                  : ImageIcon;
            return (
              <article
                className={`workflow-standard-card ${
                  item?.imported ? "ready" : ""
                }`}
                key={spec.title}
              >
                <div className="workflow-standard-card-top">
                  <span className="workflow-standard-icon">
                    <Icon size={18} />
                  </span>
                  <span className={`workflow-standard-status ${item?.status ?? ""}`}>
                    {loading && !item
                      ? "加载中"
                      : item?.imported
                      ? item.status === "ready"
                        ? "已就绪"
                        : item.status === "untested"
                          ? "待测试"
                          : item.status === "failed"
                            ? "测试失败"
                            : "已停用"
                      : "未导入"}
                  </span>
                </div>
                <h4>{spec.title}</h4>
                <p>{spec.description}</p>
                <div className="workflow-standard-meta">
                  <span>{spec.references}</span>
                  <span>
                    {capabilityLabel(spec.capability)}
                  </span>
                </div>
                {item?.imported ? (
                  <div className="workflow-standard-actions">
                    <button
                      type="button"
                      onClick={() => void editParameters(item)}
                    >
                      <Link2 size={13} />
                      配置生成页
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setFilter("all");
                        setSearch(item.filename);
                      }}
                    >
                      管理
                    </button>
                  </div>
                ) : (
                  <button
                    className="workflow-standard-import"
                    type="button"
                    disabled={!item || busyFile === item.filename}
                    onClick={() => item && void importItem(item)}
                  >
                    {item && busyFile === item.filename ? (
                      <LoaderCircle className="spin" size={14} />
                    ) : (
                      <Plus size={14} />
                    )}
                    {loading ? "扫描中…" : "导入标准模型"}
                  </button>
                )}
              </article>
            );
          })}
        </div>
        <div className="workflow-utility-row">
          <span>制作工具</span>
          {utilityItems.map(({ spec, item }) => (
            <button
              key={spec.title}
              type="button"
              disabled={!item?.workflowId}
              onClick={() => {
                if (!item) return;
                setFilter("all");
                setSearch(item.filename);
              }}
            >
              <strong>{spec.title}</strong>
              <small>
                {spec.description} · {item?.status === "ready" ? "可用" : "待测试"}
              </small>
            </button>
          ))}
        </div>
      </div>

      <div className="workflow-controls">
        <div className="model-filter-bar">
          {filters.map((item) => (
            <button
              key={item.id}
              className={filter === item.id ? "active" : ""}
              type="button"
              onClick={() => setFilter(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <label className="workflow-search">
          <Search size={15} />
          <input
            aria-label="搜索 ComfyUI 工作流"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="按工作流文件名搜索"
          />
        </label>
        {filter !== "standard" && (
          <label className="workflow-test-prompt">
            <span>测试提示词</span>
            <input
              value={testPrompt}
              onChange={(event) => setTestPrompt(event.target.value)}
            />
          </label>
        )}
      </div>

      {filter !== "standard" && (
        <div className="workflow-table-head" aria-hidden="true">
          <span>工作流文件</span>
          <span>模型名称</span>
          <span>类型</span>
          <span>操作</span>
        </div>
      )}

      {catalogError && (
        <div className="generation-error">
          <XCircle size={16} />
          <span>{catalogError}</span>
        </div>
      )}

      {filter !== "standard" && (
      <div className="workflow-list">
        {visibleItems.map((item) => {
          const draft = drafts[item.filename] ?? {
            name: item.name,
            capability: "image_generation" as const,
          };
          const result = results[item.filename];
          const testAssetPath = result?.testAssetUrl ??
            (item.testAssetId ? `/api/assets/${item.testAssetId}` : null);
          const testAssetUrl = testAssetPath
            ? backendResourceUrl(testAssetPath)
            : null;
          const referenceParameters = item.parameters.filter(
            (parameter) => parameter.type === "assets",
          );
          const selectedTestAssets = item.workflowId
            ? testAssetIds[item.workflowId] ?? []
            : [];
          return (
            <article className="workflow-row" key={item.filename}>
              <div className="workflow-file">
                <span className="workflow-file-icon">
                  <Workflow size={17} />
                </span>
                <div>
                  <strong>{item.filename}</strong>
                  <small>
                    {item.imported
                      ? `已导入 · ${capabilityLabel(item.capability)}`
                      : "本机 ComfyUI 工作流"}
                  </small>
                </div>
              </div>

              {item.imported ? (
                <>
                  <div className="workflow-readonly-name">
                    <strong>{item.name}</strong>
                    <span>{capabilityLabel(item.capability)}</span>
                  </div>
                  <span className="workflow-readonly-type">
                    {capabilityLabel(item.capability)}
                  </span>
                </>
              ) : (
                <>
                  <input
                    className="workflow-name"
                    value={draft.name}
                    onChange={(event) =>
                      setDrafts((current) => ({
                        ...current,
                        [item.filename]: {
                          ...draft,
                          name: event.target.value,
                        },
                      }))
                    }
                    aria-label={`${item.filename} 模型名称`}
                  />

                  <select
                    value={draft.capability}
                    onChange={(event) =>
                      setDrafts((current) => ({
                        ...current,
                        [item.filename]: {
                          ...draft,
                          capability: event.target
                            .value as Draft["capability"],
                        },
                      }))
                    }
                    aria-label={`${item.filename} 能力`}
                  >
                    <option value="image_generation">图片模型</option>
                    <option value="image_processing">图片处理工具</option>
                    <option value="video_generation">视频模型</option>
                    <option value="video_processing">视频处理模型</option>
                    <option value="audio_processing">音频模型</option>
                    <option value="transcription">语音转字幕模型</option>
                  </select>
                </>
              )}

              <div className="workflow-actions">
                {!item.imported ? (
                  <button
                    type="button"
                    disabled={busyFile === item.filename}
                    onClick={() => void importItem(item)}
                  >
                    {busyFile === item.filename ? (
                      <LoaderCircle className="spin" size={14} />
                    ) : null}
                    导入并注册
                  </button>
                ) : (
                  <>
                    <button
                      className="test-button"
                      type="button"
                      disabled={testingId === item.workflowId}
                      onClick={() => void runTest(item)}
                    >
                      {testingId === item.workflowId ? (
                        <LoaderCircle className="spin" size={14} />
                      ) : (
                        <FlaskConical size={14} />
                      )}
                      测试
                    </button>
                    <button
                      type="button"
                      disabled={loadingInputsId === item.workflowId}
                      onClick={() => void editParameters(item)}
                    >
                      {loadingInputsId === item.workflowId ? (
                        <LoaderCircle className="spin" size={14} />
                      ) : (
                        <Link2 size={14} />
                      )}
                      配置生成页
                    </button>
                    <button
                      type="button"
                      disabled={
                        item.status === "untested" ||
                        item.status === "failed"
                      }
                      onClick={() => void toggle(item)}
                    >
                      {item.status === "untested"
                        ? "待测试"
                        : item.status === "failed"
                          ? "测试失败"
                        : item.status === "disabled"
                          ? "启用"
                          : "停用"}
                    </button>
                    <button
                      className="workflow-delete-button"
                      type="button"
                      disabled={busyFile === item.filename}
                      onClick={() => void removeWorkflow(item)}
                    >
                      <Trash2 size={14} />
                      删除
                    </button>
                  </>
                )}
              </div>

              {item.workflowId &&
                referenceParameters.map((referenceParameter) => {
                  const assetType =
                    referenceParameter.assetType ?? "image";
                  const config = testAssetTypeConfig[assetType];
                  const assetsOfType = testLibraryAssets.filter(
                    (asset) => asset.type === assetType,
                  );
                  const selectedOfType = selectedTestAssets.filter(
                    (assetId) =>
                      assetsOfType.some((asset) => asset.id === assetId),
                  );
                  return (
                    <div
                      className="workflow-test-assets"
                      key={referenceParameter.key}
                    >
                      <div className="workflow-test-assets-head">
                        <span>{config.label}</span>
                        <small>
                          需要 {referenceParameter.min ?? 0}
                          {referenceParameter.max !==
                          referenceParameter.min
                            ? `–${referenceParameter.max}`
                            : ""}{" "}
                          个 · 已选 {selectedOfType.length} 个
                        </small>
                      </div>
                      <div className="workflow-test-asset-controls">
                        <select
                          value=""
                          aria-label={`${item.name} 添加${config.noun}`}
                          onChange={(event) =>
                            addTestAsset(
                              item.workflowId!,
                              event.target.value,
                            )
                          }
                        >
                          <option value="">
                            从素材库选择{config.noun}…
                          </option>
                          {assetsOfType
                            .filter(
                              (asset) =>
                                !selectedTestAssets.includes(asset.id),
                            )
                            .map((asset) => (
                              <option key={asset.id} value={asset.id}>
                                {assetName(asset)}
                              </option>
                            ))}
                        </select>
                        <label className="workflow-test-upload">
                          {uploadingTestAssets ? (
                            <LoaderCircle className="spin" size={14} />
                          ) : (
                            <Plus size={14} />
                          )}
                          上传{config.noun}
                          <input
                            type="file"
                            accept={config.accept}
                            multiple
                            disabled={uploadingTestAssets}
                            onChange={(event) => {
                              void uploadTestAssets(
                                item.workflowId!,
                                Array.from(event.target.files ?? []),
                              );
                              event.target.value = "";
                            }}
                          />
                        </label>
                      </div>
                      {selectedOfType.length > 0 && (
                        <div className="workflow-test-asset-list">
                          {selectedOfType.map((assetId, index) => {
                            const asset = assetsOfType.find(
                              (candidate) => candidate.id === assetId,
                            );
                            return (
                              <button
                                key={assetId}
                                type="button"
                                title={`移除测试${config.noun}`}
                                onClick={() =>
                                  removeTestAsset(
                                    item.workflowId!,
                                    assetId,
                                  )
                                }
                              >
                                {assetType === "image" ? (
                                  <img
                                    src={
                                      backendResourceUrl(
                                        asset?.url ?? `/api/assets/${assetId}`,
                                      )
                                    }
                                    alt={`测试参考${config.noun} ${index + 1}`}
                                  />
                                ) : (
                                  <span className="workflow-test-file-preview">
                                    {assetType === "video" ? (
                                      <VideoIcon size={20} />
                                    ) : (
                                      <Music2Icon size={20} />
                                    )}
                                  </span>
                                )}
                                <span>{index + 1}</span>
                                <X size={12} />
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}

              {rowErrors[item.filename] && (
                <p className="workflow-row-error">{rowErrors[item.filename]}</p>
              )}
              {testAssetUrl && (
                <div className="workflow-test-result">
                  <CheckCircle2 size={15} />
                  <span>{result?.testMessage || item.testMessage || "测试通过"}</span>
                  {[
                    "video_generation",
                    "video_processing",
                  ].includes(result?.capability ?? item.capability ?? "") ? (
                    <video src={testAssetUrl} controls />
                  ) : (result?.capability ?? item.capability) ===
                    "audio_processing" ? (
                    <audio src={testAssetUrl} controls />
                  ) : (result?.capability ?? item.capability) ===
                    "transcription" ? (
                    <a href={testAssetUrl} target="_blank" rel="noreferrer">
                      查看 / 下载字幕 JSON
                    </a>
                  ) : (
                    <img src={testAssetUrl} alt="工作流测试结果" />
                  )}
                </div>
              )}
              {item.workflowId && editingId === "__legacy_inline_editor__" && (
                <div className="workflow-parameter-editor">
                  <div className="workflow-parameter-editor-head">
                    <div>
                      <strong>模型参数设计器</strong>
                      <span>
                        从工作流全部输入中选择字段。参数会显示在生成页，提交前执行必填、类型和范围校验。
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => addParameter(item)}
                    >
                      <Plus size={14} />
                      新建参数
                    </button>
                  </div>
                  <p className="workflow-parameter-summary">
                    已解析 {inputCatalogs[item.workflowId!]?.length ?? 0} 个可用输入。
                    没有自动识别的参数也可以在这里手动绑定。
                  </p>
                  <div className="workflow-reference-presets">
                    <button
                      type="button"
                      onClick={() => addReference(item, "image")}
                    >
                      <ImageIcon size={13} /> 图片参考
                    </button>
                    <button
                      type="button"
                      onClick={() => addReference(item, "video")}
                    >
                      <VideoIcon size={13} /> 视频参考
                    </button>
                    <button
                      type="button"
                      onClick={() => addReference(item, "audio")}
                    >
                      <Music2Icon size={13} /> 音频参考
                    </button>
                    <button
                      type="button"
                      onClick={() => addReference(item, "file")}
                    >
                      <FileReferenceIcon size={13} /> 文件参考
                    </button>
                  </div>
                  {(parameterDrafts[item.workflowId] ?? []).length === 0 && (
                    <div className="workflow-parameter-empty">
                      还没有模型参数。点击“新建参数”，选择提示词、尺寸、种子或素材节点。
                    </div>
                  )}
                  {(parameterDrafts[item.workflowId] ?? []).map(
                    (parameter, index) => (
                      <div className="workflow-parameter-card" key={index}>
                        <div className="workflow-parameter-card-head">
                          <div>
                            <strong>{parameter.label || "未命名参数"}</strong>
                            <code>{parameter.key || "no_key"}</code>
                          </div>
                          <button
                            type="button"
                            title="删除参数"
                            onClick={() => removeParameter(item, index)}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                        <div className="workflow-parameter-fields">
                          <label>
                            <span>参数 key</span>
                            <input
                              value={parameter.key}
                              onChange={(event) =>
                                updateParameterDraft(
                                  item.workflowId!,
                                  index,
                                  (draft) => {
                                    draft.key = event.target.value;
                                  },
                                )
                              }
                            />
                          </label>
                          <label>
                            <span>显示名称</span>
                            <input
                              value={parameter.label}
                              onChange={(event) =>
                                updateParameterDraft(
                                  item.workflowId!,
                                  index,
                                  (draft) => {
                                    draft.label = event.target.value;
                                  },
                                )
                              }
                            />
                          </label>
                          <label>
                            <span>类型</span>
                            <select
                              value={parameter.type}
                              onChange={(event) =>
                                updateParameterDraft(
                                  item.workflowId!,
                                  index,
                                  (draft) => {
                                    draft.type = event.target.value as WorkflowParameter["type"];
                                    if (draft.type === "assets") {
                                      draft.assetType =
                                        draft.assetType ?? "image";
                                      reindexAssetBindings(draft);
                                    }
                                  },
                                )
                              }
                            >
                              <option value="string">文本</option>
                              <option value="integer">整数</option>
                              <option value="number">小数</option>
                              <option value="boolean">开关</option>
                              <option value="assets">素材引用</option>
                            </select>
                          </label>
                          {parameter.type === "assets" && (
                            <label>
                              <span>素材引用类型</span>
                              <select
                                value={parameter.assetType ?? "image"}
                                onChange={(event) =>
                                  updateParameterDraft(
                                    item.workflowId!,
                                    index,
                                    (draft) => {
                                      draft.assetType = event.target
                                        .value as NonNullable<
                                        WorkflowParameter["assetType"]
                                      >;
                                    },
                                  )
                                }
                              >
                                <option value="image">图片参考</option>
                                <option value="video">视频参考</option>
                                <option value="audio">音频 / 语音参考</option>
                                <option value="file">其他文件参考</option>
                              </select>
                            </label>
                          )}
                          <label>
                            <span>默认值</span>
                            <input
                              value={String(parameter.default ?? "")}
                              disabled={parameter.type === "assets"}
                              onChange={(event) =>
                                updateParameterDraft(
                                  item.workflowId!,
                                  index,
                                  (draft) => {
                                    draft.default = event.target.value;
                                  },
                                )
                              }
                            />
                          </label>
                          <label className="parameter-required">
                            <span>必填</span>
                            <input
                              type="checkbox"
                              checked={parameter.required}
                              onChange={(event) =>
                                updateParameterDraft(
                                  item.workflowId!,
                                  index,
                                  (draft) => {
                                    draft.required = event.target.checked;
                                  },
                                )
                              }
                            />
                          </label>
                          {(parameter.type === "integer" ||
                            parameter.type === "number" ||
                            parameter.type === "assets") && (
                            <>
                              <label>
                                <span>最小值</span>
                                <input
                                  type="number"
                                  value={parameter.min ?? ""}
                                  onChange={(event) =>
                                    updateParameterDraft(
                                      item.workflowId!,
                                      index,
                                      (draft) => {
                                        draft.min = numberOrUndefined(
                                          event.target.value,
                                        );
                                      },
                                    )
                                  }
                                />
                              </label>
                              <label>
                                <span>最大值</span>
                                <input
                                  type="number"
                                  value={parameter.max ?? ""}
                                  onChange={(event) =>
                                    updateParameterDraft(
                                      item.workflowId!,
                                      index,
                                      (draft) => {
                                        draft.max = numberOrUndefined(
                                          event.target.value,
                                        );
                                      },
                                    )
                                  }
                                />
                              </label>
                            </>
                          )}
                        </div>
                        <div className="workflow-binding-list">
                          <div className="workflow-binding-title">
                            <span>绑定工作流输入</span>
                            <button
                              type="button"
                              disabled={
                                !(inputCatalogs[item.workflowId!] ?? []).length
                              }
                              onClick={() =>
                                addParameterBinding(item, index)
                              }
                            >
                              <Plus size={13} />
                              添加绑定
                            </button>
                          </div>
                          {(parameter.bindings ?? []).map(
                            (binding, bindingIndex) => (
                              <div
                                className="workflow-binding-row"
                                key={`${binding.nodeId}:${binding.field}:${bindingIndex}`}
                              >
                                <select
                                  value={`${binding.nodeId}:${binding.field}`}
                                  onChange={(event) =>
                                    selectParameterBinding(
                                      item,
                                      index,
                                      bindingIndex,
                                      event.target.value,
                                    )
                                  }
                                >
                                  {(inputCatalogs[item.workflowId!] ?? []).map(
                                    (input) => (
                                      <option key={input.id} value={input.id}>
                                        {input.label} · {input.type}
                                        {input.assetType
                                          ? ` · ${input.assetType}`
                                          : ""}
                                        {input.linked ? " · 已连线" : ""}
                                      </option>
                                    ),
                                  )}
                                </select>
                                <button
                                  type="button"
                                  title="移除绑定"
                                  onClick={() =>
                                    removeParameterBinding(
                                      item,
                                      index,
                                      bindingIndex,
                                    )
                                  }
                                >
                                  <Trash2 size={13} />
                                </button>
                              </div>
                            ),
                          )}
                        </div>
                      </div>
                    ),
                  )}
                  <div className="workflow-parameter-editor-actions">
                    <button type="button" onClick={() => setEditingId(null)}>
                      取消
                    </button>
                    <button
                      type="button"
                      disabled={busyFile === item.filename}
                      onClick={() => void saveParameters(item)}
                    >
                      保存参数
                    </button>
                  </div>
                </div>
              )}
            </article>
          );
        })}
      </div>
      )}

      {editingItem && editingItem.workflowId && (
        <WorkflowConfigurator
          item={editingItem}
          inputs={editingInputs}
          allInputs={inputCatalogs[editingItem.workflowId] ?? []}
          topology={
            inputTopologies[editingItem.workflowId] ?? {
              nodes: [],
              links: [],
            }
          }
          totalInputs={inputCatalogs[editingItem.workflowId]?.length ?? 0}
          parameters={
            parameterDrafts[editingItem.workflowId] ?? []
          }
          search={inputSearch}
          busy={busyFile === editingItem.filename}
          onChangeSearch={setInputSearch}
          onClose={() => setEditingId(null)}
          onAddParameter={() => addParameter(editingItem)}
          onAddReference={(assetType) =>
            addReference(editingItem, assetType)
          }
          onAddInput={(input) =>
            addInputAsParameter(editingItem, input)
          }
          onChangeParameter={(index, update) =>
            updateParameterDraft(
              editingItem.workflowId!,
              index,
              update,
            )
          }
          onRemoveParameter={(index) =>
            removeParameter(editingItem, index)
          }
          onAddBinding={(index) =>
            addParameterBinding(editingItem, index)
          }
          onSelectBinding={(parameterIndex, bindingIndex, inputId) =>
            selectParameterBinding(
              editingItem,
              parameterIndex,
              bindingIndex,
              inputId,
            )
          }
          onRemoveBinding={(parameterIndex, bindingIndex) =>
            removeParameterBinding(
              editingItem,
              parameterIndex,
              bindingIndex,
            )
          }
          onSave={() => void saveParameters(editingItem)}
        />
      )}

      <footer className="workflow-footer">
        已显示 {visibleItems.length} / {items.length} 个工作流。自定义输入、子图和
        网络上传节点可能需要额外适配。
      </footer>
    </section>
  );
}

type WorkflowTopologyMapProps = {
  topology: WorkflowTopology;
  boundNodeIds: Set<string>;
  activeNodeIds: Set<string>;
  selectedNodeId: string | null;
  selectedInputs: WorkflowInput[];
  boundInputKeys: Set<string>;
  onSelectNode: (nodeId: string) => void;
  onEnableInput: (input: WorkflowInput) => void;
  onCloseInspector: () => void;
};

function WorkflowTopologyMap({
  topology,
  boundNodeIds,
  activeNodeIds,
  selectedNodeId,
  selectedInputs,
  boundInputKeys,
  onSelectNode,
  onEnableInput,
  onCloseInspector,
}: WorkflowTopologyMapProps) {
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const nodes = topology.nodes.filter(
    (node) => node.mode !== 2 && node.mode !== 4,
  );
  if (nodes.length === 0) return null;
  const minX = Math.min(...nodes.map((node) => node.pos[0]));
  const minY = Math.min(...nodes.map((node) => node.pos[1]));
  const maxX = Math.max(
    ...nodes.map((node) => node.pos[0] + Math.max(node.size[0], 220)),
  );
  const maxY = Math.max(
    ...nodes.map((node) => node.pos[1] + Math.max(node.size[1], 100)),
  );
  const scale = Math.min(
    0.72,
    Math.max(
      0.38,
      Math.min(1200 / Math.max(maxX - minX, 1), 620 / Math.max(maxY - minY, 1)),
    ),
  );
  const layout = new Map(
    nodes.map((node) => {
      const width = Math.max(170, Math.min(260, node.size[0] * scale));
      return [
        node.id,
        {
          left: 36 + (node.pos[0] - minX) * scale,
          top: 30 + (node.pos[1] - minY) * scale,
          width,
          height: 46,
        },
      ];
    }),
  );
  const popoverWidth = 330;
  const selectedPosition = selectedNodeId
    ? layout.get(selectedNodeId)
    : undefined;
  const inspectorLeft = selectedPosition
    ? selectedPosition.left + selectedPosition.width + 18
    : 0;
  const inspectorTop = selectedPosition ? selectedPosition.top : 0;
  const width = Math.max(
    720,
    ...Array.from(layout.values(), (item) => item.left + item.width + 36),
    selectedPosition ? inspectorLeft + popoverWidth + 30 : 0,
  );
  const height = Math.max(
    300,
    ...Array.from(layout.values(), (item) => item.top + item.height + 34),
    selectedPosition ? inspectorTop + 390 : 0,
  );

  function selectNode(nodeId: string) {
    onSelectNode(nodeId);
    const position = layout.get(nodeId);
    window.setTimeout(() => {
      const viewport = viewportRef.current;
      if (!viewport || !position) return;
      const right = position.left + position.width + popoverWidth + 40;
      if (right > viewport.scrollLeft + viewport.clientWidth) {
        viewport.scrollLeft = right - viewport.clientWidth + 12;
      }
      if (
        position.top < viewport.scrollTop ||
        position.top > viewport.scrollTop + viewport.clientHeight - 90
      ) {
        viewport.scrollTop = Math.max(0, position.top - 80);
      }
    }, 30);
  }

  return (
    <div className="workflow-map-shell">
      <div className="workflow-map-legend">
        <span>
          <i className="used" /> 已用于生成页
        </span>
        <span>
          <i className="link" /> 节点连线
        </span>
        <span>可横向、纵向滚动</span>
      </div>
      <div className="workflow-map-viewport" ref={viewportRef}>
        <div className="workflow-map-canvas" style={{ width, height }}>
          <svg
            className="workflow-map-links"
            width={width}
            height={height}
            viewBox={`0 0 ${width} ${height}`}
            aria-hidden="true"
          >
            <defs>
              <marker
                id="workflow-link-arrow"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="5"
                markerHeight="5"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" />
              </marker>
            </defs>
            {topology.links.map((link, index) => {
              const source = layout.get(link.originId);
              const target = layout.get(link.targetId);
              if (!source || !target) return null;
              const startX = source.left + source.width;
              const startY = source.top + 25;
              const endX = target.left;
              const endY = target.top + 25;
              const bend = Math.max(45, Math.abs(endX - startX) * 0.45);
              return (
                <path
                  key={`${link.originId}:${link.originSlot}:${link.targetId}:${index}`}
                  d={`M ${startX} ${startY} C ${startX + bend} ${startY}, ${endX - bend} ${endY}, ${endX} ${endY}`}
                  className={`workflow-map-link ${topologyLinkClass(link.type)}`}
                  markerEnd="url(#workflow-link-arrow)"
                />
              );
            })}
          </svg>
          {nodes.map((node) => {
            const position = layout.get(node.id);
            if (!position) return null;
            return (
              <button
                key={node.id}
                type="button"
                className={[
                  "workflow-map-node",
                  activeNodeIds.has(node.id) ? "is-filter-active" : "is-dimmed",
                  boundNodeIds.has(node.id) ? "is-used" : "",
                  selectedNodeId === node.id ? "is-selected" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                style={position}
                title={`${node.title} · 节点 #${node.id}`}
                onClick={() => selectNode(node.id)}
              >
                <strong>{node.title || node.classType}</strong>
                <span>
                  #{node.id} · {node.classType}
                </span>
              </button>
            );
          })}
          {selectedPosition && (
            <aside
              className="workflow-node-popover"
              style={{
                left: inspectorLeft,
                top: inspectorTop,
                width: popoverWidth,
              }}
            >
              {(() => {
                const selectedNode = nodes.find(
                  (node) => node.id === selectedNodeId,
                );
                if (!selectedNode) return null;
                return (
                  <>
                    <header>
                      <div>
                        <span>
                          {selectedNode.subgraph
                            ? "子图聚合节点"
                            : "ComfyUI 节点"}
                        </span>
                        <strong>
                          {selectedNode.title || selectedNode.classType}
                        </strong>
                        <small>
                          #{selectedNode.id} · {selectedNode.classType}
                        </small>
                      </div>
                      <button
                        type="button"
                        aria-label="关闭节点控件"
                        onClick={onCloseInspector}
                      >
                        <X size={15} />
                      </button>
                    </header>
                    <div className="workflow-popover-fields">
                      {selectedInputs.map((input) => {
                        const bound = inputIsBound(input, boundInputKeys);
                        return (
                          <div className="workflow-popover-field" key={input.id}>
                            <div>
                              <strong>{input.fieldLabel}</strong>
                              <code>{input.field}</code>
                            </div>
                            <span className="workflow-popover-value">
                              {formatWorkflowValue(input.default)}
                            </span>
                            <div className="workflow-popover-tags">
                              <span>{input.assetType ?? input.type}</span>
                              {input.linked && (
                                <span className="linked">
                                  <Link2 size={11} /> 已连线
                                </span>
                              )}
                            </div>
                            <button
                              type="button"
                              disabled={bound}
                              onClick={() => onEnableInput(input)}
                            >
                              {bound ? (
                                "已启用"
                              ) : (
                                <>
                                  <Plus size={13} /> 启用
                                </>
                              )}
                            </button>
                          </div>
                        );
                      })}
                      {selectedInputs.length === 0 && (
                        <p>这个节点没有可启用的参数。</p>
                      )}
                    </div>
                  </>
                );
              })()}
            </aside>
          )}
        </div>
      </div>
    </div>
  );
}

function topologyLinkClass(type?: string) {
  switch ((type ?? "").toUpperCase()) {
    case "IMAGE":
      return "image";
    case "VIDEO":
      return "video";
    case "AUDIO":
      return "audio";
    case "CONDITIONING":
      return "conditioning";
    case "LATENT":
      return "latent";
    default:
      return "default";
  }
}

type WorkflowConfiguratorProps = {
  item: WorkflowCatalogItem;
  inputs: WorkflowInput[];
  allInputs: WorkflowInput[];
  topology: WorkflowTopology;
  totalInputs: number;
  parameters: WorkflowParameter[];
  search: string;
  busy: boolean;
  onChangeSearch: (value: string) => void;
  onClose: () => void;
  onAddParameter: () => void;
  onAddReference: (
    assetType: NonNullable<WorkflowParameter["assetType"]>,
  ) => void;
  onAddInput: (input: WorkflowInput) => void;
  onChangeParameter: (
    index: number,
    update: (parameter: WorkflowParameter) => void,
  ) => void;
  onRemoveParameter: (index: number) => void;
  onAddBinding: (index: number) => void;
  onSelectBinding: (
    parameterIndex: number,
    bindingIndex: number,
    inputId: string,
  ) => void;
  onRemoveBinding: (
    parameterIndex: number,
    bindingIndex: number,
  ) => void;
  onSave: () => void;
};

function WorkflowConfigurator({
  item,
  inputs,
  allInputs,
  topology,
  totalInputs,
  parameters,
  search,
  busy,
  onChangeSearch,
  onClose,
  onAddParameter,
  onAddReference,
  onAddInput,
  onChangeParameter,
  onRemoveParameter,
  onAddBinding,
  onSelectBinding,
  onRemoveBinding,
  onSave,
}: WorkflowConfiguratorProps) {
  const [inputView, setInputView] = useState<
    "used" | "all" | "assets" | "linked"
  >("used");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const boundInputs = new Set(
    parameters.flatMap((parameter) =>
      (parameter.bindings ?? []).map(
        (binding) => `${binding.nodeId}:${binding.field}`,
      ),
    ),
  );
  const boundCatalogInputs = inputs.filter((input) =>
    inputIsBound(input, boundInputs),
  );
  const scopedInputs = search.trim()
    ? inputs
    : inputs.filter((input) => {
        if (inputView === "all") return true;
        if (inputView === "assets") return input.type === "assets";
        if (inputView === "linked") return input.linked;
        return inputIsBound(input, boundInputs);
      });
  const activeNodeIds = new Set(
    scopedInputs.map((input) => input.nodeId),
  );
  const boundNodeIds = new Set(
    topology.nodes
      .filter((node) =>
        inputs.some(
          (input) =>
            input.nodeId === node.id &&
            inputIsBound(input, boundInputs),
        ),
      )
      .map((node) => node.id),
  );
  const selectedNode =
    topology.nodes.find((node) => node.id === selectedNodeId) ?? null;
  const selectedInputs = selectedNode
    ? allInputs.filter((input) => input.nodeId === selectedNode.id)
    : [];

  useEffect(() => {
    if (search.trim() && inputs[0]) {
      setSelectedNodeId(inputs[0].nodeId);
    }
  }, [inputs, search]);

  function focusNode(nodeId: string) {
    setSelectedNodeId(nodeId);
  }

  return (
    <section className="workflow-configurator" id="workflow-configurator">
      <header className="workflow-configurator-head">
        <div>
          <span className="eyebrow">ComfyUI 工作流表单配置</span>
          <h3>{item.name}</h3>
          <p>
            下面就是保存的 ComfyUI 节点。找到想让用户填写或上传的控件，
            点击“加到生成页”，它就会变成创作页上的一个输入项。
          </p>
        </div>
        <button type="button" onClick={onClose} aria-label="关闭工作流配置">
          <X size={20} />
        </button>
      </header>

      <div className="workflow-config-guide">
        <div>
          <strong>1</strong>
          <span>在节点中找控件</span>
        </div>
        <ArrowRight size={16} />
        <div>
          <strong>2</strong>
          <span>加到生成页并命名</span>
        </div>
        <ArrowRight size={16} />
        <div>
          <strong>3</strong>
          <span>保存后测试工作流</span>
        </div>
      </div>

      <section className="workflow-node-browser">
        <div className="workflow-section-head">
          <div>
            <span>步骤 1</span>
            <h4>选择 ComfyUI 节点控件</h4>
            <p>
              节点 ID、节点名称和字段名与 ComfyUI 中一致。已连线表示该控件的值
              当前来自其他节点，你也可以把它改成用户输入。
            </p>
          </div>
          <label className="workflow-input-search">
            <Search size={16} />
            <input
              value={search}
              onChange={(event) => onChangeSearch(event.target.value)}
              placeholder="搜索节点名称、节点 ID、字段名，例如 K采样器、seed"
            />
          </label>
        </div>
        <WorkflowTopologyMap
          topology={topology}
          boundNodeIds={boundNodeIds}
          activeNodeIds={activeNodeIds}
          selectedNodeId={selectedNodeId}
          selectedInputs={selectedInputs}
          boundInputKeys={boundInputs}
          onSelectNode={focusNode}
          onEnableInput={(input) => onAddInput(input)}
          onCloseInspector={() => setSelectedNodeId(null)}
        />
        <p className="workflow-map-hint">
          点击节点后，参数小卡片会出现在节点右侧。勾选“启用”即可加入生成页。
        </p>
        <div className="workflow-browser-meta">
          当前筛选涉及 {activeNodeIds.size} 个节点、{scopedInputs.length} 个控件。
        </div>
        <div className="workflow-input-views">
          <button
            type="button"
            className={inputView === "used" && !search ? "active" : ""}
            onClick={() => setInputView("used")}
          >
            当前参数使用 {boundCatalogInputs.length}
          </button>
          <button
            type="button"
            className={inputView === "all" && !search ? "active" : ""}
            onClick={() => setInputView("all")}
          >
            所有控件 {totalInputs}
          </button>
          <button
            type="button"
            className={inputView === "assets" && !search ? "active" : ""}
            onClick={() => setInputView("assets")}
          >
            素材控件 {inputs.filter((input) => input.type === "assets").length}
          </button>
          <button
            type="button"
            className={inputView === "linked" && !search ? "active" : ""}
            onClick={() => setInputView("linked")}
          >
            已连线 {inputs.filter((input) => input.linked).length}
          </button>
        </div>
      </section>

      <section className="workflow-parameter-designer">
        <div className="workflow-section-head">
          <div>
            <span>步骤 2</span>
            <h4>配置生成页上的输入项</h4>
            <p>
              左侧每个参数对应生成页上的一个控件；右侧预览用户最终会看到什么。
            </p>
          </div>
          <button type="button" onClick={onAddParameter}>
            <Plus size={15} />
            新建空白参数
          </button>
        </div>

        <div className="workflow-reference-presets">
          <span>快速创建素材输入：</span>
          <button type="button" onClick={() => onAddReference("image")}>
            <ImageIcon size={14} /> 图片参考
          </button>
          <button type="button" onClick={() => onAddReference("video")}>
            <VideoIcon size={14} /> 视频参考
          </button>
          <button type="button" onClick={() => onAddReference("audio")}>
            <Music2Icon size={14} /> 音频 / 语音参考
          </button>
          <button type="button" onClick={() => onAddReference("file")}>
            <FileReferenceIcon size={14} /> 文件参考
          </button>
        </div>

        <div className="workflow-designer-grid">
          <div className="workflow-parameter-list">
            {parameters.length === 0 && (
              <div className="workflow-parameter-empty">
                还没有生成页输入。请先在上面的节点里点击“加到生成页”。
              </div>
            )}
            {parameters.map((parameter, index) => (
              <WorkflowParameterCard
                key={`${parameter.key}:${index}`}
                parameter={parameter}
                inputs={allInputs}
                onChange={(update) => onChangeParameter(index, update)}
                onRemove={() => onRemoveParameter(index)}
                onAddBinding={() => onAddBinding(index)}
                onSelectBinding={(bindingIndex, inputId) =>
                  onSelectBinding(index, bindingIndex, inputId)
                }
                onRemoveBinding={(bindingIndex) =>
                  onRemoveBinding(index, bindingIndex)
                }
              />
            ))}
          </div>
          <aside className="workflow-form-preview">
            <div className="workflow-form-preview-head">
              <span>步骤 3</span>
              <strong>创作页预览</strong>
            </div>
            {parameters.map((parameter) => (
              <PreviewParameter key={parameter.key} parameter={parameter} />
            ))}
            {parameters.length === 0 && (
              <p>配置参数后，这里会预览创作页上的输入表单。</p>
            )}
          </aside>
        </div>
      </section>

      <footer className="workflow-configurator-actions">
        <span>
          保存后模型会回到未测试状态，需要再点一次“测试”确认工作流可以执行。
        </span>
        <div>
          <button type="button" onClick={onClose}>
            关闭
          </button>
          <button type="button" disabled={busy} onClick={onSave}>
            {busy ? <LoaderCircle className="spin" size={15} /> : null}
            保存生成页配置
          </button>
        </div>
      </footer>
    </section>
  );
}

type WorkflowParameterCardProps = {
  parameter: WorkflowParameter;
  inputs: WorkflowInput[];
  onChange: (update: (parameter: WorkflowParameter) => void) => void;
  onRemove: () => void;
  onAddBinding: () => void;
  onSelectBinding: (bindingIndex: number, inputId: string) => void;
  onRemoveBinding: (bindingIndex: number) => void;
};

function WorkflowParameterCard({
  parameter,
  inputs,
  onChange,
  onRemove,
  onAddBinding,
  onSelectBinding,
  onRemoveBinding,
}: WorkflowParameterCardProps) {
  return (
    <article className="workflow-parameter-card">
      <header className="workflow-parameter-card-head">
        <div>
          <strong>{parameter.label || "未命名输入"}</strong>
          <span>
            生成页输入项 ·{" "}
            {parameter.required ? "必填" : "可选"}
          </span>
        </div>
        <button type="button" title="删除输入项" onClick={onRemove}>
          <Trash2 size={15} />
        </button>
      </header>
      <div className="workflow-parameter-route">
        <span>{parameter.label || parameter.key}</span>
        <ArrowRight size={15} />
        <code>{bindingSummary(parameter, inputs)}</code>
      </div>
      <div className="workflow-parameter-basic">
        <label>
          <span>创作页显示名称</span>
          <input
            value={parameter.label}
            onChange={(event) =>
              onChange((draft) => {
                draft.label = event.target.value;
              })
            }
          />
        </label>
        <label>
          <span>默认值</span>
          <input
            value={String(parameter.default ?? "")}
            disabled={parameter.type === "assets"}
            placeholder={
              parameter.type === "assets" ? "运行时选择文件" : "可以留空"
            }
            onChange={(event) =>
              onChange((draft) => {
                draft.default = event.target.value;
              })
            }
          />
        </label>
        <label className="parameter-required">
          <span>生成前必须填写</span>
          <input
            type="checkbox"
            checked={parameter.required}
            onChange={(event) =>
              onChange((draft) => {
                draft.required = event.target.checked;
              })
            }
          />
        </label>
      </div>
      <details className="workflow-parameter-advanced">
        <summary>
          <Settings2 size={14} />
          高级设置：程序 key、类型、范围和绑定
        </summary>
        <div className="workflow-parameter-fields">
          <label>
            <span>上层语义</span>
            <select
              value={parameter.semanticKey ?? inferSemanticRole(parameter)}
              onChange={(event) =>
                onChange((draft) => {
                  draft.semanticKey = event.target.value;
                })
              }
            >
              <option value={parameter.key}>自定义（{parameter.key}）</option>
              <option value="prompt">提示词</option>
              <option value="negativePrompt">反向提示词</option>
              <option value="aspectRatio">画面比例</option>
              <option value="resolution">分辨率 1K / 2K / 4K</option>
              <option value="width">宽度</option>
              <option value="height">高度</option>
              <option value="seed">随机种子</option>
              <option value="count">生成数量</option>
              <option value="duration">时长</option>
              <option value="length">帧数</option>
              <option value="fps">帧率</option>
              <option value="quality">质量</option>
            </select>
          </label>
          <label>
            <span>参数 key</span>
            <input
              value={parameter.key}
              onChange={(event) =>
                onChange((draft) => {
                  draft.key = event.target.value;
                })
              }
            />
          </label>
          <label>
            <span>输入类型</span>
            <select
              value={parameter.type}
              onChange={(event) =>
                onChange((draft) => {
                  draft.type = event.target.value as WorkflowParameter["type"];
                  if (draft.type === "assets") {
                    draft.assetType = draft.assetType ?? "image";
                    reindexAssetBindings(draft);
                  }
                })
              }
            >
              <option value="string">文本</option>
              <option value="integer">整数</option>
              <option value="number">小数</option>
              <option value="boolean">开关</option>
              <option value="assets">素材引用</option>
            </select>
          </label>
          {parameter.type === "assets" && (
            <label>
              <span>素材类型</span>
              <select
                value={parameter.assetType ?? "image"}
                onChange={(event) =>
                  onChange((draft) => {
                    draft.assetType = event.target.value as NonNullable<
                      WorkflowParameter["assetType"]
                    >;
                  })
                }
              >
                <option value="image">图片参考</option>
                <option value="video">视频参考</option>
                <option value="audio">音频 / 语音参考</option>
                <option value="file">文件参考</option>
              </select>
            </label>
          )}
          {(parameter.type === "integer" ||
            parameter.type === "number" ||
            parameter.type === "assets") && (
            <>
              <label>
                <span>最小值</span>
                <input
                  type="number"
                  value={parameter.min ?? ""}
                  onChange={(event) =>
                    onChange((draft) => {
                      draft.min = numberOrUndefined(event.target.value);
                    })
                  }
                />
              </label>
              <label>
                <span>最大值</span>
                <input
                  type="number"
                  value={parameter.max ?? ""}
                  onChange={(event) =>
                    onChange((draft) => {
                      draft.max = numberOrUndefined(event.target.value);
                    })
                  }
                />
              </label>
            </>
          )}
        </div>
        <div className="workflow-binding-list">
          <div className="workflow-binding-title">
            <span>写入哪些 ComfyUI 节点控件</span>
            <button type="button" onClick={onAddBinding}>
              <Plus size={13} />
              再绑定一个控件
            </button>
          </div>
          {(parameter.bindings ?? []).map((binding, bindingIndex) => (
            <div
              className="workflow-binding-row"
              key={`${binding.nodeId}:${binding.field}:${bindingIndex}`}
            >
              <select
                value={`${binding.nodeId}:${binding.field}`}
                onChange={(event) =>
                  onSelectBinding(bindingIndex, event.target.value)
                }
              >
                {inputs.map((input) => (
                  <option key={input.id} value={input.id}>
                    {input.label} · {input.type}
                    {input.linked ? " · 当前已连线" : ""}
                  </option>
                ))}
              </select>
              <button
                type="button"
                title="移除绑定"
                onClick={() => onRemoveBinding(bindingIndex)}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </details>
    </article>
  );
}

function PreviewParameter({ parameter }: { parameter: WorkflowParameter }) {
  if (parameter.type === "assets") {
    return (
      <div className="workflow-preview-field preview-asset">
        <span>
          {parameter.label}
          {parameter.required ? " *" : ""}
        </span>
        <div>
          <Plus size={15} />
          上传{assetTypeLabel(parameter.assetType)}
        </div>
      </div>
    );
  }
  if (parameter.type === "boolean") {
    return (
      <label className="workflow-preview-field preview-checkbox">
        <span>
          {parameter.label}
          {parameter.required ? " *" : ""}
        </span>
        <input type="checkbox" disabled />
      </label>
    );
  }
  return (
    <label className="workflow-preview-field">
      <span>
        {parameter.label}
        {parameter.required ? " *" : ""}
      </span>
      <div className="preview-input">
        {String(parameter.default ?? parameter.options?.[0] ?? "等待输入")}
      </div>
    </label>
  );
}

function bindingSummary(
  parameter: WorkflowParameter,
  inputs: WorkflowInput[],
) {
  const bindings = parameter.bindings ?? [];
  if (bindings.length === 0) return "还没有绑定节点控件";
  return bindings
    .map((binding) => {
      const input = inputs.find(
        (candidate) =>
          (candidate.nodeId === binding.nodeId &&
            candidate.field === binding.field) ||
          (candidate.bindings ?? []).some(
            (target) =>
              target.nodeId === binding.nodeId &&
              target.field === binding.field,
          ),
      );
      return input
        ? `#${input.nodeId} ${input.nodeTitle} / ${input.field}`
        : `#${binding.nodeId} / ${binding.field}`;
    })
    .join(" + ");
}

function inputIsBound(
  input: WorkflowInput,
  boundKeys: Set<string>,
) {
  const targets =
    input.bindings && input.bindings.length
      ? input.bindings
      : [{ nodeId: input.nodeId, field: input.field }];
  return targets.some((target) =>
    boundKeys.has(`${target.nodeId}:${target.field}`),
  );
}

function formatWorkflowValue(value: unknown) {
  if (value == null || value === "") return "空";
  if (Array.isArray(value) && value.length === 2) {
    return `来自节点 ${value[0]} 的输出 ${value[1]}`;
  }
  const text = String(value).replace(/\s+/g, " ").trim();
  return text.length > 90 ? `${text.slice(0, 90)}…` : text;
}

function assetTypeLabel(assetType?: string) {
  return {
    image: "图片",
    video: "视频",
    audio: "音频 / 语音",
    file: "文件",
  }[assetType ?? "image"] ?? "素材";
}

function assetName(asset: LibraryAsset) {
  const original = asset.metadata.originalFilename;
  if (typeof original === "string" && original.trim()) return original;
  return `${asset.source === "generated" ? "生成图片" : "图片"} ${asset.id.slice(0, 8)}`;
}

function inferSemanticRole(parameter: {
  key: string;
  label?: string;
  semanticKey?: string;
}) {
  if (parameter.semanticKey) return parameter.semanticKey;
  const text = `${parameter.key} ${parameter.label ?? ""}`.toLowerCase();
  if (hasAny(text, ["negative", "反向", "负面"])) return "negativePrompt";
  if (
    hasAny(text, ["prompt", "提示词"]) ||
    ["replace", "text", "string"].includes(parameter.key)
  ) {
    return "prompt";
  }
  if (hasAny(text, ["aspect", "ratio", "宽高比"])) return "aspectRatio";
  if (hasAny(text, ["megapixel", "resolution", "像素", "分辨率"])) {
    return "resolution";
  }
  if (parameter.key === "width" || text.includes("宽度")) return "width";
  if (parameter.key === "height" || text.includes("高度")) return "height";
  if (
    text.includes("noise_seed") ||
    parameter.key === "seed" ||
    text.includes("种子")
  ) {
    return "seed";
  }
  if (hasAny(text, ["batch", "数量"]) || ["count", "n"].includes(parameter.key)) {
    return "count";
  }
  if (parameter.key === "fps" || text.includes("帧率")) return "fps";
  if (text.includes("duration") || text.includes("时长")) return "duration";
  if (text.includes("length") || text.includes("帧数")) return "length";
  if (text.includes("quality") || text.includes("质量")) return "quality";
  return parameter.key;
}

function hasAny(text: string, values: string[]) {
  return values.some((value) => text.includes(value));
}

function capabilityLabel(capability: string | null) {
  if (capability === "image_processing") return "图片处理";
  if (capability === "video_generation") return "视频模型";
  if (capability === "video_processing") return "视频处理模型";
  if (capability === "audio_processing") return "音频模型";
  if (capability === "transcription") return "语音转字幕";
  return "图片模型";
}

function numberOrUndefined(value: string) {
  if (value === "") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function countAssetBindings(
  bindings: WorkflowParameter["bindings"],
) {
  return (bindings ?? []).filter(
    (binding) => typeof binding.assetIndex === "number",
  ).length;
}

function applyInputMetadata(
  parameter: WorkflowParameter,
  input: WorkflowInput,
) {
  if (parameter.type !== "assets") {
    parameter.type = input.type;
  }
  if (parameter.type === "assets" && input.type === "assets") {
    parameter.assetType = input.assetType ?? "image";
  }
  parameter.options = input.options;
  parameter.default = input.type === "assets" ? undefined : input.default;
  if (/^参数 \d+$/.test(parameter.label)) {
    parameter.label = input.fieldLabel;
  }
  if (/^parameter_\d+$/.test(parameter.key)) {
    parameter.key =
      input.field
        .trim()
        .replace(/[^\w]+/g, "_")
        .replace(/^_+|_+$/g, "") || parameter.key;
  }
}

function reindexAssetBindings(parameter: WorkflowParameter) {
  if (parameter.type !== "assets") return;
  parameter.bindings = (parameter.bindings ?? []).map(
    (binding, index) => ({
      ...binding,
      assetIndex: index,
    }),
  );
}
