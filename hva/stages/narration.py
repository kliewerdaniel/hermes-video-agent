"""Stage 4 — narration.

One wav per scene, so a single line can be re-voiced without re-rendering the
whole video. Scene durations are then MEASURED from the audio rather than
estimated from word count — the timeline is derived from the artifact, which is
what keeps captions in sync with speech.
"""
from __future__ import annotations

from ..manifest import Project
from ..providers import tts


def run(project_id: str, *, provider: str = "", voice: str = "",
        rate: int = 0, only: list[str] | None = None,
        pad: float = 0.25) -> Project:
    proj = Project.load(project_id)
    if not proj.scenes:
        raise SystemExit("no scenes — run the storyboard stage first")

    provider = provider or proj.tts_provider or ""
    voice = voice or proj.voice or ""

    for sc in proj.scenes:
        if only and sc.id not in only:
            continue
        if not sc.narration.strip():
            sc.duration = max(sc.duration, 1.5)
            continue
        dest = proj.audio_dir / f"{sc.id}.wav"
        path, dur = tts.synthesize(sc.narration, dest, provider=provider,
                                   voice=voice, rate=rate)
        sc.audio_path = str(path.relative_to(proj.dir))
        # A small tail keeps the cut from clipping the final consonant and gives
        # the eye a beat on the image before the next line starts.
        sc.duration = round(dur + pad, 3)
        print(f"[narration] {sc.id}: {dur:.2f}s (+{pad}s pad) -> {sc.audio_path}")

    proj.tts_provider = provider or tts.config.TTS_PROVIDER
    proj.voice = voice or tts.config.TTS_VOICE
    proj.note(f"narration rendered via {proj.tts_provider}/{proj.voice}; "
              f"total {proj.total_duration:.2f}s")
    proj.save()
    print(f"[narration] total {proj.total_duration:.2f}s across "
          f"{len(proj.scenes)} scenes")
    return proj


def concat_audio(proj: Project) -> "object":
    """Build one continuous narration track in scene order. Returns its path."""
    import subprocess
    from .. import config

    parts = [(proj.dir / s.audio_path) for s in proj.scenes
             if s.audio_path and (proj.dir / s.audio_path).exists()]
    if not parts:
        raise SystemExit("no narration audio — run the narration stage first")
    listing = proj.audio_dir / "_concat.txt"
    lines = []
    for s in proj.scenes:
        if not s.audio_path:
            continue
        p = proj.dir / s.audio_path
        lines.append(f"file '{p}'")
        # pad each scene out to its recorded duration so audio and video agree
        from ..providers.tts import duration_of
        gap = round(s.duration - duration_of(p), 3)
        if gap > 0.01:
            sil = proj.audio_dir / f"_sil_{s.id}.wav"
            if not sil.exists() or abs(duration_of(sil) - gap) > 0.02:
                subprocess.run(
                    [config.FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                     "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                     "-t", f"{gap:.3f}", str(sil)], check=True)
            lines.append(f"file '{sil}'")
    listing.write_text("\n".join(lines) + "\n")
    out = proj.audio_dir / "narration.wav"
    subprocess.run(
        [config.FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "concat", "-safe", "0", "-i", str(listing),
         "-ar", "24000", "-ac", "1", str(out)], check=True)
    return out
