"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api, assetProxy } from "@/lib/api";
import { Candidate, Project, Scene } from "@/lib/types";
import { Badge, Button } from "./ui";
import { JobRunner } from "./JobRunner";

function Thumb({
  scene,
  cand,
  pid,
  onChanged,
}: {
  scene: Scene;
  cand: Candidate;
  pid: string;
  onChanged: () => void;
}) {
  const url = assetProxy(pid, cand.thumb_path) || assetProxy(pid, cand.local_path);
  const selected = scene.selected === cand.id;
  return (
    <button
      onClick={() => void api.select(pid, scene.id, cand.id).then(onChanged)}
      title={`${cand.title || cand.provider}\n${cand.reason || ""}`}
      className={`relative rounded-lg overflow-hidden border-2 transition-all ${
        selected ? "border-primary shadow-glow" : "border-edge hover:border-primary2"
      }`}
    >
      {url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt={cand.title || cand.id} className="h-24 w-full object-cover" />
      ) : (
        <div className="h-24 w-full grid place-items-center text-muted text-xs">
          {cand.provider}
        </div>
      )}
      <span className="absolute bottom-0 inset-x-0 bg-black/60 text-[10px] px-1.5 py-0.5 truncate">
        {cand.license}
      </span>
      {selected && (
        <span className="absolute top-1 right-1 bg-primary text-white text-[10px] rounded px-1">
          used
        </span>
      )}
    </button>
  );
}

export function SceneCard({
  scene,
  project,
  index,
  onChanged,
}: {
  scene: Scene;
  project: Project;
  index: number;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [narration, setNarration] = useState(scene.narration);
  const [terms, setTerms] = useState((scene.search_terms || []).join(", "));
  const [query, setQuery] = useState("");
  const [showAudio, setShowAudio] = useState(false);
  const sid = scene.id;
  const pid = project.id;

  const selectedCand = scene.candidates.find((c) => c.id === scene.selected);
  const statusTone =
    scene.status === "skipped" ? "warn" : selectedCand ? "success" : "muted";

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass rounded-2xl p-4"
    >
      <div className="flex items-center gap-3">
        <span className="font-mono text-primary2 text-sm">{String(index + 1).padStart(2, "0")}</span>
        <p className="text-sm flex-1 text-ink/90">{scene.narration}</p>
        <Badge tone={statusTone}>
          {scene.status === "skipped" ? "skipped" : selectedCand ? "visual set" : "no visual"}
        </Badge>
        <button
          className="text-muted hover:text-white text-xs"
          onClick={() => setOpen((o) => !o)}
        >
          {open ? "collapse" : "expand"}
        </button>
      </div>

      <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2 mt-3">
        {scene.candidates.map((c) => (
          <Thumb key={c.id} scene={scene} cand={c} pid={pid} onChanged={onChanged} />
        ))}
        <label className="h-24 rounded-lg border-2 border-dashed border-edge grid place-items-center text-muted text-xs cursor-pointer hover:border-primary2">
          + upload
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={async (e) => {
              const f = e.target.files?.[0];
              if (f) {
                await api.upload(pid, sid, f);
                onChanged();
              }
            }}
          />
        </label>
        <button
          className="h-24 rounded-lg border-2 border-dashed border-edge grid place-items-center text-muted text-xs hover:border-primary2"
          onClick={() => {
            const prompt = window.prompt(
              "Image prompt for generation",
              scene.image_prompt || scene.visual_concept || ""
            );
            if (prompt) void api.generate(pid, sid, prompt).then(onChanged);
          }}
        >
          + generate
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2 mt-3">
        {(scene.search_terms || []).map((t) => (
          <Badge key={t} tone="primary">{t}</Badge>
        ))}
        <span className="ml-auto flex items-center gap-2">
          <JobRunner
            label="re-search"
            run={() => api.research(pid, { scene: sid, query, limit: 4 })}
            onDone={onChanged}
          />
          <Button variant="ghost" onClick={() => void api.skip(pid, sid).then(onChanged)}>
            skip
          </Button>
        </span>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-3 space-y-2 border-t border-edge pt-3">
              <div className="flex gap-2">
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="search specifically for…"
                  className="flex-1 bg-surface2 border border-edge rounded-lg px-3 py-1.5 text-sm outline-none focus:border-primary"
                />
                <Button
                  onClick={() =>
                    void api.research(pid, { scene: sid, query, limit: 4 }).then(onChanged)
                  }
                >
                  search
                </Button>
              </div>
              <textarea
                value={narration}
                onChange={(e) => setNarration(e.target.value)}
                rows={2}
                className="w-full bg-surface2 border border-edge rounded-lg px-3 py-2 text-sm outline-none focus:border-primary"
              />
              <input
                value={terms}
                onChange={(e) => setTerms(e.target.value)}
                placeholder="search terms (comma separated)"
                className="w-full bg-surface2 border border-edge rounded-lg px-3 py-1.5 text-sm outline-none focus:border-primary"
              />
              <div className="flex gap-2 flex-wrap">
                <Button
                  variant="success"
                  onClick={() =>
                    void api
                      .editScene(pid, sid, {
                        narration,
                        search_terms: terms
                          .split(",")
                          .map((t) => t.trim())
                          .filter(Boolean),
                      })
                      .then(onChanged)
                  }
                >
                  save edits
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    const p = window.prompt(
                      "New visual concept / direction",
                      scene.visual_concept || ""
                    );
                    if (p) void api.replan(pid, sid, p).then(onChanged);
                  }}
                >
                  re-plan scene
                </Button>
                <span className="ml-auto">
                  <JobRunner
                    label="re-narrate"
                    run={() => api.narrate(pid, { scene: sid })}
                    onDone={onChanged}
                  />
                </span>
              </div>
              {showAudio ? (
                <audio
                  controls
                  src={assetProxy(pid, scene.audio_path || "")}
                  className="w-full"
                />
              ) : scene.audio_path ? (
                <button
                  className="text-xs text-muted underline"
                  onClick={() => setShowAudio(true)}
                >
                  show audio
                </button>
              ) : null}
              {selectedCand?.source_url && (
                <a
                  href={selectedCand.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-primary2 underline block truncate"
                >
                  source: {selectedCand.source_url}
                </a>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
