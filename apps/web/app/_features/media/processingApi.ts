import { apiFetch, requireJson } from "../../_shared/api/client";

export async function extractVideoAudio(videoAssetId: string) {
  return requireJson<{
    assetId: string;
    sourceAssetId: string;
    type: "audio";
    url: string;
  }>(
    await apiFetch("/api/media/processing/extract-audio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ videoAssetId }),
    }),
  );
}

export async function normalizeAudio(
  audioAssetId: string,
  targetLufs = -16,
) {
  return requireJson<{
    assetId: string;
    sourceAssetId: string;
    type: "audio";
    targetLufs: number;
    url: string;
  }>(
    await apiFetch("/api/media/processing/normalize-audio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ audioAssetId, targetLufs }),
    }),
  );
}

export async function transcribeAudio(
  audioAssetId: string,
  language = "auto",
) {
  return requireJson<{
    assetId: string;
    sourceAssetId: string;
    type: "file";
    language: string;
    cues: Array<{
      startSeconds: number;
      endSeconds: number;
      text: string;
    }>;
    url: string;
  }>(
    await apiFetch("/api/media/processing/transcribe-audio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ audioAssetId, language }),
    }),
  );
}

export async function loadSpeechVoices() {
  return requireJson<{
    voices: Array<{
      name: string;
      culture: string;
      gender?: string;
    }>;
  }>(await apiFetch("/api/media/processing/tts/voices"));
}

export async function synthesizeSpeech(
  text: string,
  voiceName: string,
  rate: number,
) {
  return requireJson<{
    assetId: string;
    type: "audio";
    url: string;
  }>(
    await apiFetch("/api/media/processing/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voiceName, rate }),
    }),
  );
}

export async function upscaleVideo(
  videoAssetId: string,
  aspectRatio: string,
) {
  return requireJson<{
    assetId: string;
    sourceAssetId: string;
    type: "video";
    url: string;
  }>(
    await apiFetch("/api/media/processing/upscale-video", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ videoAssetId, aspectRatio }),
    }),
  );
}
