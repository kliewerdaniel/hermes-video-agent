"""Sanity checks that run as part of the pipeline, not as a separate test suite.

These encode defects that actually shipped once: caption text silently dropped
by two-line truncation, cue timing drifting away from the audio, and scenes
whose selected asset has a licence this pipeline may not legally edit.
"""
from __future__ import annotations

import re

from .manifest import Project
from .stages import captions as captions_stage


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def check_captions_complete(proj: Project) -> list[str]:
    """Every word the narrator says must appear in the caption track."""
    problems = []
    cue_words = _words(" ".join(t for _, _, t in captions_stage._cues(proj)))
    for sc in proj.scenes:
        if sc.status == "skipped" or not sc.narration.strip():
            continue
        missing = [w for w in _words(sc.narration) if w not in cue_words]
        if missing:
            problems.append(f"{sc.id}: {len(missing)} word(s) missing from "
                            f"captions, e.g. {missing[:6]}")
    return problems


def check_cue_timing(proj: Project) -> list[str]:
    problems = []
    cues = captions_stage._cues(proj)
    total = proj.total_duration
    for i, (a, b, t) in enumerate(cues):
        if b <= a:
            problems.append(f"cue {i}: non-positive duration ({a:.2f}->{b:.2f})")
        if b - a < 0.4:
            problems.append(f"cue {i}: {b - a:.2f}s is too short to read: {t[:40]!r}")
        if i and cues[i - 1][1] > a + 0.001:
            problems.append(f"cue {i}: overlaps the previous cue")
    if cues and abs(cues[-1][1] - total) > 0.25:
        problems.append(f"caption track ends at {cues[-1][1]:.2f}s but video is "
                        f"{total:.2f}s — captions would desync")
    return problems


def check_licences(proj: Project) -> list[str]:
    """This pipeline crops and zooms every still, which makes derivatives."""
    problems = []
    for sc in proj.scenes:
        c = sc.selected_candidate
        if not c or c.provider in ("upload", "comfyui", "placeholder"):
            continue
        lic = (c.license or "").upper()
        if "ND" in re.sub(r"[^A-Z]", "", lic.replace("PUBLIC DOMAIN", "")):
            problems.append(f"{sc.id}: {lic} forbids derivatives, but the "
                            f"renderer crops and zooms this image")
        if not lic:
            problems.append(f"{sc.id}: asset has no recorded licence")
    return problems


def check_assets_present(proj: Project) -> list[str]:
    problems = []
    for sc in proj.scenes:
        if sc.status == "skipped":
            continue
        c = sc.selected_candidate
        if c and not (proj.dir / c.local_path).exists():
            problems.append(f"{sc.id}: selected asset missing on disk "
                            f"({c.local_path})")
        if sc.audio_path and not (proj.dir / sc.audio_path).exists():
            problems.append(f"{sc.id}: narration audio missing ({sc.audio_path})")
    return problems


ALL_CHECKS = [check_captions_complete, check_cue_timing, check_licences,
              check_assets_present]


def run(project_id: str, *, strict: bool = False) -> list[str]:
    proj = Project.load(project_id)
    problems: list[str] = []
    for check in ALL_CHECKS:
        problems += check(proj)
    if problems:
        print(f"[check] {len(problems)} issue(s):")
        for p in problems:
            print(f"  ✗ {p}")
        if strict:
            raise SystemExit("preflight checks failed")
    else:
        print("[check] all preflight checks passed")
    return problems
