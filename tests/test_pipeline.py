"""Unit tests that do not need the network, an LLM, or a GPU.

Run: env -u PYTHONPATH -u PYTHONHOME ./.venv/bin/python -m pytest tests -q
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

TMP = tempfile.mkdtemp(prefix="hva-test-")
os.environ["HVA_PROJECTS"] = TMP

from hva import checks, config  # noqa: E402
from hva.manifest import Candidate, Project, Scene, slugify  # noqa: E402
from hva.stages import captions as captions_stage  # noqa: E402
from hva.stages import research, storyboard  # noqa: E402


@pytest.fixture
def proj():
    p = Project.create("why people doomscroll", title="Doomscroll",
                       duration=30, project_id="t-doom")
    p.script = ("You are looking for a prize that never comes. "
                "Your thumb keeps pulling down on the glass. "
                "It feels just like a slot machine in a dark casino.")
    p.scenes = [
        Scene(id="scene_001", narration="You are looking for a prize that never comes.",
              duration=3.0, search_terms=["phone dark"]),
        Scene(id="scene_002", narration="Your thumb keeps pulling down on the glass.",
              duration=3.5, search_terms=["thumb scrolling"]),
    ]
    return p.save()


# ---------------------------------------------------------------- manifest
def test_slugify():
    assert slugify("Why You're STILL Scrolling!") == "why-you-re-still-scrolling"


def test_roundtrip_preserves_candidates(proj):
    proj.scenes[0].candidates.append(Candidate(id="c1", local_path="a.jpg",
                                               license="CC BY"))
    proj.scenes[0].selected = "c1"
    proj.save()
    again = Project.load(proj.id)
    assert again.scenes[0].selected_candidate.license == "CC BY"
    assert again.total_duration == pytest.approx(6.5)


def test_approval_gates(proj):
    with pytest.raises(PermissionError):
        proj.require("script")
    proj.approve("script")
    proj.require("script")           # no raise
    assert Project.load(proj.id).approvals["script"] is True


def test_reopen_semantics(proj):
    proj.approve("script"); proj.approve("scenes")
    assert proj.stage == "scenes"


# ---------------------------------------------------------------- captions
def test_cues_cover_every_word(proj):
    """The defect this guards: two-line truncation silently dropped narration."""
    assert checks.check_captions_complete(proj) == []


def test_no_runt_cues(proj):
    long_scene = Scene(
        id="scene_003", duration=9.0,
        narration=("Engineers designed this feed to exploit your brain's craving "
                   "for novelty, and every single swipe is a high-stakes gamble."))
    proj.scenes.append(long_scene)
    proj.save()
    cues = captions_stage._cues(proj)
    assert all(b - a >= 0.4 for a, b, _ in cues), "a cue is too short to read"
    assert all(t.strip(" .,") for _, _, t in cues), "bare-punctuation cue emitted"


def test_cues_fit_two_lines(proj):
    import textwrap
    for _, _, text in captions_stage._cues(proj):
        assert len(textwrap.wrap(text, config.CAPTION_MAX_CHARS)) <= 2


def test_cue_track_matches_video_length(proj):
    assert checks.check_cue_timing(proj) == []


def test_srt_written(proj):
    out = captions_stage.write_srt(proj)
    body = out.read_text()
    assert "-->" in body and "prize that never" in body


# ---------------------------------------------------------------- research
def test_queries_are_separate_not_joined():
    """Joining search terms ANDs them and matches nothing — the real bug."""
    sc = Scene(id="s", search_terms=["thumb scrolling phone", "macro smartphone"],
               visual_concept="Extreme close up of a hand")
    qs = research._queries(sc, "")
    assert "thumb scrolling phone" in qs
    assert not any(len(q.split()) > 5 for q in qs)


def test_query_override_wins():
    sc = Scene(id="s", search_terms=["a", "b"])
    assert research._queries(sc, "explicit") == ["explicit"]


def test_scoring_prefers_on_topic_title():
    tokens = research._tokens("a person scrolling a phone in the dark")
    good = {"title": "person scrolling phone at night", "provider": "openverse/pixabay",
            "width": 1600, "height": 1000}
    bad = {"title": "3D printed phone stand", "provider": "openverse/thingiverse",
           "width": 600, "height": 600}
    assert (research._score(good, tokens, "scrolling phone")
            > research._score(bad, tokens, "scrolling phone"))


def test_no_derivatives_licences_are_excluded():
    """Ken Burns crops the still, which ND forbids."""
    assert "by-nd" in research.NO_DERIVATIVES
    assert "by-nd" not in research.COMMERCIAL_OK


def test_licence_check_flags_nd(proj):
    proj.scenes[0].candidates.append(
        Candidate(id="x", local_path="a.jpg", license="CC BY-ND",
                  provider="openverse/flickr"))
    proj.scenes[0].selected = "x"
    problems = checks.check_licences(proj)
    assert any("forbids derivatives" in p for p in problems)


# ---------------------------------------------------------------- storyboard
def test_storyboard_fallback_covers_the_script(proj):
    raw = storyboard._fallback(proj, 2)
    joined = " ".join(s["narration"] for s in raw)
    for sentence in ("prize that never comes", "slot machine in a dark casino"):
        assert sentence in joined


def test_keywords_skip_stopwords():
    kw = storyboard._keywords("The person is looking at their glowing phone")
    assert "the" not in kw and len(kw) <= 3


# ---------------------------------------------------------------- llm parsing
def test_json_extraction_survives_fences_and_prose():
    from hva.providers.llm import _extract_json
    assert _extract_json('Sure!\n```json\n{"a": [1,2]}\n```\nHope that helps')["a"] == [1, 2]
    assert _extract_json('{"s": "a } brace in a string"}')["s"].endswith("string")
