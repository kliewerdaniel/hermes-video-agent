"use client";

import { useRouter } from "next/navigation";
import { Project } from "@/lib/types";
import { fmtDur } from "@/components/helpers";
import { Button, Badge } from "@/components/ui";
import {
  IconArrowLeft,
  IconSettings,
  IconSpark,
  IconCheck,
} from "@/components/icons";
import { useWorkspace } from "@/components/Workspace";

export function ProjectHeader({
  onOpenSettings,
  onOpenInference,
}: {
  onOpenSettings: () => void;
  onOpenInference: () => void;
}) {
  const router = useRouter();
  const { project } = useWorkspace();
  const saved = true; // manifest is the source of truth; every edit persists

  return (
    <header className="h-14 shrink-0 flex items-center gap-3 px-3 border-b border-edge bg-panel/80 backdrop-blur-md">
      <button
        onClick={() => router.push("/")}
        className="grid place-items-center h-8 w-8 rounded-lg text-muted hover:text-text hover:bg-surface2 transition-colors"
        title="All projects"
      >
        <IconArrowLeft />
      </button>

      <div className="flex flex-col leading-tight min-w-0">
        <div className="flex items-center gap-2 min-w-0">
          <h1 className="font-semibold text-sm truncate max-w-[34vw]">
            {project.title || "Untitled"}
          </h1>
          {saved && (
            <span className="text-2xs text-faint flex items-center gap-1 shrink-0">
              <IconCheck width={12} height={12} /> saved
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 text-2xs text-muted mono">
          <span>{project.aspect}</span>
          <span className="text-faint">·</span>
          <span>{project.scenes.length} scenes</span>
          <span className="text-faint">·</span>
          <span>~{fmtDur(project.total_duration)}</span>
        </div>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={onOpenInference} title="Inference provider">
          <IconSpark width={13} height={13} />
        </Button>
        <Button variant="ghost" size="sm" onClick={onOpenSettings} title="Project settings">
          <IconSettings width={13} height={13} />
        </Button>
      </div>
    </header>
  );
}
