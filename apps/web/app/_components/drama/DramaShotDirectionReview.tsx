"use client";

import { Bot, Clapperboard } from "lucide-react";
import type { DramaShot } from "../../_features/drama/types";

const directionFields = [
  { key: "shotSize", label: "景别" },
  { key: "cameraAngle", label: "机位角度" },
  { key: "cameraMovement", label: "镜头运动" },
  { key: "lens", label: "镜头焦段" },
  { key: "blocking", label: "人物调度" },
  { key: "performanceAction", label: "表演动作" },
  { key: "expression", label: "表情" },
  { key: "composition", label: "构图" },
  { key: "lighting", label: "灯光" },
  { key: "sound", label: "声音" },
  { key: "transition", label: "转场" },
  { key: "referenceNotes", label: "参考说明" },
] as const;

export function DramaShotDirectionReview({
  shot,
  onOpenAgent,
}: {
  shot: DramaShot & { sceneHeading?: string };
  onOpenAgent?: (context?: string) => void;
}) {
  const completed = directionFields.filter((field) =>
    Boolean(shot.direction?.[field.key]?.trim()),
  ).length;

  return (
    <details className="drama-shot-direction">
      <summary>
        <span>
          <Clapperboard size={13} />
          镜头导演设计
        </span>
        <small>
          {completed
            ? `${completed} / ${directionFields.length} 项已明确`
            : "待 Agent 建立景别、调度、表演与声音"}
        </small>
      </summary>
      {completed ? (
        <div>
          {directionFields.map((field) => (
            <section key={field.key}>
              <span>{field.label}</span>
              <p>{shot.direction[field.key] || "待补"}</p>
            </section>
          ))}
        </div>
      ) : null}
      <button
        type="button"
        disabled={!onOpenAgent}
        onClick={() =>
          onOpenAgent?.(
            [
              `请为镜头“${shot.title}”（${shot.sceneHeading || "当前场次"}）建立或优化结构化导演设计。`,
              `镜头 ID：${shot.id}。`,
              "读取场景创作契约、镜头描述、对白和资产，写清景别、机位角度、镜头运动、焦段、人物调度、表演动作、表情、构图、灯光、声音、转场和参考说明。",
              "调用 zaojing_update_drama_shot_direction 保存，保存后重新审核该镜头；不要修改故事事实，也不要启动视频生成。",
            ].join("\n"),
          )
        }
      >
        <Bot size={13} />
        {completed ? "让 Agent 优化镜头设计" : "让 Agent 补齐镜头设计"}
      </button>
    </details>
  );
}
