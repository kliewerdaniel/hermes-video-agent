"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Project, assetUrl } from "@/lib/types";
import { Button, Card } from "@/components/ui";
import { IconSpark, IconPlay, IconX } from "@/components/icons";
import { InferenceSettings } from "@/components/InferenceSettings";

const STAGE_HINT: Record<string, string> = {
  script: "write the script",
  scenes: "plan the shots",
  visuals: "pick images",
  narration: "voice it",
  draft: "render & review",
};

export default function Dashboard() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [idea, setIdea] = useState("");
  const [title, setTitle] = useState("");
  const [aspect, setAspect] = useState("16:9");
  const [duration, setDuration] = useState(45);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [inferenceOpen, setInferenceOpen] = useState(false);

  async function load() {
    try {
      const [{ projects: ps }] = await Promise.all([api.listProjects()]);
      setProjects(ps);
    } catch (e) {
      setErr(String(e));
    }
  }
  useEffect(() => {
    void load();
  }, []);

  async function create() {
    if (!idea.trim()) return;
    setBusy(true);
    setErr("");
    try {
      const p = await api.createProject({ idea, title, aspect, duration });
      router.push(`/project/${p.id}`);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="max-w-5xl mx-auto px-5 py-10">
      <header className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Hermes <span className="text-primary2">Video Agent</span>
          </h1>
          <p className="text-muted text-sm">
            Idea → script → shot list → visuals → narration → captioned MP4.
          </p>
        </div>
        <Button variant="ghost" onClick={() => setInferenceOpen(true)} className="gap-1.5">
          <IconSpark width={14} height={14} /> Inference provider
        </Button>
      </header>

      <Card className="p-5 mb-8">
        <div className="text-sm font-semibold mb-3">New video</div>
        <textarea
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          placeholder="Describe the video you want — a topic, a thesis, a script…"
          rows={3}
          className="w-full bg-surface2 border border-edge rounded-xl px-3 py-2 text-sm outline-none focus:border-primary resize-none"
        />
        <div className="flex flex-wrap gap-3 mt-3 items-center">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="title (optional)"
            className="bg-surface2 border border-edge rounded-lg px-3 py-1.5 text-sm outline-none focus:border-primary w-48"
          />
          <select
            value={aspect}
            onChange={(e) => setAspect(e.target.value)}
            className="bg-surface2 border border-edge rounded-lg px-3 py-1.5 text-sm outline-none focus:border-primary"
          >
            {["16:9", "9:16", "1:1", "4:5"].map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
          <label className="flex items-center gap-2 text-sm text-muted">
            length
            <input
              type="number"
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              className="bg-surface2 border border-edge rounded-lg px-2 py-1.5 text-sm w-20 outline-none focus:border-primary"
            />
            s
          </label>
          <Button onClick={create} disabled={busy} className="ml-auto">
            {busy ? "creating…" : "Create"}
          </Button>
        </div>
        {err && <p className="text-danger text-xs mt-2">{err}</p>}
      </Card>

      <div className="text-sm font-semibold mb-3 text-muted">Projects</div>
      {projects.length === 0 ? (
        <p className="text-muted text-sm">No projects yet — create one above.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {projects.map((p, i) => {
            const videoUrl = assetUrl(p, p.final);
            return (
              <motion.div
                key={p.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
              >
                <Card className="flex items-center gap-3 px-4 py-3">
                  <button
                    onClick={() => router.push(`/project/${p.id}`)}
                    className="flex-1 min-w-0 text-left font-medium truncate hover:text-primary2"
                    title="Open project"
                  >
                    {p.title || p.idea}
                  </button>

                  {videoUrl ? (
                    <a
                      href={videoUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-lg text-sm bg-surface2 border border-edge text-text hover:border-primary2"
                      title="Show finished video"
                    >
                      <IconPlay width={13} height={13} /> Display
                    </a>
                  ) : (
                    <span className="text-2xs text-faint px-2 py-1">no video yet</span>
                  )}

                  <button
                    onClick={async () => {
                      if (!confirm(`Delete project "${p.title || p.idea}"? This cannot be undone.`)) return;
                      try {
                        await api.deleteProject(p.id);
                        setProjects((ps) => ps.filter((x) => x.id !== p.id));
                      } catch (e) {
                        setErr(String(e instanceof Error ? e.message : e));
                      }
                    }}
                    className="grid place-items-center h-8 w-8 rounded-lg text-faint hover:text-danger hover:bg-danger/10"
                    title="Delete project"
                  >
                    <IconX width={15} height={15} />
                  </button>
                </Card>
              </motion.div>
            );
          })}
        </div>
      )}

      {inferenceOpen && (
        <InferenceSettings
          open={inferenceOpen}
          onClose={() => setInferenceOpen(false)}
        />
      )}
    </main>
  );
}
