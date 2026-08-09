"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { Project } from "@/lib/types";
import { WorkspaceProvider, useWorkspace } from "@/components/Workspace";
import { ProjectHeader } from "@/components/ProjectHeader";
import { StepRail, StepId, stepDone } from "@/components/StepRail";
import { ScriptEditor } from "@/components/ScriptEditor";
import { Storyboard } from "@/components/Storyboard";
import { VisualsStep } from "@/components/VisualsStep";
import { NarrationStep } from "@/components/NarrationStep";
import { ExportPanel } from "@/components/ExportPanel";
import { ProjectEditDialog } from "@/components/ProjectEditDialog";
import { InferenceSettings } from "@/components/InferenceSettings";
import { VisualStrip } from "@/components/VisualStrip";

export default function ProjectPage() {
  const params = useParams();
  const id = String(params.id);
  const [project, setProject] = useState<Project | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = () => {
    setErr(null);
    api.getProject(id).then(setProject).catch((e) => setErr(String(e)));
  };
  useEffect(load, [id]);

  if (err)
    return (
      <div className="grid place-items-center h-screen text-muted">
        <div className="text-center">
          <p className="mb-2">Could not load project.</p>
          <pre className="text-danger text-xs max-w-md mx-auto">{err}</pre>
          <button onClick={load} className="mt-3 px-3 py-1.5 rounded-lg bg-surface2 border border-edge text-sm">
            Retry
          </button>
        </div>
      </div>
    );

  if (!project)
    return (
      <div className="grid place-items-center h-screen">
        <span className="h-6 w-6 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
      </div>
    );

  return (
    <WorkspaceProvider initial={project}>
      <Studio key={project.id} />
    </WorkspaceProvider>
  );
}

function Studio() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [inferenceOpen, setInferenceOpen] = useState(false);
  const [step, setStep] = useState<StepId>("script");
  const { project, setProject } = useWorkspace();

  // Make each step lead to the next: auto-advance when a step completes.
  const advance = (id: StepId) => {
    setStep(id);
  };

  return (
    <div className="h-screen flex flex-col bg-ink text-text">
      <ProjectHeader
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenInference={() => setInferenceOpen(true)}
      />
      <div className="flex-1 flex min-h-0">
        <StepRail project={project} active={step} onJump={advance} />

        <main className="flex-1 min-w-0 flex flex-col">
          <div className="flex-1 overflow-y-auto">
            <div className="max-w-5xl mx-auto px-5 py-5">
              {step === "script" && <ScriptEditor onDone={() => advance("scenes")} />}
              {step === "scenes" && <Storyboard onDone={() => advance("visuals")} />}
              {step === "visuals" && <VisualsStep onDone={() => advance("narration")} />}
              {step === "narration" && <NarrationStep onDone={() => advance("export")} />}
              {step === "export" && <ExportPanel />}
            </div>
          </div>

          {/* bottom dock: visual strip for quick scene scrubbing */}
          <div className="shrink-0 border-t border-edge bg-panel/50">
            <VisualStrip />
          </div>
        </main>
      </div>

      {settingsOpen && (
        <ProjectEditDialog
          project={project}
          onClose={() => setSettingsOpen(false)}
          onSaved={(p) => setProject(p)}
        />
      )}

      {inferenceOpen && (
        <InferenceSettings
          open={inferenceOpen}
          onClose={() => setInferenceOpen(false)}
        />
      )}
    </div>
  );
}
