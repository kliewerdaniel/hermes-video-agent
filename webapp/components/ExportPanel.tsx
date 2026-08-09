"use client";

import { useState } from "react";
import { useWorkspace } from "@/components/Workspace";
import { Button, Badge, StatusDot } from "@/components/ui";
import { projectReadiness, fmtDur } from "@/components/helpers";
import { IconExport, IconPlay, IconCheck, IconAlert } from "@/components/icons";

export function ExportPanel() {
  const { project, isBusy, render } = useWorkspace();
  const [burnCaptions, setBurnCaptions] = useState(true);
  const r = projectReadiness(project);
  const [w, h] = project.size ?? (project.aspect === "9:16" ? [1080, 1920] : [1920, 1080]);
  const busy = isBusy("render");

  const finalUrl = project.final ? `/api/projects/${project.id}/file/${project.final}` : null;
  const draftUrl = project.draft ? `/api/projects/${project.id}/file/${project.draft}` : null;

  return (
    <div className="p-3 space-y-3" id="rail-export">
      <div className="flex items-center gap-2">
        <IconExport width={16} height={16} className="text-primary2" />
        <h2 className="text-sm font-semibold tracking-wide">EXPORT</h2>
      </div>

      {/* readiness gate */}
      <div className="inset p-3 space-y-2">
        <Row label="Visuals" ok={r.allVisuals} text={`${r.withVisual}/${r.total} selected`} />
        <Row label="Narration" ok={r.allAudio} text={`${r.withAudio}/${r.total} generated`} />
        <Row label="Scenes ready" ok={r.allReady} text={`${r.ready}/${r.total}`} />
        {!r.allReady && (
          <p className="text-2xs text-warn flex items-center gap-1 pt-1">
            <IconAlert width={12} height={12} /> Complete the above before final render.
          </p>
        )}
      </div>

      {/* spec */}
      <div className="grid grid-cols-3 gap-2 text-center">
        <Spec label="Resolution" value={`${w}×${h}`} />
        <Spec label="FPS" value="30" />
        <Spec label="Format" value="MP4" />
      </div>
      <div className="flex items-center justify-between inset px-3 py-2">
        <span className="label">Duration</span>
        <span className="mono text-sm">{fmtDur(project.total_duration)}</span>
      </div>

      <label className="flex items-center gap-2 text-2xs text-muted cursor-pointer">
        <input
          type="checkbox"
          checked={burnCaptions}
          onChange={(e) => setBurnCaptions(e.target.checked)}
        />
        Burn-in captions
      </label>

      <div className="space-y-2">
        <Button
          className="w-full"
          loading={isBusy("render")}
          disabled={!r.allReady || busy}
          onClick={() => render(true, burnCaptions, "")}
        >
          <IconExport width={14} height={14} /> Render final video
        </Button>
      </div>

      {(finalUrl || draftUrl) && (
        <div className="inset p-3 animate-scale-in">
          <div className="flex items-center gap-2 text-success mb-2">
            <IconCheck width={14} height={14} /> Video ready
          </div>
          <div className="flex gap-2">
            <a
              href={finalUrl ?? draftUrl!}
              target="_blank"
              className="flex-1 h-9 inline-flex items-center justify-center gap-1.5 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary2"
            >
              <IconPlay width={13} height={13} /> Watch
            </a>
            <a
              href={finalUrl ?? draftUrl!}
              download
              className="flex-1 h-9 inline-flex items-center justify-center gap-1.5 rounded-lg bg-surface2 border border-edge text-sm text-muted hover:text-text"
            >
              Export
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ label, ok, text }: { label: string; ok: boolean; text: string }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <StatusDot tone={ok ? "success" : "warn"} />
      <span className={ok ? "text-text" : "text-muted"}>{label}</span>
      <span className="ml-auto mono text-2xs text-faint">{text}</span>
    </div>
  );
}

function Spec({ label, value }: { label: string; value: string }) {
  return (
    <div className="inset py-2 rounded-lg">
      <div className="label text-center text-[10px]">{label}</div>
      <div className="mono text-xs text-text mt-0.5">{value}</div>
    </div>
  );
}
