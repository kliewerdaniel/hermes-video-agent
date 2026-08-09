#!/usr/bin/env python3
"""hva — Hermes Video Agent CLI.

Every stage is separately runnable and separately re-runnable. `hva auto` walks
the whole chain but STOPS at each human gate unless --yes is given.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hva import config                                    # noqa: E402
from hva import checks                                    # noqa: E402
from hva.manifest import Project, STAGES                  # noqa: E402
from hva.stages import (captions as captions_stage,       # noqa: E402
                        narration as narration_stage,
                        render as render_stage,
                        research as research_stage,
                        script as script_stage,
                        storyboard as storyboard_stage)


def _print_project(p: Project) -> None:
    print(f"\n{p.id}  [{p.stage}]  {p.aspect}  {p.total_duration:.1f}s")
    print(f"  title: {p.title}")
    approved = ",".join(k for k, v in p.approvals.items() if v) or "none"
    print(f"  approved: {approved}")
    for s in p.scenes:
        c = s.selected_candidate
        vis = (c.provider + ":" + c.id) if c else "—"
        print(f"  {s.id} [{s.status:<12}] {s.duration:5.2f}s  {vis:<24} "
              f"{s.narration[:60]}")


def cmd_new(a):
    p = Project.create(a.idea, title=a.title, aspect=a.aspect, duration=a.duration,
                       project_id=a.id or "")
    print(f"created {p.id} -> {p.path}")


def cmd_script(a):
    text = ""
    if a.file:
        text = Path(a.file).read_text()
    elif a.text:
        text = a.text
    p = script_stage.generate(a.id, script=text, extra_direction=a.direction or "")
    print("\n" + p.script + "\n")


def cmd_storyboard(a):
    p = storyboard_stage.build(a.id, scene_count=a.scenes, use_llm=not a.no_llm)
    _print_project(p)


def cmd_research(a):
    p = research_stage.run(a.id, limit=a.limit, only=a.scene or None,
                           commercial_only=not a.any_license)
    _print_project(p)


def cmd_narrate(a):
    p = narration_stage.run(a.id, provider=a.provider or "", voice=a.voice or "",
                            rate=a.rate, only=a.scene or None)
    _print_project(p)


def cmd_captions(a):
    captions_stage.run(a.id)
    checks.run(a.id)


def cmd_check(a):
    problems = checks.run(a.id, strict=a.strict)
    return 1 if (problems and a.strict) else 0


def cmd_render(a):
    out = render_stage.build(a.id, draft=not a.final, burn_captions=not a.no_captions,
                             music=a.music or "")
    print(out)


def cmd_select(a):
    p = Project.load(a.id)
    sc = p.scene(a.scene)
    ids = [c.id for c in sc.candidates]
    if a.candidate not in ids:
        raise SystemExit(f"candidate {a.candidate!r} not in {ids}")
    sc.selected = a.candidate
    sc.status = "approved"
    p.note(f"{a.scene}: human selected {a.candidate}")
    p.save()
    print(f"{a.scene} -> {a.candidate}")


def cmd_approve(a):
    p = Project.load(a.id)
    p.approve(a.stage)
    print(f"{a.id}: approved {a.stage}")


def cmd_status(a):
    _print_project(Project.load(a.id))


def cmd_list(a):
    for p in Project.list_all():
        print(f"{p.id:<44} {p.stage:<10} {len(p.scenes):>2} scenes  {p.title[:40]}")


def cmd_doctor(a):
    from hva.providers import image as ip, llm, tts
    import shutil
    import subprocess
    print(f"projects dir : {config.PROJECTS_DIR}")
    print(f"ffmpeg       : {config.FFMPEG}")
    filt = subprocess.run([config.FFMPEG, "-hide_banner", "-filters"],
                          capture_output=True, text=True).stdout
    for f in ("zoompan", "overlay", "drawtext", "subtitles"):
        print(f"  filter {f:<10}: {'yes' if f' {f} ' in filt else 'NO'}")
    print(f"LLM {config.LLM_URL:<22}: {'up — ' + llm.model_name() if llm.available() else 'DOWN'}")
    print(f"ComfyUI {config.COMFY_URL:<18}: {'up' if ip.comfy_up() else 'down'}"
          f"  (resolved provider: {ip.resolve()})")
    print(f"TTS provider : {config.TTS_PROVIDER}  voice={config.TTS_VOICE}")
    print(f"  `say`      : {'yes' if shutil.which('say') else 'NO'}")
    print(f"  clone venv : {'yes' if config.CLONE_VENV.exists() else 'no'} ({config.CLONE_VENV})")
    try:
        import playwright  # noqa: F401
        print("playwright   : installed")
    except ImportError:
        print("playwright   : MISSING")


def cmd_web(a):
    import uvicorn
    print(f"review UI: http://{a.host}:{a.port}")
    uvicorn.run("hva.web.app:app", host=a.host, port=a.port, reload=False)


def cmd_auto(a):
    """The full vertical slice, stopping at each gate unless --yes."""
    p = Project.create(a.idea, title=a.title, aspect=a.aspect, duration=a.duration,
                       project_id=a.id or "")
    pid = p.id
    print(f"[auto] project {pid}")
    script_stage.generate(pid, script=Path(a.file).read_text() if a.file else "")
    if not a.yes:
        print(f"\nReview the script, then: hva approve {pid} script && hva auto-continue {pid}")
        return
    Project.load(pid).approve("script")
    storyboard_stage.build(pid, scene_count=a.scenes)
    Project.load(pid).approve("scenes")
    research_stage.run(pid, limit=a.limit)
    Project.load(pid).approve("visuals")
    narration_stage.run(pid, provider=a.provider or "", voice=a.voice or "")
    Project.load(pid).approve("narration")
    captions_stage.run(pid)
    out = render_stage.build(pid, draft=True)
    Project.load(pid).approve("draft")
    _print_project(Project.load(pid))
    print(f"\ndraft: {out}")


def cmd_continue(a):
    """Resume after a human gate, doing only what is still un-approved."""
    p = Project.load(a.id)
    order = [("script", None), ("scenes", storyboard_stage.build),
             ("visuals", research_stage.run), ("narration", narration_stage.run),
             ("draft", None)]
    for stage, fn in order:
        if p.approvals.get(stage):
            continue
        prev = STAGES[STAGES.index(stage) - 1]
        if not p.approvals.get(prev) and prev != "idea":
            raise SystemExit(f"waiting on approval of '{prev}' "
                             f"(hva approve {a.id} {prev})")
        if stage == "draft":
            captions_stage.run(a.id)
            print(render_stage.build(a.id, draft=True))
        elif fn:
            fn(a.id)
        print(f"\nstage '{stage}' ready for review — "
              f"hva approve {a.id} {stage} to continue")
        return
    print("all stages approved; nothing to do")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hva", description="Hermes Video Agent")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        s = sub.add_parser(name, help=help_)
        s.set_defaults(func=fn)
        return s

    s = add("new", cmd_new, "create a project from an idea")
    s.add_argument("idea"); s.add_argument("--title", default="")
    s.add_argument("--aspect", default="16:9", choices=list(config.ASPECTS))
    s.add_argument("--duration", type=int, default=60); s.add_argument("--id", default="")

    s = add("script", cmd_script, "generate or set the script")
    s.add_argument("id"); s.add_argument("--text", default="")
    s.add_argument("--file", default=""); s.add_argument("--direction", default="")

    s = add("storyboard", cmd_storyboard, "split the script into scenes")
    s.add_argument("id"); s.add_argument("--scenes", type=int, default=0)
    s.add_argument("--no-llm", action="store_true")

    s = add("research", cmd_research, "find visual candidates with a real browser")
    s.add_argument("id"); s.add_argument("--limit", type=int, default=0)
    s.add_argument("--scene", action="append")
    s.add_argument("--any-license", action="store_true",
                   help="include non-commercial licences")

    s = add("narrate", cmd_narrate, "render narration audio per scene")
    s.add_argument("id"); s.add_argument("--provider", default="")
    s.add_argument("--voice", default=""); s.add_argument("--rate", type=int, default=0)
    s.add_argument("--scene", action="append")

    s = add("captions", cmd_captions, "write srt/vtt + burn-in cards")
    s.add_argument("id")

    s = add("render", cmd_render, "assemble the video")
    s.add_argument("id"); s.add_argument("--final", action="store_true")
    s.add_argument("--no-captions", action="store_true"); s.add_argument("--music", default="")

    s = add("select", cmd_select, "choose a visual candidate for a scene")
    s.add_argument("id"); s.add_argument("scene"); s.add_argument("candidate")

    s = add("approve", cmd_approve, "approve a stage gate")
    s.add_argument("id"); s.add_argument("stage", choices=STAGES)

    s = add("web", cmd_web, "serve the human review UI")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8777)

    s = add("check", cmd_check, "run preflight checks on the manifest")
    s.add_argument("id"); s.add_argument("--strict", action="store_true")

    s = add("status", cmd_status, "show the manifest summary"); s.add_argument("id")
    add("list", cmd_list, "list projects")
    add("doctor", cmd_doctor, "check the local environment")

    s = add("auto", cmd_auto, "run the whole slice (gates unless --yes)")
    s.add_argument("idea"); s.add_argument("--title", default="")
    s.add_argument("--aspect", default="16:9", choices=list(config.ASPECTS))
    s.add_argument("--duration", type=int, default=60)
    s.add_argument("--scenes", type=int, default=0); s.add_argument("--limit", type=int, default=0)
    s.add_argument("--provider", default=""); s.add_argument("--voice", default="")
    s.add_argument("--file", default=""); s.add_argument("--id", default="")
    s.add_argument("--yes", action="store_true", help="skip human gates (demo mode)")

    s = add("auto-continue", cmd_continue, "resume after an approval")
    s.add_argument("id")

    a = ap.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main() or 0)
