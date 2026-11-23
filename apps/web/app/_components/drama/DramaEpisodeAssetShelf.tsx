"use client";

import {
  Image as ImageIcon,
  Images,
} from "lucide-react";
import type { LibraryAsset } from "../../_features/assets/types";
import type { DramaEntity } from "../../_features/drama/types";
import { backendResourceUrl } from "../../../shared/ui/backend-resource";

type DramaEpisodeAssetShelfProps = {
  entities: DramaEntity[];
  assets: Map<string, LibraryAsset>;
  compact?: boolean;
};

export function DramaEpisodeAssetShelf({
  entities,
  assets,
  compact = false,
}: DramaEpisodeAssetShelfProps) {
  const groups = entities.reduce<Record<string, DramaEntity[]>>(
    (result, entity) => {
      (result[entity.kind] ??= []).push(entity);
      return result;
    },
    {},
  );
  return (
    <section
      className={`drama-episode-asset-shelf ${
        compact ? "compact" : ""
      }`}
    >
      <header>
        <span>
          <Images size={14} />
          本集资产
        </span>
        <small>{entities.length} 个</small>
      </header>
      {entities.length ? (
        <div className="drama-episode-asset-groups">
          {Object.entries(groups).map(([kind, group]) => (
            <div key={kind}>
              <strong>{entityKindLabel(kind)}</strong>
              <div>
                {group.map((entity) => {
                  const assetId =
                    entity.primaryAssetId ??
                    Object.values(entity.assetSlots)[0];
                  const asset = assetId ? assets.get(assetId) : null;
                  return (
                    <article key={entity.id}>
                      {asset ? (
                        <img
                          src={backendResourceUrl(asset.url)}
                          alt={entity.name}
                        />
                      ) : (
                        <ImageIcon size={16} />
                      )}
                      <span>
                        <strong>{entity.name}</strong>
                        <small>
                          {entity.status === "locked" ? "已锁定" : "草稿"}
                        </small>
                      </span>
                    </article>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p>当前镜头尚未关联角色、场景或道具资产。</p>
      )}
    </section>
  );
}

function entityKindLabel(kind: string) {
  return {
    character: "角色",
    location: "场景",
    costume: "服装",
    prop: "道具",
    style: "风格",
  }[kind] ?? kind;
}
