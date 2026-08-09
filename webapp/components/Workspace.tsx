"use client";

import { createContext, useCallback, useContext, useMemo, useState, ReactNode } from "react";
import { api, useJob } from "@/lib/api";
import { Project, Scene } from "@/lib/types";

type ActionKey =
  | "script"
  | "storyboard"
  | "research"
  | "select"
  | "skip"
  | "edit"
  | "replan"
  | "generate"
  | "upload"
  | "narrate"
  | "captions"
  | "render"
  | "reorder"
  | "approve"
  | "save"
  | "refresh";

interface Ctx {
  project: Project;
  setProject: (p: Project | ((p: Project) => Project)) => void;
  activeSceneId: string | null;
  setActiveSceneId: (id: string | null) => void;
  activeScene: Scene | null;
  busy: Set<ActionKey>;
  isBusy: (k: ActionKey) => boolean;
  busyScenes: Set<string>;
  isSceneBusy: (sid: string) => boolean;
  notify: (msg: string, tone?: "ok" | "err") => void;
  toast: { msg: string; tone: "ok" | "err" } | null;
  // template job polling for the render/export workspace
  job: { id: string | null; label: string };
  startJob: (id: string | null, label: string) => void;
  refresh: () => Promise<void>;
  saveScript: (script: string, generate: boolean) => Promise<void>;
  buildStoryboard: () => Promise<void>;
  researchScene: (sid: string, terms?: string) => Promise<void>;
  researchAll: () => Promise<void>;
  selectCandidate: (sid: string, cid: string) => Promise<void>;
  skipScene: (sid: string) => Promise<void>;
  editScene: (sid: string, body: Record<string, unknown>) => Promise<void>;
  replan: (sid: string, prompt?: string) => Promise<void>;
  generateScene: (sid: string) => Promise<void>;
  uploadScene: (sid: string, file: File) => Promise<void>;
  narrate: () => Promise<void>;
  narrateScene: (sid: string) => Promise<void>;
  setVoice: (v: string) => Promise<void>;
  captions: () => Promise<void>;
  render: (final: boolean, captions: boolean, music: string) => Promise<void>;
  reorder: (order: string[]) => Promise<void>;
  approve: (stage: string) => Promise<void>;
  reopen: (stage: string) => Promise<void>;
}

const WorkspaceCtx = createContext<Ctx | null>(null);

export function useWorkspace(): Ctx {
  const c = useContext(WorkspaceCtx);
  if (!c) throw new Error("useWorkspace must be used within WorkspaceProvider");
  return c;
}

/** Resolve whatever an api call returns: a Project, or a {job} to poll. */
async function resolve(thing: Promise<Project | { job: string }>): Promise<void> {
  const res = await thing;
  if ("job" in res && res.job) {
    await new Promise<void>((resolvePoll) => {
      const timer = setInterval(async () => {
        try {
          const { jobs } = await api.jobs();
          const j = jobs.find((x) => x.id === res.job);
          if (j && j.state !== "running") {
            clearInterval(timer);
            resolvePoll();
          }
        } catch {
          /* keep polling */
        }
      }, 1000);
    });
  }
}

export function WorkspaceProvider({
  initial,
  children,
}: {
  initial: Project;
  children: ReactNode;
}) {
  const [project, setProject] = useState<Project>(initial);
  const [activeSceneId, setActiveSceneId] = useState<string | null>(
    initial.scenes[0]?.id ?? null
  );
  const [busy, setBusy] = useState<Set<ActionKey>>(new Set());
  const [busyScenes, setBusyScenes] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState<{ msg: string; tone: "ok" | "err" } | null>(null);
  const [job, setJob] = useState<{ id: string | null; label: string }>({
    id: null,
    label: "",
  });

  const activeScene = useMemo(
    () => project.scenes.find((s) => s.id === activeSceneId) ?? null,
    [project.scenes, activeSceneId]
  );

  const notify = useCallback((msg: string, tone: "ok" | "err" = "ok") => {
    setToast({ msg, tone });
    setTimeout(() => setToast(null), 2600);
  }, []);

  const run = useCallback(
    async (key: ActionKey, fn: () => Promise<void>) => {
      setBusy((b) => new Set(b).add(key));
      try {
        await fn();
      } catch (e) {
        notify(`Error: ${String(e)}`, "err");
        throw e;
      } finally {
        setBusy((b) => {
          const n = new Set(b);
          n.delete(key);
          return n;
        });
      }
    },
    [notify]
  );

  const refresh = useCallback(async () => {
    const res = await api.getProject(initial.id);
    setProject(res);
  }, [initial.id]);

  const saveScript = useCallback(
    async (script: string, generate: boolean) => {
      await run("script", async () => {
        const res = await api.script(initial.id, generate ? { script: "" } : { script });
        setProject(res);
        notify(generate ? "Script generated" : "Script saved", "ok");
      });
    },
    [initial.id, run, notify]
  );

  const buildStoryboard = useCallback(
    async () => {
      await run("storyboard", async () => {
        const res = await api.storyboard(initial.id, {});
        setProject(res);
        if ((res.scenes?.length ?? 0) > 0) setActiveSceneId(res.scenes[0].id);
        notify("Storyboard built", "ok");
      });
    },
    [initial.id, run, notify]
  );

  const researchScene = useCallback(
    async (sid: string, terms?: string) => {
      await run("research", async () => {
        await resolve(api.research(initial.id, { scene: sid, query: terms }));
        setProject(await api.getProject(initial.id));
        notify("Visuals researched", "ok");
      });
    },
    [initial.id, run, notify]
  );

  const researchAll = useCallback(
    async () => {
      await run("research", async () => {
        await resolve(api.research(initial.id, {}));
        setProject(await api.getProject(initial.id));
        notify("Visuals researched for all scenes", "ok");
      });
    },
    [initial.id, run, notify]
  );

  const selectCandidate = useCallback(
    async (sid: string, cid: string) => {
      await run("select", async () => {
        const res = await api.select(initial.id, sid, cid);
        setProject(res);
        notify("Visual selected", "ok");
      });
    },
    [initial.id, run, notify]
  );

  const skipScene = useCallback(
    async (sid: string) => {
      await run("skip", async () => {
        const res = await api.skip(initial.id, sid);
        setProject(res);
        notify("Scene skipped", "ok");
      });
    },
    [initial.id, run, notify]
  );

  const editScene = useCallback(
    async (sid: string, body: Record<string, unknown>) => {
      await run("edit", async () => {
        const res = await api.editScene(initial.id, sid, body);
        setProject(res);
      });
    },
    [initial.id, run]
  );

  const replan = useCallback(
    async (sid: string, prompt?: string) => {
      await run("replan", async () => {
        const res = await api.replan(initial.id, sid, prompt);
        setProject(res);
        notify("Scene re-planned", "ok");
      });
    },
    [initial.id, run, notify]
  );

  const generateScene = useCallback(
    async (sid: string) => {
      await run("generate", async () => {
        await resolve(api.generate(initial.id, sid));
        setProject(await api.getProject(initial.id));
        notify("Image generated", "ok");
      });
    },
    [initial.id, run, notify]
  );

  const uploadScene = useCallback(
    async (sid: string, file: File) => {
      await run("upload", async () => {
        const res = (await api.upload(initial.id, sid, file)) as Project;
        setProject(res);
        notify("Image uploaded", "ok");
      });
    },
    [initial.id, run, notify]
  );

  const narrate = useCallback(
    async () => {
      await run("narrate", async () => {
        await resolve(api.narrate(initial.id, {}));
        setProject(await api.getProject(initial.id));
        notify("Narration generated", "ok");
      });
    },
    [initial.id, run, notify]
  );

  const narrateScene = useCallback(
    async (sid: string) => {
      setBusyScenes((b) => new Set(b).add(sid));
      try {
        await resolve(api.narrate(initial.id, { scene: sid }));
        setProject(await api.getProject(initial.id));
        notify("Narration generated for scene", "ok");
      } catch (e) {
        notify(`Error: ${String(e)}`, "err");
        throw e;
      } finally {
        setBusyScenes((b) => {
          const n = new Set(b);
          n.delete(sid);
          return n;
        });
      }
    },
    [initial.id, run, notify]
  );

  const setVoice = useCallback(
    async (v: string) => {
      await run("edit", async () => {
        const res = await api.updateProject(initial.id, { voice: v });
        setProject(res);
      });
    },
    [initial.id, run]
  );

  const captions = useCallback(
    async () => {
      await run("captions", async () => {
        const res = await api.captions(initial.id);
        setProject(res);
        notify("Captions built", "ok");
      });
    },
    [initial.id, run, notify]
  );

  const render = useCallback(
    async (final: boolean, captions: boolean, music: string) => {
      await run("render", async () => {
        setJob({ id: null, label: final ? "Rendering final video" : "Rendering draft" });
        await resolve(api.render(initial.id, { final, captions, music }));
        setProject(await api.getProject(initial.id));
        notify(final ? "Render complete" : "Draft complete", "ok");
      });
    },
    [initial.id, run, notify]
  );

  const reorder = useCallback(
    async (order: string[]) => {
      await run("reorder", async () => {
        const res = await api.reorder(initial.id, order);
        setProject(res);
      });
    },
    [initial.id, run]
  );

  const approve = useCallback(
    async (stage: string) => {
      await run("approve", async () => {
        const res = await api.approve(initial.id, stage);
        setProject(res);
        notify(`${stage} approved`, "ok");
      });
    },
    [initial.id, run, notify]
  );

  const reopen = useCallback(
    async (stage: string) => {
      await run("approve", async () => {
        const res = await api.reopen(initial.id, stage);
        setProject(res);
      });
    },
    [initial.id, run]
  );

  const isBusy = useCallback((k: ActionKey) => busy.has(k), [busy]);

  const isSceneBusy = useCallback((sid: string) => busyScenes.has(sid), [busyScenes]);

  const value: Ctx = {
    project,
    setProject,
    activeSceneId,
    setActiveSceneId,
    activeScene,
    busy,
    isBusy,
    busyScenes,
    isSceneBusy,
    notify,
    toast,
    job,
    startJob: (id, label) => setJob({ id, label }),
    refresh,
    saveScript,
    buildStoryboard,
    researchScene,
    researchAll,
    selectCandidate,
    skipScene,
    editScene,
    replan,
    generateScene,
    uploadScene,
    narrate,
    narrateScene,
    setVoice,
    captions,
    render,
    reorder,
    approve,
    reopen,
  };

  return (
    <WorkspaceCtx.Provider value={value}>
      {children}
      {toast && (
        <div
          className={`fixed bottom-5 left-1/2 -translate-x-1/2 z-[60] px-4 py-2 rounded-lg text-sm
            shadow-pop animate-slide-up border ${
              toast.tone === "ok"
                ? "bg-success/15 border-success/40 text-success"
                : "bg-danger/15 border-danger/40 text-danger"
            }`}
        >
          {toast.msg}
        </div>
      )}
    </WorkspaceCtx.Provider>
  );
}
