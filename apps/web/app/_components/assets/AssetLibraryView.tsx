"use client";

import {
  FileAudio,
  FileImage,
  FileText,
  Film,
  FolderOpen,
  HardDrive,
  LoaderCircle,
  RefreshCw,
  Search,
  Upload,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  loadAssets,
  uploadAssets,
} from "../../_features/assets/api";
import type {
  AssetLibraryResponse,
  LibraryAsset,
} from "../../_features/assets/types";

const assetTypes = [
  { type: "image", label: "图片素材", icon: FileImage },
  { type: "video", label: "视频素材", icon: Film },
  { type: "audio", label: "音频素材", icon: FileAudio },
] as const;

const assetFilters = [
  { type: "all", label: "全部" },
  { type: "image", label: "图片" },
  { type: "video", label: "视频" },
  { type: "audio", label: "音频" },
  { type: "file", label: "其他文件" },
] as const;

export function AssetLibraryView() {
  const [data, setData] = useState<AssetLibraryResponse>({
    assets: [],
    summary: {},
  });
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<(typeof assetFilters)[number]["type"]>(
    "all",
  );
  const [query, setQuery] = useState("");

  async function refresh() {
    setLoading(true);
    setError("");
    try {
      setData(await loadAssets());
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function onUpload(files: File[]) {
    if (!files.length) return;
    setUploading(true);
    setError("");
    try {
      await uploadAssets(files);
      await refresh();
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setUploading(false);
    }
  }

  const visibleAssets = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return data.assets.filter((asset) => {
      if (filter !== "all" && asset.type !== filter) return false;
      if (!keyword) return true;
      const searchable = [
        asset.id,
        asset.type,
        asset.mimeType ?? "",
        asset.taskId ?? "",
        String(asset.metadata.originalFilename ?? ""),
        String(asset.metadata.model ?? ""),
      ]
        .join(" ")
        .toLowerCase();
      return searchable.includes(keyword);
    });
  }, [data.assets, filter, query]);

  return (
    <main className="workbench-page asset-library-page">
      <h1 className="visually-hidden">素材库</h1>
      {error && <div className="generation-error">{error}</div>}

      <section className="stat-strip">
        {assetTypes.map(({ type, label, icon: Icon }) => (
          <article key={type}>
            <Icon size={19} />
            <div>
              <span>{label}</span>
              <strong>{data.summary[type] ?? 0}</strong>
            </div>
          </article>
        ))}
        <article>
          <HardDrive size={19} />
          <div>
            <span>已使用空间</span>
            <strong>{formatBytes(data.summary.totalSize ?? 0)}</strong>
          </div>
        </article>
      </section>

      <section className="asset-library-toolbar" aria-label="筛选素材">
        <div className="asset-library-filters">
          {assetFilters.map((item) => (
            <button
              key={item.type}
              className={filter === item.type ? "active" : ""}
              type="button"
              onClick={() => setFilter(item.type)}
            >
              {item.label}
              <span>
                {item.type === "all"
                  ? data.assets.length
                  : data.assets.filter((asset) => asset.type === item.type)
                      .length}
              </span>
            </button>
          ))}
        </div>
        <label className="asset-library-search">
          <Search size={16} />
          <input
            aria-label="搜索素材"
            placeholder="搜索文件名、模型或任务 ID"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <div className="workspace-toolbar-actions">
          <button
            className="compact-action"
            type="button"
            onClick={() => void refresh()}
          >
            <RefreshCw className={loading ? "spin" : ""} size={15} />
            刷新
          </button>
          <label className="compact-action asset-upload-action">
            {uploading ? (
              <LoaderCircle className="spin" size={15} />
            ) : (
              <Upload size={15} />
            )}
            上传素材
            <input
              type="file"
              multiple
              disabled={uploading}
              onChange={(event) => {
                void onUpload(Array.from(event.target.files ?? []));
                event.target.value = "";
              }}
            />
          </label>
        </div>
      </section>

      {visibleAssets.length > 0 ? (
        <section className="asset-library-grid">
          {visibleAssets.map((asset) => (
            <AssetCard asset={asset} key={asset.id} />
          ))}
        </section>
      ) : (
        !loading && (
          <section className="empty-library">
            <span className="empty-library-icon">
              <FolderOpen size={30} />
            </span>
            <h2>{data.assets.length ? "没有符合条件的素材" : "素材库还是空的"}</h2>
            <p>
              {data.assets.length
                ? "调整素材类型、文件名、模型或任务 ID 后重试。"
                : "上传参考素材或提交生成任务后，结果会出现在这里。"}
            </p>
          </section>
        )
      )}
    </main>
  );
}

function AssetCard({ asset }: { asset: LibraryAsset }) {
  return (
    <article className="asset-library-card">
      <div className="asset-library-preview">
        {asset.type === "image" ? (
          <img src={asset.url} alt="图片素材" />
        ) : asset.type === "video" ? (
          <video src={asset.url} muted controls />
        ) : asset.type === "audio" ? (
          <FileAudio size={34} />
        ) : (
          <FileText size={34} />
        )}
      </div>
      <div className="asset-library-copy">
        <div>
          <strong>{assetTypeLabel(asset.type)}</strong>
          <span>{sourceLabel(asset.source)}</span>
        </div>
        <p>
          {asset.width && asset.height
            ? `${asset.width} × ${asset.height}`
            : asset.mimeType || "未知格式"}
          {asset.size ? ` · ${formatBytes(asset.size)}` : ""}
        </p>
        <div className="asset-library-meta">
          <span>{formatTime(asset.createdAt)}</span>
          {asset.taskId && <code>{asset.taskId.slice(0, 8)}</code>}
          {Boolean(asset.metadata.test) && <span>工作流测试</span>}
        </div>
      </div>
    </article>
  );
}

function assetTypeLabel(type: string) {
  return {
    image: "图片",
    video: "视频",
    audio: "音频",
    file: "文件",
  }[type] ?? type;
}

function sourceLabel(source: string) {
  return {
    upload: "用户上传",
    generated: "生成结果",
    remote: "远程素材",
  }[source] ?? source;
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function formatTime(value: string) {
  const date = new Date(value.replace(" ", "T") + "Z");
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("zh-CN", { hour12: false });
}
