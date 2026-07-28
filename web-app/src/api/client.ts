const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
export const AUTH_INVALID_EVENT = "textblast:auth-invalid";

export type HttpMethod = "GET" | "POST" | "PUT" | "DELETE";

function notifyInvalidSession(response: Response, token?: string) {
  if (response.status === 401 && token && typeof window !== "undefined") {
    window.setTimeout(() => window.dispatchEvent(new Event(AUTH_INVALID_EVENT)), 0);
  }
}

export async function apiRequest<T>(
  path: string,
  method: HttpMethod = "GET",
  body?: unknown,
  token?: string,
): Promise<T> {
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers: {
      ...(!isFormData && body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: isFormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    notifyInvalidSession(response, token);
    const text = await response.text();
    let message = text;
    try {
      const payload = JSON.parse(text) as { detail?: string | { msg?: string }[] };
      if (typeof payload.detail === "string") {
        message = payload.detail;
      } else if (Array.isArray(payload.detail)) {
        message = payload.detail.map((item) => item.msg).filter(Boolean).join(", ");
      }
    } catch {
      // Keep the plain-text response when the API does not return JSON.
    }
    throw new Error(message || `Request failed (HTTP ${response.status})`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function apiDownload(path: string, token?: string): Promise<{ blob: Blob; filename?: string }> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    notifyInvalidSession(response, token);
    const text = await response.text();
    let message = text;
    try {
      const payload = JSON.parse(text) as { detail?: string };
      if (typeof payload.detail === "string") message = payload.detail;
    } catch {
      // Keep the plain-text response when the API does not return JSON.
    }
    throw new Error(message || `Download failed (HTTP ${response.status})`);
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = disposition.match(/filename="?([^"]+)"?/i)?.[1];
  return { blob: await response.blob(), filename };
}
