"use client";

import {
  Captions,
  CheckCircle2,
  CircleAlert,
  Clock3,
  Download,
  Film,
  LoaderCircle,
  Music2,
  Play,
  Plus,
  Sparkles,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import type { LibraryAsset } from "../../_features/assets/types";
import { mediaAssetUrl } from "../../_features/media/api";
import type {
  DramaAudioMix,
  DramaShot,
  DramaSubtitleStyle,
  DramaSubtitleCue,
} from "../../_features/drama/types";
import { useDramaAssets } from "../../_features/drama/useDramaAssets";
import { useDramaProduction } from "../../_features/drama/useDramaProduction";

type DramaTimelineBoardProps = {
  projectId: string;
  aspectRatio: string;
  refreshToken?: number;
};

const subtitlePresets: Array<{
  id: DramaSubtitleStyle["preset"];
  label: string;
  style: Omit<DramaSubtitleStyle, "preset">;
}> = [
  {
    id: "short_video",
    label: "短视频",
    style: {
      fontSize: 32,
      outline: 2,
      marginV: 110,
      primaryColor: "#FFFFFF",
      outlineColor: "#101010",
    },
  },
  {
    id: "cinema",
    label: "电影",
    style: {
      fontSize: 28,
      outline: 1.5,
      marginV: 96,
      primaryColor: "#FFF4E5",
      outlineColor: "#101418",
    },
  },
  {
    id: "minimal",
    label: "极简",
    style: {
      fontSize: 22,
      outline: 1,
      marginV: 72,
      primaryColor: "#F7F7F7",
      outlineColor: "#202020",
    },
  },
];

export function DramaTimelineBoard({
  projectId,
  aspectRatio,
  refreshToken = 0,
}: DramaTimelineBoardProps) {
  const production = useDramaProduction(projectId);
  const library = useDramaAssets(projectId);
  const [activeEpisodeId, setActiveEpisodeId] = useState<string | null>(null);
  const [activeShotId, setActiveShotId] = useState<string | null>(null);
  const [draftCues, setDraftCues] = useState<DramaSubtitleCue[]>([]);
  const [transition, setTransition] = useState<"none" | "crossfade">(
    "crossfade",
  );
  const [transitionDuration, setTransitionDuration] = useState(0.4);
  const [draftMix, setDraftMix] = useState<DramaAudioMix>({
    soundEffects: [],
    musicAssetId: null,
    musicVolumeDb: -18,
    ambienceAssetId: null,
    ambienceVolumeDb: -22,
    ducking: true,
  });

  useEffect(() => {
    if (!refreshToken) return;
    void production.refresh();
    void library.refresh();
    // The token is an explicit Agent mutation signal.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshToken]);
  const [subtitleStyle, setSubtitleStyle] = useState<DramaSubtitleStyle>({
    preset: "short_video",
    fontSize: 30,
    outline: 2,
    marginV: 96,
    primaryColor: "#FFFFFF",
    outlineColor: "#101010",
  });

  useEffect(() => {
    if (
      activeEpisodeId &&
      production.episodes.some((episode) => episode.id === activeEpisodeId)
    ) {
      return;
    }
    setActiveEpisodeId(production.episodes[0]?.id ?? null);
  }, [activeEpisodeId, production.episodes]);

  const episode =
    production.episodes.find((item) => item.id === activeEpisodeId) ??
    production.episodes[0] ??
    null;
  const shots = episode?.scenes.flatMap((scene) =>
    scene.shots.map((shot) => ({
      ...shot,
      sceneHeading: scene.heading,
    })),
  ) ?? [];
  const shot =
    shots.find((item) => item.id === activeShotId) ?? shots[0] ?? null;
  const totalDuration = shots.reduce(
    (duration, item) => duration + item.durationSeconds,
    0,
  );
  const effectiveDuration =
    totalDuration -
    (transition === "crossfade" && shots.length > 1
      ? transitionDuration * (shots.length - 1)
      : 0);
  const clipsReady = shots.filter((item) => item.videoAssetId).length;
  const approvedShots = shots.filter(
    (item) => item.status === "approved",
  ).length;
  const audioReady = shots.filter((item) => item.audioAssetId).length;
  const captionsReady = shots.filter((item) => item.dialogue.trim()).length;
  const allClipsReady = shots.length > 0 && clipsReady === shots.length;
  const allShotsApproved =
    shots.length > 0 && approvedShots === shots.length;
  const shotKey = shots.map((item) => item.id).join("|");
  const rendering = production.renderingEpisodeId === episode?.id;
  const persistedSubtitleKey =
    episode?.subtitleCues
      .map(
        (cue) =>
          `${cue.startSeconds}:${cue.endSeconds}:${cue.text}`,
      )
      .join("|") ?? "";
  const persistedMixKey = episode
    ? [
        episode.audioMix.musicAssetId,
        episode.audioMix.musicVolumeDb,
        episode.audioMix.ambienceAssetId,
        episode.audioMix.ambienceVolumeDb,
        episode.audioMix.ducking,
        JSON.stringify(episode.audioMix.soundEffects),
      ].join("|")
    : "";
  const persistedStyleKey = episode
    ? [
        episode.subtitleStyle.preset,
        episode.subtitleStyle.fontSize,
        episode.subtitleStyle.outline,
        episode.subtitleStyle.marginV,
        episode.subtitleStyle.primaryColor,
        episode.subtitleStyle.outlineColor,
      ].join("|")
    : "";
  const audioAssets = library.assets.filter(
    (asset) => asset.type === "audio",
  );

  useEffect(() => {
    if (activeShotId && shots.some((item) => item.id === activeShotId)) {
      return;
    }
    setActiveShotId(shots[0]?.id ?? null);
  }, [activeShotId, shotKey]);

  useEffect(() => {
    if (!episode) {
      setDraftCues([]);
      return;
    }
    setDraftCues(
      episode.subtitleCues.length
        ? episode.subtitleCues
        : deriveSubtitles(shots),
    );
  }, [episode?.id, persistedSubtitleKey, shotKey]);

  useEffect(() => {
    if (episode) setDraftMix(episode.audioMix);
  }, [episode?.id, persistedMixKey]);

  useEffect(() => {
    if (episode) setSubtitleStyle(episode.subtitleStyle);
  }, [episode?.id, persistedStyleKey]);

  async function saveSubtitles() {
    if (!episode) return false;
    return Boolean(
      await production.updateSubtitles(episode.id, draftCues),
    );
  }

  async function renderWithSubtitles() {
    if (!episode) return;
    if (!(await saveSubtitles())) return;
    if (
      !(await production.updateSubtitleStyle(
        episode.id,
        subtitleStyle,
      ))
    ) {
      return;
    }
    if (!(await production.updateAudioMix(episode.id, draftMix))) return;
    await production.renderEpisode(
      episode.id,
      transition,
      transitionDuration,
    );
  }

  return (
    <section className="drama-timeline-board">
      <header className="drama-timeline-head">
        <div>
          <span className="eyebrow">Episode Assembly</span>
          <h3>字幕与成片</h3>
          <p>按剧情顺序审核镜头、对白、音频和整集时长，确认后进入合成。</p>
        </div>
        <div className="drama-timeline-summary">
          <span><Clock3 size={13} /> {formatDuration(effectiveDuration)}</span>
          <span>{shots.length} 个镜头</span>
          <span>{clipsReady} 个成片就绪</span>
          <span>{approvedShots} 个镜头已审核</span>
        </div>
      </header>

      {!production.episodes.length ? (
        <div className="drama-timeline-empty">
          <Film size={32} />
          <strong>还没有分集</strong>
          <p>先在镜头拆解阶段创建分集和镜头，再回到这里组织整集时间线。</p>
        </div>
      ) : (
        <div className="drama-timeline-layout">
          <aside className="drama-timeline-episodes">
            <div className="drama-timeline-panel-title">
              <span>分集</span>
              <small>{production.episodes.length} 集</small>
            </div>
            {production.episodes.map((item) => {
              const itemShots = item.scenes.flatMap((scene) => scene.shots);
              const ready = itemShots.filter((shot) => shot.videoAssetId).length;
              return (
                <button
                  key={item.id}
                  className={item.id === episode?.id ? "active" : ""}
                  type="button"
                  onClick={() => setActiveEpisodeId(item.id)}
                >
                  <span>{String(item.episodeNumber).padStart(2, "0")}</span>
                  <div>
                    <strong>{item.title}</strong>
                    <small>{ready} / {itemShots.length} 镜有视频</small>
                  </div>
                </button>
              );
            })}
          </aside>

          <section className="drama-timeline-stage">
            <div className="drama-timeline-stage-head">
              <div>
                <span>整集预览</span>
                <h4>{episode?.title}</h4>
                <p>{episode?.synopsis || "按场次顺序组装已通过的镜头视频。"}</p>
              </div>
              <div>
                <span><Film size={13} /> {formatDuration(effectiveDuration)}</span>
                <span><Captions size={13} /> {captionsReady} 条对白</span>
              </div>
            </div>

            <div className="drama-timeline-ruler">
              {timelineTicks(effectiveDuration).map((tick) => (
                <span key={tick}>{formatDuration(tick)}</span>
              ))}
            </div>

            <div className="drama-timeline-sequence">
              {shots.map((item, index) => (
                <TimelineShot
                  key={item.id}
                  shot={item}
                  index={index}
                  active={item.id === shot?.id}
                  onSelect={() => setActiveShotId(item.id)}
                />
              ))}
              {!shots.length && (
                <div className="drama-timeline-sequence-empty">
                  <CircleAlert size={24} />
                  <strong>本集还没有镜头</strong>
                  <p>完成镜头拆解后才能建立整集时间线。</p>
                </div>
              )}
              {shots.length > 0 && (
                <article className="drama-timeline-ending">
                  <Sparkles size={20} />
                  <div>
                    <span>片尾</span>
                    <strong>本集结束</strong>
                  </div>
                </article>
              )}
            </div>

            {episode?.exportAssetId && (
              <div className="drama-timeline-export">
                <div>
                  <span>整集成片已生成</span>
                  <strong>导出资产 {episode.exportAssetId.slice(0, 8)}</strong>
                </div>
                <video
                  key={episode.exportAssetId}
                  src={mediaAssetUrl(episode.exportAssetId)}
                  controls
                  preload="metadata"
                />
              </div>
            )}

            <div className="drama-timeline-preview">
              <div>
                <span>当前选中</span>
                <strong>{shot?.title ?? "未选择镜头"}</strong>
                <small>{shot?.sceneHeading}</small>
              </div>
              {shot?.videoAssetId ? (
                <video
                  key={shot.videoAssetId}
                  src={mediaAssetUrl(shot.videoAssetId)}
                  controls
                  preload="metadata"
                />
              ) : (
                <div className="drama-timeline-no-video">
                  <Film size={28} />
                  <strong>镜头视频尚未生成</strong>
                  <p>返回上一阶段生成并绑定视频后，这里会自动进入时间线。</p>
                </div>
              )}
            </div>
          </section>

          <aside className="drama-timeline-audit">
            <div className="drama-timeline-panel-title">
              <span>成片检查</span>
              <small>{allClipsReady ? "可以合成" : "仍有缺失"}</small>
            </div>
            <div className="drama-timeline-checks">
              <CheckRow
                ok={allClipsReady}
                label="镜头视频"
                detail={`${clipsReady} / ${shots.length}`}
              />
              <CheckRow
                ok={audioReady === shots.length && shots.length > 0}
                label="镜头音频"
                detail={`${audioReady} / ${shots.length}`}
              />
              <CheckRow
                ok={draftCues.length > 0}
                label="对白字幕"
                detail={`${draftCues.length} 条 / ${captionsReady} 镜有对白`}
              />
            </div>

            {production.audit && (
              <div className="drama-timeline-audit-list">
                <div>
                  <span>连续性审查</span>
                  <strong>{production.audit.score} 分</strong>
                </div>
                {production.audit.issues.slice(0, 5).map((issue, index) => (
                  <article
                    key={`${issue.code}-${issue.shotId ?? issue.entityId ?? index}`}
                    className={issue.severity}
                  >
                    {issue.severity === "info" ? (
                      <CheckCircle2 size={14} />
                    ) : (
                      <CircleAlert size={14} />
                    )}
                    <span>{issue.message}</span>
                  </article>
                ))}
                {!production.audit.issues.length && (
                  <p>连续性检查通过，没有发现问题。</p>
                )}
              </div>
            )}

            {shot && (
              <div className="drama-timeline-cue">
                <span>当前对白</span>
                <p>{shot.dialogue || "该镜头没有对白，可补充字幕或环境声。"}</p>
                <div>
                  <span><Music2 size={12} /> {shot.audioAssetId ? "音频已绑定" : "缺少音频"}</span>
                  <span><Captions size={12} /> {shot.dialogue ? "字幕待排版" : "无对白"}</span>
                </div>
              </div>
            )}

            <div className="drama-timeline-subtitles">
              <div className="drama-timeline-subtitle-head">
                <div>
                  <span>字幕轨</span>
                  <small>{draftCues.length} 条 cue</small>
                </div>
                <button type="button" onClick={() => void saveSubtitles()}>
                  保存字幕
                </button>
              </div>
              <div className="drama-timeline-cues">
                {draftCues.map((cue, index) => (
                  <article key={index}>
                    <div>
                      <label>
                        <span>入点</span>
                        <input
                          type="number"
                          min={0}
                          step={0.1}
                          value={cue.startSeconds}
                          onChange={(event) => {
                            const start = Number(event.target.value);
                            setDraftCues((items) =>
                              items.map((item, itemIndex) =>
                                itemIndex === index
                                  ? { ...item, startSeconds: start }
                                  : item,
                              ),
                            );
                          }}
                        />
                      </label>
                      <label>
                        <span>出点</span>
                        <input
                          type="number"
                          min={0.1}
                          step={0.1}
                          value={cue.endSeconds}
                          onChange={(event) => {
                            const end = Number(event.target.value);
                            setDraftCues((items) =>
                              items.map((item, itemIndex) =>
                                itemIndex === index
                                  ? { ...item, endSeconds: end }
                                  : item,
                              ),
                            );
                          }}
                        />
                      </label>
                    </div>
                    <textarea
                      value={cue.text}
                      rows={2}
                      onChange={(event) => {
                        const text = event.target.value;
                        setDraftCues((items) =>
                          items.map((item, itemIndex) =>
                            itemIndex === index
                              ? { ...item, text }
                              : item,
                          ),
                        );
                      }}
                    />
                  </article>
                ))}
                {!draftCues.length && (
                  <p>镜头还没有对白，可先在剧本和镜头阶段补充。</p>
                )}
              </div>
            </div>

            <div className="drama-subtitle-style">
              <div className="drama-subtitle-style-head">
                <span>字幕样式</span>
                <strong
                  style={{
                    color: subtitleStyle.primaryColor,
                    fontSize: `${Math.max(13, subtitleStyle.fontSize * 0.45)}px`,
                    textShadow: `0 1px ${Math.max(1, subtitleStyle.outline)}px ${subtitleStyle.outlineColor}`,
                  }}
                >
                  字幕预览 Aa
                </strong>
              </div>
              <div className="drama-subtitle-presets">
                {subtitlePresets.map((preset) => (
                  <button
                    key={preset.id}
                    className={
                      subtitleStyle.preset === preset.id ? "active" : ""
                    }
                    type="button"
                    onClick={() =>
                      setSubtitleStyle({
                        ...preset.style,
                        preset: preset.id,
                      })
                    }
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
              <label>
                <span>字号 {subtitleStyle.fontSize}</span>
                <input
                  type="range"
                  min={18}
                  max={52}
                  step={1}
                  value={subtitleStyle.fontSize}
                  onChange={(event) =>
                    setSubtitleStyle((style) => ({
                      ...style,
                      preset: "custom",
                      fontSize: Number(event.target.value),
                    }))
                  }
                />
              </label>
              <label>
                <span>下边距 {subtitleStyle.marginV}</span>
                <input
                  type="range"
                  min={32}
                  max={260}
                  step={4}
                  value={subtitleStyle.marginV}
                  onChange={(event) =>
                    setSubtitleStyle((style) => ({
                      ...style,
                      preset: "custom",
                      marginV: Number(event.target.value),
                    }))
                  }
                />
              </label>
            </div>

            <div className="drama-timeline-transition">
              <div>
                <span>镜头转场</span>
                <small>
                  {transition === "crossfade"
                    ? `输出 ${formatDuration(effectiveDuration)}`
                    : "硬切"}
                </small>
              </div>
              <select
                value={transition}
                onChange={(event) =>
                  setTransition(
                    event.target.value as "none" | "crossfade",
                  )
                }
              >
                <option value="none">无转场 / 硬切</option>
                <option value="crossfade">交叉淡化</option>
              </select>
              {transition === "crossfade" && (
                <label>
                  <span>转场时长 {transitionDuration.toFixed(1)}s</span>
                  <input
                    type="range"
                    min={0.1}
                    max={1.5}
                    step={0.1}
                    value={transitionDuration}
                    onChange={(event) =>
                      setTransitionDuration(Number(event.target.value))
                    }
                  />
                </label>
              )}
            </div>

            <div className="drama-timeline-mix">
              <div className="drama-timeline-mix-head">
                <span>音乐与环境声</span>
                <label>
                  <input
                    type="checkbox"
                    checked={draftMix.ducking}
                    onChange={(event) =>
                      setDraftMix((mix) => ({
                        ...mix,
                        ducking: event.target.checked,
                      }))
                    }
                  />
                  对白时自动闪避音乐
                </label>
              </div>
              <label>
                <span>背景音乐</span>
                <select
                  value={draftMix.musicAssetId ?? ""}
                  onChange={(event) =>
                    setDraftMix((mix) => ({
                      ...mix,
                      musicAssetId: event.target.value || null,
                    }))
                  }
                >
                  <option value="">不使用背景音乐</option>
                  {audioAssets.map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {assetLabel(asset)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>音乐音量 {draftMix.musicVolumeDb.toFixed(0)} dB</span>
                <input
                  type="range"
                  min={-40}
                  max={0}
                  step={1}
                  value={draftMix.musicVolumeDb}
                  onChange={(event) =>
                    setDraftMix((mix) => ({
                      ...mix,
                      musicVolumeDb: Number(event.target.value),
                    }))
                  }
                />
              </label>
              <label>
                <span>环境声</span>
                <select
                  value={draftMix.ambienceAssetId ?? ""}
                  onChange={(event) =>
                    setDraftMix((mix) => ({
                      ...mix,
                      ambienceAssetId: event.target.value || null,
                    }))
                  }
                >
                  <option value="">不使用单独环境声</option>
                  {audioAssets.map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {assetLabel(asset)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>环境声音量 {draftMix.ambienceVolumeDb.toFixed(0)} dB</span>
                <input
                  type="range"
                  min={-40}
                  max={0}
                  step={1}
                  value={draftMix.ambienceVolumeDb}
                  onChange={(event) =>
                    setDraftMix((mix) => ({
                      ...mix,
                      ambienceVolumeDb: Number(event.target.value),
                    }))
                  }
                />
              </label>
              <div className="drama-sfx-head">
                <span>音效 cue</span>
                <button
                  type="button"
                  disabled={!audioAssets.length || draftMix.soundEffects.length >= 20}
                  onClick={() =>
                    setDraftMix((mix) => ({
                      ...mix,
                      soundEffects: [
                        ...mix.soundEffects,
                        {
                          assetId: audioAssets[0]?.id ?? "",
                          startSeconds: 0,
                          durationSeconds: 1,
                          volumeDb: -12,
                        },
                      ],
                    }))
                  }
                >
                  <Plus size={12} /> 添加音效
                </button>
              </div>
              <div className="drama-sfx-list">
                {draftMix.soundEffects.map((effect, index) => (
                  <article key={`${effect.assetId}-${index}`}>
                    <select
                      value={effect.assetId}
                      onChange={(event) =>
                        setDraftMix((mix) => ({
                          ...mix,
                          soundEffects: mix.soundEffects.map((item, itemIndex) =>
                            itemIndex === index
                              ? { ...item, assetId: event.target.value }
                              : item,
                          ),
                        }))
                      }
                    >
                      {audioAssets.map((asset) => (
                        <option key={asset.id} value={asset.id}>
                          {assetLabel(asset)}
                        </option>
                      ))}
                    </select>
                    <div>
                      <label>
                        <span>入点</span>
                        <input
                          type="number"
                          min={0}
                          step={0.1}
                          value={effect.startSeconds}
                          onChange={(event) =>
                            setDraftMix((mix) => ({
                              ...mix,
                              soundEffects: mix.soundEffects.map(
                                (item, itemIndex) =>
                                  itemIndex === index
                                    ? {
                                        ...item,
                                        startSeconds: Number(event.target.value),
                                      }
                                    : item,
                              ),
                            }))
                          }
                        />
                      </label>
                      <label>
                        <span>时长</span>
                        <input
                          type="number"
                          min={0.1}
                          step={0.1}
                          value={effect.durationSeconds}
                          onChange={(event) =>
                            setDraftMix((mix) => ({
                              ...mix,
                              soundEffects: mix.soundEffects.map(
                                (item, itemIndex) =>
                                  itemIndex === index
                                    ? {
                                        ...item,
                                        durationSeconds: Number(event.target.value),
                                      }
                                    : item,
                              ),
                            }))
                          }
                        />
                      </label>
                      <label>
                        <span>{effect.volumeDb} dB</span>
                        <input
                          type="range"
                          min={-40}
                          max={0}
                          step={1}
                          value={effect.volumeDb}
                          onChange={(event) =>
                            setDraftMix((mix) => ({
                              ...mix,
                              soundEffects: mix.soundEffects.map(
                                (item, itemIndex) =>
                                  itemIndex === index
                                    ? {
                                        ...item,
                                        volumeDb: Number(event.target.value),
                                      }
                                    : item,
                              ),
                            }))
                          }
                        />
                      </label>
                    </div>
                    <button
                      type="button"
                      title="删除音效"
                      onClick={() =>
                        setDraftMix((mix) => ({
                          ...mix,
                          soundEffects: mix.soundEffects.filter(
                            (_, itemIndex) => itemIndex !== index,
                          ),
                        }))
                      }
                    >
                      <X size={12} />
                    </button>
                  </article>
                ))}
              </div>
            </div>

            <div className="drama-timeline-format">
              <span>输出规格</span>
              <strong>{aspectRatio} · 最高 60fps · H.264 + AAC</strong>
              <small>合成时会统一画幅、帧率，并为无音频镜头补静音轨。</small>
              {episode.exportManifestId && (
                <a
                  href={`/api/drama/projects/episodes/${episode.id}/export-manifests`}
                  target="_blank"
                  rel="noreferrer"
                >
                  查看成片血缘清单
                </a>
              )}
            </div>

            <button
              className="drama-timeline-render"
              type="button"
              disabled={!allClipsReady || !allShotsApproved || rendering}
              title={
                !allClipsReady
                  ? "还有镜头视频未就绪"
                  : !allShotsApproved
                    ? "还有镜头未通过审核"
                    : "按时间线顺序合成整集"
              }
              onClick={() => void renderWithSubtitles()}
            >
              {rendering ? (
                <LoaderCircle className="spin" size={15} />
              ) : (
                <Download size={15} />
              )}
              {rendering
                ? "正在合成整集"
                : allShotsApproved
                  ? "渲染最终成片"
                  : "等待镜头审核"}
              <span>
                {allClipsReady
                  ? allShotsApproved
                    ? "FFmpeg"
                    : "未全部通过"
                  : "镜头未就绪"}
              </span>
            </button>
            {production.notice && (
              <span className="drama-timeline-error">{production.notice}</span>
            )}
            {production.loading && (
              <span className="drama-timeline-loading">
                <LoaderCircle className="spin" size={13} /> 正在读取制作状态
              </span>
            )}
          </aside>
        </div>
      )}
    </section>
  );
}

function TimelineShot({
  shot,
  index,
  active,
  onSelect,
}: {
  shot: DramaShot & { sceneHeading: string };
  index: number;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <article
      className={`${active ? "active" : ""} ${shot.videoAssetId ? "" : "missing"}`}
      onClick={onSelect}
    >
      <span className="drama-timeline-shot-index">
        {String(index + 1).padStart(2, "0")}
      </span>
      <div className="drama-timeline-shot-media">
        {shot.videoAssetId ? (
          <video
            src={mediaAssetUrl(shot.videoAssetId)}
            muted
            preload="metadata"
          />
        ) : shot.firstFrameAssetId ? (
          <img src={mediaAssetUrl(shot.firstFrameAssetId)} alt="" />
        ) : (
          <Film size={21} />
        )}
        {shot.videoAssetId && <Play size={16} />}
      </div>
      <div className="drama-timeline-shot-copy">
        <span>{shot.sceneHeading}</span>
        <strong>{shot.title}</strong>
        <small>{shot.dialogue || "无对白"}</small>
      </div>
      <div className="drama-timeline-shot-status">
        <span>
          <Clock3 size={12} /> {formatDuration(shot.durationSeconds)}
        </span>
        {shot.audioAssetId && <Music2 size={13} />}
        {shot.videoAssetId ? (
          <CheckCircle2 size={14} />
        ) : (
          <CircleAlert size={14} />
        )}
      </div>
    </article>
  );
}

function CheckRow({
  ok,
  label,
  detail,
}: {
  ok: boolean;
  label: string;
  detail: string;
}) {
  return (
    <div className={ok ? "ok" : ""}>
      <span>{ok ? <CheckCircle2 size={15} /> : <CircleAlert size={15} />}</span>
      <div>
        <strong>{label}</strong>
        <small>{detail}</small>
      </div>
    </div>
  );
}

function formatDuration(seconds: number) {
  const value = Math.max(0, Math.round(seconds));
  return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, "0")}`;
}

function timelineTicks(total: number) {
  if (total <= 0) return [0];
  const midpoint = total / 2;
  return [0, midpoint, total];
}

function assetLabel(asset: LibraryAsset) {
  const operation = String(asset.metadata.operation ?? "");
  if (operation === "tts") {
    const voice = String(asset.metadata.voiceName ?? "配音");
    const text = String(asset.metadata.text ?? "").slice(0, 18);
    return `${voice} · ${text}`;
  }
  if (operation === "extract_audio") {
    const source = String(asset.metadata.sourceAssetId ?? "");
    return `视频原声 · ${source.slice(0, 8)}`;
  }
  const name = asset.metadata.originalFilename ?? "音频素材";
  return `${String(name)} · ${asset.id.slice(0, 8)}`;
}

function deriveSubtitles(
  shots: Array<DramaShot & { sceneHeading: string }>,
) {
  let cursor = 0;
  const cues: DramaSubtitleCue[] = [];
  for (const shot of shots) {
    const duration = Math.max(0.1, shot.durationSeconds);
    if (shot.dialogue.trim()) {
      cues.push({
        startSeconds: Number(cursor.toFixed(2)),
        endSeconds: Number((cursor + duration).toFixed(2)),
        text: shot.dialogue.trim(),
      });
    }
    cursor += duration;
  }
  return cues;
}
