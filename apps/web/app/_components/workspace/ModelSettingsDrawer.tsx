import { Settings2 } from "lucide-react";
import Link from "next/link";
import type { Model } from "../../_features/models/types";

type ModelSettingsDrawerProps = {
  open: boolean;
  models: Model[];
  selectedModel: Model | undefined;
  selectedModelId: string;
  apiKey: string;
  notice: string;
  onChangeModel: (modelId: string) => void;
  onChangeApiKey: (value: string) => void;
  onClose: () => void;
  onSaveKey: () => void;
};

export function ModelSettingsDrawer({
  open,
  models,
  selectedModel,
  selectedModelId,
  apiKey,
  notice,
  onChangeModel,
  onChangeApiKey,
  onClose,
  onSaveKey,
}: ModelSettingsDrawerProps) {
  return (
    <aside className={`settings-drawer ${open ? "open" : ""}`}>
      <div className="drawer-head">
        <div>
          <Settings2 size={18} />
          <strong>模型与偏好</strong>
        </div>
        <button type="button" title="关闭" onClick={onClose}>
          ×
        </button>
      </div>
      <p className="settings-help">
        选择默认文本模型。火山方舟模型需要填入你自己的 API Key，密钥只保存在本地后端。
      </p>
      <label className="settings-field">
        默认文本模型
        <select
          value={selectedModelId}
          onChange={(event) => onChangeModel(event.target.value)}
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
      {selectedModel?.providerId === "volcengine" && (
        <>
          <label className="settings-field">
            火山引擎 API Key
            <input
              type="password"
              value={apiKey}
              onChange={(event) => onChangeApiKey(event.target.value)}
              placeholder="输入 Ark API Key"
              autoComplete="off"
            />
          </label>
          <button
            className="save-settings"
            type="button"
            disabled={!apiKey.trim()}
            onClick={onSaveKey}
          >
            保存 Key
          </button>
        </>
      )}
      {notice && <p className="settings-notice">{notice}</p>}
      <Link className="settings-model-center" href="/models">
        打开模型中心
      </Link>
      <div className="settings-status">
        <span
          className={
            selectedModel?.configured ||
            selectedModel?.providerId === "codex_local"
              ? "online"
              : ""
          }
        />
        <span>
          {selectedModel?.configured ||
          selectedModel?.providerId === "codex_local"
            ? "当前模型已配置"
            : "当前模型尚未配置 API Key"}
        </span>
      </div>
    </aside>
  );
}
