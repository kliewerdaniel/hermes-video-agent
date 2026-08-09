"""Stage 6 — render. Deterministic project.json -> mp4.

Given the same manifest and the same assets, this produces the same video. All
timing comes from the manifest; nothing is decided here.

Pipeline per scene: still -> Ken Burns (zoompan) -> concat -> caption overlay ->
optional music duck -> narration mux -> H.264/yuv420p faststart mp4.

Caption burn-in uses timed PNG overlays because this ffmpeg has no
drawtext/libass (see stages/captions.py).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .. import config
from ..manifest import Project
from ..providers import image as image_provider
from . import captions as captions_stage
from . import narration as narration_stage


def _clean_env() -> dict:
    import os
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    return env


def _kenburns(motion: str, frames: int, w: int, h: int) -> str:
    z = config.ZOOM_MAX
    n = max(2, frames)
    p = f"min(1,(on-1)/{n})"
    if motion == "out":
        zp = f"min({z},max(1.0,1.0+({z}-1.0)*(1-{p})))"
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif motion in ("left", "right"):
        zp = f"min({z},max(1.0,1.0+({z}-1.0)*(0.15+0.85*{p})))"
        # the only travel available is (iw - iw/zoom); panning further just
        # clamps at the edge and the shot sits frozen for the rest of the scene
        x = f"(iw-iw/zoom)*{p}" if motion == "left" else f"(iw-iw/zoom)*(1-{p})"
        y = "ih/2-(ih/zoom/2)"
    else:
        zp = f"min({z},max(1.0,1.0+({z}-1.0)*{p}))"
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    # scale up first so zoompan has pixels to work with, crop-fill to the frame,
    # then scale down: avoids the shimmer zoompan shows on native-size input.
    return (f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,"
            f"crop={w*2}:{h*2},"
            f"zoompan=z='{zp}':d=1:s={w}x{h}:x='{x}':y='{y}',"
            f"scale={w}:{h}:flags=lanczos,setsar=1")


def resolve_visuals(proj: Project, *, generate_missing: bool = True) -> list[tuple[Path, float, str]]:
    """Return the ordered (image, duration, motion) segments to render.

    A scene with no selected candidate gets a generated image if a backend is
    available, else a placeholder card — the render never silently drops a line
    of narration just because its picture is missing.
    """
    segs = []
    for sc in proj.scenes:
        if sc.status == "skipped":
            continue
        dur = max(0.6, sc.duration or 2.0)
        cand = sc.selected_candidate
        if cand and (proj.dir / cand.local_path).exists():
            segs.append((proj.dir / cand.local_path, dur, sc.motion))
            continue
        if generate_missing:
            dest = proj.assets_dir / sc.id / "generated.png"
            prompt = sc.image_prompt or sc.visual_concept or sc.narration
            image_provider.generate(prompt, dest, size=proj.size)
            segs.append((dest, dur, sc.motion))
        else:
            raise SystemExit(f"{sc.id} has no selected visual")
    if not segs:
        raise SystemExit("nothing to render — every scene is skipped")
    return segs


def build(project_id: str, *, draft: bool = True, burn_captions: bool = True,
          music: str = "", music_db: float = -22.0) -> Path:
    proj = Project.load(project_id)
    w, h = proj.size

    if not any(s.audio_path for s in proj.scenes):
        raise SystemExit("no narration audio — run the narration stage first")

    segs = resolve_visuals(proj)
    audio = narration_stage.concat_audio(proj)
    cards = captions_stage.render_cards(proj) if burn_captions else []

    cmd = [config.FFMPEG, "-y", "-hide_banner", "-loglevel", "error"]
    for path, _, _ in segs:
        cmd += ["-loop", "1", "-i", str(path)]
    n_img = len(segs)
    cmd += ["-i", str(audio)]
    audio_idx = n_img
    music_idx = None
    if music and Path(music).exists():
        cmd += ["-i", str(music)]
        music_idx = n_img + 1

    card_base = (music_idx if music_idx is not None else audio_idx) + 1
    for _, _, p in cards:
        cmd += ["-i", str(p)]

    filters = []
    for i, (_, dur, motion) in enumerate(segs):
        frames = int(round(dur * config.FPS))
        filters.append(
            f"[{i}:v]trim=duration={dur:.3f},setpts=PTS-STARTPTS,fps={config.FPS},"
            f"{_kenburns(motion, frames, w, h)},format=yuv420p[v{i}]")
    filters.append("".join(f"[v{i}]" for i in range(n_img))
                   + f"concat=n={n_img}:v=1:a=0[vcat]")

    last = "vcat"
    for j, (a, b, _p) in enumerate(cards):
        src = card_base + j
        out = f"vc{j}"
        filters.append(
            f"[{last}][{src}:v]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'[{out}]")
        last = out
    filters.append(f"[{last}]format=yuv420p[vout]")

    if music_idx is not None:
        filters.append(
            f"[{music_idx}:a]volume={music_db}dB,afade=t=out:st="
            f"{max(0.0, proj.total_duration - 2):.2f}:d=2[mus]")
        filters.append(f"[{audio_idx}:a][mus]amix=inputs=2:duration=first:"
                       f"dropout_transition=0[aout]")
        amap = "[aout]"
    else:
        amap = f"{audio_idx}:a"

    name = "draft.mp4" if draft else "final.mp4"
    out_path = proj.dir / name
    cmd += ["-filter_complex", ";".join(filters),
            "-map", "[vout]", "-map", amap,
            "-t", f"{proj.total_duration:.3f}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-crf", str(config.CRF if not draft else config.CRF + 4),
            "-preset", "medium" if not draft else "veryfast",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
            "-r", str(config.FPS), str(out_path)]

    print(f"[render] {name}: {n_img} scenes, {len(cards)} caption cues, "
          f"{proj.total_duration:.1f}s @ {w}x{h}")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=_clean_env())
    if proc.returncode != 0:
        raise SystemExit(f"ffmpeg failed:\n{proc.stderr[-3000:]}")

    captions_stage.write_srt(proj)
    captions_stage.write_vtt(proj)
    write_credits(proj)
    if draft:
        proj.draft = name
    else:
        proj.final = name
    proj.note(f"rendered {name} ({proj.total_duration:.2f}s)")
    proj.save()
    print(f"[render] -> {out_path}")
    return out_path


def write_credits(proj: Project) -> Path:
    """Attribution file. Sourced assets carry obligations; emit them by default."""
    lines = [f"# Asset credits — {proj.title}", ""]
    for sc in proj.scenes:
        c = sc.selected_candidate
        if not c:
            continue
        if c.provider in ("comfyui", "placeholder", "generated", "upload"):
            lines.append(f"- {sc.id}: {c.provider} (no third-party rights)")
            continue
        lines.append(
            f"- {sc.id}: {c.title or 'untitled'}"
            + (f" by {c.creator}" if c.creator else "")
            + f" — {c.license or 'licence unknown'}"
            + (f" <{c.license_url}>" if c.license_url else "")
            + (f" · source: {c.source_url}" if c.source_url else ""))
    out = proj.dir / "CREDITS.md"
    out.write_text("\n".join(lines) + "\n")
    return out
