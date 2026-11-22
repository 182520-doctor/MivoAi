"use client";

import {
  CheckCircle2,
  FlaskConical,
  KeyRound,
  LoaderCircle,
  Network,
  TriangleAlert,
} from "lucide-react";
import { useState } from "react";
import { testTextModel } from "../../_features/models/api";
import type { Model, ModelTestResult } from "../../_features/models/types";
import { useModelSettings } from "../../_features/models/useModelSettings";
import { ModelsSectionNav } from "./ModelsSectionNav";

export function ConnectionsView() {
  const settings = useModelSettings();
  const [testPrompt, setTestPrompt] = useState("只回复：模型连接正常");
  const [testingId, setTestingId] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, ModelTestResult>>({});
  const textModels = settings.models.filter((model) =>
    model.capabilities.includes("text"),
  );

  async function runTest(model: Model) {
    setTestingId(model.id);
    try {
      const result = await testTextModel(
        model.id,
        model.providerId,
        testPrompt,
      );
      setResults((current) => ({ ...current, [model.id]: result }));
      await settings.loadSettings();
    } catch (error) {
      setResults((current) => ({
        ...current,
        [model.id]: {
          success: false,
          modelId: model.id,
          providerId: model.providerId,
          latencyMs: 0,
          message: (error as Error).message,
          responsePreview: "",
        },
      }));
    } finally {
      setTestingId(null);
    }
  }

  return (
    <main className="workbench-page model-page">
      <h1 className="visually-hidden">连接与测试</h1>
      <ModelsSectionNav active="connections" />

      <section className="connections-layout">
        <aside className="workbench-panel connections-form">
          <div className="panel-heading">
            <div>
              <Network size={18} />
              <strong>连接配置</strong>
            </div>
          </div>
          <div className="model-config-body">
            <label className="workbench-field">
              <span>默认文本模型</span>
              <select
                value={settings.selectedModelId}
                onChange={(event) =>
                  void settings.selectModel(event.target.value)
                }
              >
                {textModels.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.providerName} / {model.name}
                  </option>
                ))}
              </select>
            </label>

            {settings.selectedModel?.providerId === "volcengine" && (
              <>
                <label className="workbench-field">
                  <span>火山方舟 API Key</span>
                  <input
                    type="password"
                    value={settings.apiKey}
                    onChange={(event) => settings.setApiKey(event.target.value)}
                    placeholder="输入 Ark API Key"
                    autoComplete="off"
                  />
                </label>
                <button
                  className="secondary-action"
                  type="button"
                  disabled={!settings.apiKey.trim()}
                  onClick={() => void settings.saveVolcengineKey()}
                >
                  保存密钥
                </button>
              </>
            )}

            <label className="workbench-field model-test-prompt">
              <span>测试提示词</span>
              <textarea
                rows={4}
                value={testPrompt}
                onChange={(event) => setTestPrompt(event.target.value)}
              />
            </label>
            {settings.settingsNotice && (
              <p className="settings-notice">{settings.settingsNotice}</p>
            )}
            <div className="security-note">
              <KeyRound size={16} />
              <p>
                API Key 只发送到本地后端并加密保存。测试提示词会发送给所选外部模型。
              </p>
            </div>
          </div>
        </aside>

        <section className="connections-model-list">
          <div className="connections-list-head">
            <div>
              <span>文本模型</span>
              <h2>连接状态与测试</h2>
            </div>
            <span>{textModels.length} 个模型</span>
          </div>
          {textModels.map((model) => {
            const result = results[model.id];
            const configured =
              model.configured || model.providerId === "codex_local";
            return (
              <article className="connection-model-row" key={model.id}>
                <span className="model-provider-icon">
                  <Network size={18} />
                </span>
                <div className="connection-model-copy">
                  <strong>{model.name}</strong>
                  <span>
                    {model.providerName} · {model.modelKey}
                  </span>
                </div>
                <span
                  className={`model-status ${
                    configured && model.integrationStatus === "ready"
                      ? "ready"
                      : ""
                  }`}
                >
                  {configured && model.integrationStatus === "ready"
                    ? "已配置"
                    : "缺凭证"}
                </span>
                <button
                  className="test-button"
                  type="button"
                  disabled={testingId === model.id}
                  onClick={() => void runTest(model)}
                >
                  {testingId === model.id ? (
                    <LoaderCircle className="spin" size={14} />
                  ) : (
                    <FlaskConical size={14} />
                  )}
                  测试
                </button>
                {result && (
                  <div
                    className={`model-test-result ${
                      result.success ? "success" : "failure"
                    }`}
                  >
                    {result.success ? (
                      <CheckCircle2 size={15} />
                    ) : (
                      <TriangleAlert size={15} />
                    )}
                    <div>
                      <strong>{result.message}</strong>
                      {result.responsePreview && (
                        <p>{result.responsePreview}</p>
                      )}
                    </div>
                  </div>
                )}
              </article>
            );
          })}
        </section>
      </section>
    </main>
  );
}
