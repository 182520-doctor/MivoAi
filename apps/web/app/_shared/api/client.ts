export async function requireJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = "";
    try {
      const payload = await response.json();
      detail =
        typeof payload?.detail === "string"
          ? payload.detail
          : typeof payload?.message === "string"
            ? payload.message
            : "";
    } catch {
      // Keep the status fallback for non-JSON upstream errors.
    }
    throw new Error(detail || `请求失败（${response.status}）`);
  }
  return response.json() as Promise<T>;
}

export async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  return requireJson<T>(await fetch(url, { signal }));
}

export async function putJson<T>(
  url: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<T> {
  return requireJson<T>(await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  }));
}
