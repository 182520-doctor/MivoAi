"use client";

import { useState } from "react";
import { Settings2, X } from "lucide-react";
import type { Model } from "../types";

type Props = {
  open: boolean;
  models: Model[];
  selectedId: string;
  loading: boolean;
  saving: boolean;
  notice: string;
  disabled: boolean;
  onClose: () => void;
  onSelect: (id: string) => Promise<void>;
  onSaveKey: (key: string) => Promise<boolean>;
};

export function ModelSettings(props: Props) {
  const {
    open,
    models,
    selectedId,
    loading,
    saving,
    notice,
    disabled,
    onClose,
    onSelect,
    onSaveKey,
  } = props;
  const [key, setKey] = useState("");
  const selected = models.find((model) => model.id === selectedId);
  function close() {
    setKey("");
    onClose();
  }
  async function save() {
    if (await onSaveKey(key)) setKey("");
  }
  return (
    <>
      {open && (
        <button
          className="drawer-backdrop"
          type="button"
          aria-label="关闭模型设置"
          onClick={close}
        />
      )}
      <aside
        className={`settings-drawer ${open ? "open" : ""}`}
        aria-label="模型与偏好"
        aria-busy={saving || loading}
      >
        <div className="drawer-head">
          <div>
            <Settings2 size={18} />
            <strong>模型与偏好</strong>
          </div>
          <button type="button" title="关闭" onClick={close}>
            <X size={18} />
          </button>
        </div>
        <label className="settings-field">
          默认文本模型
          <select
            value={selectedId}
            disabled={loading || saving || disabled}
            onChange={(event) => void onSelect(event.target.value)}
          >
            {models
              .filter((model) => model.capabilities.includes("text"))
              .map((model) => (
                <option key={model.id} value={model.id}>
                  {model.providerName} / {model.name}
                  {model.integrationStatus !== "ready" ? "（待接入）" : ""}
                </option>
              ))}
          </select>
        </label>
        {selected?.providerId === "volcengine" && (
          <>
            <label className="settings-field">
              火山引擎 API Key
              <input
                type="password"
                value={key}
                onChange={(event) => setKey(event.target.value)}
                placeholder="输入 Ark API Key"
                autoComplete="off"
              />
            </label>
            <button
              className="save-settings"
              type="button"
              disabled={!key.trim() || saving}
              onClick={() => void save()}
            >
              {saving ? "保存中…" : "保存 Key"}
            </button>
          </>
        )}
        {notice && (
          <p className="settings-notice" role="status">
            {notice}
          </p>
        )}
        <div className="settings-status">
          <span
            className={
              selected?.configured || selected?.providerId === "codex_local"
                ? "online"
                : ""
            }
          />
          <span>
            {selected?.configured || selected?.providerId === "codex_local"
              ? "当前模型已配置"
              : "当前模型尚未配置 API Key"}
          </span>
        </div>
      </aside>
    </>
  );
}
