export interface Candidate {
  id: string;
  kind?: string;          // image | video | generated
  local_path?: string;
  thumb_path?: string;
  source_url?: string;
  direct_url?: string;    // the asset file itself
  title?: string;
  creator?: string;
  license?: string;
  license_url?: string;
  provider?: string;      // openverse | wikimedia | comfyui | upload
  reason?: string;
  width?: number;
  height?: number;
}

export interface Scene {
  id: string;
  index?: number;
  narration: string;
  visual_concept?: string;
  composition?: string;
  image_prompt?: string;
  search_terms?: string[];
  motion?: string;
  transition?: string;
  text_overlay?: string;
  duration?: number;
  audio_path?: string;
  candidates: Candidate[];
  selected?: string | null;
  status?: string;
  notes?: string;
}

export interface ProjectEnv {
  llm: boolean;
  llm_model: string;
  image_provider: string;
  comfy: boolean;
  tts_provider: string;
  tts_voice: string;
  voices: string[];
  aspects: string[];
}

export const STAGES = [
  "script",
  "scenes",
  "visuals",
  "narration",
  "draft",
] as const;
export type Stage = (typeof STAGES)[number];

export interface Project {
  id: string;
  title: string;
  idea: string;
  aspect: string;
  target_duration?: number;
  duration?: number;
  script?: string;
  approvals: Partial<Record<string, boolean>>;
  stage?: string;
  scenes: Scene[];
  total_duration?: number;
  size?: [number, number];
  has_draft?: boolean;
  has_final?: boolean;
  draft?: string;       // relative path to draft.mp4
  final?: string;       // relative path to final.mp4
  stages?: string[];
  tts_provider?: string;
  tts_voice?: string;
  voices?: string[];
  notes?: string[];
}

export interface Job {
  id: string;
  name: string;
  state: "running" | "done" | "error";
  error?: string;
}

export function assetUrl(p: Project, path?: string): string | null {
  if (!path) return null;
  return `/api/projects/${p.id}/file/${path}`;
}
