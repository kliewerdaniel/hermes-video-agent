"use client";

import { useState } from "react";
import { Project, Scene } from "@/lib/types";
import { useWorkspace } from "@/components/Workspace";
import { SceneThumb } from "@/components/SceneThumb";
import { sceneStatus, fmtDur, thumbUrl, selectedCandidate } from "@/components/helpers";
import { StatusDot, Badge } from "@/components/ui";
import { IconMic, IconImage, IconDrag, IconCheck } from "@/components/icons";

export function Storyboard({ onDone }: { onDone?: () => void }) {
  const { project, activeSceneId, setActiveSceneId, reorder, isBusy } = useWorkspace();
  const [dragId, setDragId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);

  const onDrop = (targetId: string) => {
    if (!dragId || dragId === targetId) return;
    const ids = project.scenes.map((s) => s.id);
    const from = ids.indexOf(dragId);
    const to = ids.indexOf(targetId);
    if (from < 0 || to < 0) return;
    ids.splice(to, 0, ids.splice(from, 1)[0]);
    reorder(ids);
    setDragId(null);
    setOverId(null);
  };

  if (project.scenes.length === 0) return <StoryboardEmpty />;

  return (
    <div
      id="rail-scenes"
      className="grid gap-3 p-3 [grid-template-columns:repeat(auto-fill,minmax(230px,1fr))]"
    >
      {project.scenes.map((scene, i) => {
        const st = sceneStatus(scene);
        const active = scene.id === activeSceneId;
        const sel = selectedCandidate(scene);
        const url = thumbUrl(project, sel);
        return (
          <div
            key={scene.id}
            onDragOver={(e) => {
              e.preventDefault();
              setOverId(scene.id);
            }}
            onDragLeave={() => setOverId((o) => (o === scene.id ? null : o))}
            onDrop={() => onDrop(scene.id)}
            onClick={() => setActiveSceneId(scene.id)}
            className={`group relative panel-2 p-2 cursor-pointer transition-all duration-150 animate-scale-in
              ${active ? "ring-1 ring-primary/70 shadow-glow" : "hover:border-edge2"}
              ${overId === scene.id && dragId !== scene.id ? "border-primary/60" : ""}
              ${dragId === scene.id ? "opacity-40" : ""}
            `}
          >
            {/* drag handle + number */}
            <div className="absolute top-2 left-2 z-10 flex items-center gap-1">
              <span className="grid place-items-center h-5 w-5 rounded bg-black/60 backdrop-blur text-2xs mono text-text font-semibold">
                {String(i + 1).padStart(2, "0")}
              </span>
            </div>
            <div
              draggable={!isBusy("reorder")}
              onDragStart={() => setDragId(scene.id)}
              onDragEnd={() => {
                setDragId(null);
                setOverId(null);
              }}
              onClick={(e) => e.stopPropagation()}
              className="absolute top-2 right-2 z-20 opacity-0 group-hover:opacity-100 transition-opacity cursor-grab active:cursor-grabbing text-white/70 hover:text-white"
              title="Drag to reorder"
            >
              <IconDrag width={14} height={14} />
            </div>

            <SceneThumb project={project} scene={scene} />

            <div className="px-1 pt-2">
              <p className="text-[13px] leading-snug text-text/90 line-clamp-2 min-h-[2.4em]">
                {scene.narration || <span className="text-faint">No narration</span>}
              </p>
              <div className="flex items-center gap-2 mt-2 text-2xs text-muted">
                <span className="mono">{fmtDur(scene.duration)}</span>
                {scene.audio_path ? (
                  <span className="flex items-center gap-0.5 text-success">
                    <IconMic width={12} height={12} /> VO
                  </span>
                ) : (
                  <span className="flex items-center gap-0.5 text-faint">
                    <IconMic width={12} height={12} /> —
                  </span>
                )}
                {sel ? (
                  <span className="flex items-center gap-0.5 text-primary2">
                    <IconImage width={12} height={12} /> img
                  </span>
                ) : (
                  <span className="flex items-center gap-0.5 text-faint">
                    <IconImage width={12} height={12} /> —
                  </span>
                )}
                <span className="ml-auto flex items-center gap-1">
                  <StatusDot tone={st.tone} />
                </span>
              </div>
            </div>
          </div>
        );
      })}
      {onDone && (
        <div className="col-span-full flex justify-end pt-1">
          <button
            onClick={onDone}
            className="h-9 px-4 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary2"
          >
            Next: Visuals →
          </button>
        </div>
      )}
    </div>
  );
}

function StoryboardEmpty() {
  const { buildStoryboard, isBusy } = useWorkspace();
  return (
    <div className="grid place-items-center h-full p-10">
      <div className="text-center max-w-sm animate-fade-in">
        <div className="mx-auto mb-4 h-14 w-14 grid place-items-center rounded-2xl bg-surface2 border border-edge">
          <IconImage width={26} height={26} />
        </div>
        <h3 className="text-base font-semibold mb-1">No storyboard yet</h3>
        <p className="text-muted text-sm mb-4">
          Generate a script, then build a scene-by-scene storyboard. Each scene
          becomes a connected object: visual + narration + audio + motion.
        </p>
        <button
          onClick={() => buildStoryboard()}
          disabled={isBusy("storyboard")}
          className="h-9 px-4 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary2 disabled:opacity-40"
        >
          {isBusy("storyboard") ? "Building…" : "Build storyboard"}
        </button>
      </div>
    </div>
  );
}
