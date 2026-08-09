"""Stage 5 — captions.

Emits SRT and VTT from the scene timeline, plus (optionally) burn-in frames.

Important environment fact: the ffmpeg on this machine is built WITHOUT
libass/freetype/fontconfig, so `drawtext` and the `subtitles` filter do not
exist. Verify yours before assuming otherwise:

    ffmpeg -hide_banner -filters | grep -iE "subtitles|drawtext"

Burn-in therefore rasterizes each caption card to a transparent PNG with Pillow
and composites it with the `overlay` filter, which every ffmpeg build has.
Cards are cut at scene granularity and wrapped to two lines.
"""
from __future__ import annotations

import re
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .. import config
from ..manifest import Project


def _available_text_px(w: int) -> int:
    """Usable text width: full frame width minus side-safe margins."""
    return int(w * (1.0 - 2.0 * config.CAPTION_SIDE_MARGIN))


def _chars_per_line(px: int, font: ImageFont.FreeTypeFont, avail_px: int) -> int:
    """Estimate how many chars fit one line at this font within avail_px.

    Char-based wrapping is only safe if the budget tracks the real glyph
    width for the current font size AND the (narrower) frame dimension.
    A fixed 42-char budget overflows on 9:16, where the frame is 1080 wide
    but the height-derived font is large — the line runs off both edges.
    """
    sample = "The quick brown fox jumps over the lazy dog 0123456789"
    total = font.getlength(sample)
    avg = total / len(sample)
    if avg <= 0:
        return 20
    # 1.05 safety factor for proportional-width variance across cues
    return max(8, int(avail_px / (avg * 1.05)))


def _max_chars(proj: Project) -> int:
    w, h = proj.size
    base_px = max(18, int(h * config.CAPTION_REL_SIZE))
    return _chars_per_line(base_px, _font(base_px), _available_text_px(w))


def _wrap_px(text: str, font: ImageFont.FreeTypeFont, avail_px: int) -> list[str]:
    """Wrap by measured pixel width (not chars) so a line can never exceed
    the frame. Greedy word-pack; guaranteed to fit within avail_px."""
    words = text.split()
    if not words:
        return [text]
    lines, cur = [], ""
    for word in words:
        cand = (cur + " " + word).strip()
        if cur and font.getlength(cand) > avail_px:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def _ts(t: float, comma: bool = True) -> str:
    h = int(t // 3600); m = int(t % 3600 // 60); s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    if ms == 1000:
        s, ms = s + 1, 0
    sep = "," if comma else "."
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


MIN_CUE = 0.9          # seconds; anything shorter is unreadable
MAX_CUE_LINES = 2      # cards render two lines — cues must fit in that


def _split_readable(text: str, max_chars: int) -> list[str]:
    """Break a scene's narration into cues that FIT ON A CARD.

    Two traps this exists to avoid:
      * wrapping to more than MAX_CUE_LINES silently truncates the card, so a
        chunk of narration disappears from the burned-in captions while the
        voice still says it;
      * naive character-width wrapping produces orphan cues like "." which
        flash for a third of a second.

    So: split on clause boundaries first, then pack clauses into cues that wrap
    to at most two lines, and fold any runt back into its neighbour.

    `max_chars` is the per-line character budget derived from the actual frame
    width + font (see `_max_chars`), not a fixed constant — that is what kept
    captions from spilling off 9:16 frames.
    """
    clauses = [c.strip() for c in re.split(r"(?<=[.,;:!?])\s+", text.strip()) if c.strip()]
    cues, cur = [], ""
    for c in clauses:
        cand = (cur + " " + c).strip()
        if cur and len(textwrap.wrap(cand, max_chars)) > MAX_CUE_LINES:
            cues.append(cur)
            cur = c
        else:
            cur = cand
        # a single clause longer than a card must be hard-split
        while len(textwrap.wrap(cur, max_chars)) > MAX_CUE_LINES:
            head = textwrap.wrap(cur, max_chars)[:MAX_CUE_LINES]
            cues.append(" ".join(head))
            cur = cur[len(" ".join(head)):].strip()
    if cur:
        cues.append(cur)
    # fold runts (bare punctuation, single short word) into the previous cue
    cleaned: list[str] = []
    for c in cues:
        if cleaned and (len(c) <= 2 or not re.search(r"[A-Za-z0-9]", c)):
            cleaned[-1] = (cleaned[-1] + " " + c).strip()
        else:
            cleaned.append(c)
    return cleaned or [text]


def _cues(proj: Project) -> list[tuple[float, float, str]]:
    """Split each scene into readable caption cues at its own pace."""
    cues, t = [], 0.0
    max_chars = _max_chars(proj)
    for sc in proj.scenes:
        text = sc.narration.strip()
        dur = max(0.2, sc.duration)
        if not text:
            t += dur
            continue
        chunks = _split_readable(text, max_chars)
        # weight each cue's screen time by its share of the scene's characters
        total_chars = sum(len(c) for c in chunks) or 1
        start = t
        for i, c in enumerate(chunks):
            share = dur * (len(c) / total_chars)
            end = (t + dur) if i == len(chunks) - 1 else (start + share)
            cues.append((start, end, c))
            start = end
        t += dur
    # merge any cue that is still too short to read
    merged: list[tuple[float, float, str]] = []
    for a, b, text in cues:
        if merged and (b - a) < MIN_CUE:
            pa, _pb, pt = merged[-1]
            merged[-1] = (pa, b, (pt + " " + text).strip())
        else:
            merged.append((a, b, text))
    return merged


def write_srt(proj: Project) -> Path:
    out = proj.captions_dir / "captions.srt"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    max_chars = _max_chars(proj)
    for i, (a, b, text) in enumerate(_cues(proj), 1):
        lines += [str(i), f"{_ts(a)} --> {_ts(b)}",
                  "\n".join(textwrap.wrap(text, max_chars)), ""]
    out.write_text("\n".join(lines))
    return out


def write_vtt(proj: Project) -> Path:
    out = proj.captions_dir / "captions.vtt"
    lines = ["WEBVTT", ""]
    max_chars = _max_chars(proj)
    for a, b, text in _cues(proj):
        lines += [f"{_ts(a, False)} --> {_ts(b, False)}",
                  "\n".join(textwrap.wrap(text, max_chars)), ""]
    out.write_text("\n".join(lines))
    return out


def _font(px: int) -> ImageFont.FreeTypeFont:
    for p in [config.CAPTION_FONT, *config.CAPTION_FONT_FALLBACKS]:
        try:
            return ImageFont.truetype(str(p), px)
        except Exception:
            continue
    return ImageFont.load_default()


def render_cards(proj: Project) -> list[tuple[float, float, Path]]:
    """One transparent PNG per cue, sized to the output frame.

    Returned as (start, end, path) so the renderer can time each overlay.

    Every caption line is wrapped by MEASURED pixel width against the actual
    font and frame, so text can never run off the left/right edges — this is
    what broke 9:16 (tall frame -> large height-derived font, but only 1080px
    wide, so a char-based wrap spilled past both sides and was clipped).
    """
    w, h = proj.size
    base_px = max(18, int(h * config.CAPTION_REL_SIZE))
    avail_px = _available_text_px(w)
    outdir = proj.captions_dir / "cards"
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob("*.png"):
        old.unlink()

    made = []
    for i, (a, b, text) in enumerate(_cues(proj)):
        # Per-cue local state. Sizing must NOT leak between cues: shrinking once
        # for a long line used to permanently shrink every caption after it.
        px, font = base_px, _font(base_px)
        lines = _wrap_px(text, font, avail_px)
        if len(lines) > MAX_CUE_LINES:
            # _split_readable should have prevented this. Shrink to fit rather
            # than drop words the narrator is about to say.
            px = max(14, int(base_px * MAX_CUE_LINES / len(lines)))
            font = _font(px)
            lines = _wrap_px(text, font, avail_px)
        # Final guard: if a single very long token still exceeds avail_px,
        # shrink the font until the longest line (plus plate padding) fits
        # the frame width. The plate adds pad_x on each side, so text must
        # stay ~2*pad_x inside avail_px or the dark bar itself gets clipped.
        while px > 14:
            widest = max((font.getlength(ln) for ln in lines), default=0)
            pad_x = int(px * 0.7)
            if widest + 2 * pad_x <= avail_px:
                break
            px -= 2
            font = _font(px)
            lines = _wrap_px(text, font, avail_px)

        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        line_h = int(px * 1.28)
        block_h = line_h * len(lines)
        y = h - int(h * config.CAPTION_BOTTOM_MARGIN) - block_h

        widest = max((d.textlength(ln, font=font) for ln in lines), default=0)
        pad_x, pad_y = int(px * 0.7), int(px * 0.45)
        d.rounded_rectangle(
            [(w - widest) / 2 - pad_x, y - pad_y,
             (w + widest) / 2 + pad_x, y + block_h + pad_y],
            radius=int(px * 0.35), fill=(0, 0, 0, 165))

        for ln in lines:
            tw = d.textlength(ln, font=font)
            # stroke keeps it legible over a bright photo even if the plate fails
            d.text(((w - tw) / 2, y), ln, font=font, fill=(255, 255, 255, 255),
                   stroke_width=max(2, px // 14), stroke_fill=(0, 0, 0, 235))
            y += line_h
        p = outdir / f"cue_{i:04d}.png"
        img.save(p)
        made.append((a, b, p))
    return made


def run(project_id: str) -> Project:
    proj = Project.load(project_id)
    if not proj.scenes:
        raise SystemExit("no scenes to caption")
    srt, vtt = write_srt(proj), write_vtt(proj)
    cards = render_cards(proj)
    proj.note(f"captions: {len(cards)} cues -> srt/vtt/cards")
    proj.save()
    print(f"[captions] {len(cards)} cues -> {srt.name}, {vtt.name}, "
          f"{len(cards)} burn-in cards")
    return proj
