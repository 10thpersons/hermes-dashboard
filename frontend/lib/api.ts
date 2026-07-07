const API_BASE = "/api/proxy";

interface FetchOptions extends RequestInit {
  params?: Record<string, string>;
}

export async function apiFetch<T = any>(path: string, options: FetchOptions = {}): Promise<T> {
  const { params, ...init } = options;
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  }

  const res = await fetch(url.toString(), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
  });

  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("Session expired");
  }

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

export const fetchers = {
  sessions: (limit = 50, offset = 0, q?: string) =>
    apiFetch("/sessions", { params: { limit: String(limit), offset: String(offset), ...(q ? { q } : {}) } }),

  sessionDetail: (id: string) =>
    apiFetch(`/sessions/${id}`),

  cronJobs: () =>
    apiFetch("/cron"),

  toggleCron: (id: string, enabled: boolean) =>
    apiFetch(`/cron/${id}/toggle`, { method: "POST", body: JSON.stringify({ enabled }) }),

  cronOutput: (id: string) =>
    apiFetch(`/cron/${id}/output`),

  cronOutputFile: (id: string, filename: string) =>
    apiFetch(`/cron/${id}/output/${encodeURIComponent(filename)}`),

  cronHistory: (id: string) =>
    apiFetch(`/cron/${id}/history`),

  memory: () =>
    apiFetch("/knowledge/memory"),

  skills: () =>
    apiFetch("/knowledge/skills"),

  souls: () =>
    apiFetch("/knowledge/souls"),

  config: () =>
    apiFetch("/config"),

  updateConfig: (updates: Record<string, any>) =>
    apiFetch("/config", { method: "PUT", body: JSON.stringify({ updates }) }),

  systemHealth: () =>
    apiFetch("/system/health"),

  providers: () =>
    apiFetch("/providers"),

  providerModels: () =>
    apiFetch("/providers/models"),

  obsidianTree: (path = "") =>
    apiFetch("/obsidian/tree", { params: { path } }),

  obsidianFile: (path: string) =>
    apiFetch("/obsidian/file", { params: { path } }),

  usageSummary: () =>
    apiFetch("/usage/summary"),

  usageDaily: (days = 30) =>
    apiFetch("/usage/daily", { params: { days: String(days) } }),

  usageByModel: () =>
    apiFetch("/usage/by-model"),
};
