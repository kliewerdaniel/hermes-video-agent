"use client";

import { useState, useEffect } from "react";
import { useWorkspace } from "@/components/Workspace";
import { Button, Field, Badge } from "@/components/ui";
import { IconMic, IconPlay, IconPause, IconCheck, IconX, IconUpload } from "@/components/icons";
import { selectedCandidate, thumbUrl, sceneNumber, sceneStatus, fmtDur } from "@/components/helpers";
import { SelectInput } from "@/components/inspectorBits";
import { Waveform } from "@/components/Waveform";
import { api } from "@/lib/api";

type VoiceInfo = { name: string; url: string };

export function NarrationStep({ onDone }: { onDone?: () => void }) {
  const { project, narrate, narrateScene, setVoice, isBusy, isSceneBusy } = useWorkspace();
  const [playing, setPlaying] = useState<string | null>(null);
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [preview, setPreview] = useState<string | null>(null);
  const [uploadName, setUploadName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [voiceErr, setVoiceErr] = useState("");

  async function refreshVoices() {
    try {
      const { voices: vs } = await api.voices();
      setVoices(vs);
    } catch {
      /* non-fatal — picker still works */
    }
  }
  useEffect(() => {
    void refreshVoices();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const r = project.scenes.filter((s) => s.status !== "skipped");
  const withAudio = r.filter((s) => s.audio_path).length;
  const needAudio = r.filter((s) => !s.audio_path).length;

  const play = (sceneId: string, url: string) => {
    if (playing === sceneId) {
      setPlaying(null);
      return;
    }
    const au = new Audio(url);
    setPlaying(sceneId);
    au.onended = () => setPlaying(null);
    au.play().catch(() => setPlaying(null));
  };

  async function onUpload(e: React.FormEvent) {
    e.preventDefault();
    const input = (e.target as HTMLFormElement).querySelector<HTMLInputElement>("input[type=file]");
    const file = input?.files?.[0];
    if (!file) return;
    setUploading(true);
    setVoiceErr("");
    try {
      await api.uploadVoice(uploadName, file);
      setUploadName("");
      if (input) input.value = "";
      await refreshVoices();
    } catch (err) {
      setVoiceErr(String(err instanceof Error ? err.message : err));
    } finally {
      setUploading(false);
    }
  }

  async function onDelete(name: string) {
    if (!confirm(`Delete voice "${name}"? This cannot be undone.`)) return;
    setVoiceErr("");
    try {
      await api.deleteVoice(name);
      await refreshVoices();
    } catch (err) {
      setVoiceErr(String(err instanceof Error ? err.message : err));
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 flex-wrap">
        <div>
          <h2 className="text-base font-semibold flex items-center gap-2">
            <IconMic width={18} height={18} className="text-primary2" /> Narration
          </h2>
          <p className="text-muted text-sm">
            {withAudio}/{r.length} scenes voiced. {needAudio > 0
              ? `Generate voiceover for the ${needAudio} remaining scene${needAudio > 1 ? "s" : ""}.`
              : "Every scene has narration — play, re-voice, or change the speaker."}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <SelectInput
            value={project.tts_voice ?? ""}
            options={[...new Set([...(project.voices ?? []), ...voices.map((v) => v.name)])]}
            onChange={(v) => setVoice(v)}
            placeholder="Default voice"
          />
          <Button
            loading={isBusy("narrate")}
            disabled={isBusy("narrate")}
            onClick={() => narrate()}
            title="Generate voiceover for every scene at once"
          >
            <IconMic width={14} height={14} /> Narrate all
          </Button>
        </div>
      </div>

      {/* Voice library — self-contained, no external TTS server required */}
      <div className="panel-2 p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <IconMic width={15} height={15} className="text-primary2" /> Voice library
          </h3>
          <span className="text-2xs text-muted">{voices.length} voice{voices.length === 1 ? "" : "s"}</span>
        </div>
        <div className="flex flex-wrap gap-2 mb-3">
          {voices.map((v) => {
            const isPreviewing = preview === v.url;
            const isSelected = (project.tts_voice || "") === v.name;
            return (
              <div
                key={v.name}
                role="button"
                tabIndex={0}
                onClick={() => void setVoice(v.name).catch(() => {})}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    void setVoice(v.name).catch(() => {});
                  }
                }}
                className={`group flex items-center gap-1.5 rounded-lg border px-1.5 py-1 text-xs cursor-pointer transition-colors ${
                  isSelected
                    ? "border-primary/70 bg-primary/10 text-text"
                    : "border-edge bg-surface2 text-text hover:border-edge2"
                }`}
                title={`Use ${v.name} for narration`}
              >
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (isPreviewing) { setPreview(null); return; }
                    const au = new Audio(v.url);
                    setPreview(v.url);
                    au.onended = () => setPreview(null);
                    au.play().catch(() => setPreview(null));
                  }}
                  className="grid place-items-center h-5 w-5 rounded hover:bg-surface text-faint hover:text-primary2"
                  title="Preview this voice"
                >
                  {isPreviewing ? <IconPause width={12} height={12} /> : <IconPlay width={12} height={12} />}
                </button>
                <span className={isSelected ? "font-medium" : ""}>{v.name}</span>
                {isSelected && <IconCheck width={12} height={12} className="text-primary2" />}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(v.name);
                  }}
                  className="text-faint hover:text-danger opacity-0 group-hover:opacity-100 transition-opacity"
                  title={`Delete ${v.name}`}
                >
                  <IconX width={11} height={11} />
                </button>
              </div>
            );
          })}
        </div>
        <form onSubmit={onUpload} className="flex items-center gap-2 flex-wrap">
          <input
            value={uploadName}
            onChange={(e) => setUploadName(e.target.value)}
            placeholder="voice name (e.g. Morgan)"
            className="bg-surface2 border border-edge rounded-lg px-2.5 py-1.5 text-sm outline-none focus:border-primary w-44"
          />
          <label className="inline-flex items-center gap-1.5 text-xs text-muted bg-surface2 border border-edge rounded-lg px-2.5 py-1.5 cursor-pointer hover:border-edge2">
            <IconUpload width={13} height={13} /> Choose sample
            <input type="file" accept="audio/*" className="hidden" />
          </label>
          <Button type="submit" variant="secondary" size="sm" loading={uploading} disabled={uploading}>
            Upload voice
          </Button>
        </form>
        {voiceErr && <p className="text-danger text-xs mt-2">{voiceErr}</p>}
        <p className="text-faint text-2xs mt-2">
          Upload a short clean clip (&lt;30s) of the speaker. It is stored locally and used for voice cloning.
        </p>
      </div>

      <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(320px,1fr))]">
        {r.map((scene) => {
          const sel = selectedCandidate(scene);
          const audioUrl = scene.audio_path
            ? `/api/projects/${project.id}/file/${scene.audio_path}`
            : null;
          const st = sceneStatus(scene);
          return (
            <div key={scene.id} className="panel-2 p-3 flex gap-3">
              {/* thumbnail */}
              <div className="w-20 shrink-0 rounded-lg overflow-hidden bg-panel border border-edge self-start">
                {sel ? (
                  <img src={thumbUrl(project, sel) ?? ""} className="w-full aspect-video object-cover" alt="" />
                ) : (
                  <div className="grid place-items-center h-[45px] text-faint text-[10px]">no img</div>
                )}
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="mono text-sm text-primary2 font-semibold">
                    {String(sceneNumber(project, scene.id)).padStart(2, "0")}
                  </span>
                  <span className="text-2xs text-faint mono">{fmtDur(scene.duration)}</span>
                  <Badge tone={st.tone}>{st.label}</Badge>
                  {audioUrl && (
                    <span className="ml-auto text-2xs text-success flex items-center gap-1">
                      <IconCheck width={12} height={12} /> voiced
                    </span>
                  )}
                </div>

                <p className="text-[12px] text-text/90 line-clamp-2 mb-2">{scene.narration}</p>

                {audioUrl ? (
                  <>
                    <Waveform src={audioUrl} duration={scene.duration} height={36} />
                    <div className="flex items-center gap-2 mt-2">
                      <button
                        onClick={() => play(scene.id, audioUrl)}
                        className="grid place-items-center h-8 w-8 rounded-lg bg-primary text-white hover:bg-primary2"
                        title="Play narration"
                      >
                        {playing === scene.id ? <IconPause width={14} height={14} /> : <IconPlay width={14} height={14} />}
                      </button>
                      <Button
                        variant="secondary"
                        size="sm"
                        loading={isSceneBusy(scene.id)}
                        onClick={() => narrateScene(scene.id)}
                        title="Regenerate this scene's voiceover"
                      >
                        <IconMic width={13} height={13} /> Re-narrate
                      </Button>
                    </div>
                  </>
                ) : (
                  <Button
                    variant="secondary"
                    size="sm"
                    loading={isSceneBusy(scene.id)}
                    onClick={() => narrateScene(scene.id)}
                    title="Generate this scene's voiceover"
                  >
                    <IconMic width={13} height={13} /> Narrate this scene
                  </Button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {onDone && (
        <div className="flex justify-end">
          <button
            onClick={onDone}
            className="h-9 px-4 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary2"
          >
            Next: Export →
          </button>
        </div>
      )}
    </div>
  );
}
