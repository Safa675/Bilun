import { fetchJSON } from "../apiClient";

export function isAbortError(error: unknown): error is DOMException {
  return error instanceof DOMException && error.name === "AbortError";
}

export async function requestJSON<TResponse>(
  path: string,
  options?: RequestInit,
): Promise<TResponse> {
  return fetchJSON<TResponse>(path, options);
}

export async function postJSON<TResponse, TBody>(
  path: string,
  body: TBody,
  options?: RequestInit,
): Promise<TResponse> {
  return requestJSON<TResponse>(path, {
    ...options,
    method: "POST",
    body: JSON.stringify(body),
  });
}
