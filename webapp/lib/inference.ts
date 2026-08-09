"use client";

import { ApiError } from "./api";

/* Provider-agnostic inference config client.
 *
 * Security: the browser NEVER sends API keys in the body. The backend reads
 * keys from its own persisted config (inference.json). The client only sends
 * non-secret overrides (base_url/model) for transient test runs, and the
 * server redacts any key before returning config.
 */

export type ProviderId = "local" | "gemini" | "openrouter";

export interface ModelInfo {
  id: string;
  label: string;
  description: string;
  free: boolean;
  context_length: number | null;
}

export interface InferenceSettings {
  base_url?: string;
  model?: string;
  api_key?: string; // only ever "••••••••" from the server
  // gemini / openrouter use `api_key`; local uses `base_url`+`model`+optional key
  [k: string]: unknown;
}

export interface InferencePublicView {
  provider: ProviderId;
  providers: { id: ProviderId; label: string }[];
  settings: Partial<Record<ProviderId, InferenceSettings>>;
}

export interface TestResult {
  ok: boolean;
  provider: ProviderId;
  model: string;
  message: string;
  latency_ms?: number;
  category?: string | null;
}

async function jget<T>(path: string): Promise<T> {
  const res = await fetch("/api" + path, { headers: { "Content-Type": "application/json" } });
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
  return res.json() as Promise<T>;
}

async function jsend<T>(path: string, init: RequestInit): Promise<T> {
  const res = await fetch("/api" + path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
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
  return res.json() as Promise<T>;
}

export const inferenceApi = {
  get: () => jget<InferencePublicView>("/inference"),

  save: (provider: ProviderId, settings: Record<string, unknown>) =>
    jsend<InferencePublicView>("/inference", {
      method: "PUT",
      body: JSON.stringify({ provider, settings }),
    }),

  models: (provider?: ProviderId, refresh = false) =>
    jget<{ provider: ProviderId; models: ModelInfo[] }>(
      `/inference/models?${provider ? `provider=${provider}&` : ""}refresh=${refresh}`
    ),

  // Fetch models using transient overrides (e.g. a freshly-typed key/URL that
  // hasn't been saved yet). Never persists anything.
  modelsWith: (provider: ProviderId, settings?: Record<string, unknown>) =>
    jsend<{ provider: ProviderId; models: ModelInfo[] }>("/inference/models", {
      method: "POST",
      body: JSON.stringify({ provider, settings: settings || {} }),
    }),

  test: (provider: ProviderId, settings?: Record<string, unknown>) =>
    jsend<TestResult>("/inference/test", {
      method: "POST",
      body: JSON.stringify({ provider, settings: settings || {} }),
    }),
};
