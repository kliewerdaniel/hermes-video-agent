"use client";

import { useState } from "react";
import { useWorkspace } from "@/components/Workspace";
import { SceneThumb } from "@/components/SceneThumb";
import { fmtDur } from "@/components/helpers";

export function VisualStrip() {
  const { project, activeSceneId, setActiveSceneId, reorder } = useWorkspace();
  const [dragId, setDragId] = useState<string | null>(null);

  const onDrop = (targetId: string) => {
    if (!dragId || dragId === targetId) return;
    const ids = project.scenes.map((s) => s.id);
    const from = ids.indexOf(dragId);
    const to = ids.indexOf(targetId);
    ids.splice(to, 0, ids.splice(from, 1)[0]);
    reorder(ids);
    setDragId(null);
  };

  return (
    <div className="flex items-stretch gap-1.5 overflow-x-auto no-scrollbar px-3 py-2 h-full">
      {project.scenes.map((scene, i) => {
        const active = scene.id === activeSceneId;
        return (
          <div
            key={scene.id}
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => onDrop(scene.id)}
            onClick={() => setActiveSceneId(scene.id)}
            className={`group relative shrink-0 w-[68px] flex flex-col gap-1 transition-all cursor-pointer
              ${active ? "opacity-100" : "opacity-70 hover:opacity-100"}`}
            title={`Scene ${i + 1}: ${scene.narration?.slice(0, 80)}`}
          >
            <div
              className={`relative rounded-md overflow-hidden border aspect-[9/16]
                ${active ? "border-primary ring-1 ring-primary/60" : "border-edge"}`}
            >
              <SceneThumb
                project={project}
                scene={scene}
                rounded="rounded-md"
                className="aspect-[9/16]"
              />
              <span
                className={`absolute top-0.5 left-0.5 grid place-items-center h-4 w-4 rounded
                  bg-black/70 text-[10px] mono font-semibold ${active ? "text-primary2" : "text-text/80"}`}
              >
                {i + 1}
              </span>
              <div
                draggable
                onDragStart={() => setDragId(scene.id)}
                onDragEnd={() => setDragId(null)}
                onClick={(e) => e.stopPropagation()}
                className="absolute inset-0 cursor-grab active:cursor-grabbing"
                title="Drag to reorder"
              />
            </div>
            <span className="mono text-[10px] text-faint text-center">
              {fmtDur(scene.duration)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
