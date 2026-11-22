"use client";

import { useCallback, useEffect, useState } from "react";
import {
  loadAssets,
  uploadAssets,
} from "../assets/api";
import type { LibraryAsset } from "../assets/types";
import {
  createDramaEntity,
  loadDramaEntities,
  updateDramaEntity,
} from "./api";
import type {
  DramaEntity,
  DramaEntityKind,
} from "./types";

export function useDramaAssets(projectId: string | null) {
  const [entities, setEntities] = useState<DramaEntity[]>([]);
  const [assets, setAssets] = useState<LibraryAsset[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    if (!projectId) {
      setEntities([]);
      setAssets([]);
      return;
    }
    setLoading(true);
    setNotice("");
    try {
      const [nextEntities, assetLibrary] = await Promise.all([
        loadDramaEntities(projectId),
        loadAssets(300),
      ]);
      setEntities(nextEntities);
      setAssets(assetLibrary.assets);
    } catch (error) {
      setNotice((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function addEntity(
    kind: DramaEntityKind,
    name: string,
    description = "",
  ) {
    if (!projectId) return null;
    setSaving(true);
    setNotice("");
    try {
      const entity = await createDramaEntity(projectId, {
        kind,
        name,
        description,
      });
      setEntities((items) => [...items, entity]);
      return entity;
    } catch (error) {
      setNotice((error as Error).message);
      return null;
    } finally {
      setSaving(false);
    }
  }

  async function saveEntity(
    entityId: string,
    input: {
      name: string;
      description: string;
      status: DramaEntity["status"];
      primaryAssetId: string | null;
      referenceAssetIds: string[];
      assetSlots: Record<string, string>;
      profile: Record<string, string>;
      voiceName: string | null;
      voiceRate: number;
    },
  ) {
    setSaving(true);
    setNotice("");
    try {
      const entity = await updateDramaEntity(entityId, input);
      setEntities((items) =>
        items.map((item) => (item.id === entityId ? entity : item)),
      );
      return entity;
    } catch (error) {
      setNotice((error as Error).message);
      return null;
    } finally {
      setSaving(false);
    }
  }

  async function upload(files: File[]) {
    if (!files.length) return [];
    setUploading(true);
    setNotice("");
    try {
      const result = await uploadAssets(files);
      const library = await loadAssets(300);
      setAssets(library.assets);
      return result.assetIds;
    } catch (error) {
      setNotice((error as Error).message);
      return [];
    } finally {
      setUploading(false);
    }
  }

  return {
    entities,
    assets,
    loading,
    saving,
    uploading,
    notice,
    refresh,
    addEntity,
    saveEntity,
    upload,
  };
}
