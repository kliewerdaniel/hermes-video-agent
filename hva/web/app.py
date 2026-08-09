"""Local review UI — FastAPI + one static page.

The whole point of this app is the human gate, so the server is deliberately
thin: every route maps to a stage function or a manifest edit, and the manifest
on disk stays the source of truth. No database, no sessions, no auth. It runs on
localhost for one operator.

Notes learned the hard way and encoded here:
* A route whose body can legitimately be ``{}`` must declare every field
  Optional, or FastAPI 422s and the button looks dead.
* Long stages (research, render) block for minutes. They run in a worker thread
  and the UI polls ``/api/jobs`` rather than holding an HTTP connection open.
* SystemExit from a stage is a user-facing precondition failure -> HTTP 400,
  not an opaque 500.
"""
from __future__ import annotations

import threading
import traceback
import uuid
import json
import urllib.request
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import config
from ..manifest import Candidate, Project, STAGES
from ..providers import (image as image_provider, inference,
                          inference_config, llm, tts)
from ..stages import (captions as captions_stage, narration as narration_stage,
                      render as render_stage, research as research_stage,
                      script as script_stage, storyboard as storyboard_stage)

app = FastAPI(title="Hermes Video Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
STATIC = Path(__file__).parent / "static"

# --- background jobs ------------------------------------------------------
JOBS: dict[str, dict] = {}


def _run_job(name: str, fn, *args, **kwargs) -> str:
    jid = uuid.uuid4().hex[:8]
    JOBS[jid] = {"id": jid, "name": name, "state": "running", "error": ""}

    def _work():
        try:
            fn(*args, **kwargs)
            JOBS[jid]["state"] = "done"
        except SystemExit as e:
            JOBS[jid].update(state="error", error=str(e))
        except Exception as e:
            JOBS[jid].update(state="error", error=f"{e}\n{traceback.format_exc()[-800:]}")

    threading.Thread(target=_work, daemon=True).start()
    return jid


@app.get("/api/jobs")
def jobs():
    return {"jobs": list(JOBS.values())[-12:]}


# --- models ---------------------------------------------------------------
class NewProject(BaseModel):
    idea: str
    title: str | None = ""
    aspect: str | None = "16:9"
    duration: int | None = 60


# Whitelisted top-level metadata fields a human may edit directly. Stages own
# script/scenes/approvals/artifacts, so those are deliberately excluded here.
class UpdateProject(BaseModel):
    title: str | None = None
    idea: str | None = None
    aspect: str | None = None
    target_duration: int | None = None
    voice: str | None = None
    tts_provider: str | None = None


class ScriptBody(BaseModel):
    script: str | None = None
    direction: str | None = None


class StoryboardBody(BaseModel):
    scenes: int | None = 0
    use_llm: bool | None = True


class ResearchBody(BaseModel):
    scene: str | None = None
    query: str | None = None
    limit: int | None = 0
    commercial_only: bool | None = True


class SceneEdit(BaseModel):
    narration: str | None = None
    visual_concept: str | None = None
    image_prompt: str | None = None
    search_terms: list[str] | None = None
    motion: str | None = None
    transition: str | None = None
    duration: float | None = None
    status: str | None = None
    notes: str | None = None


class GenerateBody(BaseModel):
    prompt: str | None = None


class NarrateBody(BaseModel):
    provider: str | None = None
    voice: str | None = None
    rate: int | None = 0
    scene: str | None = None


class RenderBody(BaseModel):
    final: bool | None = False
    captions: bool | None = True
    music: str | None = ""


# --- helpers --------------------------------------------------------------
def _proj(pid: str) -> Project:
    try:
        return Project.load(pid)
    except SystemExit as e:
        raise HTTPException(404, str(e)) from e


def _guard(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except HTTPException:
        raise
    except SystemExit as e:
        raise HTTPException(400, str(e)) from e
    except PermissionError as e:
        raise HTTPException(409, str(e)) from e
    except llm.LLMUnavailable as e:
        # The model is down, too slow, or returned something we couldn't
        # parse. Surface it as a clean 502 so the UI can show a message
        # instead of the whole request crashing.
        raise HTTPException(502, f"AI generation failed: {e}") from e
    except inference.InferenceError as e:
        # Normalized provider error -> map category to an HTTP status the UI
        # can render meaningfully. Keys are never in `e.message`.
        code = {
            "auth": 401, "connection": 502, "timeout": 504, "model": 404,
            "rate_limit": 429, "context_length": 413, "provider": 502,
            "malformed": 502, "config": 400,
        }.get(e.category, 502)
        raise HTTPException(code, f"{e.category}: {e.message}") from e
    except Exception as e:
        # Anything else (KeyError/JSONDecodeError from a flaky model reply,
        # missing file, etc.) must NOT escape as an opaque 500 — that is what
        # produced the "Unhandled Runtime Error" white screen. Log it and
        # return a 500 with the message so the UI can surface it cleanly.
        print(f"[guard] {fn.__name__} failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        raise HTTPException(500, f"{type(e).__name__}: {e}") from e


def _serialize(p: Project) -> dict:
    d = p.to_dict()
    d["total_duration"] = p.total_duration
    d["size"] = list(p.size)
    d["has_draft"] = bool(p.draft and (p.dir / p.draft).exists())
    d["has_final"] = bool(p.final and (p.dir / p.final).exists())
    d["stages"] = STAGES
    # TTS/voice metadata so the UI can render the voice picker without a
    # second /api/env round-trip. `voices` is not persisted on the manifest.
    provider = p.tts_provider or config.TTS_PROVIDER
    d["tts_provider"] = provider
    d["tts_voice"] = p.voice or config.TTS_VOICE
    d["voices"] = tts.list_voices(provider)
    return d


# --- routes ---------------------------------------------------------------
@app.get("/api/env")
def env():
    return {"llm": llm.available(), "llm_model": llm.model_name() if llm.available() else "",
            "image_provider": image_provider.resolve(),
            "comfy": image_provider.comfy_up(),
            "tts_provider": config.TTS_PROVIDER,
            "tts_voice": config.TTS_VOICE,
            "voices": tts.list_voices()[:60],
            "aspects": list(config.ASPECTS)}


# --- voice management (self-contained vox backend; no external TTS server) --
@app.get("/api/voices")
def list_voices():
    """Voices available to the active TTS provider for voice cloning."""
    out = []
    if config.TTS_PROVIDER == "vox":
        for f in sorted(config.VOX_VOICES_DIR.iterdir()):
            if f.suffix.lower() in (".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac"):
                out.append({"name": f.stem, "url": f"/api/voices/{f.name}"})
    elif config.TTS_PROVIDER == "qwen":
        try:
            base = config.QWEN_TTS_URL.rstrip("/")
            with urllib.request.urlopen(base + "/api/voices", timeout=10) as r:
                data = json.loads(r.read().decode())
            out = [{"name": v["name"], "url": base + v.get("url", "")}
                   for v in data.get("voices", [])]
        except Exception:
            pass
    return {"voices": out}


@app.post("/api/voices")
async def upload_voice(
    name: str = Form(""),
    file: UploadFile = File(...),
):
    if config.TTS_PROVIDER != "vox":
        raise HTTPException(400, "voice upload requires the 'vox' TTS provider")
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty upload")
    fname = file.filename or f"{name}.wav"
    try:
        registered = tts._vox_upload_voice(name, data, fname)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"name": registered,
            "url": f"/api/voices/{registered}{Path(fname).suffix.lower()}"}


@app.delete("/api/voices/{name}")
def delete_voice(name: str):
    if config.TTS_PROVIDER != "vox":
        raise HTTPException(400, "voice deletion requires the 'vox' TTS provider")
    if not tts._vox_delete_voice(name):
        raise HTTPException(404, f"voice {name!r} not found")
    return {"ok": True}


@app.get("/api/voices/{filename}")
def serve_voice(filename: str):
    if config.TTS_PROVIDER != "vox":
        raise HTTPException(404, "voice serving requires the 'vox' TTS provider")
    path = config.VOX_VOICES_DIR / Path(filename).name
    if not path.exists():
        raise HTTPException(404, "voice sample not found")
    mime = "audio/mpeg" if path.suffix.lower() == ".mp3" else "audio/wav"
    return FileResponse(path, media_type=mime)


# --- inference provider config --------------------------------------------
def _inf_status(category: str) -> int:
    return {
        "auth": 401, "connection": 502, "timeout": 504, "model": 404,
        "rate_limit": 429, "context_length": 413, "provider": 502,
        "malformed": 502, "config": 400,
    }.get(category, 502)


class InferenceConfigBody(BaseModel):
    provider: str
    settings: dict = {}


@app.get("/api/inference")
def get_inference():
    """Returns the public (key-redacted) view of the inference config."""
    return inference_config.InferenceConfig.load().public_view()


@app.put("/api/inference")
def put_inference(body: InferenceConfigBody):
    cfg = inference_config.InferenceConfig.load()
    try:
        cfg.update(body.provider, body.settings or {})
    except inference.InferenceError as e:
        raise HTTPException(400, f"{e.category}: {e.message}") from e
    cfg.save()
    return cfg.public_view()


@app.get("/api/inference/models")
def inference_models(provider: str | None = None, refresh: bool = False):
    """List models for a provider. Uses `provider` from the query, else the
    currently-selected provider. Keys are required server-side and taken from
    the persisted (not client-supplied) config, so secrets never arrive in the
    request body."""
    cfg = inference_config.InferenceConfig.load()
    pid = provider or cfg.provider
    try:
        p = cfg.active_provider() if pid == cfg.provider else \
            inference.make_provider(pid, **cfg.provider_settings(pid))
        models = p.list_models()
    except inference.InferenceError as e:
        raise HTTPException(_inf_status(e.category), f"{e.category}: {e.message}") from e
    return {"provider": pid, "models": [m.to_dict() for m in models]}


class InferenceModelsBody(BaseModel):
    # Optional overrides supplied by the UI (e.g. a freshly-typed key or URL
    # that has not been saved yet). Used transiently to fetch the list.
    provider: str | None = None
    settings: dict = {}


@app.post("/api/inference/models")
def inference_models_post(body: InferenceModelsBody | None = None):
    body = body or InferenceModelsBody()
    cfg = inference_config.InferenceConfig.load()
    pid = body.provider or cfg.provider
    s = dict(cfg.provider_settings(pid))
    s.update(body.settings or {})
    try:
        p = inference.make_provider(pid, **s)
        models = p.list_models()
    except inference.InferenceError as e:
        raise HTTPException(_inf_status(e.category), f"{e.category}: {e.message}") from e
    return {"provider": pid, "models": [m.to_dict() for m in models]}


class InferenceTestBody(BaseModel):
    # Optional overrides supplied by the UI *for this test only*. If a key is
    # present it is used transiently and never persisted.
    provider: str | None = None
    settings: dict = {}


@app.post("/api/inference/test")
def test_inference(body: InferenceTestBody | None = None):
    body = body or InferenceTestBody()
    cfg = inference_config.InferenceConfig.load()
    pid = body.provider or cfg.provider
    s = dict(cfg.provider_settings(pid))
    s.update(body.settings or {})
    try:
        p = inference.make_provider(pid, **s)
        result = p.test_connection()
    except inference.InferenceError as e:
        return {"ok": False, "provider": pid,
                "message": e.message, "category": e.category}
    return {"ok": result.ok, "provider": result.provider,
            "model": result.model, "message": result.message,
            "latency_ms": result.latency_ms,
            "category": None if result.ok else "provider"}



@app.get("/api/projects")
def list_projects():
    return {"projects": [
        {
            "id": p.id,
            "title": p.title,
            "idea": p.idea,
            "stage": p.stage,
            "scenes": len(p.scenes),
            "duration": p.total_duration,
            "final": p.final if (p.final and (p.dir / p.final).exists()) else None,
            "has_final": bool(p.final and (p.dir / p.final).exists()),
        }
        for p in Project.list_all()
    ]}


@app.post("/api/projects")
def create_project(body: NewProject):
    p = Project.create(body.idea, title=body.title or "",
                       aspect=body.aspect or "16:9", duration=body.duration or 60)
    return _serialize(p)


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    return _serialize(_proj(pid))


@app.patch("/api/projects/{pid}")
def update_project(pid: str, body: UpdateProject):
    """Edit top-level metadata (title, idea, aspect, duration, voice)."""
    p = _proj(pid)
    changed = []
    if body.title is not None:
        p.title = body.title
        changed.append("title")
    if body.idea is not None:
        p.idea = body.idea
        changed.append("idea")
    if body.aspect is not None:
        if body.aspect not in config.ASPECTS:
            raise HTTPException(400, f"unknown aspect {body.aspect!r}")
        p.aspect = body.aspect
        changed.append("aspect")
    if body.target_duration is not None:
        if body.target_duration <= 0:
            raise HTTPException(400, "duration must be positive")
        p.target_duration = body.target_duration
        changed.append("duration")
    if body.voice is not None:
        p.voice = body.voice
        changed.append("voice")
    if body.tts_provider is not None:
        p.tts_provider = body.tts_provider
        changed.append("tts_provider")
    p.note(f"metadata edited: {', '.join(changed) or 'nothing'}")
    p.save()
    return _serialize(p)


@app.delete("/api/projects/{pid}")
def delete_project(pid: str):
    """Remove the project directory (manifest + all artifacts) from disk."""
    p = _proj(pid)
    import shutil

    shutil.rmtree(p.dir, ignore_errors=True)
    return {"id": pid, "deleted": True}


@app.post("/api/projects/{pid}/script")
def do_script(pid: str, body: ScriptBody | None = None):
    body = body or ScriptBody()
    p = _guard(script_stage.generate, pid, script=body.script or "",
               extra_direction=body.direction or "")
    return _serialize(p)


@app.post("/api/projects/{pid}/storyboard")
def do_storyboard(pid: str, body: StoryboardBody | None = None):
    body = body or StoryboardBody()
    p = _guard(storyboard_stage.build, pid, scene_count=body.scenes or 0,
               use_llm=bool(body.use_llm))
    return _serialize(p)


@app.post("/api/projects/{pid}/research")
def do_research(pid: str, body: ResearchBody | None = None):
    body = body or ResearchBody()
    if body.scene:
        proj = _proj(pid)
        _guard(research_scene_sync, proj, body)
        return _serialize(Project.load(pid))
    jid = _run_job(f"research {pid}", research_stage.run, pid,
                   limit=body.limit or 0,
                   commercial_only=bool(body.commercial_only))
    return {"job": jid}


def research_scene_sync(proj: Project, body: ResearchBody):
    research_stage.research_scene(proj, body.scene, limit=body.limit or 0,
                                  query_override=body.query or "",
                                  commercial_only=bool(body.commercial_only))


@app.post("/api/projects/{pid}/scenes/{sid}/select/{cand}")
def select(pid: str, sid: str, cand: str):
    p = _proj(pid)
    sc = p.scene(sid)
    if cand not in [c.id for c in sc.candidates]:
        raise HTTPException(404, f"no candidate {cand}")
    sc.selected = cand
    sc.status = "approved"
    p.note(f"{sid}: human selected {cand}")
    p.save()
    return _serialize(p)


@app.post("/api/projects/{pid}/scenes/{sid}/skip")
def skip(pid: str, sid: str):
    p = _proj(pid)
    p.scene(sid).status = "skipped"
    p.note(f"{sid}: skipped by human")
    p.save()
    return _serialize(p)


@app.patch("/api/projects/{pid}/scenes/{sid}")
def edit_scene(pid: str, sid: str, body: SceneEdit):
    p = _proj(pid)
    sc = p.scene(sid)
    for f in ("narration", "visual_concept", "image_prompt", "motion",
              "transition", "status", "notes"):
        v = getattr(body, f)
        if v is not None:
            setattr(sc, f, v)
    if body.search_terms is not None:
        sc.search_terms = body.search_terms
    if body.duration is not None:
        sc.duration = max(0.3, float(body.duration))
    p.note(f"{sid}: edited by human")
    p.save()
    return _serialize(p)


class ReorderBody(BaseModel):
    order: list[str] | None = None  # ordered scene ids


@app.post("/api/projects/{pid}/reorder")
def reorder_scenes(pid: str, body: ReorderBody | None = None):
    """Reorder scenes by an explicit list of scene ids (drag & drop)."""
    p = _proj(pid)
    if not body or not body.order:
        raise HTTPException(400, "order list required")
    by_id = {s.id: s for s in p.scenes}
    new = []
    for sid in body.order:
        if sid not in by_id:
            raise HTTPException(400, f"unknown scene id {sid}")
        new.append(by_id[sid])
    if len(new) != len(p.scenes):
        raise HTTPException(400, "order must contain every scene id exactly once")
    p.scenes = new
    p.note("scenes reordered by human")
    p.save()
    return _serialize(p)


@app.post("/api/projects/{pid}/scenes/{sid}/replan")
def replan(pid: str, sid: str, body: GenerateBody | None = None):
    body = body or GenerateBody()
    p = _guard(storyboard_stage.regenerate_scene, pid, sid, body.prompt or "")
    return _serialize(p)


@app.post("/api/projects/{pid}/scenes/{sid}/generate")
def generate_image(pid: str, sid: str, body: GenerateBody | None = None):
    body = body or GenerateBody()
    p = _proj(pid)
    sc = p.scene(sid)
    prompt = (body.prompt or sc.image_prompt or sc.visual_concept
              or sc.narration).strip()
    n = len([c for c in sc.candidates if c.provider in ("comfyui", "placeholder")])
    dest = p.assets_dir / sc.id / f"generated_{n:02d}.png"

    def _work():
        image_provider.generate(prompt, dest, size=p.size)
        proj = Project.load(pid)
        s = proj.scene(sid)
        cid = f"gen{n:02d}"
        s.candidates.append(Candidate(
            id=cid, kind="generated",
            local_path=str(dest.relative_to(proj.dir)),
            thumb_path=str(dest.relative_to(proj.dir)),
            provider=image_provider.resolve(), license="generated locally",
            title=prompt[:100], reason="generated on request"))
        s.selected = cid
        s.image_prompt = prompt
        proj.note(f"{sid}: generated image via {image_provider.resolve()}")
        proj.save()

    return {"job": _run_job(f"generate {sid}", _work)}


@app.post("/api/projects/{pid}/scenes/{sid}/upload")
async def upload(pid: str, sid: str, file: UploadFile = File(...)):
    p = _proj(pid)
    sc = p.scene(sid)
    ext = Path(file.filename or "upload.png").suffix or ".png"
    n = len([c for c in sc.candidates if c.provider == "upload"])
    dest = p.assets_dir / sid / f"upload_{n:02d}{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(await file.read())
    cid = f"up{n:02d}"
    sc.candidates.append(Candidate(
        id=cid, kind="image", local_path=str(dest.relative_to(p.dir)),
        thumb_path=str(dest.relative_to(p.dir)), provider="upload",
        license="supplied by operator", title=file.filename or "",
        reason="uploaded by human"))
    sc.selected = cid
    sc.status = "approved"
    p.note(f"{sid}: human uploaded {file.filename}")
    p.save()
    return _serialize(p)


@app.put("/api/projects/{pid}/script")
def put_script(pid: str, body: ScriptBody):
    if body.script is None:
        raise HTTPException(400, "script field required")
    return _serialize(_guard(script_stage.set_script, pid, body.script))


@app.post("/api/projects/{pid}/narrate")
def do_narrate(pid: str, body: NarrateBody | None = None):
    body = body or NarrateBody()
    jid = _run_job(f"narrate {pid}", narration_stage.run, pid,
                   provider=body.provider or "", voice=body.voice or "",
                   rate=body.rate or 0,
                   only=[body.scene] if body.scene else None)
    return {"job": jid}


@app.post("/api/projects/{pid}/captions")
def do_captions(pid: str):
    return _serialize(_guard(captions_stage.run, pid))


@app.post("/api/projects/{pid}/render")
def do_render(pid: str, body: RenderBody | None = None):
    body = body or RenderBody()

    def _work():
        captions_stage.run(pid)
        render_stage.build(pid, draft=not body.final,
                           burn_captions=bool(body.captions),
                           music=body.music or "")

    return {"job": _run_job(f"render {pid}", _work)}


@app.post("/api/projects/{pid}/approve/{stage}")
def approve(pid: str, stage: str):
    p = _proj(pid)
    if stage not in STAGES:
        raise HTTPException(400, f"unknown stage {stage}")
    p.approve(stage)
    return _serialize(p)


@app.post("/api/projects/{pid}/reopen/{stage}")
def reopen(pid: str, stage: str):
    """Going backwards is a first-class operation, not an error path."""
    p = _proj(pid)
    idx = STAGES.index(stage)
    for s in STAGES[idx:]:
        p.approvals.pop(s, None)
    p.stage = STAGES[max(0, idx - 1)]
    p.note(f"reopened from stage {stage}")
    p.save()
    return _serialize(p)


@app.get("/api/projects/{pid}/file/{path:path}")
def project_file(pid: str, path: str):
    p = _proj(pid)
    target = (p.dir / path).resolve()
    if not str(target).startswith(str(p.dir.resolve())) or not target.exists():
        raise HTTPException(404, "not found")
    return FileResponse(target)


@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC / "index.html").read_text()


app.mount("/static", StaticFiles(directory=STATIC), name="static")
