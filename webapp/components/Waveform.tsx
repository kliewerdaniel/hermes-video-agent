"use client";

import { useEffect, useRef, useState } from "react";
import { fmtTime } from "@/components/helpers";

/** Decode an audio file (served via the project file endpoint) into peak bars. */
async function peaksFromUrl(url: string, buckets = 120): Promise<number[]> {
  const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
  const buf = await (await fetch(url)).arrayBuffer();
  const audio = await ctx.decodeAudioData(buf);
  const data = audio.getChannelData(0);
  const block = Math.floor(data.length / buckets) || 1;
  const peaks: number[] = [];
  for (let i = 0; i < buckets; i++) {
    let max = 0;
    for (let j = 0; j < block; j++) {
      const v = Math.abs(data[i * block + j] || 0);
      if (v > max) max = v;
    }
    peaks.push(max);
  }
  ctx.close();
  return peaks;
}

export function Waveform({
  src,
  duration,
  onSeek,
  currentTime,
  color = "#7c6aff",
  height = 48,
}: {
  src: string;
  duration?: number;
  onSeek?: (frac: number) => void;
  currentTime?: number;
  color?: string;
  height?: number;
}) {
  const [peaks, setPeaks] = useState<number[]>([]);
  const [failed, setFailed] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let dead = false;
    setFailed(false);
    peaksFromUrl(src)
      .then((p) => !dead && setPeaks(p))
      .catch(() => !dead && setFailed(true));
    return () => {
      dead = true;
    };
  }, [src]);

  const max = Math.max(...peaks, 0.0001);
  const played = currentTime != null && duration ? currentTime / duration : 0;

  const seek = (e: React.MouseEvent) => {
    if (!onSeek || !ref.current) return;
    const r = ref.current.getBoundingClientRect();
    onSeek((e.clientX - r.left) / r.width);
  };

  if (failed) {
    return (
      <div className="flex items-center gap-2 text-muted text-xs h-12">
        <audio src={src} controls className="w-full h-9" />
      </div>
    );
  }

  return (
    <div
      ref={ref}
      onClick={seek}
      className="relative w-full cursor-pointer flex items-center gap-[2px]"
      style={{ height }}
    >
      {peaks.map((p, i) => {
        const filled = played > 0 && i / peaks.length <= played;
        return (
          <span
            key={i}
            className="flex-1 rounded-full transition-colors"
            style={{
              height: `${Math.max(4, (p / max) * 100)}%`,
              background: filled ? color : "#2e2e3b",
            }}
          />
        );
      })}
      {played > 0 && (
        <span
          className="absolute top-0 bottom-0 w-px bg-white/70 pointer-events-none"
          style={{ left: `${played * 100}%` }}
        />
      )}
      {duration != null && (
        <span className="mono text-2xs text-faint absolute -bottom-4 left-0">
          {fmtTime(currentTime ?? 0)} / {fmtTime(duration)}
        </span>
      )}
    </div>
  );
}
