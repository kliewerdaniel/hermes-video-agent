"use client";

import { useState, useEffect, useRef } from "react";
import { useWorkspace } from "@/components/Workspace";
import { selectedCandidate, thumbUrl, fmtDur, fmtTime } from "@/components/helpers";
import { IconPlay, IconPause } from "@/components/icons";

export function Timeline() {
  const { project, activeSceneId, setActiveSceneId } = useWorkspace();
  const [playAll, setPlayAll] = useState(false);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const total = project.total_duration || 1;
  const audios = useRef<Record<string, HTMLAudioElement>>({});
  const timer = useRef<number | null>(null);

  const clips = project.scenes
    .filter((s) => s.status !== "skipped")
    .map((s) => s);

  const stopAll = () => {
    Object.values(audios.current).forEach((a) => a.pause());
    audios.current = {};
    setPlayingId(null);
    setPlayAll(false);
  };

  // audition: sequentially play each scene's narration
  useEffect(() => {
    if (!playAll) return;
    let cancelled = false;
    const order = clips.filter((s) => s.audio_path);
    let i = 0;
    const step = () => {
      if (cancelled || i >= order.length) {
        setPlayAll(false);
        setPlayingId(null);
        return;
      }
      const s = order[i];
      setActiveSceneId(s.id);
      setPlayingId(s.id);
      const au = new Audio(`/api/projects/${project.id}/file/${s.audio_path}`);
      audios.current[s.id] = au;
      au.onended = () => {
        i++;
        step();
      };
      au.play().catch(() => {
        i++;
        step();
      });
    };
    step();
    return () => {
      cancelled = true;
      Object.values(audios.current).forEach((a) => a.pause());
      audios.current = {};
      if (timer.current) window.clearTimeout(timer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playAll]);

  // build a flattened timeline of scene clips with running start times
  let t = 0;
  const spans = project.scenes
    .filter((s) => s.status !== "skipped")
    .map((s) => {
      const start = t;
      const dur = s.duration || 0;
      t += dur;
      return { s, start, dur };
    });

  const togglePlay = (s: (typeof spans)[number]["s"]) => {
    if (!s.audio_path) return;
    if (playingId === s.id) {
      audios.current[s.id]?.pause();
      setPlayingId(null);
      return;
    }
    stopAll();
    setActiveSceneId(s.id);
    setPlayingId(s.id);
    const au = new Audio(`/api/projects/${project.id}/file/${s.audio_path}`);
    audios.current[s.id] = au;
    au.onended = () => setPlayingId(null);
    au.play();
  };

  return (
    <div className="h-full flex flex-col px-3 py-2 gap-2" id="rail-timeline">
      <div className="flex items-center gap-2">
        <button
          onClick={() => (playAll ? stopAll() : setPlayAll(true))}
          className="grid place-items-center h-7 w-7 rounded-md bg-surface2 border border-edge text-muted hover:text-text"
          title="Play sequence (audition)"
        >
          {playAll ? <IconPause width={13} height={13} /> : <IconPlay width={13} height={13} />}
        </button>
        <span className="label">Timeline</span>
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={stopAll}
            className="text-2xs text-faint hover:text-text"
            title="Stop"
          >
            stop
          </button>
          <span className="mono text-2xs text-faint">
            {fmtTime(total)} · {project.scenes.length} clips
          </span>
        </div>
      </div>

      {/* VIDEO track */}
      <Track label="VIDEO">
        {spans.map(({ s, start, dur }) => {
          const active = s.id === activeSceneId;
          return (
            <Clip
              key={s.id}
              left={(start / total) * 100}
              width={(dur / total) * 100}
              active={active}
              onClick={() => setActiveSceneId(s.id)}
            >
              <div
                className="w-full h-full bg-cover bg-center"
                style={{
                  backgroundImage: selectedCandidate(s)
                    ? `url(${thumbUrl(project, selectedCandidate(s))})`
                    : undefined,
                  background: selectedCandidate(s)
                    ? undefined
                    : "linear-gradient(135deg,#1d1d2b,#121218)",
                }}
              />
            </Clip>
          );
        })}
      </Track>

      {/* AUDIO track — clickable per-scene playback */}
      <Track label="AUDIO">
        {spans.map(({ s, start, dur }) => {
          const active = s.id === activeSceneId;
          const has = !!s.audio_path;
          const playing = playingId === s.id;
          return (
            <Clip
              key={s.id}
              left={(start / total) * 100}
              width={(dur / total) * 100}
              active={active || playing}
              onClick={() => togglePlay(s)}
              className={has ? (playing ? "bg-primary/60" : "bg-primary/30") : "bg-surface2/40"}
              title={has ? (playing ? "Stop narration" : "Play narration") : "No narration"}
            >
              <div className="w-full h-full flex items-center justify-center">
                {has ? (
                  playing ? (
                    <IconPause width={12} height={12} className="text-white" />
                  ) : (
                    <IconPlay width={11} height={11} className="text-primary2/80" />
                  )
                ) : (
                  <span className="text-[9px] text-faint">—</span>
                )}
              </div>
            </Clip>
          );
        })}
      </Track>
    </div>
  );
}

function Track({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="label w-10 shrink-0 text-faint">{label}</span>
      <div className="relative flex-1 h-9 rounded-md bg-panel border border-edge overflow-hidden">
        {children}
      </div>
    </div>
  );
}

function Clip({
  left,
  width,
  active,
  onClick,
  children,
  className = "",
  title,
}: {
  left: number;
  width: number;
  active: boolean;
  onClick: () => void;
  children?: React.ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      style={{ left: `${left}%`, width: `${Math.max(width, 1.5)}%` }}
      className={`absolute top-0 bottom-0 border-r border-black/40 overflow-hidden transition-all
        ${active ? "ring-1 ring-primary z-10" : ""} ${className}`}
    >
      {children}
    </button>
  );
}
