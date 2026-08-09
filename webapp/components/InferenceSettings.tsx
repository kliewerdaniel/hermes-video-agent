"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Button, Field, Modal, Badge, Spinner } from "./ui";
import { IconAlert, IconCheck, IconSpark } from "./icons";
import {
  inferenceApi,
  InferencePublicView,
  ModelInfo,
  ProviderId,
  TestResult,
} from "@/lib/inference";

const PROVIDER_COPY: Record<ProviderId, { title: string; privacy: string; fields: ("base_url" | "api_key" | "model")[] }> = {
  local: {
    title: "Local Endpoint",
    privacy: "Your prompts stay on your machine / network. Nothing leaves this device.",
    fields: ["base_url", "api_key", "model"],
  },
  gemini: {
    title: "Google Gemini",
    privacy: "Requests are sent directly to Google using your API key.",
    fields: ["api_key", "model"],
  },
  openrouter: {
    title: "OpenRouter",
    privacy: "Requests are sent to OpenRouter using your API key.",
    fields: ["api_key", "model"],
  },
};

export function InferenceSettings({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [view, setView] = useState<InferencePublicView | null>(null);
  const [provider, setProvider] = useState<ProviderId>("local");
  const [values, setValues] = useState<Record<string, string>>({});
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [modelLoading, setModelLoading] = useState(false);
  const [test, setTest] = useState<TestResult | null>(null);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  // Load current config when opened.
  useEffect(() => {
    if (!open) return;
    setTest(null);
    setErr("");
    inferenceApi
      .get()
      .then((v) => {
        setView(v);
        setProvider(v.provider);
        const merged: Record<string, string> = {};
        for (const pid of Object.keys(v.settings) as ProviderId[]) {
          const s = v.settings[pid as ProviderId] || {};
          for (const k of ["base_url", "api_key", "model"]) {
            if (s[k] != null && s[k] !== "••••••••") merged[`${pid}.${k}`] = String(s[k]);
          }
        }
        setValues(merged);
        loadModels(v.provider, transientOverrides(merged, v.provider));
      })
      .catch((e) => setErr(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Build the transient per-request overrides for a provider: only the
  // non-secret fields the user typed this session (a fresh key or URL). The
  // server merges these with the persisted config to fetch the model list.
  function transientOverrides(vals: Record<string, string>, pid: ProviderId) {
    const out: Record<string, string> = {};
    for (const f of PROVIDER_COPY[pid].fields) {
      const v = vals[`${pid}.${f}`];
      if (v && v !== "••••••••") out[f] = v;
    }
    return out;
  }

  function loadModels(pid: ProviderId, overrides?: Record<string, string>) {
    setModelLoading(true);
    const ov = overrides ?? transientOverrides(values, pid);
    const call = Object.keys(ov).length
      ? inferenceApi.modelsWith(pid, ov)
      : inferenceApi.models(pid);
    call
      .then((r) => setModels(r.models))
      .catch(() => setModels([]))
      .finally(() => setModelLoading(false));
  }

  // Refetch the model list (debounced) whenever the active provider or the
  // key/URL for it changes — so pasting a key or pointing at a new local URL
  // immediately populates models instead of waiting for a save.
  const liveSig = `${provider}|${values[`${provider}.base_url`] ?? ""}|${values[`${provider}.api_key`] ?? ""}`;
  const firstRun = useRef(true);
  useEffect(() => {
    if (!open) return;
    if (firstRun.current) {
      firstRun.current = false;
      return;
    }
    const t = setTimeout(() => loadModels(provider), 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveSig, open]);
  const cfg = PROVIDER_COPY[provider];
  const model = values[`${provider}.model`] || "";
  const [freeOnly, setFreeOnly] = useState(false);

  const modelOptions = useMemo(() => {
    let list = models;
    if (freeOnly) list = list.filter((m) => m.free);
    return list;
  }, [models, freeOnly]);

  function setField(k: string, v: string) {
    setValues((p) => ({ ...p, [`${provider}.${k}`]: v }));
    setTest(null);
  }

  async function runTest() {
    setTesting(true);
    setTest(null);
    setErr("");
    // Send only non-secret overrides; api_key stays server-side unless the
    // user typed a brand-new one in this session (then it is sent transiently
    // for the test only and is never persisted by the backend).
    const payload: Record<string, string> = {};
    for (const f of cfg.fields) {
      const v = values[`${provider}.${f}`];
      if (v && v !== "••••••••") payload[f] = v;
    }
    try {
      const r = await inferenceApi.test(provider, payload);
      setTest(r);
    } catch (e) {
      setTest({ ok: false, provider, model, message: String(e), category: "connection" });
    } finally {
      setTesting(false);
    }
  }

  async function save() {
    setSaving(true);
    setErr("");
    const payload: Record<string, string> = {};
    for (const f of cfg.fields) {
      const v = values[`${provider}.${f}`];
      if (v && v !== "••••••••") payload[f] = v;
    }
    try {
      const v = await inferenceApi.save(provider, payload);
      setView(v);
      setTest({ ok: true, provider, model, message: "Saved." });
    } catch (e) {
      setErr(String(e));
    } finally {
      setSaving(false);
    }
  }

  if (!open) return null;

  return (
    <Modal open title="Inference Provider" onClose={onClose} width="max-w-lg">
      <div className="space-y-4">
        <p className="text-xs text-muted">
          Choose where AI generation runs. This is local-first: pick a local
          OpenAI-compatible endpoint to keep everything on your hardware, or
          paste a Gemini / OpenRouter key to use a cloud model. The app never
          proxies your requests through anyone else&apos;s server.
        </p>

        {/* provider selector */}
        <div className="grid grid-cols-3 gap-2">
          {(view?.providers ?? [
            { id: "local" as ProviderId, label: "Local Endpoint" },
            { id: "gemini" as ProviderId, label: "Google Gemini" },
            { id: "openrouter" as ProviderId, label: "OpenRouter" },
          ]).map((p) => (
            <button
              key={p.id}
              onClick={() => {
                setProvider(p.id as ProviderId);
                setTest(null);
                loadModels(p.id as ProviderId, values);
              }}
              className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors
                ${provider === p.id
                  ? "border-primary/60 bg-primary/15 text-primary2"
                  : "border-edge bg-surface2 text-muted hover:text-text hover:border-edge2"}`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* privacy note */}
        <div className="flex items-start gap-2 rounded-lg bg-surface2 border border-edge px-3 py-2 text-xs text-muted">
          <IconSpark width={14} height={14} className="mt-0.5 text-primary2" />
          <span>{cfg.privacy}</span>
        </div>

        {/* per-provider fields */}
        <div className="space-y-3">
          {cfg.fields.includes("base_url") && (
            <Field label="Base URL">
              <input
                value={values[`${provider}.base_url`] ?? ""}
                onChange={(e) => setField("base_url", e.target.value)}
                placeholder="http://localhost:11434/v1"
                className="input w-full h-9"
              />
              <p className="text-2xs text-faint mt-1">
                Any OpenAI-compatible server — Ollama, llama.cpp, vLLM, LM Studio.
                Not just localhost: use a LAN address like{" "}
                <span className="mono">http://192.168.1.100:8000/v1</span>.
              </p>
            </Field>
          )}

          {cfg.fields.includes("api_key") && (
            <Field label="API Key">
              <input
                type="password"
                value={values[`${provider}.api_key`] ?? ""}
                onChange={(e) => setField("api_key", e.target.value)}
                placeholder={view?.settings[provider]?.api_key === "••••••••"
                  ? "•••••••• (stored — re-enter to change)"
                  : "Paste your API key"}
                className="input w-full h-9"
                autoComplete="off"
                spellCheck={false}
              />
              <p className="text-2xs text-faint mt-1">
                Stored locally in inference.json on this machine and used directly
                by the backend. Never shown back and never logged.
              </p>
            </Field>
          )}

          <Field label="Model">
            {modelLoading ? (
              <div className="h-9 grid place-items-center">
                <Spinner label="Loading models…" />
              </div>
            ) : (
              <div className="space-y-1.5">
                <select
                  value={model}
                  onChange={(e) => setField("model", e.target.value)}
                  className="input w-full h-9 appearance-none"
                >
                  <option value="">— select a model —</option>
                  {modelOptions.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                      {m.free ? "  (free)" : ""}
                      {m.context_length ? `  · ${m.context_length} ctx` : ""}
                    </option>
                  ))}
                </select>
                {/* manual fallback */}
                {model && !modelOptions.some((m) => m.id === model) && (
                  <p className="text-2xs text-warn">
                    “{model}” isn&apos;t in the fetched list — used as typed.
                  </p>
                )}
                <input
                  value={model}
                  onChange={(e) => setField("model", e.target.value)}
                  placeholder="…or type a model name manually"
                  className="input w-full h-8 text-xs"
                  spellCheck={false}
                />
                {models.some((m) => m.free) && (
                  <label className="flex items-center gap-2 text-2xs text-muted mt-1 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={freeOnly}
                      onChange={(e) => setFreeOnly(e.target.checked)}
                    />
                    Show free models only
                  </label>
                )}
              </div>
            )}
          </Field>
        </div>

        {/* test connection */}
        <div className="flex items-center gap-3">
          <Button onClick={runTest} loading={testing} disabled={testing}>
            Test Connection
          </Button>
          {test && (
            <span
              className={`inline-flex items-center gap-1.5 text-xs ${
                test.ok ? "text-success" : "text-danger"
              }`}
            >
              {test.ok ? <IconCheck width={13} height={13} /> : <IconAlert width={13} height={13} />}
              {test.message}
              {test.latency_ms != null && (
                <span className="text-faint">({test.latency_ms} ms)</span>
              )}
            </span>
          )}
        </div>

        {err && <p className="text-danger text-xs">{err}</p>}

        <div className="flex items-center gap-2 pt-1">
          <Button onClick={save} loading={saving} disabled={saving}>
            Save
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </Modal>
  );
}
