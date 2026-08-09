import { Candidate, Project, Scene } from "@/lib/types";

export function fmtDur(s?: number): string {
  if (s == null || !isFinite(s)) return "—";
  return `${s.toFixed(1)}s`;
}

export function fmtTime(s: number): string {
  if (!isFinite(s)) s = 0;
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  const cs = Math.floor((s % 1) * 100);
  return `${m}:${String(sec).padStart(2, "0")}.${String(cs).padStart(2, "0")}`;
}

/** CSS aspect-ratio for a given aspect string. */
export function aspectClass(aspect: string): string {
  if (aspect === "9:16") return "aspect-[9/16]";
  if (aspect === "1:1") return "aspect-square";
  if (aspect === "4:5") return "aspect-[4/5]";
  return "aspect-video";
}

export function aspectRatio(aspect: string): number {
  // width / height
  if (aspect === "9:16") return 9 / 16;
  if (aspect === "1:1") return 1;
  if (aspect === "4:5") return 4 / 5;
  return 16 / 9;
}

export type SceneStatus = {
  key: string;
  label: string;
  tone: "muted" | "primary" | "success" | "warn" | "danger" | "info";
};

export function sceneStatus(scene: Scene): SceneStatus {
  if (scene.status === "skipped")
    return { key: "skipped", label: "Skipped", tone: "muted" };
  if (!scene.candidates || scene.candidates.length === 0)
    return { key: "needs-visual", label: "Needs visual", tone: "warn" };
  if (!scene.selected)
    return { key: "suggested", label: "AI suggested", tone: "primary" };
  if (!scene.audio_path)
    return scene.status === "approved"
      ? { key: "visual-approved", label: "Visual approved", tone: "success" }
      : { key: "needs-review", label: "Needs review", tone: "warn" };
  return { key: "ready", label: "Ready", tone: "success" };
}

export function projectReadiness(p: Project) {
  const scenes = p.scenes.filter((s) => s.status !== "skipped");
  const total = scenes.length || 1;
  const withVisual = scenes.filter((s) => s.selected).length;
  const withAudio = scenes.filter((s) => s.audio_path).length;
  const ready = scenes.filter((s) => s.selected && s.audio_path).length;
  const approved = scenes.filter((s) => s.status === "approved").length;
  return {
    total: scenes.length,
    withVisual,
    withAudio,
    ready,
    approved,
    allVisuals: withVisual === total,
    allAudio: withAudio === total,
    anyVisual: withVisual > 0,
    anyAudio: withAudio > 0,
    allReady: ready === total,
    pct: Math.round((ready / total) * 100),
  };
}

export function selectedCandidate(scene: Scene): Candidate | undefined {
  return scene.candidates.find((c) => c.id === scene.selected);
}

export function sceneNumber(project: Project, sceneId?: string): number {
  if (!sceneId) return 0;
  return project.scenes.findIndex((s) => s.id === sceneId) + 1;
}

export function thumbUrl(p: Project, c?: Candidate): string | null {
  if (!c) return null;
  if (c.thumb_path) return `/api/projects/${p.id}/file/${c.thumb_path}`;
  if (c.local_path) return `/api/projects/${p.id}/file/${c.local_path}`;
  if (c.direct_url) return c.direct_url;
  return null;
}

export function assetUrl(p: Project, path?: string): string | null {
  if (!path) return null;
  return `/api/projects/${p.id}/file/${path}`;
}

export function compactLicense(lic?: string): string {
  if (!lic) return "Unknown";
  const m = lic.match(/CC[- ](BY(?:-[A-Z0-9.]+)?)/i) || lic.match(/(public domain|pdm)/i);
  if (m) return m[1].toUpperCase().replace(" ", "-");
  return lic.length > 16 ? lic.slice(0, 14) + "…" : lic;
}
