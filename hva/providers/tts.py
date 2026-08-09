"""TTS providers.

Two adapters ship today:

* ``say``          — macOS built-in `say`. Zero setup, always available, decent
                     for drafts and CI. This is the default so a fresh clone can
                     produce a real video on the first run.
* ``kleincannon``  — bridge to a local Qwen3-TTS voice-clone venv (see
                     config.CLONE_VENV). Optional; used when you want your own
                     cloned voice.
* ``qwen``         — a local Qwen TTS HTTP server (default :7860, see
                     config.QWEN_TTS_URL) exposing /api/generate + /api/audio.
                     Ships a library of named voices; "default" works too.

Adding a provider = one function + a registry entry. Nothing else in the
pipeline knows which one produced the wav.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .. import config


def _clean_env() -> dict:
    """Child interpreters must not inherit a leaked PYTHONPATH/PYTHONHOME.

    An agent shell can export both; a 3.11 numpy then gets pulled into a 3.14
    process and it dies mid-call. Strip them for every child we spawn.
    """
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    return env


def duration_of(path: Path) -> float:
    out = subprocess.run(
        [config.FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, env=_clean_env())
    try:
        return round(float(out.stdout.strip()), 3)
    except ValueError:
        return 0.0


# ---------------------------------------------------------------- say (macOS)
def _say(text: str, dest: Path, voice: str, rate: int) -> Path:
    """macOS `say` straight to WAV.

    Gotcha: `--data-format` alone fails with "Opening output file failed: fmt?"
    because say infers the container from the extension and won't accept a
    LEF32 payload in an .aiff. Pass --file-format=WAVE explicitly and write the
    .wav directly — no intermediate aiff, no ffmpeg conversion step.
    """
    if not shutil.which("say"):
        raise RuntimeError("macOS `say` not found; set HVA_TTS_PROVIDER")
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["say", "-o", str(dest), "--file-format=WAVE",
           "--data-format=LEI16@24000"]
    if voice:
        cmd += ["-v", voice]
    if rate:
        cmd += ["-r", str(rate)]
    cmd += [text]
    p = subprocess.run(cmd, capture_output=True, text=True, env=_clean_env())
    if p.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        raise RuntimeError(f"say failed: {p.stderr[-400:] or 'empty output'}")
    return dest


# ------------------------------------------------- kleincannon voice-clone
_CLONE_SNIPPET = r'''
import sys, numpy as np, soundfile as sf
from pathlib import Path
text, ref, dest, speed = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
reftext = Path(ref).with_suffix(".reftext")
kw = dict(text=text, speed=speed, verbose=False, ref_audio=ref)
if reftext.exists():
    kw["ref_text"] = reftext.read_text().strip()
from mlx_audio.tts.utils import load_model
m = load_model("mlx-community/Qwen3-TTS-12Hz-1.7B-Base-4bit")
parts, sr = [], 24000
for r in m.generate(**kw):
    parts.append(np.asarray(r.audio, dtype=np.float32)); sr = getattr(r, "sample_rate", sr)
sf.write(dest, np.concatenate(parts) if len(parts) > 1 else parts[0], sr)
'''


def _clone(text: str, dest: Path, voice: str, rate: int) -> Path:
    py = config.CLONE_VENV
    if not py.exists():
        raise RuntimeError(f"clone venv missing: {py}")
    ref = None
    for ext in (".wav", ".mp3", ".flac", ".m4a"):
        cand = config.CLONE_VOICES / f"{voice}{ext}"
        if cand.exists():
            ref = cand
            break
    if ref is None:
        raise RuntimeError(f"no reference clip for voice {voice!r} in {config.CLONE_VOICES}")
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(_CLONE_SNIPPET)
        script = f.name
    speed = max(0.5, min(2.0, rate / 175.0)) if rate else 1.0
    p = subprocess.run([str(py), script, text, str(ref), str(dest), f"{speed:.2f}"],
                       capture_output=True, text=True, env=_clean_env())
    os.unlink(script)
    if p.returncode != 0 or not dest.exists():
        raise RuntimeError(f"voice-clone TTS failed: {p.stderr[-600:]}")
    return dest


# ------------------------------------------------- vox (in-process Qwen3-TTS)
import re as _re

_VOX_EXTS = (".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac")
_VOX_NAME_SANITIZER = _re.compile(r"[^a-zA-Z0-9_]")


def _vox_voices_dir() -> Path:
    d = config.VOX_VOICES_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _vox_voice_path(name: str) -> Path | None:
    """Resolve a voice name to its on-disk sample (any supported extension)."""
    if not name or name == "default":
        return None
    d = _vox_voices_dir()
    if name.lower().endswith(_VOX_EXTS):
        cand = d / name
        return cand if cand.exists() else None
    for ext in _VOX_EXTS:
        cand = d / f"{name}{ext}"
        if cand.exists():
            return cand
    return None


def _vox_list_voices() -> list[str]:
    d = _vox_voices_dir()
    out = []
    for f in sorted(d.iterdir()):
        if f.suffix.lower() in _VOX_EXTS:
            out.append(f.stem)
    return out or ["default"]


# The model runs in a sibling venv (the one `vox` already ships with mlx-audio),
# so the hva process itself stays free of MLX and the running :7860 server is
# no longer required. The snippet mirrors vox/app.py's generate_long path:
# chunk long text on sentence boundaries, clone via ref_audio + whisper
# transcription, concat segments with a short silence gap.
_VOX_SNIPPET = r'''
import sys, json, uuid, re, tempfile, subprocess
import numpy as np, soundfile as sf
from pathlib import Path

text, ref, dest, speed, model_id, stt_model = sys.argv[1:7]
if ref == "":
    ref = None

def split_chunks(t, max_words=50):
    sents = [s.strip() for s in re.split(r'(?<=[.!?;:])\s+', t.strip()) if s.strip()]
    if not sents:
        return [t] if t.strip() else []
    chunks, cur, n = [], [], 0
    for s in sents:
        wc = len(s.split())
        if wc > max_words * 1.5:
            for part in re.split(r'(?<=,)\s*', s):
                part = part.strip()
                if not part: continue
                pw = len(part.split())
                if n + pw > max_words and cur:
                    chunks.append(" ".join(cur)); cur=[part]; n=pw
                else:
                    cur.append(part); n+=pw
        else:
            if n + wc > max_words and cur:
                chunks.append(" ".join(cur)); cur=[s]; n=wc
            else:
                cur.append(s); n+=wc
    if cur: chunks.append(" ".join(cur))
    return chunks or [t]

from mlx_audio.tts.utils import load_model
m = load_model(model_id)
ref_text = None
if ref:
    try:
        from mlx_audio.stt import load as load_stt
        ref_text = load_stt(stt_model).generate(ref).text
    except Exception as e:
        print("warn: ref transcribe failed:", e)

chunks = split_chunks(text)
sr = 24000
segs = []
for c in chunks:
    kw = dict(text=c, speed=float(speed), verbose=False)
    if ref:
        kw["ref_audio"] = ref
        if ref_text: kw["ref_text"] = ref_text
    parts = [np.asarray(r.audio, dtype=np.float32) for r in m.generate(**kw)]
    if parts:
        segs.append(np.concatenate(parts) if len(parts) > 1 else parts[0])

if not segs:
    sys.exit("no audio generated")

silence = np.zeros(int(sr * 0.1), dtype=np.float32)
out = []
for i, seg in enumerate(segs):
    out.append(seg)
    if i < len(segs) - 1:
        out.append(silence)
audio = np.concatenate(out)
sf.write(dest, audio, sr)
print(f"vox wrote {len(audio)/sr:.2f}s in {len(segs)} segment(s)")
'''


def _vox_generate(text: str, dest: Path, voice: str, rate: int) -> Path:
    py = config.VOX_VENV
    if not py.exists():
        raise RuntimeError(f"vox TTS venv missing: {py}")
    ref = _vox_voice_path(voice)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(_VOX_SNIPPET)
        script = f.name
    # `say` rate 175 ≈ speed 1.0; clamp the rest into a sane range.
    speed = max(0.5, min(2.0, rate / 175.0)) if rate else 1.0
    cmd = [str(py), script, text, str(ref) if ref else "",
           str(dest), f"{speed:.2f}", config.VOX_MODEL_ID, config.VOX_STT_MODEL]
    p = subprocess.run(cmd, capture_output=True, text=True, env=_clean_env())
    try:
        os.unlink(script)
    except OSError:
        pass
    if p.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        raise RuntimeError(f"vox TTS failed: {p.stderr[-800:] or 'empty output'}")
    return dest


def _vox_upload_voice(name: str, data: bytes, filename: str) -> str:
    """Save an uploaded voice sample; returns the registered voice name."""
    if not name:
        name = Path(filename).stem
    name = _VOX_NAME_SANITIZER.sub("_", name).strip().strip("_")
    if not name:
        raise ValueError("voice name has no valid characters")
    ext = Path(filename).suffix.lower()
    if ext not in _VOX_EXTS:
        raise ValueError(f"unsupported voice format: {ext}")
    d = _vox_voices_dir()
    # Replace any existing sample with the same name (any extension).
    for existing in d.iterdir():
        if existing.stem == name:
            existing.unlink()
    path = d / f"{name}{ext}"
    path.write_bytes(data)
    return name


def _vox_delete_voice(name: str) -> bool:
    d = _vox_voices_dir()
    deleted = False
    for f in list(d.iterdir()):
        if f.stem == name:
            f.unlink()
            deleted = True
    return deleted


# ------------------------------------------------- Qwen TTS HTTP server
import json as _json
import urllib.request as _urlreq

_QWEN_VOICES_CACHE: list[str] | None = None
_QWEN_NAME_TO_FILE: dict[str, str] | None = None


def _qwen_name_to_file(voice: str) -> str:
    global _QWEN_NAME_TO_FILE
    if not voice or voice == "default":
        return ""
    if voice.lower().endswith((".wav", ".mp3", ".flac", ".m4a", ".ogg")):
        return voice  # already a filename
    if _QWEN_NAME_TO_FILE is None:
        _QWEN_NAME_TO_FILE = {}
        try:
            base = config.QWEN_TTS_URL.rstrip("/")
            with _urlreq.urlopen(base + "/api/voices", timeout=10) as r:
                data = _json.loads(r.read().decode())
            for v in data.get("voices", []):
                _QWEN_NAME_TO_FILE[v["name"]] = v.get("filename") or v["name"]
        except Exception:
            pass
    return _QWEN_NAME_TO_FILE.get(voice, voice)


def _qwen_generate(text: str, dest: Path, voice: str, rate: int) -> Path:
    """Call the local Qwen TTS HTTP server (config.QWEN_TTS_URL).

    Protocol (discovered from the server's own UI):
      GET  /api/voices                -> {"voices":[{"name","filename","url"}...]}
      POST /api/generate   {text, voice_file, speed}
                                       -> {file_id, duration, sample_rate, success}
      GET  /api/audio/{file_id}        -> raw WAV bytes
    """
    base = config.QWEN_TTS_URL.rstrip("/")
    speed = max(0.5, min(2.0, rate / 175.0)) if rate else 1.0
    # The /api/generate server wants the sample FILENAME (e.g. "Me.wav"), not the
    # display voice NAME ("Me"). Resolve name -> filename when needed.
    voice_file = _qwen_name_to_file(voice)
    payload = _json.dumps({"text": text,
                           "voice_file": voice_file,
                           "speed": speed}).encode()
    req = _urlreq.Request(base + "/api/generate", data=payload,
                          headers={"Content-Type": "application/json"},
                          method="POST")
    for attempt in range(3):
        try:
            with _urlreq.urlopen(req, timeout=120) as r:
                data = _json.loads(r.read().decode())
            break
        except Exception as e:
            if attempt == 2:
                raise RuntimeError(f"qwen TTS generate failed: {e}")
            import time as _t
            _t.sleep(1 + attempt)
    if not data.get("success"):
        raise RuntimeError(f"qwen TTS rejected: {data}")
    fid = data["file_id"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    with _urlreq.urlopen(base + "/api/audio/" + fid, timeout=120) as r, \
            open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
    if not dest.exists() or dest.stat().st_size == 0:
        raise RuntimeError("qwen TTS returned an empty audio file")
    return dest


def _qwen_voices() -> list[str]:
    global _QWEN_VOICES_CACHE
    if _QWEN_VOICES_CACHE is not None:
        return _QWEN_VOICES_CACHE
    try:
        base = config.QWEN_TTS_URL.rstrip("/")
        with _urlreq.urlopen(base + "/api/voices", timeout=10) as r:
            data = _json.loads(r.read().decode())
        names = [v["name"] for v in data.get("voices", [])]
        _QWEN_VOICES_CACHE = names or ["default"]
    except Exception:
        _QWEN_VOICES_CACHE = ["default"]
    return _QWEN_VOICES_CACHE


PROVIDERS = {"say": _say, "kleincannon": _clone, "qwen": _qwen_generate,
              "vox": _vox_generate}


def synthesize(text: str, dest: Path, *, provider: str = "", voice: str = "",
               rate: int = 0) -> tuple[Path, float]:
    """Render `text` to `dest` (wav). Returns (path, duration_seconds)."""
    provider = provider or config.TTS_PROVIDER
    voice = voice or config.TTS_VOICE
    rate = rate or config.TTS_RATE
    fn = PROVIDERS.get(provider)
    if fn is None:
        raise RuntimeError(f"unknown TTS provider {provider!r}; have {list(PROVIDERS)}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    fn(text, dest, voice, rate)
    return dest, duration_of(dest)


def list_voices(provider: str = "") -> list[str]:
    provider = provider or config.TTS_PROVIDER
    if provider == "say":
        p = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
        return [ln.split()[0] for ln in p.stdout.splitlines() if ln.strip()]
    if provider == "kleincannon" and config.CLONE_VOICES.exists():
        return sorted({f.stem for f in config.CLONE_VOICES.iterdir()
                       if f.suffix in (".wav", ".mp3", ".flac", ".m4a")})
    if provider == "qwen":
        return _qwen_voices()
    if provider == "vox":
        return _vox_list_voices()
    return []
