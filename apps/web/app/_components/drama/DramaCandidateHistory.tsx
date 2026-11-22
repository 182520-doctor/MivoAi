"use client";

import { Check, EyeOff, History } from "lucide-react";
import { mediaAssetUrl } from "../../_features/media/api";
import type { DramaAssetCandidate } from "../../_features/drama/types";

type DramaCandidateHistoryProps = {
  title: string;
  candidates: DramaAssetCandidate[];
  mediaType: "image" | "video" | "audio";
  busyCandidateId?: string | null;
  onSelect: (candidate: DramaAssetCandidate) => void | Promise<void>;
  onReject: (candidate: DramaAssetCandidate) => void | Promise<void>;
};

export function DramaCandidateHistory({
  title,
  candidates,
  mediaType,
  busyCandidateId,
  onSelect,
  onReject,
}: DramaCandidateHistoryProps) {
  if (!candidates.length) return null;

  return (
    <section className="drama-candidate-history">
      <header>
        <span>
          <History size={14} />
          {title}
        </span>
        <small>{candidates.length} 个持久候选</small>
      </header>
      <div className="drama-candidate-history-grid">
        {candidates.map((candidate, index) => {
          const selected = candidate.status === "selected";
          const busy = busyCandidateId === candidate.id;
          return (
            <article
              className={`${selected ? "selected" : ""} ${
                candidate.status === "rejected" ? "rejected" : ""
              }`}
              key={candidate.id}
            >
              <div className="drama-candidate-preview">
                {mediaType === "video" ? (
                  <video
                    src={mediaAssetUrl(candidate.assetId)}
                    controls
                    preload="metadata"
                  />
                ) : mediaType === "audio" ? (
                  <audio
                    src={mediaAssetUrl(candidate.assetId)}
                    controls
                    preload="metadata"
                  />
                ) : (
                  <img
                    src={mediaAssetUrl(candidate.assetId)}
                    alt={`${title} ${index + 1}`}
                  />
                )}
                <span className={`drama-candidate-status ${candidate.status}`}>
                  {candidateStatusLabel(candidate.status)}
                </span>
              </div>
              <div className="drama-candidate-copy">
                <div>
                  <strong>候选 {String(index + 1).padStart(2, "0")}</strong>
                  <small>{candidate.assetId.slice(0, 8)}</small>
                </div>
                <div className="drama-candidate-actions">
                  <button
                    type="button"
                    disabled={selected || busy}
                    onClick={() => void onSelect(candidate)}
                  >
                    <Check size={13} />
                    {selected ? "当前使用" : "设为当前"}
                  </button>
                  <button
                    type="button"
                    disabled={selected || busy}
                    onClick={() => void onReject(candidate)}
                  >
                    <EyeOff size={13} />
                    弃用
                  </button>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function candidateStatusLabel(status: DramaAssetCandidate["status"]) {
  return {
    candidate: "待选择",
    selected: "当前使用",
    rejected: "已弃用",
    superseded: "历史版本",
  }[status];
}
