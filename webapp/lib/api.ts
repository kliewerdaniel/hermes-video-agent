"use client";

import { useEffect, useRef, useState } from "react";

/**
 * All calls go through the custom dev-server proxy at /api/* -> FastAPI :8777
 * (see webapp/server.mjs; the proxy lives outside Next so long requests don't
 * 500 on HMR recompiles). The browser only ever talks to same-origin Next, so
 * there is no CORS pain.
 */
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// Retry transient failures (e.g. the backend restarting) so a brief blip
// doesn't white-screen the whole app.
const TRANSIENT = new Set([502, 503, 504]);
async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let lastErr: unknown;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const res = await fetch("/api" + path, {
        headers: { "Content-Type": "application/json" },
        ...init,
      });
      if (res.ok) return res.json() as Promise<T>;
      let msg = `${res.status} ${res.statusText}`;
      try {
        const j = await res.json();
        msg = j.detail || JSON.stringify(j);
      } catch {
        /* ignore */
      }
      // Don't retry genuine client/server errors (4xx/5xx app errors) —
      // only transient gateway-style failures.
      if (!TRANSIENT.has(res.status)) throw new ApiError(res.status, msg);
      lastErr = new ApiError(res.status, msg);
    } catch (e) {
      if (e instanceof ApiError) throw e;
      lastErr = e;
    }
    await new Promise((r) => setTimeout(r, 400 * (attempt + 1)));
  }
  throw lastErr instanceof Error ? lastErr : new Error(String(lastErr));
}

export const api = {
  env: () => req<import("./types").ProjectEnv>("/env"),
  listProjects: () =>
    req<{ projects: import("./types").Project[] }>("/projects"),
  getProject: (id: string) => req<import("./types").Project>(`/projects/${id}`),
  createProject: (body: {
    idea: string;
    title?: string;
    aspect?: string;
    duration?: number;
  }) => req<import("./types").Project>("/projects", {
    method: "POST",
    body: JSON.stringify(body),
  }),
  updateProject: (
    id: string,
    body: Partial<{
      title: string;
      idea: string;
      aspect: string;
      target_duration: number;
      voice: string;
      tts_provider: string;
    }>
  ) =>
    req<import("./types").Project>(`/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteProject: (id: string) =>
    req<{ id: string; deleted: boolean }>(`/projects/${id}`, {
      method: "DELETE",
    }),

  script: (id: string, body: { script?: string; direction?: string }) =>
    req<import("./types").Project>(`/projects/${id}/script`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  putScript: (id: string, script: string) =>
    req<import("./types").Project>(`/projects/${id}/script`, {
      method: "PUT",
      body: JSON.stringify({ script }),
    }),
  storyboard: (id: string, body: { scenes?: number; use_llm?: boolean }) =>
    req<import("./types").Project>(`/projects/${id}/storyboard`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  research: (id: string, body: {
    scene?: string;
    query?: string;
    limit?: number;
    commercial_only?: boolean;
  }) =>
    req<{ job: string } | import("./types").Project>(
      `/projects/${id}/research`,
      { method: "POST", body: JSON.stringify(body) }
    ),
  select: (id: string, sid: string, cand: string) =>
    req<import("./types").Project>(`/projects/${id}/scenes/${sid}/select/${cand}`, {
      method: "POST",
    }),
  skip: (id: string, sid: string) =>
    req<import("./types").Project>(`/projects/${id}/scenes/${sid}/skip`, {
      method: "POST",
    }),
  editScene: (id: string, sid: string, body: Record<string, unknown>) =>
    req<import("./types").Project>(`/projects/${id}/scenes/${sid}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  reorder: (id: string, order: string[]) =>
    req<import("./types").Project>(`/projects/${id}/reorder`, {
      method: "POST",
      body: JSON.stringify({ order }),
    }),
  replan: (id: string, sid: string, prompt?: string) =>
    req<import("./types").Project>(`/projects/${id}/scenes/${sid}/replan`, {
      method: "POST",
      body: JSON.stringify({ prompt }),
    }),
  generate: (id: string, sid: string, prompt?: string) =>
    req<{ job: string }>(`/projects/${id}/scenes/${sid}/generate`, {
      method: "POST",
      body: JSON.stringify({ prompt }),
    }),
  upload: async (id: string, sid: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`/api/projects/${id}/scenes/${sid}/upload`, {
      method: "POST",
      body: fd,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  narrate: (id: string, body: {
    provider?: string;
    voice?: string;
    rate?: number;
    scene?: string;
  }) =>
    req<{ job: string }>(`/projects/${id}/narrate`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  captions: (id: string) =>
    req<import("./types").Project>(`/projects/${id}/captions`, {
      method: "POST",
    }),
  render: (id: string, body: { final?: boolean; captions?: boolean; music?: string }) =>
    req<{ job: string }>(`/projects/${id}/render`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  approve: (id: string, stage: string) =>
    req<import("./types").Project>(`/projects/${id}/approve/${stage}`, {
      method: "POST",
    }),
  reopen: (id: string, stage: string) =>
    req<import("./types").Project>(`/projects/${id}/reopen/${stage}`, {
      method: "POST",
    }),
  // --- voice library (self-contained vox backend) ---
  voices: () => req<{ voices: { name: string; url: string }[] }>("/voices"),
  uploadVoice: async (name: string, file: File) => {
    const fd = new FormData();
    fd.append("name", name);
    fd.append("file", file);
    const res = await fetch("/api/voices", { method: "POST", body: fd });
    if (!res.ok) {
      let msg = `${res.status} ${res.statusText}`;
      try {
        const j = await res.json();
        msg = j.detail || JSON.stringify(j);
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, msg);
    }
    return res.json() as Promise<{ name: string; url: string }>;
  },
  deleteVoice: (name: string) =>
    req<{ ok: boolean }>(`/voices/${name}`, { method: "DELETE" }),
  jobs: () => req<{ jobs: import("./types").Job[] }>("/jobs"),
};

/** Poll /api/jobs until `jobId` is done/error, then refetch the project. */
export function useJob(
  jobId: string | null,
  onDone: (ok: boolean) => void
): { state: "idle" | "running" | "done" | "error"; error?: string } {
  const [state, setState] = useState<"idle" | "running" | "done" | "error">(
    jobId ? "running" : "idle"
  );
  const [error, setError] = useState<string>();
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    if (!jobId) return;
    setState("running");
    let alive = true;
    const timer = setInterval(async () => {
      try {
        const { jobs } = await api.jobs();
        const j = jobs.find((x) => x.id === jobId);
        if (j && j.state !== "running") {
          clearInterval(timer);
          if (!alive) return;
          if (j.state === "error") {
            setError(j.error);
            setState("error");
            onDoneRef.current(false);
          } else {
            setState("done");
            onDoneRef.current(true);
          }
        }
      } catch {
        /* keep polling */
      }
    }, 1000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [jobId]);

  return { state, error };
}

export function assetProxy(id: string, path?: string): string | null {
  if (!path) return null;
  return `/api/projects/${id}/file/${path}`;
}
