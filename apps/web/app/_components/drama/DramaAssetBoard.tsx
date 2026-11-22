"use client";

import {
  Aperture,
  Check,
  CheckCircle2,
  Clapperboard,
  ImagePlus,
  Images,
  Link2,
  LoaderCircle,
  LockKeyhole,
  MapPin,
  Mic2,
  Palette,
  Plus,
  Save,
  Search,
  Shirt,
  Sparkles,
  Upload,
  UserRound,
  WandSparkles,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { LibraryAsset } from "../../_features/assets/types";
import {
  bindDramaEntityAsset,
  saveDramaEntityPrompt,
  updateDramaShotReferences,
} from "../../_features/drama/api";
import type {
  DramaEntity,
  DramaEntityKind,
} from "../../_features/drama/types";
import { useDramaAssets } from "../../_features/drama/useDramaAssets";
import { useDramaProduction } from "../../_features/drama/useDramaProduction";
import {
  createMediaTask,
  pollMediaTask,
} from "../../_features/media/api";
import { loadSpeechVoices } from "../../_features/media/processingApi";
import type { Model } from "../../_features/models/types";
import { useModelSettings } from "../../_features/models/useModelSettings";
import { backendResourceUrl } from "../../../shared/ui/backend-resource";

type DramaAssetBoardProps = {
  projectId: string;
  refreshToken?: number;
  onOpenAgent?: (context?: string) => void;
};

type PickerMode = "primary" | "references";

const entityKinds: Array<{
  id: DramaEntityKind;
  label: string;
  hint: string;
  icon: typeof UserRound;
}> = [
  {
    id: "character",
    label: "角色",
    hint: "16:9 单张定妆总表",
    icon: UserRound,
  },
  { id: "costume", label: "服装", hint: "造型与材质", icon: Shirt },
  { id: "prop", label: "道具", hint: "剧情关键物件", icon: Aperture },
  { id: "location", label: "场景", hint: "空间与氛围", icon: MapPin },
  { id: "style", label: "风格", hint: "色彩与镜头语言", icon: Palette },
];

const assetSlotDefinitions: Record<
  DramaEntityKind,
  Array<{ id: string; label: string; hint: string }>
> = {
  character: [
    {
      id: "character_sheet",
      label: "角色设定总表",
      hint: "单张 16:9 · 头特写 / 正侧背全身 / 表情 / 服饰",
    },
  ],
  location: [
    { id: "master", label: "总场景", hint: "空间总关系" },
    { id: "interior", label: "内景", hint: "室内分场景" },
    { id: "exterior", label: "外景", hint: "室外分场景" },
    { id: "lighting_reference", label: "灯光参考", hint: "光源与色温" },
  ],
  costume: [
    { id: "front", label: "正面", hint: "完整造型" },
    { id: "back", label: "背面", hint: "背部结构" },
    { id: "fabric_detail", label: "材质细节", hint: "纹样和织物" },
  ],
  prop: [
    { id: "hero", label: "主视觉", hint: "道具标准图" },
    { id: "scale_reference", label: "比例参考", hint: "与人物比例" },
  ],
  style: [
    { id: "moodboard", label: "风格板", hint: "色彩与镜头语言" },
  ],
};

const characterProfileFields = [
  { key: "want", label: "外在目标" },
  { key: "need", label: "内在需求" },
  { key: "wound", label: "创伤来源" },
  { key: "falseBelief", label: "错误信念" },
  { key: "fear", label: "核心恐惧" },
  { key: "contradiction", label: "性格矛盾" },
  { key: "publicMask", label: "公开面具" },
  { key: "privateSelf", label: "私下自我" },
  { key: "speechPattern", label: "语言习惯" },
  { key: "voiceNotes", label: "声音与台词" },
  { key: "bodyBehavior", label: "形体与动作" },
  { key: "arcStart", label: "初始状态" },
  { key: "arcEnd", label: "转变终点" },
  { key: "relationships", label: "关系张力" },
  { key: "continuityRules", label: "不可漂移规则" },
] as const;

export function DramaAssetBoard({
  projectId,
  refreshToken = 0,
  onOpenAgent,
}: DramaAssetBoardProps) {
  const library = useDramaAssets(projectId);
  const production = useDramaProduction(projectId);
  const models = useModelSettings();
  const [activeKind, setActiveKind] = useState<DramaEntityKind>("character");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newKind, setNewKind] = useState<DramaEntityKind>("character");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [primaryAssetId, setPrimaryAssetId] = useState<string | null>(null);
  const [referenceAssetIds, setReferenceAssetIds] = useState<string[]>([]);
  const [assetSlots, setAssetSlots] = useState<Record<string, string>>({});
  const [pickerMode, setPickerMode] = useState<PickerMode | null>(null);
  const [assetQuery, setAssetQuery] = useState("");
  const [activeShotId, setActiveShotId] = useState<string | null>(null);
  const [shotReferenceIds, setShotReferenceIds] = useState<string[]>([]);
  const [localNotice, setLocalNotice] = useState("");
  const [savingReferences, setSavingReferences] = useState(false);
  const [upscaleTaskId, setUpscaleTaskId] = useState<string | null>(null);
  const [upscaling, setUpscaling] = useState(false);
  const [upscaleError, setUpscaleError] = useState("");
  const [slotModelId, setSlotModelId] = useState("");
  const [generatingSlot, setGeneratingSlot] = useState<string | null>(null);
  const [slotTaskProgress, setSlotTaskProgress] = useState(0);
  const [slotError, setSlotError] = useState("");
  const [slotPromptDrafts, setSlotPromptDrafts] = useState<
    Record<string, string>
  >({});
  const [candidateSlotBusy, setCandidateSlotBusy] = useState<string | null>(
    null,
  );
  const [voices, setVoices] = useState<
    Array<{ name: string; culture: string }>
  >([]);
  const [voiceName, setVoiceName] = useState("");
  const [voiceRate, setVoiceRate] = useState(0);

  useEffect(() => {
    void loadSpeechVoices()
      .then((result) => setVoices(result.voices))
      .catch(() => setVoices([]));
  }, []);

  useEffect(() => {
    if (!refreshToken) return;
    void library.refresh();
    void production.refresh();
    // The token is an explicit Agent mutation signal.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshToken]);

  const selected =
    library.entities.find((entity) => entity.id === selectedId) ?? null;
  const assetMap = useMemo(
    () => new Map(library.assets.map((asset) => [asset.id, asset])),
    [library.assets],
  );
  const shots = useMemo(
    () =>
      production.episodes.flatMap((episode) =>
        episode.scenes.flatMap((scene) =>
          scene.shots.map((shot) => ({
            ...shot,
            episodeTitle: episode.title,
            sceneHeading: scene.heading,
          })),
        ),
      ),
    [production.episodes],
  );
  const activeShot =
    shots.find((shot) => shot.id === activeShotId) ?? null;
  const filteredEntities = library.entities.filter(
    (entity) => entity.kind === activeKind,
  );
  const imageAssets = library.assets.filter((asset) => {
    if (asset.type !== "image") return false;
    const query = assetQuery.trim().toLowerCase();
    if (!query) return true;
    const filename = String(
      asset.metadata.originalFilename ?? asset.metadata.filename ?? "",
    ).toLowerCase();
    return asset.id.toLowerCase().includes(query) || filename.includes(query);
  });
  const lockedCount = library.entities.filter(
    (entity) => entity.status === "locked",
  ).length;
  const slotImageModels = useMemo(
    () =>
      models.models.filter(
        (model) =>
          model.capabilities.includes("image_generation") &&
          model.integrationStatus === "ready" &&
          model.configured &&
          !model.references?.some(
            (reference) => reference.type !== "image" && reference.min > 0,
          ),
      ),
    [models.models],
  );
  const slotReferenceIds = useMemo(
    () =>
      Array.from(
        new Set(
          [
            primaryAssetId,
            ...Object.values(assetSlots),
          ].filter((value): value is string => Boolean(value)),
        ),
      ),
    [assetSlots, primaryAssetId],
  );
  const selectedSlotModel =
    slotImageModels.find((model) => model.id === slotModelId) ??
    chooseSlotModel(slotImageModels, slotReferenceIds.length) ??
    null;
  const slotImageMinimum = imageMinimumFor(selectedSlotModel);
  const slotImageLimit = imageLimitFor(selectedSlotModel);

  useEffect(() => {
    if (selectedId && library.entities.some((item) => item.id === selectedId)) {
      return;
    }
    setSelectedId(
      library.entities.find((item) => item.kind === activeKind)?.id ??
        library.entities[0]?.id ??
        null,
    );
  }, [activeKind, library.entities, selectedId]);

  useEffect(() => {
    const recommended = chooseSlotModel(
      slotImageModels,
      slotReferenceIds.length,
    );
    if (recommended?.id) {
      setSlotModelId(recommended.id);
    }
  }, [selected?.id, slotImageModels, slotReferenceIds.length]);

  useEffect(() => {
    setName(selected?.name ?? "");
    setDescription(selected?.description ?? "");
    setPrimaryAssetId(selected?.primaryAssetId ?? null);
    setReferenceAssetIds(selected?.referenceAssetIds ?? []);
    setAssetSlots(selected?.assetSlots ?? {});
    setSlotPromptDrafts(selected?.assetPrompts ?? {});
    setVoiceName(selected?.voiceName ?? "");
    setVoiceRate(selected?.voiceRate ?? 0);
  }, [selected]);

  useEffect(() => {
    if (activeShotId && shots.some((shot) => shot.id === activeShotId)) {
      return;
    }
    setActiveShotId(shots[0]?.id ?? null);
  }, [activeShotId, shots]);

  useEffect(() => {
    setShotReferenceIds(
      activeShot?.entityReferences?.map((item) => item.entityId) ?? [],
    );
  }, [activeShot]);

  async function createEntity() {
    if (!newName.trim()) return;
    const entity = await library.addEntity(
      newKind,
      newName.trim(),
      "",
    );
    if (!entity) return;
    setNewName("");
    setShowCreate(false);
    setActiveKind(newKind);
    setSelectedId(entity.id);
  }

  async function saveDraft(status: DramaEntity["status"]) {
    if (!selected) return;
    setLocalNotice("");
    const result = await library.saveEntity(selected.id, {
      name: name.trim() || selected.name,
      description,
      status,
      primaryAssetId,
      referenceAssetIds: referenceAssetIds.filter(
        (id) => id !== primaryAssetId,
      ),
      assetSlots,
      profile: selected.profile,
      voiceName: voiceName || null,
      voiceRate,
    });
    if (result) {
      setLocalNotice(
        status === "locked" ? "资产已锁定，可用于镜头制作。" : "资产草稿已保存。",
      );
    }
  }

  function chooseAsset(assetId: string) {
    if (pickerMode === "primary") {
      setPrimaryAssetId(assetId);
      setReferenceAssetIds((items) =>
        items.filter((item) => item !== assetId),
      );
      setPickerMode(null);
      return;
    }
    if (pickerMode === "references") {
      setReferenceAssetIds((items) => {
        if (items.includes(assetId)) {
          return items.filter((item) => item !== assetId);
        }
        return items.length >= 10 ? items : [...items, assetId];
      });
    }
  }

  function toggleShotEntity(entity: DramaEntity) {
    setShotReferenceIds((items) =>
      items.includes(entity.id)
        ? items.filter((item) => item !== entity.id)
        : [...items, entity.id],
    );
  }

  async function saveShotReferences() {
    if (!activeShot) return;
    setSavingReferences(true);
    setLocalNotice("");
    try {
      const references = shotReferenceIds.flatMap((entityId) => {
        const entity = library.entities.find((item) => item.id === entityId);
        return entity
          ? [{ entityId, role: entity.kind }]
          : [];
      });
      await updateDramaShotReferences(activeShot.id, references);
      setLocalNotice(
        `镜头 ${activeShot.shotNumber} 已关联 ${references.length} 个资产。`,
      );
    } catch (error) {
      setLocalNotice((error as Error).message);
    } finally {
      setSavingReferences(false);
    }
  }

  async function generateSlot(slotId: string, slotLabel: string) {
    if (!selected || !selectedSlotModel || generatingSlot) return;
    setGeneratingSlot(slotId);
    setSlotError("");
    setSlotTaskProgress(0);
    try {
      const referenceIds = slotReferenceIds.slice(0, slotImageLimit);
      if (referenceIds.length < slotImageMinimum) {
        throw new Error(
          `当前图片工作流至少需要 ${slotImageMinimum} 张参考图，`
          + `当前只有 ${referenceIds.length} 张。请先绑定主视觉或选择其他工作流。`,
        );
      }
      const missing = (selectedSlotModel.parameters ?? []).filter(
        (parameter) =>
          parameter.type !== "assets" &&
          !parameter.derived &&
          parameter.required &&
          parameter.semanticKey !== "prompt" &&
          parameter.default == null,
      );
      if (missing.length) {
        throw new Error(
          `工作流缺少默认参数：${missing
            .map((parameter) => parameter.label)
            .join("、")}`,
        );
      }
      const parameters = Object.fromEntries(
        (selectedSlotModel.parameters ?? [])
          .filter(
            (parameter) =>
              parameter.type !== "assets" &&
              !parameter.derived &&
              parameter.default !== undefined,
          )
          .map((parameter) => [parameter.key, parameter.default]),
      );
      if (slotId === "character_sheet") {
        parameters.aspectRatio = "16:9";
      }
      const promptKey =
        selectedSlotModel.parameters?.find(
          (parameter) =>
            parameter.semanticKey === "prompt" ||
            parameter.key === "prompt",
        )?.key ?? "prompt";
      const prompt =
        slotPromptDrafts[slotId]?.trim() ||
        selected.assetPrompts[slotId] ||
        buildAssetSlotPrompt(selected, slotId, slotLabel);
      await saveDramaEntityPrompt(selected.id, slotId, prompt);
      const created = await createMediaTask({
        providerId: selectedSlotModel.providerId,
        modelId: selectedSlotModel.id,
        taskType: "image_generation",
        prompt,
        inputAssetIds: referenceIds,
        images: referenceIds,
        videos: [],
        audios: [],
        files: [],
        parameters: {
          ...parameters,
          [promptKey]: prompt,
        },
        clientRequestId: crypto.randomUUID(),
      });
      const completed = await pollMediaTask(
        created.id,
        (task) => setSlotTaskProgress(task.progress ?? 0),
        new AbortController().signal,
      );
      if (completed.status === "failed") {
        throw new Error(completed.errorMessage || "资产槽位生成失败");
      }
      const assetId = completed.resultAssetIds[0];
      if (!assetId) {
        throw new Error("生成完成，但没有返回素材");
      }
      const updated = await bindDramaEntityAsset(
        selected.id,
        slotId,
        assetId,
      );
      setAssetSlots(updated.assetSlots);
      await library.refresh();
      setLocalNotice(
        `${selected.name} · ${slotLabel}已生成并绑定。`,
      );
    } catch (error) {
      setSlotError((error as Error).message);
    } finally {
      setGeneratingSlot(null);
      setSlotTaskProgress(0);
    }
  }

  async function saveSlotPrompt(slotId: string) {
    if (!selected) return;
    setSlotError("");
    try {
      const prompt =
        slotPromptDrafts[slotId] ??
        buildAssetSlotPrompt(
          selected,
          slotId,
          assetSlotDefinitions[selected.kind].find(
            (slot) => slot.id === slotId,
          )?.label ?? slotId,
        );
      const updated = await saveDramaEntityPrompt(
        selected.id,
        slotId,
        prompt,
      );
      setSlotPromptDrafts(updated.assetPrompts);
      await library.refresh();
      setLocalNotice("资产提示词已保存。");
    } catch (error) {
      setSlotError((error as Error).message);
    }
  }

  function planMissingAssets(scope: "kind" | "entity") {
    if (!onOpenAgent) return;
    const kind = scope === "entity" ? selected?.kind : activeKind;
    const target = scope === "entity" ? selected?.name : null;
    onOpenAgent(
      [
        `请为当前项目规划缺失的${kindLabel(kind ?? "character")}资产。`,
        target ? `本次只处理实体“${target}”。` : "本次处理当前资产分类中的全部实体。",
        "读取实体描述、已填专业槽位、保存的槽位提示词和现有参考图。",
        "调用 zaojing_plan_drama_production_run，stage 使用 assets，只规划缺失槽位。",
        "先展示将生成的槽位、参考资产、模型和任务数量，不要直接启动。",
      ].join("\n"),
    );
  }

  async function upscalePrimary() {
    if (!primaryAssetId || upscaling) return;
    const model = models.models.find(
      (item) =>
        item.capabilities.some((capability) =>
          ["image_generation", "image_processing"].includes(capability),
        ) &&
        item.name.includes("图片放大") &&
        item.integrationStatus === "ready",
    );
    if (!model) {
      setUpscaleError("模型中心还没有启用的图片放大工作流");
      return;
    }
    setUpscaling(true);
    setUpscaleError("");
    try {
      const parameters = Object.fromEntries(
        (model.parameters ?? [])
          .filter(
            (parameter) =>
              parameter.type !== "assets" &&
              !parameter.derived &&
              parameter.default !== undefined,
          )
          .map((parameter) => [parameter.key, parameter.default]),
      );
      const created = await createMediaTask({
        providerId: model.providerId,
        modelId: model.id,
        taskType: model.capabilities.includes("image_processing")
          ? "image_processing"
          : "image_generation",
        prompt: "4x upscale and detail enhancement",
        inputAssetIds: [primaryAssetId],
        images: [primaryAssetId],
        videos: [],
        audios: [],
        files: [],
        parameters,
        clientRequestId: crypto.randomUUID(),
      });
      setUpscaleTaskId(created.id);
      const controller = new AbortController();
      const completed = await pollMediaTask(
        created.id,
        () => undefined,
        controller.signal,
      );
      if (completed.status === "failed") {
        setUpscaleError(completed.errorMessage || "图片放大失败");
        return;
      }
      const assetId = completed.resultAssetIds[0];
      if (!assetId) {
        setUpscaleError("图片放大完成，但没有返回素材");
        return;
      }
      await library.refresh();
      setPrimaryAssetId(assetId);
      setReferenceAssetIds((items) =>
        items.filter((item) => item !== assetId),
      );
      setLocalNotice("图片已放大并设为草稿主视觉，保存后生效。");
    } catch (error) {
      setUpscaleError((error as Error).message);
    } finally {
      setUpscaling(false);
      setUpscaleTaskId(null);
    }
  }

  return (
    <section className="drama-asset-board">
      <header className="drama-asset-board-head">
        <div>
          <span className="eyebrow">Asset Bible</span>
          <h3>角色与场景资产</h3>
          <p>先锁定可复用的视觉身份，再让每个镜头引用同一套资产。</p>
        </div>
        <div className="drama-asset-metrics">
          <span>
            <strong>{library.entities.length}</strong> 个实体
          </span>
          <span>
            <strong>{lockedCount}</strong> 个已锁定
          </span>
          <button
            className="drama-asset-ai-plan"
            type="button"
            disabled={!onOpenAgent}
            onClick={() => planMissingAssets("kind")}
          >
            <WandSparkles size={15} />
            AI 补齐缺失资产
          </button>
          <button
            type="button"
            onClick={() => {
              setShowCreate((value) => !value);
              setNewKind(activeKind);
            }}
          >
            <Plus size={15} /> 新建资产
          </button>
        </div>
      </header>

      {(library.notice || localNotice) && (
        <div className="drama-asset-notice">
          {localNotice || library.notice}
        </div>
      )}

      <div className="drama-asset-tabs">
        {entityKinds.map(({ id, label, hint, icon: Icon }) => {
          const count = library.entities.filter(
            (entity) => entity.kind === id,
          ).length;
          return (
            <button
              key={id}
              className={activeKind === id ? "active" : ""}
              type="button"
              onClick={() => {
                setActiveKind(id);
                setSelectedId(
                  library.entities.find((entity) => entity.kind === id)?.id ??
                    null,
                );
              }}
            >
              <span><Icon size={17} /></span>
              <div>
                <strong>{label}</strong>
                <small>{hint}</small>
              </div>
              <em>{count}</em>
            </button>
          );
        })}
      </div>

      {showCreate && (
        <div className="drama-entity-create">
          <span><Sparkles size={17} /></span>
          <label>
            <small>资产类型</small>
            <select
              value={newKind}
              onChange={(event) =>
                setNewKind(event.target.value as DramaEntityKind)
              }
            >
              {entityKinds.map((kind) => (
                <option key={kind.id} value={kind.id}>{kind.label}</option>
              ))}
            </select>
          </label>
          <label>
            <small>名称</small>
            <input
              autoFocus
              value={newName}
              onChange={(event) => setNewName(event.target.value)}
              placeholder="例如：宋宁公主 / 公主寝宫"
              onKeyDown={(event) => {
                if (event.key === "Enter") void createEntity();
              }}
            />
          </label>
          <button
            type="button"
            disabled={!newName.trim() || library.saving}
            onClick={() => void createEntity()}
          >
            创建
          </button>
          <button type="button" onClick={() => setShowCreate(false)}>
            <X size={15} />
          </button>
        </div>
      )}

      <div className="drama-asset-layout">
        <aside className="drama-entity-list">
          <div className="drama-asset-panel-title">
            <span>资产清单</span>
            <small>{kindLabel(activeKind)}</small>
          </div>
          <div className="drama-entity-cards">
            {filteredEntities.map((entity) => {
              const asset = entity.primaryAssetId
                ? assetMap.get(entity.primaryAssetId)
                : null;
              return (
                <button
                  key={entity.id}
                  className={`${entity.id === selectedId ? "active" : ""} ${
                    entity.status
                  }`}
                  type="button"
                  onClick={() => setSelectedId(entity.id)}
                >
                  <span className="drama-entity-thumb">
                    {asset ? (
                      <img src={backendResourceUrl(asset.url)} alt="" />
                    ) : (
                      <ImagePlus size={21} />
                    )}
                  </span>
                  <span className="drama-entity-copy">
                    <strong>{entity.name}</strong>
                    <small>
                      {entity.status === "locked" ? "已锁定" : "草稿"}
                      {entity.referenceAssetIds.length
                        ? ` · ${entity.referenceAssetIds.length + (asset ? 1 : 0)} 图`
                        : ""}
                    </small>
                  </span>
                  {entity.status === "locked" && (
                    <LockKeyhole size={13} />
                  )}
                </button>
              );
            })}
            {!filteredEntities.length && !library.loading && (
              <div className="drama-entity-empty">
                <Images size={25} />
                <strong>还没有{kindLabel(activeKind)}资产</strong>
                <p>创建实体后，从素材库绑定定妆图或概念图。</p>
              </div>
            )}
          </div>
        </aside>

        <section className="drama-entity-editor">
          {selected ? (
            <>
              <div className="drama-entity-editor-head">
                <div>
                  <span>正在编辑 · {kindLabel(selected.kind)}</span>
                  <h4>{selected.name}</h4>
                </div>
                <div className="drama-entity-head-actions">
                  <button
                    type="button"
                    disabled={!onOpenAgent}
                    onClick={() => planMissingAssets("entity")}
                  >
                    <WandSparkles size={13} />
                    AI 补齐此资产
                  </button>
                  <span className={`drama-entity-state ${selected.status}`}>
                    {selected.status === "locked" ? (
                      <LockKeyhole size={13} />
                    ) : (
                      <WandSparkles size={13} />
                    )}
                    {selected.status === "locked" ? "已锁定" : "草稿"}
                  </span>
                </div>
              </div>

              <div className="drama-review-priority">
                <strong>AI 负责制作，你负责审核</strong>
                <span>
                  主要确认身份是否一致、角色设定总表是否可用，以及锁定或要求 Agent
                  重做。专业字段由 Agent 维护，必要时再展开修改。
                </span>
              </div>

              {selected.kind === "character" && (
                <details className="drama-character-profile">
                  <summary>
                    <span>人物创作档案</span>
                    <small>Agent 生成，供你审核人物是否真实、可演、前后一致</small>
                  </summary>
                  <div>
                    {characterProfileFields.map((field) => (
                      <section key={field.key}>
                        <span>{field.label}</span>
                        <p>
                          {selected.profile[field.key] ||
                            "待 Agent 补齐"}
                        </p>
                      </section>
                    ))}
                  </div>
                </details>
              )}

              <details className="drama-manual-editor">
                <summary>
                  <span>人工修改资产设定（可选）</span>
                  <small>名称、连续性规则、音色与语速</small>
                </summary>
                <div className="drama-entity-form">
                  <label>
                    <span>资产名称</span>
                    <input
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                    />
                  </label>
                  <label>
                    <span>视觉说明与连续性规则</span>
                    <textarea
                      value={description}
                      onChange={(event) => setDescription(event.target.value)}
                      placeholder="发型、服装材质、色彩、年龄、不可改变的特征…"
                      rows={4}
                    />
                  </label>
                </div>

                {selected.kind === "character" && (
                  <div className="drama-character-voice">
                    <div className="drama-asset-panel-title">
                      <span>角色音色</span>
                      <small>镜头对白自动匹配</small>
                    </div>
                    <label>
                      <span>本机音色</span>
                      <select
                        value={voiceName}
                        onChange={(event) => setVoiceName(event.target.value)}
                      >
                        <option value="">跟随镜头默认音色</option>
                        {voices.map((voice) => (
                          <option key={voice.name} value={voice.name}>
                            {voice.name} · {voice.culture}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span>
                        <Mic2 size={12} /> 语速 {voiceRate > 0 ? "+" : ""}
                        {voiceRate}
                      </span>
                      <input
                        type="range"
                        min={-5}
                        max={5}
                        step={1}
                        value={voiceRate}
                        onChange={(event) =>
                          setVoiceRate(Number(event.target.value))
                        }
                      />
                    </label>
                  </div>
                )}
              </details>

              <div className="drama-primary-asset">
                <div className="drama-asset-panel-title">
                  <span>主视觉</span>
                  <small>生成和镜头引用时的第一参考</small>
                </div>
                {primaryAssetId ? (
                  <div className="drama-primary-preview">
                    <AssetPreview asset={assetMap.get(primaryAssetId)} />
                    <div>
                      <strong>{assetName(assetMap.get(primaryAssetId))}</strong>
                      <p>这是该资产的标准形象，后续镜头将优先引用。</p>
                      <div className="drama-primary-actions">
                        <button
                          type="button"
                          disabled={upscaling}
                          onClick={() => void upscalePrimary()}
                        >
                          {upscaling ? (
                            <LoaderCircle className="spin" size={12} />
                          ) : (
                            <Sparkles size={12} />
                          )}
                          {upscaling ? "4× 放大中" : "4× 放大"}
                        </button>
                        <button
                          type="button"
                          onClick={() => setPickerMode("primary")}
                        >
                          更换主视觉
                        </button>
                      </div>
                      {upscaleTaskId && (
                        <small className="drama-primary-task">
                          任务 {upscaleTaskId.slice(0, 8)}
                        </small>
                      )}
                      {upscaleError && (
                        <small className="drama-primary-error">
                          {upscaleError}
                        </small>
                      )}
                    </div>
                  </div>
                ) : (
                  <button
                    className="drama-primary-placeholder"
                    type="button"
                    onClick={() => setPickerMode("primary")}
                  >
                    <ImagePlus size={24} />
                    <strong>绑定主视觉</strong>
                    <small>从素材库选择，或上传一张新图</small>
                  </button>
                )}
              </div>

              <div className="drama-reference-assets">
                <div className="drama-asset-panel-title">
                  <span>补充参考</span>
                  <small>{referenceAssetIds.length} / 10</small>
                </div>
                <div className="drama-reference-strip">
                  {referenceAssetIds.map((assetId, index) => {
                    const asset = assetMap.get(assetId);
                    return (
                      <div key={assetId}>
                        <AssetPreview asset={asset} compact />
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <button
                          type="button"
                          title="移除参考图"
                          onClick={() =>
                            setReferenceAssetIds((items) =>
                              items.filter((item) => item !== assetId),
                            )
                          }
                        >
                          <X size={12} />
                        </button>
                      </div>
                    );
                  })}
                  {referenceAssetIds.length < 10 && (
                    <button
                      className="drama-add-reference"
                      type="button"
                      onClick={() => setPickerMode("references")}
                    >
                      <Plus size={18} />
                      <span>添加参考</span>
                    </button>
                  )}
                </div>
              </div>

              <div className="drama-professional-slots">
                <div className="drama-asset-panel-title">
                  <span>专业资产槽位</span>
                  <small>
                    {assetSlotDefinitions[selected.kind].filter(
                      (slot) => Boolean(assetSlots[slot.id]),
                    ).length} /{" "}
                    {assetSlotDefinitions[selected.kind].length} 已填
                  </small>
                </div>
                <div className="drama-slot-generation-bar">
                  <label>
                    <span>图片工作流</span>
                    <select
                      value={selectedSlotModel?.id ?? ""}
                      disabled={Boolean(generatingSlot)}
                      onChange={(event) => setSlotModelId(event.target.value)}
                    >
                      {slotImageModels.map((model) => (
                        <option key={model.id} value={model.id}>
                          {model.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div>
                    <strong>
                      {slotReferenceIds.length} 张参考
                    </strong>
                    <small>
                      工作流要求 {slotImageMinimum}–{slotImageLimit} 张
                    </small>
                  </div>
                  {generatingSlot && (
                    <span className="drama-slot-generation-live">
                      <LoaderCircle className="spin" size={14} />
                      生成 {generatingSlot} · {slotTaskProgress || 1}%
                    </span>
                  )}
                </div>
                {slotError && (
                  <div className="drama-slot-error">
                    <X size={14} />
                    {slotError}
                  </div>
                )}
                <div
                  className={`drama-professional-slot-grid ${
                    assetSlotDefinitions[selected.kind].length === 1
                      ? "single"
                      : ""
                  }`}
                >
                  {assetSlotDefinitions[selected.kind].map((slot) => {
                    const slotAsset = assetSlots[slot.id]
                      ? assetMap.get(assetSlots[slot.id])
                      : null;
                    const slotCandidates = (selected.candidates ?? []).filter(
                      (candidate) => candidate.slot === slot.id,
                    );
                    const promptDraft =
                      slotPromptDrafts[slot.id] ??
                      selected.assetPrompts[slot.id] ??
                      buildAssetSlotPrompt(
                        selected,
                        slot.id,
                        slot.label,
                      );
                    return (
                      <label key={slot.id}>
                        <span>
                          {slot.label}
                          <small>{slot.hint}</small>
                        </span>
                        <div>
                          {slotAsset ? (
                            <img
                              src={backendResourceUrl(slotAsset.url)}
                              alt={slot.label}
                            />
                          ) : (
                            <ImagePlus size={18} />
                          )}
                          <select
                            value={assetSlots[slot.id] ?? ""}
                            onChange={(event) =>
                              setAssetSlots((current) => {
                                const next = { ...current };
                                if (event.target.value) {
                                  next[slot.id] = event.target.value;
                                } else {
                                  delete next[slot.id];
                                }
                                return next;
                              })
                            }
                          >
                            <option value="">绑定素材</option>
                            {imageAssets.map((asset) => (
                              <option key={asset.id} value={asset.id}>
                                {assetName(asset)}
                              </option>
                            ))}
                          </select>
                        </div>
                        <button
                          type="button"
                          disabled={
                            !selectedSlotModel || Boolean(generatingSlot)
                          }
                          onClick={() =>
                            void generateSlot(slot.id, slot.label)
                          }
                        >
                          {generatingSlot === slot.id ? (
                            <LoaderCircle className="spin" size={13} />
                          ) : (
                            <Sparkles size={13} />
                          )}
                          {generatingSlot === slot.id
                            ? "生成中"
                            : slotAsset
                              ? "重新生成"
                              : "按说明生成"}
                        </button>
                        {slotCandidates.length > 1 && (
                          <span className="drama-slot-candidate-history">
                            <select
                              aria-label={`${slot.label}历史候选`}
                              value={assetSlots[slot.id] ?? ""}
                              disabled={candidateSlotBusy === slot.id}
                              onChange={async (event) => {
                                const assetId = event.target.value;
                                if (!assetId) return;
                                setCandidateSlotBusy(slot.id);
                                try {
                                  const updated = await bindDramaEntityAsset(
                                    selected.id,
                                    slot.id,
                                    assetId,
                                  );
                                  setAssetSlots(updated.assetSlots);
                                  await library.refresh();
                                  await production.refresh();
                                } catch (error) {
                                  setSlotError((error as Error).message);
                                } finally {
                                  setCandidateSlotBusy(null);
                                }
                              }}
                            >
                              {slotCandidates.map((candidate) => (
                                <option
                                  key={candidate.id}
                                  value={candidate.assetId}
                                >
                                  {candidateStatusLabel(candidate.status)}
                                  {" · "}
                                  {candidate.assetId.slice(0, 8)}
                                </option>
                              ))}
                            </select>
                            <small>
                              {slotCandidates.length} 个历史候选
                            </small>
                          </span>
                        )}
                        <details className="drama-asset-slot-prompt">
                          <summary>编辑槽位提示词</summary>
                          <textarea
                            value={promptDraft}
                            rows={5}
                            onChange={(event) =>
                              setSlotPromptDrafts((current) => ({
                                ...current,
                                [slot.id]: event.target.value,
                              }))
                            }
                          />
                          <button
                            type="button"
                            onClick={() => void saveSlotPrompt(slot.id)}
                          >
                            保存提示词版本
                          </button>
                        </details>
                      </label>
                    );
                  })}
                </div>
              </div>

              <footer className="drama-entity-actions">
                <span>
                  锁定后作为镜头生成的稳定视觉依据；仍可解锁后再编辑草稿。
                </span>
                <button
                  type="button"
                  disabled={library.saving}
                  onClick={() => void saveDraft("draft")}
                >
                  <Save size={14} /> 保存草稿
                </button>
                <button
                  className="primary"
                  type="button"
                  disabled={!primaryAssetId || library.saving}
                  onClick={() => void saveDraft("locked")}
                >
                  <LockKeyhole size={14} /> 锁定资产
                </button>
              </footer>
            </>
          ) : (
            <div className="drama-entity-editor-empty">
              <span><Images size={30} /></span>
              <h4>选择一个资产开始编辑</h4>
              <p>角色、服装、道具、场景和风格都使用同一套版本与锁定机制。</p>
              <button type="button" onClick={() => setShowCreate(true)}>
                <Plus size={14} /> 新建{kindLabel(activeKind)}
              </button>
            </div>
          )}
        </section>

        <aside className="drama-shot-binding">
          <div className="drama-asset-panel-title">
            <span>镜头引用</span>
            <small>Agent 的生成上下文</small>
          </div>
          {shots.length ? (
            <>
              <label className="drama-shot-select">
                <span>选择镜头</span>
                <select
                  value={activeShotId ?? ""}
                  onChange={(event) => setActiveShotId(event.target.value)}
                >
                  {shots.map((shot) => (
                    <option key={shot.id} value={shot.id}>
                      {shot.episodeTitle} · {shot.sceneHeading} · 镜 {shot.shotNumber} {shot.title}
                    </option>
                  ))}
                </select>
              </label>
              {activeShot && (
                <>
                  <div className="drama-shot-binding-context">
                    <span><Clapperboard size={14} /> 镜头 {activeShot.shotNumber}</span>
                    <strong>{activeShot.title}</strong>
                    <p>{activeShot.description || "尚未填写镜头画面描述。"}</p>
                  </div>
                  <div className="drama-binding-entities">
                    {library.entities.map((entity) => {
                      const checked = shotReferenceIds.includes(entity.id);
                      return (
                        <button
                          key={entity.id}
                          className={checked ? "checked" : ""}
                          type="button"
                          onClick={() => toggleShotEntity(entity)}
                        >
                          <span>
                            {checked ? (
                              <Check size={13} />
                            ) : (
                              entityKindIcon(entity.kind)
                            )}
                          </span>
                          <div>
                            <strong>{entity.name}</strong>
                            <small>
                              {kindLabel(entity.kind)} ·{" "}
                              {entity.status === "locked" ? "已锁定" : "草稿"}
                            </small>
                          </div>
                        </button>
                      );
                    })}
                    {!library.entities.length && (
                      <p>先创建资产，再关联到镜头。</p>
                    )}
                  </div>
                  <button
                    className="drama-save-binding"
                    type="button"
                    disabled={savingReferences}
                    onClick={() => void saveShotReferences()}
                  >
                    {savingReferences ? (
                      <LoaderCircle className="spin" size={15} />
                    ) : (
                      <Link2 size={15} />
                    )}
                    保存镜头引用
                  </button>
                </>
              )}
            </>
          ) : (
            <div className="drama-binding-empty">
              <Clapperboard size={26} />
              <strong>还没有可关联的镜头</strong>
              <p>先在“镜头拆解”阶段创建分集、场次和镜头。</p>
            </div>
          )}
        </aside>
      </div>

      {pickerMode && (
        <div
          className="drama-asset-picker-backdrop"
          role="presentation"
          onMouseDown={() => setPickerMode(null)}
        >
          <section
            className="drama-asset-picker"
            role="dialog"
            aria-modal="true"
            aria-label="选择素材"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header>
              <div>
                <span>{pickerMode === "primary" ? "选择主视觉" : "添加参考图"}</span>
                <strong>
                  {pickerMode === "primary"
                    ? "这张图会定义资产的标准形象"
                    : `已选择 ${referenceAssetIds.length} / 10`}
                </strong>
              </div>
              <button type="button" onClick={() => setPickerMode(null)}>
                <X size={18} />
              </button>
            </header>
            <div className="drama-picker-toolbar">
              <label>
                <Search size={15} />
                <input
                  autoFocus
                  value={assetQuery}
                  onChange={(event) => setAssetQuery(event.target.value)}
                  placeholder="搜索素材名称或 ID"
                />
              </label>
              <label className="drama-picker-upload">
                {library.uploading ? (
                  <LoaderCircle className="spin" size={15} />
                ) : (
                  <Upload size={15} />
                )}
                上传图片
                <input
                  type="file"
                  accept="image/*"
                  multiple
                  disabled={library.uploading}
                  onChange={(event) => {
                    void library.upload(
                      Array.from(event.target.files ?? []),
                    );
                    event.target.value = "";
                  }}
                />
              </label>
            </div>
            <div className="drama-picker-grid">
              {imageAssets.map((asset) => {
                const selectedAsset =
                  pickerMode === "primary"
                    ? primaryAssetId === asset.id
                    : referenceAssetIds.includes(asset.id);
                return (
                  <button
                    key={asset.id}
                    className={selectedAsset ? "selected" : ""}
                    type="button"
                    onClick={() => chooseAsset(asset.id)}
                  >
                    <img
                      src={backendResourceUrl(asset.url)}
                      alt={assetName(asset)}
                    />
                    <span>
                      <strong>{assetName(asset)}</strong>
                      <small>{assetDimensions(asset)}</small>
                    </span>
                    {selectedAsset && (
                      <em><CheckCircle2 size={16} /></em>
                    )}
                  </button>
                );
              })}
              {!imageAssets.length && (
                <div className="drama-picker-empty">
                  <ImagePlus size={30} />
                  <strong>{assetQuery ? "没有匹配的图片" : "素材库里还没有图片"}</strong>
                  <p>上传参考图，或在多模态创作工作台生成候选图。</p>
                </div>
              )}
            </div>
            {pickerMode === "references" && (
              <footer>
                <span>最多选择 10 张，保持主体、服装、场景与风格一致。</span>
                <button type="button" onClick={() => setPickerMode(null)}>
                  完成选择
                </button>
              </footer>
            )}
          </section>
        </div>
      )}
    </section>
  );
}

function AssetPreview({
  asset,
  compact = false,
}: {
  asset: LibraryAsset | undefined;
  compact?: boolean;
}) {
  if (!asset) {
    return (
      <span className={compact ? "drama-asset-preview compact" : "drama-asset-preview"}>
        <ImagePlus size={compact ? 17 : 26} />
      </span>
    );
  }
  return (
    <span className={compact ? "drama-asset-preview compact" : "drama-asset-preview"}>
      <img src={backendResourceUrl(asset.url)} alt={assetName(asset)} />
    </span>
  );
}

function chooseSlotModel(models: Model[], referenceCount: number) {
  return models
    .filter((model) => {
      const minimum = imageMinimumFor(model);
      const maximum = imageLimitFor(model);
      return (
        referenceCount >= minimum &&
        referenceCount <= maximum
      );
    })
    .sort((left, right) => {
      const leftPreferred =
        referenceCount > 0 && left.name.includes("多图参考") ? 4 : 0;
      const rightPreferred =
        referenceCount > 0 && right.name.includes("多图参考") ? 4 : 0;
      return (
        rightPreferred -
        leftPreferred ||
        imageLimitFor(left) - imageLimitFor(right)
      );
    })[0];
}

function imageMinimumFor(model: Model | undefined) {
  return (
    model?.references?.find((reference) => reference.type === "image")
      ?.min ?? 0
  );
}

function imageLimitFor(model: Model | undefined) {
  return (
    model?.references?.find((reference) => reference.type === "image")
      ?.max ?? 0
  );
}

function buildAssetSlotPrompt(
  entity: DramaEntity,
  slotId: string,
  slotLabel: string,
) {
  const identity = [
    `资产：${entity.name}（${kindLabel(entity.kind)}）`,
    entity.description
      ? `既定视觉设定：${entity.description}`
      : "严格延续参考图中的身份、造型、材质与色彩。",
  ].join("\n");
  const instruction: Record<string, string> = {
    character_sheet:
      "生成单张 16:9 角色设定总表。所有内容必须排在同一张连续画布内：头部与面部特写；全身正面、正侧面和背面视图；表情特写；服装、纹样、发饰与材质细节特写。各视图的人物脸型、体型比例、妆发、服装左右方向和色彩必须一致，使用统一中性背景与柔光。这是一张总表，不是多张独立图片，不要输出多文件拼贴，不要添加文字标签、字幕、水印或装饰边框。",
    master:
      "生成无人物的场景总览图。展示空间整体结构、主要入口、家具陈设、前后景关系、光源方向与时代地域特征，用于镜头调度。画面中不要出现人物。",
    interior:
      "生成同一场景的内景分场景。保持总场景的空间逻辑和材质，展示室内陈设、门窗、光源和行动通道，画面中不要出现人物。",
    exterior:
      "生成同一场景的外景分场景。保持建筑、地理、时间和空间关系一致，展示入口、道路或环境层次，画面中不要出现人物。",
    lighting_reference:
      "生成该场景的灯光参考图。明确主光方向、色温、明暗反差、时间氛围和阴影方向，保持场景结构不变，画面中不要出现人物。",
    front:
      "生成服装正面标准图。完整展示版型、层次、纹样、配饰和鞋履，中性背景，均匀柔光。",
    back:
      "生成同一套服装的背面标准图。保持纹样、腰带、披风和外袍结构一致，中性背景，均匀柔光。",
    fabric_detail:
      "生成服装材质细节参考。展示纹样、刺绣、织法、光泽、磨损与颜色，保持整体造型一致。",
    hero:
      "生成道具主视觉。物件完整居中，结构、材质、磨损、颜色和时代特征清楚，中性背景，无人物。",
    scale_reference:
      "生成道具比例参考图。展示道具与成年人手部或身体的相对尺寸关系，造型与主视觉完全一致。",
    moodboard:
      "生成项目视觉风格板。以无文字的构图整理色彩、光线、材质、镜头语言和氛围参考，明确整体统一风格。",
  };
  return [
    instruction[slotId] || `生成${slotLabel}标准参考图。`,
    identity,
    "这是短剧制作资产，不是海报；不要添加文字、字幕、水印、边框、拼贴标签或与设定冲突的现代元素。",
  ].join("\n\n");
}

function kindLabel(kind: DramaEntityKind) {
  return entityKinds.find((item) => item.id === kind)?.label ?? kind;
}

function entityKindIcon(kind: DramaEntityKind) {
  const Icon = entityKinds.find((item) => item.id === kind)?.icon ?? Images;
  return <Icon size={13} />;
}

function assetName(asset: LibraryAsset | undefined) {
  if (!asset) return "未命名素材";
  return String(
    asset.metadata.originalFilename ??
      asset.metadata.filename ??
      `${asset.type} · ${asset.id.slice(0, 8)}`,
  );
}

function candidateStatusLabel(
  status: "candidate" | "selected" | "rejected" | "superseded",
) {
  return {
    candidate: "待选择",
    selected: "当前使用",
    rejected: "已弃用",
    superseded: "历史版本",
  }[status];
}

function assetDimensions(asset: LibraryAsset) {
  return asset.width && asset.height
    ? `${asset.width} × ${asset.height}`
    : asset.mimeType || "图片";
}
