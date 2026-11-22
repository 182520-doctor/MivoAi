const DEFAULT_API_BASE_URL = "http://127.0.0.1:8010";

export function apiBaseUrl() {
  return (
    process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL
  ).replace(/\/+$/, "");
}

export function apiUrl(path: string) {
  if (/^(?:[a-z][a-z\d+.-]*:)?\/\//i.test(path)) return path;
  return `${apiBaseUrl()}${path.startsWith("/") ? path : `/${path}`}`;
}

export function apiFetch(
  path: string,
  options?: RequestInit,
): Promise<Response> {
  return fetch(apiUrl(path), options);
}

export function apiResourceUrl(path: string) {
  return apiUrl(path);
}
