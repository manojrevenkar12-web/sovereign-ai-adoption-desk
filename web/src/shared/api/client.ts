// Fetch wrapper: bearer token, typed errors the screens can explain.

const TOKEN_KEY = "desk.token";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public reasons: string[] = [],
  ) {
    super(message);
  }
}

function readStore(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function token(): string | null {
  try {
    const fromUrl = new URLSearchParams(window.location.search).get("token");
    if (fromUrl) {
      sessionStorage.setItem(TOKEN_KEY, fromUrl);
      const url = new URL(window.location.href);
      url.searchParams.delete("token");
      window.history.replaceState(null, "", url.toString());
      return fromUrl;
    }
  } catch {
    /* storage can be unavailable; fall through */
  }
  return readStore() ?? (import.meta.env.VITE_DESK_TOKEN as string | undefined) ?? null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const t = token();
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: {
        "content-type": "application/json",
        ...(t ? { authorization: `Bearer ${t}` } : {}),
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(0, "The desk API cannot be reached.");
  }
  if (!res.ok) {
    let message = res.statusText;
    let reasons: string[] = [];
    try {
      const body = await res.json();
      const d = body.detail;
      if (typeof d === "string") message = d;
      else if (d?.message) {
        message = d.message;
        reasons = d.reasons ?? [];
      }
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, message, reasons);
  }
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("json") ? res.json() : res.text()) as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) }),
};
