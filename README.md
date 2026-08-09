# Hermes Video Agent

A **human-in-the-loop AI video production agent**. You give it an idea or a
script; it writes the narration, plans the shot list, **browses the web to find
real licensed images**, voices the script with a **clonable voice library**, and
assembles a captioned MP4 with FFmpeg — pausing for your approval at every stage
that involves a creative decision.

It is not a "prompt in, video out" toy. The video exists as **structured data**
(`project.json`) long before it exists as pixels, and you can inspect, edit,
reject, or regenerate any individual scene without rebuilding the project.

```bash
python -m uvicorn hva.web.app:app --host 127.0.0.1 --port 8777   # backend
cd webapp && npm run dev                                          # review UI -> http://127.0.0.1:3008
```

> 📝 **Full build + replication guide (with screenshots):** read the companion
> blog post — [Building Hermes Video Agent: a local-first, human-in-the-loop
> video pipeline](https://danielkliewer.com/blog/2026-08-09-hermes-video-agent).

---

## What it does

```
IDEA ─► SCRIPT ─► STORYBOARD ─► VISUALS ─► NARRATION ─► CAPTIONS ─► DRAFT ─► FINAL
              (you approve each gate before the next runs)
```

Five review panels in a Next.js UI, backed by a FastAPI service that owns the
manifest and runs the stages:

1. **Script** — write your own or generate with a local/cloud LLM.
2. **Storyboard** — split the script into timed scenes.
3. **Visuals** — fetch licensed candidates (Openverse + Wikimedia), pick one per
   scene, upload your own, or skip.
4. **Narration** — voice each scene. Pick from a **voice library**, or upload a
   short clip to **clone a new voice** (runs fully in-process via Qwen3-TTS).
5. **Export** — burn-in captions and render the final MP4.

**Design rules**

- *The manifest is the product.* `projects/<id>/project.json` is the single
  source of truth. Every stage reads and writes it; any stage can be re-run
  alone, on one scene, in any order.
- *Providers are adapters.* TTS (`vox`/`qwen`/`say`/`kleincannon`), image
  (`comfyui`/`placeholder`), and inference (`local`/`gemini`/`openrouter`) are
  each a pluggable backend behind one registry. No module knows which ran.
- *Provenance is mandatory.* Every sourced asset keeps its source URL, creator,
  and licence; `CREDITS.md` is regenerated on every render.
- *No database.* Filesystem + JSON. One operator, one machine.

---

## Architecture

```
hva/                          the Python package (the engine)
├── manifest.py               Project / Scene / Candidate — single source of truth
├── config.py                 paths, endpoints, render + caption defaults, env switches
├── checks.py                 preflight checks (caption coverage, timing, licences)
├── providers/
│   ├── inference.py          provider-agnostic LLM (local / Gemini / OpenRouter)
│   ├── inference_config.py   persists inference.json (keys redacted on read)
│   ├── llm.py                thin wrapper used by script/storyboard stages
│   ├── tts.py                TTS adapters: vox (in-process Qwen3-TTS clone) | qwen | say | kleincannon
│   └── image.py              ComfyUI | deterministic placeholder — pluggable
├── stages/
│   ├── script.py             idea → script, or accept yours verbatim
│   ├── storyboard.py         script → shot list (LLM, with deterministic fallback)
│   ├── research.py           Openverse API + Wikimedia/Openverse via Playwright → licensed candidates
│   ├── narration.py          per-scene wav; durations MEASURED from the audio
│   ├── captions.py           SRT / VTT / Pillow burn-in cards (ffmpeg has no libass here)
│   └── render.py             Ken Burns → concat → overlay → mux (FFmpeg)
└── web/app.py                FastAPI: projects, research, narration, voices, proxy for assets

webapp/                       the review UI (Next.js 14 + Tailwind + framer-motion)
├── app/                      routes: landing (/) + project/[id]
├── components/               Workspace, StepRail, ScriptEditor, Storyboard,
│                              VisualsStep, NarrationStep, ExportPanel, InferenceSettings, …
├── lib/                      api client, types
└── server.mjs                dev server: Next.js (HMR) proxying /api/* to the FastAPI backend

hva-cli.py                    CLI entrypoint (hva new | script | research | narrate | … | web | auto)
tests/                        pytest suite (inference + pipeline; no network required)
```

---

## Requirements

| Requirement | Notes |
|---|---|
| macOS or Linux | developed on macOS 26 (Apple Silicon) |
| Python 3.12+ | tested on 3.14 |
| Node 18+ | tested on 22 (for the `webapp/`) |
| FFmpeg | `brew install ffmpeg`. `drawtext`/`libass` **not** required |
| Playwright + Chromium | for visual research (Openverse/Wikimedia) |
| Local LLM (optional) | any OpenAI-compatible server (e.g. `llama-server`) on `:8080` for script/storyboard |
| ComfyUI (optional) | for generated imagery; a placeholder card is used otherwise |
| Vox voice clone (optional) | an **existing** venv with `mlx-audio` + `mlx-whisper`; the `vox` provider shells out to it. See "Vox TTS" below |

Default TTS is **`vox`** with the built-in `Me` voice, so a fresh clone can
voice a script with no model downloads *if* you point `HVA_VOX_VENV` at a venv
that already has `mlx-audio`. Without that, set `HVA_TTS_PROVIDER=say` (macOS)
or `qwen` (external server) to get a real video immediately.

---

## Install

```bash
# 1. Clone
git clone https://github.com/kliewerdaniel/hermes-video-agent
cd hermes-video-agent

# 2. Python backend venv
#    (Strip leaked PYTHONPATH/PYTHONHOME when running from an agent shell — they
#     pull a foreign numpy into this venv and crash imports.)
env -u PYTHONPATH -u PYTHONHOME python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium

# 3. Frontend
cd webapp
npm install
cd ..
```

---

## Run it

### Backend (FastAPI)

```bash
# from the repo root, with .venv active
env -u PYTHONPATH -u PYTHONHOME \
  HVA_TTS_PROVIDER=vox HVA_TTS_VOICE=Me \
  ./.venv/bin/python -m uvicorn hva.web.app:app --host 127.0.0.1 --port 8777
```

### Frontend (Next.js review UI)

```bash
cd webapp
npm run dev        # http://127.0.0.1:3008  (proxies /api/* -> :8777)
```

Open the UI, create a project from an idea (or paste a script), then walk the
five panels. Each panel has an **Approve / Next** action that unlocks the next;
the StepRail lets you jump back to any stage and re-run it in isolation.

### CLI (headless)

```bash
./hva-cli.py new "Why people doomscroll" --duration 45 --aspect 16:9
./hva-cli.py script  <id>                       # or --file my-script.txt
./hva-cli.py storyboard <id> --scenes 7
./hva-cli.py research <id> --limit 4            # Openverse + Wikimedia
./hva-cli.py select  <id> scene_003 <cand-id>   # override the agent's pick
./hva-cli.py narrate <id> --voice Me
./hva-cli.py captions <id>
./hva-cli.py render  <id> --final               # final.mp4
./hva-cli.py auto "Why people doomscroll" --yes # full chain, no gates
```

### Output (per project)

```
projects/<id>/
├── project.json          the manifest — edit it by hand if you like
├── assets/scene_00N/     downloaded + generated candidates
├── audio/scene_00N.wav   per-scene narration
├── captions/
│   ├── captions.srt  captions.vtt
│   └── cards/            transparent PNGs used for burn-in
├── CREDITS.md            attribution for every sourced asset
├── draft.mp4
└── final.mp4
```

---

## Vox TTS (in-process voice cloning)

`vox` is the default TTS provider. It runs **Qwen3-TTS** cloning as a subprocess
in a venv you already have (the one that owns `mlx-audio`), so the app is
self-contained — no separate TTS server to keep running.

```bash
# point at the venv that has mlx-audio + mlx-whisper
export HVA_VOX_VENV="$HOME/Documents/Projects/vox/.venv/bin/python"
# where uploaded/seed voices live (seeded with 15 samples on first run copy)
export HVA_VOX_VOICES="$PWD/vox_voices"
export HVA_VOX_MODEL="mlx-community/Qwen3-TTS-12Hz-1.7B-Base-4bit"
export HVA_VOX_STT="mlx-community/whisper-large-v3-turbo-asr-fp16"
```

From the Narration panel you can **upload a short clean clip (<30s)** to clone a
new voice, **play** any voice's sample, **select** it for the whole project, and
**delete** voices you no longer want. The voice library, upload, and delete all
hit real endpoints (`GET/POST/DELETE /api/voices`); nothing depends on an
external `:7860` server.

> Note: the seeded `vox_voices/` (15 public-figure name samples) are **not**
> committed to the repo — re-clone your own reference clips, or just use
> `macOS say` / the `qwen` provider.

---

## Inference providers (LLM)

The script and storyboard stages talk to an **OpenAI-compatible** LLM through a
provider abstraction (`hva/providers/inference.py`). Configure it from the
**Inference provider** button on the landing page or project header — no code
changes, and **API keys never leave the server** (`inference.json` is read
server-side; the UI only ever sees a redacted view).

| Provider | What it needs |
|---|---|
| `local` | any OpenAI-compatible server, e.g. `llama-server` on `:8080` |
| `gemini` | a Gemini API key |
| `openrouter` | an OpenRouter key + model id |

---

## Visual research & licensing

Rather than asking an LLM which image to use, the agent **goes and looks**:

1. **Openverse API** (keyless) — the workhorse; full licence metadata.
2. **Wikimedia Commons** via Playwright — real Chromium driving MediaSearch.
3. **Openverse website** via Playwright — fallback only; may block headless.

Hits from every search term are **pooled and ranked** against the scene's own
vocabulary before download. Each candidate records *why* it was proposed
(`ranked #1 for 'casino bokeh lights' (score 2.31) on openverse/flickr`).

**Licensing.** `--commercial-only` is the default; the agent also excludes
**NoDerivatives** licences, because every still is cropped/Ken-Burns-zoomed
(a derivative work). `checks.py` flags any ND asset that sneaks in via upload.

---

## Configuration (environment)

All switches are env vars prefixed `HVA_`:

| Variable | Default | Meaning |
|---|---|---|
| `HVA_TTS_PROVIDER` | `vox` | `vox` \| `qwen` \| `say` \| `kleincannon` |
| `HVA_TTS_VOICE` | `Me` | default voice id |
| `HVA_VOX_VENV` | `…/vox/.venv/bin/python` | interpreter with `mlx-audio` |
| `HVA_VOX_VOICES` | `<root>/vox_voices` | voice sample dir |
| `HVA_VOX_MODEL` | `mlx-community/Qwen3-TTS-12Hz-1.7B-Base-4bit` | clone model |
| `HVA_VOX_STT` | `mlx-community/whisper-large-v3-turbo-asr-fp16` | ref-audio transcriber |
| `HVA_QWEN_TTS_URL` | `http://127.0.0.1:7860` | legacy `qwen` provider |
| `HVA_LLM_MODEL` | `local` | default inference model id |
| `HVA_COMFY_URL` | `http://127.0.0.1:8188` | ComfyUI endpoint |
| `HVA_BACKEND` | `http://127.0.0.1:8777` | frontend → backend target |

---

## Tests

```bash
env -u PYTHONPATH -u PYTHONHOME ./.venv/bin/python -m pytest tests -q
```

Covers the inference provider abstraction and the pipeline plumbing; no network
required.

---

## Limitations

- **The agent's first pick is often wrong.** Ranking beats raw API order, but on
  abstract lines the top candidate is frequently off-topic — which is exactly
  why the human review stage exists. Treat the agent as a researcher handing you
  a shortlist, not a picture editor.
- **Openverse's anonymous tier rate-limits hard.** The client throttles, caches,
  and backs off; sustained runs over many projects will still hit the ceiling.
- **No video-clip sources yet.** Stills with motion only; the manifest already
  models `kind: "video"` but the renderer doesn't consume it.
- **No music library.** `render --music path.mp3` mixes and ducks a file *you*
  supply; the agent won't go find one.
- **Caption timing is proportional, not forced-aligned.** Cues are timed by
  character share within a scene, not word-level alignment.
- **macOS `say` is synthetic.** Serviceable for drafts; point `HVA_TTS_PROVIDER`
  at a real voice model for client work.
- **Single user, no auth.** Bind to localhost and keep it there.

---

## Repo layout

```
hva/            the Python package (engine: manifest, stages, providers, web)
hva-cli.py       CLI entrypoint
webapp/          Next.js 14 review UI (the human-in-the-loop surface)
tests/           pytest suite
SKILL.md         Hermes Agent skill — how an agent should drive this repo
README.md        this file
requirements.txt backend deps
```

---

## Licence

MIT for the code. Assets fetched at runtime carry their own licences — see the
generated `CREDITS.md` in each project, and check them before commercial use.

---

## Companion writing

- **Blog:** [Building Hermes Video Agent: a local-first, human-in-the-loop video
  pipeline](https://danielkliewer.com/blog/2026-08-09-hermes-video-agent) — the
  full replication guide with screenshots and lessons learned.
- **Method:** [How I Taught an Agent to Edit Video — and the Repeatable Method
  Behind It](https://danielkliewer.com/blog/2026-08-05-build-a-video-editing-hermes-agent)
  — the general "software + skill beside it" pattern this project follows.
