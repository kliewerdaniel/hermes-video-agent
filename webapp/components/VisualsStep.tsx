"use client";

import { useState } from "react";
import { useWorkspace } from "@/components/Workspace";
import { Button, Field, Badge } from "@/components/ui";
import {
  IconSearch,
  IconUpload,
  IconImage,
  IconCheck,
  IconMic,
} from "@/components/icons";
import { selectedCandidate, thumbUrl, compactLicense, sceneNumber, sceneStatus } from "@/components/helpers";
import { CandidateCard } from "@/components/inspectorBits";

/**
 * Visuals step: fetch candidate images for every scene at once (the button
 * users kept asking for), then review each scene's grid and pick one.
 */
export function VisualsStep({ onDone }: { onDone?: () => void }) {
  const {
    project,
    researchAll,
    researchScene,
    selectCandidate,
    uploadScene,
    skipScene,
    activeSceneId,
    setActiveSceneId,
    isBusy,
  } = useWorkspace();
  const [uploading, setUploading] = useState<string | null>(null);

  const r = project.scenes.filter((s) => s.status !== "skipped");
  const withVisual = r.filter((s) => s.selected).length;
  const needsImages = r.filter((s) => !s.selected).length;

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 flex-wrap">
        <div>
          <h2 className="text-base font-semibold flex items-center gap-2">
            <IconImage width={18} height={18} className="text-primary2" /> Visuals
          </h2>
          <p className="text-muted text-sm">
            {withVisual}/{r.length} scenes have an image. {needsImages > 0
              ? `Fetch suggestions for the ${needsImages} remaining scene${needsImages > 1 ? "s" : ""}.`
              : "All scenes have visuals — review or replace any below."}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Button
            loading={isBusy("research")}
            onClick={() => researchAll()}
            title="Search stock image sources for every scene at once"
          >
            <IconImage width={14} height={14} /> Find images for all scenes
          </Button>
        </div>
      </div>

      {r.length === 0 && (
        <div className="inset p-6 text-center text-muted text-sm">
          Build a storyboard first to get scenes to find images for.
        </div>
      )}

      <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(300px,1fr))]">
        {r.map((scene) => {
          const sel = selectedCandidate(scene);
          const st = sceneStatus(scene);
          const active = scene.id === activeSceneId;
          return (
            <div
              key={scene.id}
              onClick={() => setActiveSceneId(scene.id)}
              className={`panel-2 p-3 cursor-pointer transition-all
                ${active ? "ring-1 ring-primary/70" : "hover:border-edge2"}`}
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="mono text-sm text-primary2 font-semibold">
                  {String(sceneNumber(project, scene.id)).padStart(2, "0")}
                </span>
                <Badge tone={st.tone}>
                  {st.label}
                </Badge>
                {sel && (
                  <span className="ml-auto text-2xs text-success flex items-center gap-1">
                    <IconCheck width={12} height={12} /> picked
                  </span>
                )}
              </div>

              {/* current selection */}
              <div className="relative rounded-lg overflow-hidden mb-2 bg-panel border border-edge">
                {sel ? (
                  <>
                    <img src={thumbUrl(project, sel) ?? ""} className="w-full aspect-video object-cover" alt="" />
                    <span className="absolute bottom-1.5 left-1.5">
                      <Badge tone="success">{compactLicense(sel.license)}</Badge>
                    </span>
                  </>
                ) : (
                  <div className="grid place-items-center h-32 text-faint text-xs">No visual yet</div>
                )}
              </div>

              {/* candidate grid */}
              {scene.candidates.length > 0 ? (
                <div className="grid grid-cols-3 gap-1.5">
                  {scene.candidates.map((c) => (
                    <CandidateCard
                      key={c.id}
                      project={project}
                      candidate={c}
                      selected={c.id === scene.selected}
                      onSelect={() => selectCandidate(scene.id, c.id)}
                    />
                  ))}
                </div>
              ) : (
                <div className="flex gap-1.5">
                  <button
                    disabled={isBusy("research")}
                    onClick={(e) => {
                      e.stopPropagation();
                      researchScene(scene.id);
                    }}
                    className="flex-1 h-7 inline-flex items-center justify-center gap-1.5 rounded-md text-xs font-medium bg-surface2 text-text border border-edge hover:border-edge2 disabled:opacity-40"
                  >
                    <IconSearch width={13} height={13} /> Search
                  </button>
                </div>
              )}

              {/* per-scene upload + skip */}
              <div className="flex items-center gap-2 mt-2">
                <label
                  className="text-2xs text-muted inline-flex items-center gap-1 cursor-pointer hover:text-text"
                  onClick={(e) => e.stopPropagation()}
                >
                  <IconUpload width={12} height={12} /> Upload
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    disabled={uploading === scene.id}
                    onChange={async (e) => {
                      const f = e.target.files?.[0];
                      if (!f) return;
                      setUploading(scene.id);
                      try {
                        await uploadScene(scene.id, f);
                      } finally {
                        setUploading(null);
                      }
                    }}
                  />
                </label>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    skipScene(scene.id);
                  }}
                  className="ml-auto text-2xs text-faint hover:text-danger"
                >
                  Skip
                </button>
              </div>

              <p className="text-[11px] text-faint mt-2 line-clamp-2">{scene.narration}</p>
            </div>
          );
        })}
      </div>

      {onDone && (
        <div className="flex justify-end">
          <button
            onClick={onDone}
            className="h-9 px-4 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary2"
          >
            Next: Narration →
          </button>
        </div>
      )}
    </div>
  );
}
