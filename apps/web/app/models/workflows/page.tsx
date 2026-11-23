"use client";

import { ModelsSectionNav } from "../../_components/models/ModelsSectionNav";
import { WorkflowManager } from "../../_components/models/WorkflowManager";

export default function WorkflowModelsPage() {
  return (
    <main className="workbench-page model-page">
      <header className="page-heading compact">
        <div>
          <span className="eyebrow">模型中心 / 工作流</span>
          <h1>ComfyUI 工作流</h1>
          <p>
            扫描本机工作流、导入模型、设计生成表单并测试执行。这里只处理工作流，
            不混入供应商密钥和其他模型设置。
          </p>
        </div>
      </header>
      <ModelsSectionNav active="workflows" />
      <WorkflowManager onModelsChanged={() => undefined} />
    </main>
  );
}
