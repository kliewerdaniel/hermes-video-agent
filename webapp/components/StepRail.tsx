"use client";

import { Project } from "@/lib/types";
import { projectReadiness } from "@/components/helpers";
import { IconScript, IconStoryboard, IconImage, IconMic, IconExport, IconCheck } from "@/components/icons";

export type StepId = "script" | "scenes" | "visuals" | "narration" | "export";

const STEP_META: Record<StepId, { label: string; sub: string; icon: React.ReactNode }> = {
  script: { label: "Script", sub: "Write or generate", icon: <IconScript width={16} height={16} /> },
  scenes: { label: "Storyboard", sub: "Break into scenes", icon: <IconStoryboard width={16} height={16} /> },
  visuals: { label: "Visuals", sub: "Pick images", icon: <IconImage width={16} height={16} /> },
  narration: { label: "Narration", sub: "Voice each scene", icon: <IconMic width={16} height={16} /> },
  export: { label: "Export", sub: "Render video", icon: <IconExport width={16} height={16} /> },
};

const ORDER: StepId[] = ["script", "scenes", "visuals", "narration", "export"];

export function stepDone(p: Project, id: StepId): boolean {
  switch (id) {
    case "script":
      return !!p.script && p.script.trim().length > 0;
    case "scenes":
      return p.scenes.length > 0;
    case "visuals":
      return projectReadiness(p).allVisuals;
    case "narration":
      return projectReadiness(p).allAudio;
    case "export":
      return !!p.final && p.has_final;
  }
}

function nextAfter(p: Project): StepId {
  for (const s of ORDER) if (!stepDone(p, s)) return s;
  return "export";
}

export function StepRail({
  project,
  active,
  onJump,
}: {
  project: Project;
  active: StepId;
  onJump: (s: StepId) => void;
}) {
  const next = nextAfter(project);

  return (
    <nav className="w-[210px] shrink-0 border-r border-edge bg-panel/40 flex flex-col py-4 px-3 gap-1">
      <div className="px-2 pb-3 text-faint text-2xs uppercase tracking-widest">Pipeline</div>
      {ORDER.map((id, i) => {
        const done = stepDone(project, id);
        const isActive = id === active;
        const isNext = id === next;
        return (
          <button
            key={id}
            onClick={() => onJump(id)}
            className={`group flex items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-all
              ${isActive ? "bg-surface2 ring-1 ring-edge2" : "hover:bg-surface2/60"}
              ${isNext && !isActive ? "ring-1 ring-primary/40" : ""}`}
          >
            <span
              className={`grid place-items-center h-8 w-8 shrink-0 rounded-lg border transition-colors
                ${done ? "bg-success/15 border-success/40 text-success" : isActive ? "bg-primary/15 border-primary/50 text-primary2" : "bg-panel border-edge text-faint"}`}
            >
              {done ? <IconCheck width={15} height={15} /> : STEP_META[id].icon}
            </span>
            <span className="min-w-0 flex-1">
              <span className={`block text-sm font-medium ${isActive ? "text-text" : "text-muted"}`}>
                {i + 1}. {STEP_META[id].label}
              </span>
              <span className="block text-[11px] text-faint truncate">{STEP_META[id].sub}</span>
            </span>
            {isNext && !isActive && (
              <span className="text-[9px] uppercase text-primary2 font-semibold tracking-wide">next</span>
            )}
          </button>
        );
      })}

      <div className="mt-auto px-2 pt-4 text-[11px] text-faint leading-relaxed">
        Click a step to jump. Each step leads to the next.
      </div>
    </nav>
  );
}
