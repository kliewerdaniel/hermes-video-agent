"""Image-generation providers.

`comfyui`     — POST a workflow graph to a user-run ComfyUI at config.COMFY_URL.
                The server is treated as someone else's long-lived service: we
                reuse it if it's up and we NEVER start or kill it.
`placeholder` — deterministic Pillow gradient card. Not art; it exists so the
                renderer can always be exercised end to end without a GPU.

`auto` picks comfyui when reachable, else placeholder.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter

from .. import config


def comfy_up() -> bool:
    try:
        return requests.get(f"{config.COMFY_URL}/system_stats", timeout=2).status_code == 200
    except Exception:
        return False


def resolve(provider: str = "") -> str:
    provider = provider or config.IMAGE_PROVIDER
    if provider != "auto":
        return provider
    return "comfyui" if comfy_up() else "placeholder"


# ------------------------------------------------------------- placeholder
def _palette(seed: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    h = hashlib.md5(seed.encode()).digest()
    a = (40 + h[0] % 90, 40 + h[1] % 90, 60 + h[2] % 120)
    b = (20 + h[3] % 60, 20 + h[4] % 60, 30 + h[5] % 80)
    return a, b


def _placeholder(prompt: str, dest: Path, size: tuple[int, int], seed: int) -> Path:
    w, h = size
    top, bottom = _palette(f"{prompt}{seed}")
    img = Image.new("RGB", (w, h), bottom)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line([(0, y), (w, y)],
               fill=tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)))
    # a few soft blobs so Ken Burns has something to move over
    hh = hashlib.md5(prompt.encode()).digest()
    for i in range(5):
        cx = int(w * (hh[i * 3] / 255)); cy = int(h * (hh[i * 3 + 1] / 255))
        r = int(min(w, h) * (0.08 + 0.22 * (hh[i * 3 + 2] / 255)))
        d.ellipse([cx - r, cy - r, cx + r, cy + r],
                  fill=tuple(min(255, c + 28) for c in top))
    img = img.filter(ImageFilter.GaussianBlur(radius=min(w, h) // 26))
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest)
    return dest


# ------------------------------------------------------------------ comfyui
def _patch_workflow(graph: dict, prompt: str, size: tuple[int, int], seed: int) -> dict:
    """Provider-agnostic patch: only touch node types that are actually present."""
    w, h = size
    for node in graph.values():
        ct = node.get("class_type", "")
        inp = node.setdefault("inputs", {})
        if ct == "CLIPTextEncode" and isinstance(inp.get("text"), str):
            # first positive encoder wins; ConditioningZeroOut handles negative
            if not inp.get("_hva_done"):
                inp["text"] = prompt
                inp["_hva_done"] = True
        if ct in ("EmptySD3LatentImage", "EmptyLatentImage"):
            inp["width"], inp["height"] = w, h
        if ct in ("KSampler", "RandomNoise"):
            key = "seed" if "seed" in inp else "noise_seed"
            inp[key] = seed
    for node in graph.values():
        node.get("inputs", {}).pop("_hva_done", None)
    return graph


def _comfyui(prompt: str, dest: Path, size: tuple[int, int], seed: int) -> Path:
    if not comfy_up():
        raise RuntimeError(
            f"ComfyUI not reachable at {config.COMFY_URL}. Start it yourself "
            f"(the agent must not launch or restart it), or use "
            f"HVA_IMAGE_PROVIDER=placeholder.")
    if not config.COMFY_WORKFLOW.exists():
        raise RuntimeError(f"workflow json missing: {config.COMFY_WORKFLOW}")
    graph = _patch_workflow(json.loads(config.COMFY_WORKFLOW.read_text()),
                            prompt, size, seed)
    r = requests.post(f"{config.COMFY_URL}/prompt", json={"prompt": graph}, timeout=30)
    r.raise_for_status()
    pid = r.json()["prompt_id"]
    deadline = time.time() + 1200
    while time.time() < deadline:
        hist = requests.get(f"{config.COMFY_URL}/history/{pid}", timeout=15).json()
        if pid in hist:
            outs = hist[pid].get("outputs", {})
            for node_out in outs.values():
                for im in node_out.get("images", []):
                    q = urllib.parse.urlencode(
                        {"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                         "type": im.get("type", "output")})
                    data = requests.get(f"{config.COMFY_URL}/view?{q}", timeout=60).content
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
                    return dest
            raise RuntimeError(f"ComfyUI job {pid} produced no images")
        time.sleep(2)
    raise RuntimeError(f"ComfyUI job {pid} timed out after 20 min")


def generate(prompt: str, dest: Path, *, size: tuple[int, int] = (1024, 576),
             seed: int | None = None, provider: str = "") -> Path:
    p = resolve(provider)
    if seed is None:
        seed = int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16)
    if p == "comfyui":
        return _comfyui(prompt, dest, size, seed)
    if p == "placeholder":
        return _placeholder(prompt, dest, size, seed)
    raise RuntimeError(f"unknown image provider {p!r}")
