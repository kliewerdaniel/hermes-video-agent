"use client";

import { useState } from "react";
import { useWorkspace } from "@/components/Workspace";
import { Scene, Candidate } from "@/lib/types";
import { Tabs, Button, Field, Badge, StatusDot, IconButton } from "@/components/ui";
import {
  IconSearch,
  IconUpload,
  IconSpark,
  IconCheck,
  IconSkip,
  IconRefresh,
  IconMic,
  IconPlay,
  IconPause,
} from "@/components/icons";
import {
  sceneStatus,
  selectedCandidate,
  thumbUrl,
  compactLicense,
  fmtDur,
  sceneNumber,
} from "@/components/helpers";
import { Waveform } from "@/components/Waveform";
import { CandidateCard, SelectInput } from "@/components/inspectorBits";

const TABS = [
  { id: "content", label: "CONTENT" },
  { id: "visual", label: "VISUAL" },
  { id: "audio", label: "AUDIO" },
  { id: "motion", label: "MOTION" },
];

export function SceneInspector() {
  const { activeScene, project } = useWorkspace();
  const [tab, setTab] = useState("content");

  if (!activeScene) {
    return (
      <div className="grid place-items-center h-full text-center p-6">
        <div className="text-muted text-sm">
          <p className="mb-1 text-text font-medium">No scene selected</p>
          Choose a scene from the storyboard to inspect and edit it.
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full" id="rail-scenes-inspector">
      <div className="px-3 pt-3 flex items-center gap-2 border-b border-edge">
        <span className="mono text-sm text-primary2 font-semibold">
          {String(sceneNumber(project, activeScene.id)).padStart(2, "0")}
        </span>
        <StatusPill scene={activeScene} />
      </div>
      <Tabs tabs={TABS} active={tab} onChange={setTab} />
      <div className="flex-1 overflow-y-auto px-3 py-3">
        {tab === "content" && <ContentTab key={activeScene.id} scene={activeScene} />}
        {tab === "visual" && <VisualTab key={activeScene.id} scene={activeScene} />}
        {tab === "audio" && <AudioTab key={activeScene.id} scene={activeScene} />}
        {tab === "motion" && <MotionTab key={activeScene.id} scene={activeScene} />}
      </div>
    </div>
  );
}

function StatusPill({ scene }: { scene: Scene }) {
  const st = sceneStatus(scene);
  return (
    <Badge tone={st.tone}>
      <StatusDot tone={st.tone} />
      {st.label}
    </Badge>
  );
}

/* ----------------------------- CONTENT ----------------------------- */
function ContentTab({ scene }: { scene: Scene }) {
  const { editScene, skipScene, isBusy } = useWorkspace();
  return (
    <div className="space-y-3 animate-fade-in">
      <Field label="Narration">
        <textarea
          defaultValue={scene.narration}
          onBlur={(e) => {
            if (e.target.value !== scene.narration)
              editScene(scene.id, { narration: e.target.value });
          }}
          className="input w-full h-28 resize-none leading-relaxed"
          placeholder="What this scene says…"
        />
      </Field>

      <div className="grid grid-cols-2 gap-2">
        <Field label="Duration (s)">
          <input
            type="number"
            step="0.1"
            min="0.3"
            defaultValue={scene.duration ?? 0}
            onBlur={(e) =>
              editScene(scene.id, { duration: parseFloat(e.target.value) })
            }
            className="input w-full mono"
          />
        </Field>
        <Field label="Transition">
          <SelectInput
            value={scene.transition ?? "cut"}
            options={["cut", "fade", "dissolve"]}
            onChange={(v) => editScene(scene.id, { transition: v })}
          />
        </Field>
      </div>

      <Field label="Visual concept (directive to the AI)">
        <textarea
          defaultValue={scene.visual_concept}
          onBlur={(e) => editScene(scene.id, { visual_concept: e.target.value })}
          className="input w-full h-20 resize-none"
          placeholder="Plain-language description of the shot…"
        />
      </Field>

      <Field label="Image prompt">
        <textarea
          defaultValue={scene.image_prompt}
          onBlur={(e) => editScene(scene.id, { image_prompt: e.target.value })}
          className="input w-full h-20 resize-none font-mono text-xs"
          placeholder="Generative prompt (optional)…"
        />
      </Field>

      <Button
        variant="ghost"
        size="sm"
        className="w-full"
        onClick={() => skipScene(scene.id)}
        disabled={isBusy("skip")}
      >
        <IconSkip width={13} height={13} /> Skip this scene
      </Button>
    </div>
  );
}

/* ------------------------------ VISUAL ----------------------------- */
function VisualTab({ scene }: { scene: Scene }) {
  const {
    project,
    activeSceneId,
    researchScene,
    researchAll,
    selectCandidate,
    generateScene,
    uploadScene,
    skipScene,
    isBusy,
  } = useWorkspace();
  const [terms, setTerms] = useState("");
  const [uploading, setUploading] = useState(false);
  const sel = selectedCandidate(scene);

  return (
    <div className="space-y-3 animate-fade-in">
      {/* current selection */}
      <div className="panel-2 p-2">
        <div className="label mb-1.5">Selected visual</div>
        {sel ? (
          <div className="relative rounded-lg overflow-hidden">
            <img
              src={thumbUrl(project, sel) ?? ""}
              className="w-full aspect-video object-cover"
              alt=""
            />
            <div className="absolute bottom-1.5 left-1.5 flex items-center gap-1.5">
              <Badge tone="success">
                <IconCheck width={11} height={11} /> selected
              </Badge>
              <Badge tone="muted">{compactLicense(sel.license)}</Badge>
            </div>
          </div>
        ) : (
          <div className="grid place-items-center h-24 text-faint text-xs rounded-lg bg-panel border border-dashed border-edge">
            No visual selected
          </div>
        )}
        {sel && (
          <p className="text-2xs text-muted mt-1.5 truncate">
            {sel.title || sel.provider}
            {sel.creator ? ` · ${sel.creator}` : ""}
          </p>
        )}
      </div>

      {/* research actions */}
      <div className="flex gap-1.5">
        <div className="relative flex-1">
          <IconSearch
            width={14}
            height={14}
            className="absolute left-2.5 top-1/2 -translate-y-1/2 text-faint"
          />
          <input
            value={terms}
            onChange={(e) => setTerms(e.target.value)}
            placeholder="Search visuals…"
            onKeyDown={(e) => {
              if (e.key === "Enter" && activeSceneId)
                researchScene(activeSceneId, terms || undefined);
            }}
            className="input w-full pl-8 h-9"
          />
        </div>
        <Button
          size="sm"
          loading={isBusy("research")}
          onClick={() => activeSceneId && researchScene(activeSceneId, terms || undefined)}
          title="Search visuals for this scene"
        >
          <IconSearch width={13} height={13} /> Search
        </Button>
      </div>

      <div className="flex gap-1.5">
        <Button
          variant="secondary"
          size="sm"
          className="flex-1"
          loading={isBusy("generate")}
          onClick={() => activeSceneId && generateScene(activeSceneId)}
          title="Generate an image with the configured backend"
        >
          <IconSpark width={13} height={13} /> Generate
        </Button>
        <label
          className={`flex-1 h-9 px-3 inline-flex items-center justify-center gap-1.5 rounded-lg text-sm font-medium
            bg-surface2 text-text border border-edge hover:border-edge2 cursor-pointer
            ${uploading ? "opacity-50" : ""}`}
        >
          <IconUpload width={13} height={13} /> Upload
          <input
            type="file"
            accept="image/*"
            className="hidden"
            disabled={uploading}
            onChange={async (e) => {
              const f = e.target.files?.[0];
              if (!f || !activeSceneId) return;
              setUploading(true);
              try {
                await uploadScene(activeSceneId, f);
              } finally {
                setUploading(false);
              }
            }}
          />
        </label>
      </div>

      {/* candidate grid */}
      <div className="label">
        {scene.candidates.length
          ? `${scene.candidates.length} options — AI proposed, you approve`
          : "No candidates yet — search or generate above"}
      </div>
      {scene.candidates.length > 0 && (
        <div className="grid grid-cols-2 gap-2">
          {scene.candidates.map((c) => (
            <CandidateCard
              key={c.id}
              project={project}
              candidate={c}
              selected={c.id === scene.selected}
              onSelect={() => selectCandidate(scene.id, c.id)}
            />
          ))}
        </div>
      )}

      {scene.candidates.length > 0 && (
        <Button
          variant="ghost"
          size="sm"
          className="w-full"
          onClick={() => skipScene(scene.id)}
          disabled={isBusy("skip")}
        >
          <IconSkip width={13} height={13} /> Skip this scene
        </Button>
      )}
    </div>
  );
}

/* ------------------------------ AUDIO ------------------------------ */
function AudioTab({ scene }: { scene: Scene }) {
  const { project, editScene, narrate, narrateScene, setVoice, isBusy } = useWorkspace();
  const audioUrl = scene.audio_path
    ? `/api/projects/${project.id}/file/${scene.audio_path}`
    : null;
  const [playing, setPlaying] = useState(false);

  return (
    <div className="space-y-3 animate-fade-in">
      <div className="flex items-center justify-between">
        <div className="label">Narration</div>
        {project.scenes.some((s) => !s.audio_path) && (
          <Button
            variant="ghost"
            size="sm"
            loading={isBusy("narrate")}
            onClick={() => narrate()}
            title="Generate voiceover for all scenes at once"
          >
            <IconMic width={13} height={13} /> Generate all
          </Button>
        )}
      </div>

      <Field label="Voice">
        <SelectInput
          value={project.tts_voice ?? ""}
          options={project.voices ?? []}
          onChange={(v) => setVoice(v)}
          placeholder="Default"
        />
      </Field>

      <div className="panel-2 p-3">
        {audioUrl ? (
          <>
            <div className="label mb-2">Narration</div>
            <Waveform src={audioUrl} duration={scene.duration} height={44} />
            <div className="flex items-center gap-2 mt-3">
              <button
                onClick={() => {
                  const au = new Audio(audioUrl);
                  au.play();
                  setPlaying(true);
                  au.onended = () => setPlaying(false);
                }}
                disabled={playing}
                className="grid place-items-center h-8 w-8 rounded-lg bg-primary text-white hover:bg-primary2 disabled:opacity-40"
                title="Play narration"
              >
                {playing ? <IconPause width={14} height={14} /> : <IconPlay width={14} height={14} />}
              </button>
              <Button
                variant="secondary"
                size="sm"
                loading={isBusy("narrate")}
                onClick={() => narrateScene(scene.id)}
                title="Regenerate voiceover for this scene"
              >
                <IconMic width={13} height={13} /> Re-narrate
              </Button>
            </div>
          </>
        ) : (
          <div className="text-center text-faint text-xs py-4 space-y-3">
            <div>No narration yet for this scene.</div>
            <Button
              variant="secondary"
              size="sm"
              loading={isBusy("narrate")}
              onClick={() => narrateScene(scene.id)}
              title="Generate voiceover for this scene"
            >
              <IconMic width={13} height={13} /> Narrate this scene
            </Button>
          </div>
        )}
      </div>

      {audioUrl && (
        <label className="label flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            defaultChecked={scene.status === "approved"}
            onChange={(e) =>
              editScene(scene.id, { status: e.target.checked ? "approved" : "needs_review" })
            }
          />
          Mark narration approved
        </label>
      )}
    </div>
  );
}

/* ------------------------------ MOTION ----------------------------- */
function MotionTab({ scene }: { scene: Scene }) {
  const { editScene } = useWorkspace();
  return (
    <div className="space-y-3 animate-fade-in">
      <Field label="Camera movement (Ken Burns)">
        <SelectInput
          value={scene.motion ?? "in"}
          options={["in", "out", "left", "right"]}
          onChange={(v) => editScene(scene.id, { motion: v })}
        />
      </Field>
      <Field label="Transition to next scene">
        <SelectInput
          value={scene.transition ?? "cut"}
          options={["cut", "fade", "dissolve"]}
          onChange={(v) => editScene(scene.id, { transition: v })}
        />
      </Field>
      <p className="text-2xs text-muted leading-relaxed">
        Motion is applied at render time. Each scene can drift (left/right) or
        zoom (in/out). Transitions play between this scene and the next.
      </p>
    </div>
  );
}
