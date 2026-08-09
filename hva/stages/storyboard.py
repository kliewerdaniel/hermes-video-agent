"""Stage 2 — storyboard: script -> scenes (shot list).

Each scene carries everything a downstream stage needs: the narration line, a
visual concept, search terms for the research stage, and an image prompt for a
generative backend. If the LLM is unavailable we still produce a usable shot
list by splitting on sentence boundaries — the narration is the human's words
either way, so a deterministic split is honest, just less clever about visuals.
"""
from __future__ import annotations

import re

from ..manifest import Project, Scene
from ..providers import llm
from .script import WORDS_PER_SECOND

SYSTEM = """You are a video storyboard artist turning narration into a shot list.
For each shot you decide what the viewer SEES while a specific line is spoken.

Rules:
- Cover the narration completely and in order. Do not drop or reorder sentences.
- Every scene's "narration" must be an exact contiguous span of the script.
- "visual_concept" describes a single concrete photographable image.
- "search_terms" are 2-4 short phrases someone would type into a photo search.
- "image_prompt" is a photographic prompt for a text-to-image model. Never ask
  for words, text, signage, logos, readable screens, or numbers in the image.
- Prefer real-world documentary imagery over abstract metaphor."""


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _fallback(proj: Project, target_scenes: int) -> list[dict]:
    sents = _sentences(proj.script)
    if not sents:
        raise SystemExit("no script to storyboard")
    per = max(1, round(len(sents) / max(1, target_scenes)))
    groups, cur = [], []
    for s in sents:
        cur.append(s)
        if len(cur) >= per:
            groups.append(" ".join(cur))
            cur = []
    if cur:
        if groups:
            groups[-1] += " " + " ".join(cur)
        else:
            groups.append(" ".join(cur))
    out = []
    for g in groups:
        kw = _keywords(g)
        out.append({
            "narration": g,
            "visual_concept": f"A documentary photograph illustrating: {g}",
            "composition": "medium shot",
            "search_terms": kw,
            "image_prompt": (
                f"documentary photograph, {', '.join(kw)}, natural light, "
                "shallow depth of field, 35mm, high detail, "
                "absolutely no text, no writing, no signage, no logos, no numbers"),
        })
    return out


_STOP = set("the a an and or but of to in on at for with from by is are was were "
            "it its this that these those you your we our they their he she as "
            "not so if then than there here what which who how why when about "
            "into over under more most just can will would could should".split())


def _keywords(text: str, n: int = 3) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z'-]+", text.lower())
    seen, out = set(), []
    for w in words:
        if w in _STOP or len(w) < 4 or w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(out) >= n:
            break
    return out or ["abstract", "concept"]


def build(project_id: str, *, scene_count: int = 0, use_llm: bool = True) -> Project:
    proj = Project.load(project_id)
    if not proj.script.strip():
        raise SystemExit("project has no script — run the script stage first")

    words = len(proj.script.split())
    est = words / WORDS_PER_SECOND
    target = scene_count or max(3, min(12, round(est / 5)))

    data = None
    if use_llm:
        user = (
            f"Title: {proj.title}\nAspect ratio: {proj.aspect}\n"
            f"Target: about {target} scenes covering ~{est:.0f} seconds.\n\n"
            f"SCRIPT:\n{proj.script}\n\n"
            'Return JSON only: {"scenes":[{"narration":"","visual_concept":"",'
            '"composition":"","search_terms":[""],"image_prompt":""}]}'
        )
        try:
            data = llm.chat_json(SYSTEM, user, temperature=0.5, max_tokens=9000)
        except Exception as e:
            print(f"[storyboard] LLM unavailable ({e}); using deterministic split")

    raw = (data or {}).get("scenes") if isinstance(data, dict) else data
    if not raw:
        raw = _fallback(proj, target)
        source = "deterministic split"
    else:
        source = "LLM"

    scenes: list[Scene] = []
    for i, s in enumerate(raw, 1):
        narration = (s.get("narration") or "").strip()
        if not narration:
            continue
        est_dur = round(len(narration.split()) / WORDS_PER_SECOND, 2)
        scenes.append(Scene(
            id=f"scene_{i:03d}",
            narration=narration,
            visual_concept=(s.get("visual_concept") or "").strip(),
            composition=(s.get("composition") or "medium shot").strip(),
            search_terms=[t.strip() for t in (s.get("search_terms") or []) if t.strip()]
                          or _keywords(narration),
            image_prompt=(s.get("image_prompt") or "").strip(),
            motion="in" if i % 2 else "out",
            duration=est_dur,
        ))
    if not scenes:
        raise SystemExit("storyboard produced no scenes")

    proj.scenes = scenes
    proj.note(f"storyboard: {len(scenes)} scenes via {source}")
    proj.save()
    print(f"[storyboard] {len(scenes)} scenes via {source} "
          f"(~{proj.total_duration:.0f}s estimated)")
    return proj


def regenerate_scene(project_id: str, scene_id: str, direction: str = "") -> Project:
    """Re-plan ONE scene without touching the rest — the core HITL affordance."""
    proj = Project.load(project_id)
    sc = proj.scene(scene_id)
    user = (
        f"Video title: {proj.title}\nNarration for this single shot:\n{sc.narration}\n\n"
        f"Current visual concept: {sc.visual_concept or '(none)'}\n"
        f"Human direction: {direction or 'propose a stronger, more concrete visual'}\n\n"
        'Return JSON only: {"visual_concept":"","composition":"",'
        '"search_terms":[""],"image_prompt":""}'
    )
    try:
        d = llm.chat_json(SYSTEM, user, temperature=0.8, max_tokens=4000)
    except Exception as e:
        raise SystemExit(f"cannot re-plan scene without the LLM: {e}")
    sc.visual_concept = d.get("visual_concept", sc.visual_concept)
    sc.composition = d.get("composition", sc.composition)
    sc.search_terms = d.get("search_terms", sc.search_terms) or sc.search_terms
    sc.image_prompt = d.get("image_prompt", sc.image_prompt)
    sc.status = "needs_review"
    proj.note(f"{scene_id}: re-planned ({direction[:60]})")
    proj.save()
    return proj
