"use client";

import { ReactNode, SVGProps } from "react";

type P = SVGProps<SVGSVGElement>;
const base = (props: P) => ({
  width: 16,
  height: 16,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  ...props,
});

export const IconArrowLeft = (p: P) => (<svg {...base(p)}><path d="M19 12H5" /><path d="M12 19l-7-7 7-7" /></svg>);
export const IconPlay = (p: P) => (<svg {...base(p)}><path d="M6 4l14 8-14 8V4z" fill="currentColor" stroke="none" /></svg>);
export const IconPause = (p: P) => (<svg {...base(p)}><rect x="6" y="5" width="4" height="14" rx="1" fill="currentColor" stroke="none" /><rect x="14" y="5" width="4" height="14" rx="1" fill="currentColor" stroke="none" /></svg>);
export const IconPrev = (p: P) => (<svg {...base(p)}><path d="M18 18V6L8 12l10 6z" fill="currentColor" stroke="none" /><rect x="5" y="5" width="2" height="14" rx="1" fill="currentColor" stroke="none" /></svg>);
export const IconNext = (p: P) => (<svg {...base(p)}><path d="M6 6v12l10-6L6 6z" fill="currentColor" stroke="none" /><rect x="17" y="5" width="2" height="14" rx="1" fill="currentColor" stroke="none" /></svg>);
export const IconSearch = (p: P) => (<svg {...base(p)}><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg>);
export const IconUpload = (p: P) => (<svg {...base(p)}><path d="M12 16V4" /><path d="M7 9l5-5 5 5" /><path d="M4 20h16" /></svg>);
export const IconSpark = (p: P) => (<svg {...base(p)}><path d="M12 3l1.8 4.7L18.5 9.5 13.8 11.3 12 16l-1.8-4.7L5.5 9.5l4.7-1.8L12 3z" /><path d="M19 14l.7 1.9 1.9.7-1.9.7-.7 1.9-.7-1.9-1.9-.7 1.9-.7.7-1.9z" /></svg>);
export const IconSettings = (p: P) => (<svg {...base(p)}><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 1 1-4 0v-.1A1.6 1.6 0 0 0 6.6 19l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.6 1.6 0 0 0 3 13.4H3a2 2 0 1 1 0-4h.1A1.6 1.6 0 0 0 4.6 6.6l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.6 1.6 0 0 0 10 3V3a2 2 0 1 1 4 0v.1A1.6 1.6 0 0 0 17.4 5l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1A1.6 1.6 0 0 0 21 10.6H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z" /></svg>);
export const IconLayers = (p: P) => (<svg {...base(p)}><path d="M12 3l9 5-9 5-9-5 9-5z" /><path d="M3 13l9 5 9-5" /></svg>);
export const IconMic = (p: P) => (<svg {...base(p)}><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0" /><path d="M12 18v3" /></svg>);
export const IconFilm = (p: P) => (<svg {...base(p)}><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M7 4v16M17 4v16M3 9h4M3 14h4M17 9h4M17 14h4" /></svg>);
export const IconEye = (p: P) => (<svg {...base(p)}><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="2.5" /></svg>);
export const IconCheck = (p: P) => (<svg {...base(p)}><path d="M20 6L9 17l-5-5" /></svg>);
export const IconX = (p: P) => (<svg {...base(p)}><path d="M18 6L6 18M6 6l12 12" /></svg>);
export const IconPlus = (p: P) => (<svg {...base(p)}><path d="M12 5v14M5 12h14" /></svg>);
export const IconDrag = (p: P) => (<svg {...base(p)}><circle cx="9" cy="6" r="1" fill="currentColor" /><circle cx="15" cy="6" r="1" fill="currentColor" /><circle cx="9" cy="12" r="1" fill="currentColor" /><circle cx="15" cy="12" r="1" fill="currentColor" /><circle cx="9" cy="18" r="1" fill="currentColor" /><circle cx="15" cy="18" r="1" fill="currentColor" /></svg>);
export const IconExpand = (p: P) => (<svg {...base(p)}><path d="M8 3H5a2 2 0 0 0-2 2v3M16 3h3a2 2 0 0 1 2 2v3M8 21H5a2 2 0 0 1-2-2v-3M16 21h3a2 2 0 0 0 2-2v-3" /></svg>);
export const IconScript = (p: P) => (<svg {...base(p)}><path d="M5 4h11a2 2 0 0 1 2 2v14H7a2 2 0 0 1-2-2V4z" /><path d="M9 8h6M9 12h6M9 16h3" /></svg>);
export const IconStoryboard = (p: P) => (<svg {...base(p)}><rect x="3" y="4" width="7" height="7" rx="1" /><rect x="14" y="4" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="6" rx="1" /><rect x="14" y="14" width="7" height="6" rx="1" /></svg>);
export const IconImage = (p: P) => (<svg {...base(p)}><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="9" cy="10" r="1.6" /><path d="M21 16l-5-5L5 20" /></svg>);
export const IconTimeline = (p: P) => (<svg {...base(p)}><path d="M3 6h18M3 12h18M3 18h18" /><circle cx="7" cy="6" r="1.6" fill="currentColor" /><circle cx="14" cy="12" r="1.6" fill="currentColor" /><circle cx="10" cy="18" r="1.6" fill="currentColor" /></svg>);
export const IconExport = (p: P) => (<svg {...base(p)}><path d="M12 15V3" /><path d="M8 7l4-4 4 4" /><path d="M4 14v5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5" /></svg>);
export const IconUndo = (p: P) => (<svg {...base(p)}><path d="M9 14L4 9l5-5" /><path d="M4 9h11a5 5 0 0 1 0 10h-3" /></svg>);
export const IconRedo = (p: P) => (<svg {...base(p)}><path d="M15 14l5-5-5-5" /><path d="M20 9H9a5 5 0 0 0 0 10h3" /></svg>);
export const IconRefresh = (p: P) => (<svg {...base(p)}><path d="M21 12a9 9 0 1 1-3-6.7L21 8" /><path d="M21 3v5h-5" /></svg>);
export const IconSkip = (p: P) => (<svg {...base(p)}><path d="M5 4l10 8-10 8V4z" fill="currentColor" stroke="none" /><rect x="17" y="4" width="2.5" height="16" rx="1" fill="currentColor" stroke="none" /></svg>);
export const IconWand = (p: P) => (<svg {...base(p)}><path d="M15 4V2M15 10V8M11 6H9M21 6h-2" /><path d="M14.5 6a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0z" /><path d="M19 13l-7.5 7.5a2.1 2.1 0 0 1-3-3L16 10" /></svg>);
export const IconClock = (p: P) => (<svg {...base(p)}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>);
export const IconAlert = (p: P) => (<svg {...base(p)}><path d="M12 9v4M12 17h.01" /><path d="M10.3 3.9l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3l-8-14a2 2 0 0 0-3.4 0z" /></svg>);
export const IconChevron = (p: P) => (<svg {...base(p)}><path d="M9 6l6 6-6 6" /></svg>);
export const IconStar = (p: P) => (<svg {...base(p)}><path d="M12 3l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9 6.8 19.9l1-5.8L3.5 9.2l5.9-.9L12 3z" /></svg>);
export const IconDownload = (p: P) => (<svg {...base(p)}><path d="M12 3v12M7 10l5 5 5-5" /><path d="M4 20h16" /></svg>);

export const Icon = ({ name, ...p }: { name: string } & P): ReactNode => {
  const map: Record<string, (x: P) => ReactNode> = {
    arrowLeft: IconArrowLeft, play: IconPlay, pause: IconPause, prev: IconPrev, next: IconNext,
    search: IconSearch, upload: IconUpload, spark: IconSpark, settings: IconSettings,
    layers: IconLayers, mic: IconMic, film: IconFilm, eye: IconEye, check: IconCheck, x: IconX,
    plus: IconPlus, drag: IconDrag, expand: IconExpand, script: IconScript, storyboard: IconStoryboard,
    image: IconImage, timeline: IconTimeline, export: IconExport, undo: IconUndo, redo: IconRedo,
    refresh: IconRefresh, skip: IconSkip, wand: IconWand, clock: IconClock, alert: IconAlert,
    chevron: IconChevron, star: IconStar, download: IconDownload,
  };
  const C = map[name] || IconSpark;
  return C(p);
};
