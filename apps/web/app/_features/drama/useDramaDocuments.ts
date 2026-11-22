"use client";

import { useCallback, useEffect, useState } from "react";
import {
  approveDramaDocument,
  createDramaDocument,
  loadDramaDocuments,
  updateDramaDocument,
} from "./api";
import type { DramaDocument, DramaDocumentKind } from "./types";

export function useDramaDocuments(projectId: string | null) {
  const [documents, setDocuments] = useState<DramaDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    if (!projectId) {
      setDocuments([]);
      return;
    }
    setLoading(true);
    setNotice("");
    try {
      setDocuments(await loadDramaDocuments(projectId));
    } catch (error) {
      setNotice((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function save(
    kind: DramaDocumentKind,
    title: string,
    content: string,
  ) {
    if (!projectId) return null;
    setSaving(true);
    setNotice("");
    try {
      const current = documents.find((document) => document.kind === kind);
      const saved =
        current?.status === "draft"
          ? await updateDramaDocument(current.id, title, content)
          : await createDramaDocument(projectId, {
              kind,
              title,
              content,
            });
      setDocuments((items) => [
        saved,
        ...items.filter(
          (document) =>
            !(
              document.projectId === projectId &&
              document.kind === kind
            ),
        ),
      ]);
      return saved;
    } catch (error) {
      setNotice((error as Error).message);
      return null;
    } finally {
      setSaving(false);
    }
  }

  async function approve(documentId: string) {
    setSaving(true);
    setNotice("");
    try {
      const approved = await approveDramaDocument(documentId);
      setDocuments((items) =>
        items.map((document) =>
          document.id === documentId ? approved : document,
        ),
      );
      return approved;
    } catch (error) {
      setNotice((error as Error).message);
      return null;
    } finally {
      setSaving(false);
    }
  }

  return {
    documents,
    loading,
    saving,
    notice,
    refresh,
    save,
    approve,
  };
}
