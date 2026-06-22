// Shared API client helpers used by endpoint wrappers in lib/api/

export function resolveApiBase(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (configured) {
    return configured.replace(/\/$/, "");
  }

  if (typeof window === "undefined") {
    return "http://localhost:8000";
  }

  return "";
}

export function buildApiUrl(path: string): string {
  return `${resolveApiBase()}${path}`;
}

export function extractErrorDetail(payload: unknown): string | null {
  if (typeof payload === "string") {
    const trimmed = payload.trim();
    return trimmed || null;
  }
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const candidate = payload as Record<string, unknown>;
  for (const key of ["detail", "message", "error"]) {
    const value = candidate[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return null;
}

export class ApiRequestError extends Error {
  status?: number;
  detail?: string;
  isNetworkError: boolean;

  constructor(
    message: string,
    options?: { status?: number; detail?: string; isNetworkError?: boolean },
  ) {
    super(message);
    this.name = "ApiRequestError";
    this.status = options?.status;
    this.detail = options?.detail;
    this.isNetworkError = options?.isNetworkError ?? false;
  }
}

export async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const url = buildApiUrl(path);
  let res: Response;
  try {
    res = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw err;
    }
    throw new ApiRequestError(`Could not reach API at ${url}`, {
      isNetworkError: true,
    });
  }
  if (!res.ok) {
    let detail: string | null = null;
    try {
      const raw = await res.text();
      if (raw.trim()) {
        try {
          detail = extractErrorDetail(JSON.parse(raw)) ?? raw.trim();
        } catch {
          detail = raw.trim();
        }
      }
    } catch {
      detail = null;
    }
    throw new ApiRequestError(
      detail
        ? `API error: ${res.status} ${res.statusText} - ${detail}`
        : `API error: ${res.status} ${res.statusText}`,
      {
        status: res.status,
        detail: detail ?? undefined,
      },
    );
  }
  try {
    return await res.json() as T;
  } catch {
    throw new ApiRequestError(`API returned invalid JSON from ${path}`);
  }
}

export interface SSEFrame {
  event: string;
  data: string;
}

export function extractSseFrames(
  buffer: string,
  flush: boolean = false,
): { frames: SSEFrame[]; remainder: string } {
  let working = buffer.replace(/\r\n/g, "\n");
  if (flush && working.trim()) {
    working += "\n\n";
  }

  const chunks = working.split("\n\n");
  const remainder = chunks.pop() ?? "";
  const frames: SSEFrame[] = [];

  for (const chunk of chunks) {
    if (!chunk.trim()) continue;

    let event = "message";
    const dataLines: string[] = [];

    for (const line of chunk.split("\n")) {
      if (!line || line.startsWith(":")) continue;
      if (line.startsWith("event:")) {
        event = line.slice(6).trim() || "message";
        continue;
      }
      if (line.startsWith("data:")) {
        const value = line.slice(5);
        dataLines.push(value.startsWith(" ") ? value.slice(1) : value);
      }
    }

    if (dataLines.length > 0) {
      frames.push({ event, data: dataLines.join("\n") });
    }
  }

  return { frames, remainder };
}

export function parseSsePayload(data: string): string {
  try {
    const parsed = JSON.parse(data);
    if (typeof parsed === "string") return parsed;
    if (
      parsed &&
      typeof parsed === "object" &&
      "token" in parsed &&
      typeof parsed.token === "string"
    ) {
      return parsed.token;
    }
    return String(parsed ?? "");
  } catch {
    return data.trim();
  }
}
