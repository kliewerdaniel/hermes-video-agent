"use client";

import { useState, useRef, useEffect } from "react";
import { useWorkspace } from "@/components/Workspace";
import { SceneThumb } from "@/components/SceneThumb";
import { aspectClass, fmtDur } from "@/components/helpers";
import { IconPlay, IconPause, IconPrev, IconNext, IconExpand, IconDownload, IconFilm } from "@/components/icons";

export function Preview() {
  const { project, activeScene, activeSceneId, setActiveSceneId } = useWorkspace();
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);

  const finalUrl = project.final ? `/api/projects/${project.id}/file/${project.final}` : null;
  const draftUrl = project.draft ? `/api/projects/${project.id}/file/${project.draft}` : null;
  const fullUrl = finalUrl ?? draftUrl;
  const fullLabel = project.final ? "final" : "draft";

  const sceneAudio =
    activeScene?.audio_path
      ? `/api/projects/${project.id}/file/${activeScene.audio_path}`
      : null;

  const idx = project.scenes.findIndex((s) => s.id === activeSceneId);

  const playScene = () => {
    if (audioRef.current) {
      audioRef.current.currentTime = 0;
      audioRef.current.play();
      setPlaying(true);
    }
  };
  const goto = (delta: number) => {
    const n = idx + delta;
    if (n >= 0 && n < project.scenes.length) setActiveSceneId(project.scenes[n].id);
  };

  useEffect(() => {
    setPlaying(false);
    audioRef.current?.pause();
  }, [activeSceneId]);

  return (
    <div className="flex flex-col flex-shrink-0 p-3 gap-3" id="rail-preview">
      <div className="flex items-center justify-between">
        <span className="label">Preview</span>
        <span className="mono text-2xs text-faint">
          scene {idx + 1}/{project.scenes.length}
        </span>
      </div>

      {/* rendered video — prominent when available */}
      {fullUrl ? (
        <div className="rounded-xl overflow-hidden border border-edge2 bg-black shadow-pop">
          <video
            src={fullUrl}
            controls
            className={`w-full ${aspectClass(project.aspect)} object-contain bg-black`}
          />
          <div className="flex items-center gap-2 px-2 py-1.5 bg-panel/80">
            <span className="text-2xs text-muted uppercase tracking-wide">Watch {fullLabel}</span>
            <div className="ml-auto flex items-center gap-1.5">
              <a
                href={fullUrl}
                target="_blank"
                className="inline-flex items-center gap-1 h-7 px-2 rounded-md bg-surface2 border border-edge text-2xs text-muted hover:text-text"
                title="Open in new tab"
              >
                <IconExpand width={13} height={13} /> Open
              </a>
              <a
                href={fullUrl}
                download
                className="inline-flex items-center gap-1 h-7 px-2 rounded-md bg-primary text-white text-2xs font-medium hover:bg-primary2"
                title="Download video"
              >
                <IconDownload width={13} height={13} /> Download
              </a>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-edge bg-panel/40 p-3 flex items-center gap-2 text-2xs text-faint">
          <IconFilm width={14} height={14} />
          No rendered video yet — build visuals + narration, then Render final.
        </div>
      )}

      {/* device frame: per-scene still + narration */}
      <div className="shrink-0 grid place-items-center min-h-0">
        <div
          className={`relative bg-black rounded-xl overflow-hidden border border-edge2 shadow-pop
            max-h-full ${aspectClass(project.aspect)}`}
        >
          <div className={`w-full h-full ${aspectClass(project.aspect)}`}>
            {activeScene ? (
              <SceneThumb project={project} scene={activeScene} rounded="rounded-xl" />
            ) : (
              <div className="grid place-items-center text-faint text-xs">no scene</div>
            )}
          </div>

          {activeScene && (
            <div className="absolute inset-x-0 bottom-0 p-3 bg-gradient-to-t from-black/80 to-transparent">
              <p className="text-white/90 text-[13px] leading-snug line-clamp-3">
                {activeScene.narration}
              </p>
            </div>
          )}

          {!fullUrl && (
            <div className="absolute top-2 right-2 mono text-2xs text-white/70 bg-black/50 px-1.5 py-0.5 rounded">
              {fmtDur(activeScene?.duration)}
            </div>
          )}
        </div>
      </div>

      {/* transport for the active scene (no full render needed) */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => goto(-1)}
          disabled={idx <= 0}
          className="grid place-items-center h-9 w-9 rounded-lg bg-surface2 border border-edge text-muted hover:text-text disabled:opacity-30"
          title="Previous scene"
        >
          <IconPrev width={15} height={15} />
        </button>
        <button
          onClick={playScene}
          disabled={!sceneAudio}
          className="grid place-items-center h-9 w-9 rounded-lg bg-primary text-white hover:bg-primary2 disabled:opacity-30"
          title="Play scene narration"
        >
          {playing ? <IconPause width={15} height={15} /> : <IconPlay width={15} height={15} />}
        </button>
        <button
          onClick={() => goto(1)}
          disabled={idx >= project.scenes.length - 1}
          className="grid place-items-center h-9 w-9 rounded-lg bg-surface2 border border-edge text-muted hover:text-text disabled:opacity-30"
          title="Next scene"
        >
          <IconNext width={15} height={15} />
        </button>

        <div className="ml-auto">
          {fullUrl ? (
            <span className="text-2xs text-faint">{fullLabel} ready</span>
          ) : (
            <span className="text-2xs text-faint">render to preview full video</span>
          )}
        </div>
      </div>

      <audio
        ref={audioRef}
        src={sceneAudio ?? ""}
        onEnded={() => setPlaying(false)}
        className="hidden"
      />
    </div>
  );
}
