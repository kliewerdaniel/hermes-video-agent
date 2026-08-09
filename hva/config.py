"""Machine-local paths, service endpoints, and render defaults.

Everything tunable lives here. Nothing else in the package hardcodes a path.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = Path(os.environ.get("HVA_PROJECTS", ROOT / "projects"))
ASSET_CACHE = Path(os.environ.get("HVA_CACHE", ROOT / ".cache"))

# --- LLM (OpenAI-compatible; llama.cpp / Ollama / LM Studio all work) ---
LLM_URL = os.environ.get("HVA_LLM_URL", "http://127.0.0.1:8080")
LLM_MODEL = os.environ.get("HVA_LLM_MODEL", "local")
LLM_TIMEOUT = int(os.environ.get("HVA_LLM_TIMEOUT", "300"))

# --- Inference provider configuration (persisted to disk) -----------------
# The operator may choose local / gemini / openrouter and supply creds. The
# selected provider + keys are stored in ``inference.json`` under ROOT. API
# keys live ONLY here and are never echoed back by the API or logged.
INFERENCE_CONFIG_PATH = Path(os.environ.get("HVA_INFERENCE_CONFIG", ROOT / "inference.json"))

# --- Image generation backend (optional; adapters in providers/image.py) ---
IMAGE_PROVIDER = os.environ.get("HVA_IMAGE_PROVIDER", "auto")  # auto|comfyui|placeholder
COMFY_URL = os.environ.get("HVA_COMFY_URL", "http://127.0.0.1:8188")
COMFY_WORKFLOW = ROOT / "hva" / "workflows" / "zimageturbo.json"

# --- TTS backend (adapters in providers/tts.py) ---
# `vox` runs the Qwen3-TTS voice-clone model in-process (via a venv that ships
# mlx-audio), so no separate TTS server is needed. `qwen` talks to the legacy
# :7860 HTTP server; `say`/`kleincannon` remain available for back-compat/CI.
TTS_PROVIDER = os.environ.get("HVA_TTS_PROVIDER", "vox")  # vox|qwen|say|kleincannon
TTS_VOICE = os.environ.get("HVA_TTS_VOICE", "Me")
TTS_RATE = int(os.environ.get("HVA_TTS_RATE", "175"))      # words/min for `say`
QWEN_TTS_URL = os.environ.get("HVA_QWEN_TTS_URL", "http://127.0.0.1:7860")
# Self-contained voice-clone backend (replaces the external vox Flask server).
VOX_VENV = Path(os.environ.get(
    "HVA_VOX_VENV", Path.home() / "Documents/Projects/vox/.venv/bin/python"))
VOX_VOICES_DIR = Path(os.environ.get(
    "HVA_VOX_VOICES", ROOT / "vox_voices"))
VOX_MODEL_ID = os.environ.get(
    "HVA_VOX_MODEL", "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-4bit")
VOX_STT_MODEL = os.environ.get(
    "HVA_VOX_STT", "mlx-community/whisper-large-v3-turbo-asr-fp16")
# Optional voice-clone bridge: an existing local pipeline venv + voices dir.
CLONE_VENV = Path(os.environ.get(
    "HVA_CLONE_VENV", Path.home() / "Documents/Projects/kleincannon/venv/bin/python"))
CLONE_VOICES = Path(os.environ.get(
    "HVA_CLONE_VOICES", Path.home() / "Documents/Projects/kleincannon/voices"))

# --- Render ---
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
FFPROBE = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"
FPS = 30
CRF = 20
ZOOM_MAX = 1.12

ASPECTS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
}

# --- Caption style (Pillow-rasterized; this ffmpeg has no drawtext/libass) ---
CAPTION_FONT = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")
CAPTION_FONT_FALLBACKS = [
    Path("/System/Library/Fonts/Helvetica.ttc"),
    Path("/Library/Fonts/Arial.ttf"),
]
CAPTION_REL_SIZE = 0.052       # fraction of frame height
CAPTION_BOTTOM_MARGIN = 0.14   # fraction of frame height
CAPTION_SIDE_MARGIN = 0.06     # fraction of frame WIDTH kept clear on each side
CAPTION_MAX_CHARS = 42         # wide-frame (16:9) character budget; narrow
                                # aspects derive a smaller budget from frame width

# --- Visual research ---
RESEARCH_SOURCES = ["openverse", "wikimedia"]
CANDIDATES_PER_SCENE = 3
PLAYWRIGHT_TIMEOUT = 30000
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 hermes-video-agent/0.1")
