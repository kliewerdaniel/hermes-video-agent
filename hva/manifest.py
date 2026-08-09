"""The project manifest — the single source of truth for a video.

A video is structured data long before it is pixels. Every stage reads and
writes this file (`project.json`); nothing is passed between stages in memory.
That is what makes a scene individually regenerable and a human able to edit
any intermediate representation by hand.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from . import config

SCHEMA_VERSION = 1

# Stage gates the human must pass. `status` on the project records the furthest
# stage that has been APPROVED, so the agent knows where it is allowed to go.
STAGES = ["idea", "script", "scenes", "visuals", "narration", "draft", "final"]


def slugify(text: str, limit: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:limit].strip("-")) or "untitled"


@dataclass
class Candidate:
    """One researched or generated visual option for a scene."""
    id: str
    kind: str = "image"          # image | video | generated
    local_path: str = ""         # relative to project dir
    thumb_path: str = ""
    source_url: str = ""         # page the asset came from
    direct_url: str = ""         # the asset file itself
    title: str = ""
    creator: str = ""
    license: str = ""
    license_url: str = ""
    provider: str = ""           # openverse | wikimedia | comfyui | upload
    reason: str = ""             # why the agent proposed it
    width: int = 0
    height: int = 0

    def attribution(self) -> str:
        bits = [b for b in (self.title, self.creator, self.license) if b]
        return " — ".join(bits) + (f" ({self.source_url})" if self.source_url else "")


@dataclass
class Scene:
    id: str
    narration: str = ""
    visual_concept: str = ""      # plain-language description of the shot
    composition: str = ""         # wide / close-up / overhead …
    search_terms: list[str] = field(default_factory=list)
    image_prompt: str = ""        # for a generative backend
    motion: str = "in"            # in | out | left | right
    transition: str = "cut"       # cut | fade | dissolve (to the next scene)
    text_overlay: str = ""
    duration: float = 0.0         # seconds; measured from narration audio
    audio_path: str = ""          # relative, e.g. audio/scene_001.wav
    candidates: list[Candidate] = field(default_factory=list)
    selected: str | None = None   # Candidate.id
    status: str = "needs_review"  # needs_review | approved | skipped
    notes: str = ""

    @property
    def selected_candidate(self) -> Candidate | None:
        for c in self.candidates:
            if c.id == self.selected:
                return c
        return None

    @property
    def index(self) -> int:
        m = re.search(r"(\d+)$", self.id)
        return int(m.group(1)) if m else 0


@dataclass
class Project:
    id: str
    title: str = ""
    idea: str = ""
    premise: str = ""
    aspect: str = "16:9"
    target_duration: int = 60
    script: str = ""
    scenes: list[Scene] = field(default_factory=list)
    music: dict[str, Any] = field(default_factory=dict)
    voice: str = ""
    tts_provider: str = ""
    approvals: dict[str, bool] = field(default_factory=dict)
    stage: str = "idea"
    schema_version: int = SCHEMA_VERSION
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    draft: str = ""
    final: str = ""
    log: list[str] = field(default_factory=list)

    # ---------- paths ----------
    @property
    def dir(self) -> Path:
        return config.PROJECTS_DIR / self.id

    @property
    def path(self) -> Path:
        return self.dir / "project.json"

    @property
    def assets_dir(self) -> Path:
        return self.dir / "assets"

    @property
    def audio_dir(self) -> Path:
        return self.dir / "audio"

    @property
    def captions_dir(self) -> Path:
        return self.dir / "captions"

    @property
    def scenes_dir(self) -> Path:
        return self.dir / "scenes"

    def mkdirs(self) -> None:
        for d in (self.dir, self.assets_dir, self.audio_dir,
                  self.captions_dir, self.scenes_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ---------- derived ----------
    @property
    def size(self) -> tuple[int, int]:
        return config.ASPECTS.get(self.aspect, config.ASPECTS["16:9"])

    @property
    def total_duration(self) -> float:
        return round(sum(s.duration for s in self.scenes), 3)

    def scene(self, scene_id: str) -> Scene:
        for s in self.scenes:
            if s.id == scene_id:
                return s
        raise KeyError(f"no such scene: {scene_id}")

    def note(self, msg: str) -> None:
        self.log.append(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}")

    def approve(self, stage: str) -> None:
        if stage not in STAGES:
            raise ValueError(f"unknown stage {stage!r}; expected one of {STAGES}")
        self.approvals[stage] = True
        if STAGES.index(stage) >= STAGES.index(self.stage):
            self.stage = stage
        self.note(f"approved stage: {stage}")
        self.save()

    def require(self, stage: str) -> None:
        """Guard a stage transition on a human approval."""
        if not self.approvals.get(stage):
            raise PermissionError(
                f"stage '{stage}' has not been approved yet — "
                f"review it (CLI: hva approve {self.id} {stage}) before continuing")

    # ---------- persistence ----------
    def save(self) -> "Project":
        self.mkdirs()
        self.updated_at = time.time()
        self.path.write_text(json.dumps(self.to_dict(), indent=2))
        return self

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        scenes = []
        for sd in d.get("scenes", []):
            cands = [Candidate(**c) for c in sd.get("candidates", [])]
            sd = {**sd, "candidates": cands}
            scenes.append(Scene(**sd))
        d = {**d, "scenes": scenes}
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})

    @classmethod
    def load(cls, project_id: str) -> "Project":
        p = config.PROJECTS_DIR / project_id / "project.json"
        if not p.exists():
            raise SystemExit(f"no such project: {project_id} (looked in {p})")
        return cls.from_dict(json.loads(p.read_text()))

    @classmethod
    def create(cls, idea: str, *, title: str = "", aspect: str = "16:9",
               duration: int = 60, project_id: str = "") -> "Project":
        pid = project_id or f"{time.strftime('%Y-%m-%d')}-{slugify(title or idea)}"
        proj = cls(id=pid, idea=idea, title=title or idea.strip().rstrip("."),
                   aspect=aspect, target_duration=duration)
        proj.note(f"created from idea: {idea!r}")
        return proj.save()

    @classmethod
    def list_all(cls) -> list["Project"]:
        if not config.PROJECTS_DIR.exists():
            return []
        out = []
        for d in sorted(config.PROJECTS_DIR.iterdir()):
            if (d / "project.json").exists():
                try:
                    out.append(cls.load(d.name))
                except Exception:
                    continue
        return out
