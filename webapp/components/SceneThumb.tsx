"use client";

import { Project, Scene, Candidate } from "@/lib/types";
import { selectedCandidate, thumbUrl, aspectClass } from "@/components/helpers";
import { IconImage } from "@/components/icons";

export function SceneThumb({
  project,
  scene,
  candidate,
  className = "",
  rounded = "rounded-lg",
}: {
  project: Project;
  scene: Scene;
  candidate?: Candidate;
  className?: string;
  rounded?: string;
}) {
  const sel = candidate ?? selectedCandidate(scene);
  const url = thumbUrl(project, sel);
  const skipped = scene.status === "skipped";

  return (
    <div className={`relative overflow-hidden bg-panel ${aspectClass(project.aspect)} ${rounded} ${className}`}>
      {skipped ? (
        <div className="absolute inset-0 grid place-items-center text-faint text-xs gap-1 flex-col">
          <span className="opacity-60">skipped</span>
        </div>
      ) : url ? (
        <img
          src={url}
          alt={scene.narration?.slice(0, 60) ?? "scene"}
          className="w-full h-full object-cover"
          loading="lazy"
        />
      ) : (
        <div className="absolute inset-0 grid place-items-center text-faint flex-col gap-1">
          <IconImage width={26} height={26} />
          <span className="text-2xs">no visual</span>
        </div>
      )}
      {/* subtle cinematic bottom scrim for caption legibility */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/55 via-transparent to-transparent pointer-events-none" />
    </div>
  );
}
