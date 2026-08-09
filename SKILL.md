---
name: hermes-video-agent
description: "Use when producing a short video from an idea or script — script, shot list, licensed visual research, narration, captions, FFmpeg assembly, with human approval gates."
version: 0.1.0
author: Daniel Kliewer
license: MIT
metadata:
  hermes:
    tags: [video, ffmpeg, playwright, tts, human-in-the-loop, openverse]
    related_skills: [visual-research, video-render, tts-narration]
---

# Hermes Video Agent — usage skill

Produce a finished, captioned MP4 from an idea or a script, keeping the human in
control of every creative decision. This skill makes you able to *run* the
workflow, not merely describe it.

## When to invoke

- "Make a 45-second video about X"
- "Turn this script into a video"
- "Find me some usable footage/images for these scenes"
- "Re-do scene 4, I don't like that image"
- Any request to assemble narration + stills + captions into an MP4

Do **not** invoke for editing existing footage (that is GreenPatch's job) or for
vertical TikTok-style generation with generated-only imagery (kleincannon).

## Environment (verify before you start)

```bash
cd ~/Documents/Projects/hermes-video-agent
env -u PYTHONPATH -u PYTHONHOME ./.venv/bin/python hva-cli.py doctor
```

- **Always** run through the venv with `env -u PYTHONPATH -u PYTHONHOME`. The
  agent shell leaks `PYTHONPATH` *and* `PYTHONHOME`; stripping only the first is
  not enough. The `./hva` wrapper does this — prefer it when the shell allows.
- FFmpeg here has **no `drawtext` and no `subtitles` filter**. All burn-in is
  Pillow-rasterized PNG + `overlay`. Never reach for `drawtext`.
- The LLM at `:8080` is optional. Script generation needs it; storyboarding has
  a deterministic fallback; everything downstream works without it.
- ComfyUI at `:8188` is **user-run**. Reuse it if up; **never launch, kill or
  restart it** — a restart poisons the MPS pool. If it is down, either ask the
  user to start it or accept the placeholder provider.

## The workflow

Each stage writes `projects/<id>/project.json` and stops. Do not skip gates
unless the user explicitly says "just build it".

```bash
H="env -u PYTHONPATH -u PYTHONHOME ./.venv/bin/python hva-cli.py"

$H new "<idea>" --duration 45 --aspect 16:9      # -> prints the project id
$H script <id>                                    # or --file script.txt (user's own)
#   >>> SHOW THE SCRIPT TO THE USER AND WAIT <<<
$H approve <id> script
$H storyboard <id> --scenes 7
#   >>> SHOW THE SHOT LIST AND WAIT <<<
$H approve <id> scenes
$H research <id> --limit 4
#   >>> SHOW THE CANDIDATES (or point them at the UI) AND WAIT <<<
$H approve <id> visuals
$H narrate <id>
$H approve <id> narration
$H captions <id>                                  # also runs preflight checks
$H render <id>                                    # draft.mp4
#   >>> USER REVIEWS THE DRAFT <<<
$H approve <id> draft
$H render <id> --final
```

For the visual-selection stage, prefer the UI:

```bash
$H web        # http://127.0.0.1:8777
```

## Expected inputs / outputs

**Inputs:** an idea string, or a script file; optionally aspect ratio, duration,
voice, scene count.

**Outputs:** `projects/<id>/` containing `project.json`, `assets/`, `audio/`,
`captions/{captions.srt,captions.vtt,cards/}`, `CREDITS.md`, `draft.mp4`,
`final.mp4`.

## Human approval points (do not bypass)

| Gate | What the human is deciding |
|---|---|
| `script` | Is the argument right? Is the hook good? |
| `scenes` | Does the shot list cover the script? Are the visuals the right ideas? |
| `visuals` | Which specific image goes in each scene |
| `narration` | Voice, pace, pronunciation |
| `draft` | Does the whole thing work? |

Going backwards is normal: `$H approve` forward, and in the UI click any stage
pill to reopen from there. **Rejecting scene 7 must regenerate scene 7, not the
project** — use `--scene scene_007` on `research`/`narrate`, or the per-scene
buttons in the UI.

## Working the manifest

`project.json` is the source of truth and is safe to edit by hand or with a
short Python snippet. Useful patterns:

```python
from hva.manifest import Project
p = Project.load("<id>")
p.scene("scene_004").search_terms = ["empty stadium", "abandoned seats"]
p.scene("scene_004").candidates = []      # force a fresh search
p.scene("scene_004").selected = None
p.save()
```

Then re-run only that scene:

```bash
$H research <id> --scene scene_004 --limit 4
```

## Preserving source information

Every sourced asset carries `source_url`, `creator`, `license`, `license_url`.
`CREDITS.md` is regenerated on every render — **deliver it alongside the MP4**.

Licence rule that is easy to get wrong: the renderer crops and Ken-Burns-zooms
every still, which makes a **derivative work**. Openverse's "commercial" filter
still returns `CC BY-ND`, which forbids exactly that. The research stage
excludes ND automatically; `$H check <id>` catches any that arrive via upload or
manual selection. Run it before delivering.

## Failure handling

| Symptom | Cause | Fix |
|---|---|---|
| `model never returned valid JSON` / empty script | reasoning model spent the whole budget in `reasoning_content` | raise `max_tokens`; the provider already falls back to reasoning text |
| research returns 0 candidates for every scene | Openverse 429 rate limit | wait ~60s; the client throttles and caps at 2 queries/scene |
| `openverse.org` returns 403 | Cloudflare blocks headless Chromium | use the API path (default), or `HVA_HEADFUL=1` for the website |
| `say failed: Opening output file failed: fmt?` | `--data-format` without a container | must pass `--file-format=WAVE` too (already fixed in the provider) |
| render: `missing images` / `no narration audio` | stage run out of order | run the missing stage; stages raise `SystemExit`, which the web layer turns into HTTP 400 |
| caption text looks cut off | a cue wrapped past two lines | `$H check <id>` — `check_captions_complete` catches dropped words |
| ComfyUI connection reset mid-render | the server died | **stop**; tell the user, give them the restart command, wait. Do not relaunch it yourself |

## Verify before you claim it is done

1. `$H check <id>` — must be clean.
2. `ffprobe` the mp4 for duration/resolution.
3. Extract 3–4 frames and inspect them with vision:
   ```bash
   for t in 2 12 24 34; do ffmpeg -v error -ss $t -i projects/<id>/final.mp4 \
     -frames:v 1 /tmp/qa_$t.png; done
   ```
   Check each for: caption visible, legible, **complete sentence**, and an image
   that actually relates to the line being spoken.
4. Report the off-topic shots you found rather than hiding them — the user is
   the picture editor and needs to know which scenes to re-pick.
