import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";

export function renderWithClient(ui: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

export function mockFetch(routes: Record<string, unknown | ((init?: RequestInit) => unknown)>, status: Record<string, number> = {}) {
  const calls: { url: string; init?: RequestInit }[] = [];
  globalThis.fetch = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url);
    calls.push({ url: u, init });
    const key = Object.keys(routes).find((k) => u.startsWith(k));
    if (!key) return new Response(JSON.stringify({ detail: "not found" }), { status: 404, headers: { "content-type": "application/json" } });
    const body = typeof routes[key] === "function" ? (routes[key] as (i?: RequestInit) => unknown)(init) : routes[key];
    const isText = typeof body === "string";
    return new Response(isText ? (body as string) : JSON.stringify(body), {
      status: status[key] ?? 200,
      headers: { "content-type": isText ? "text/plain" : "application/json" },
    });
  }) as typeof fetch;
  return calls;
}
