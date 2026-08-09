"""Stage 3 — visual research. The stage where the agent gets eyes.

Instead of asking a language model "what image should I use here?", this stage
goes looking. Three source adapters, tried in order until a scene has enough
candidates:

  1. ``openverse_api``       — api.openverse.org, keyless, returns full licence
                               metadata. Fast and reliable; the workhorse.
  2. ``wikimedia_playwright``— real Chromium driving Commons MediaSearch and
                               reading the rendered result grid.
  3. ``openverse_playwright``— the Openverse website in a real browser.
                               NOTE: openverse.org sits behind Cloudflare and
                               returns 403 to *headless* Chromium; it loads fine
                               headful. Off by default, enable with
                               HVA_HEADFUL=1 (a visible window will open).

Every candidate records source_url, creator, licence and licence URL.
Provenance is a hard requirement — an asset we cannot attribute is an asset we
cannot ship in a client's video.
"""
from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import time
import urllib.parse
from pathlib import Path

import requests

from .. import config
from ..manifest import Candidate, Project

_BROWSER_ARGS = ["--disable-blink-features=AutomationControlled"]
HEADFUL = os.environ.get("HVA_HEADFUL", "") not in ("", "0", "false")

# Openverse licence codes -> human labels
_LICENCE_LABEL = {
    "cc0": "CC0 (public domain dedication)",
    "pdm": "Public Domain Mark",
    "by": "CC BY", "by-sa": "CC BY-SA", "by-nc": "CC BY-NC",
    "by-nd": "CC BY-ND", "by-nc-sa": "CC BY-NC-SA", "by-nc-nd": "CC BY-NC-ND",
}
# Licences that permit commercial use — what a paid client job actually needs.
COMMERCIAL_OK = {"cc0", "pdm", "by", "by-sa"}
# NoDerivatives is the trap: Openverse's "commercial" filter happily returns
# BY-ND, and ND *is* commercially usable — but this pipeline crops, scales and
# Ken-Burns every still, which is exactly what "no derivatives" forbids. Any
# editing pipeline must exclude ND on top of the commercial filter.
NO_DERIVATIVES = {"by-nd", "by-nc-nd"}


def _cid(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def _download(url: str, dest_dir: Path, stem: str) -> Path | None:
    try:
        r = requests.get(url, timeout=45, headers={"User-Agent": config.USER_AGENT})
        r.raise_for_status()
    except Exception:
        return None
    ctype = r.headers.get("content-type", "").split(";")[0]
    ext = mimetypes.guess_extension(ctype) or Path(urllib.parse.urlparse(url).path).suffix
    if ext in (".jpe", "", None):
        ext = ".jpg"
    if ext.lower() not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{stem}{ext}"
    dest.write_bytes(r.content)
    return dest


def _verify_image(path: Path, min_px: int = 500) -> tuple[int, int] | None:
    """Reject corrupt files, icons and thumbnails too small to fill a frame."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            w, h = im.size
            if im.mode not in ("RGB", "L"):
                im.convert("RGB").save(path)
    except Exception:
        return None
    if max(w, h) < min_px:
        return None
    return w, h


# ------------------------------------------------------------- openverse API
# Openverse's anonymous tier is rate limited (100 req/day burst-limited per
# minute); pooling several queries per scene hits it fast and every call then
# 429s, which looks exactly like "the search found nothing". Throttle, honour
# Retry-After, and cache identical queries for the process lifetime.
_OV_MIN_INTERVAL = 3.0
_ov_last_call = 0.0
_ov_cache: dict[tuple, list[dict]] = {}


def _openverse_api(query: str, limit: int, commercial_only: bool,
                   _retries: int = 2) -> list[dict]:
    global _ov_last_call
    key = (query.lower(), commercial_only)
    if key in _ov_cache:
        return _ov_cache[key]

    params = {"q": query, "page_size": max(limit * 2, 12), "mature": "false"}
    if commercial_only:
        params["license_type"] = "commercial"

    for attempt in range(_retries + 1):
        wait = _OV_MIN_INTERVAL - (time.time() - _ov_last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            r = requests.get("https://api.openverse.org/v1/images/", params=params,
                             timeout=30, headers={"User-Agent": config.USER_AGENT})
            _ov_last_call = time.time()
            if r.status_code == 429:
                delay = float(r.headers.get("Retry-After", 0) or (4 * (attempt + 1)))
                if attempt < _retries:
                    print(f"[research] openverse rate-limited, waiting {delay:.0f}s")
                    time.sleep(min(delay, 30))
                    continue
                print("[research] openverse still rate-limited; skipping this query")
                return []
            r.raise_for_status()
            results = r.json().get("results", [])
            break
        except Exception as e:
            _ov_last_call = time.time()
            if attempt >= _retries:
                print(f"[research] openverse api failed: {e}")
                return []
            time.sleep(2 * (attempt + 1))
    else:
        return []

    out: list[dict] = []
    for it in results:
        code = (it.get("license") or "").lower()
        if commercial_only and code in NO_DERIVATIVES:
            continue  # cropping/zooming a still is a derivative work
        out.append({
            "direct": it.get("url", ""),
            "page": it.get("foreign_landing_url") or it.get("detail_url", ""),
            "title": (it.get("title") or "")[:120],
            "creator": (it.get("creator") or "")[:80],
            "license": _LICENCE_LABEL.get(code, code.upper() or "see source"),
            "license_code": code,
            "license_url": it.get("license_url", ""),
            "provider": f"openverse/{it.get('source', '')}".rstrip("/"),
            "width": it.get("width") or 0, "height": it.get("height") or 0,
        })
    _ov_cache[key] = out
    return out


# ------------------------------------------------------- playwright scrapers
def _wikimedia_playwright(page, query: str, limit: int) -> list[dict]:
    url = ("https://commons.wikimedia.org/w/index.php?search="
           + urllib.parse.quote(query) + "&title=Special:MediaSearch&type=image")
    page.goto(url, wait_until="domcontentloaded", timeout=config.PLAYWRIGHT_TIMEOUT)
    try:
        page.wait_for_selector("a.sdms-image-result", timeout=15000)
    except Exception:
        return []
    page.wait_for_timeout(900)
    items = page.evaluate(
        """() => Array.from(document.querySelectorAll('a.sdms-image-result'))
              .map(a => { const i = a.querySelector('img');
                          return i ? {thumb: i.src, page: a.href, title: i.alt || ''} : null; })
              .filter(Boolean)"""
    )
    out = []
    for it in items[:limit]:
        out.append({**it, "direct": _upscale_wikimedia(it["thumb"]),
                    "license": "Wikimedia Commons — check file page",
                    "license_code": "", "license_url": it["page"],
                    "creator": "", "provider": "wikimedia"})
    return out


def _openverse_playwright(page, query: str, limit: int) -> list[dict]:
    """Only usable headful — Cloudflare 403s headless Chromium here."""
    url = "https://openverse.org/search/image?q=" + urllib.parse.quote(query)
    resp = page.goto(url, wait_until="domcontentloaded",
                     timeout=config.PLAYWRIGHT_TIMEOUT)
    if resp and resp.status == 403:
        print("[research] openverse.org 403 (Cloudflare) — headless browsing blocked")
        return []
    page.wait_for_timeout(3500)
    items = page.evaluate(
        """() => { const out = [], seen = new Set();
            document.querySelectorAll("a[href*='/image/']").forEach(a => {
                const img = a.querySelector('img');
                if (!img || !img.src) return;
                const k = a.href.split('?')[0];
                if (seen.has(k)) return; seen.add(k);
                out.push({thumb: img.src, page: a.href, title: img.alt || ''}); });
            return out; }"""
    )
    return [{**it, "direct": it["thumb"], "license": "see source page",
             "license_code": "", "license_url": it["page"], "creator": "",
             "provider": "openverse-web"} for it in items[:limit]]


def _upscale_wikimedia(thumb: str) -> str:
    m = re.match(r"(https://upload\.wikimedia\.org/wikipedia/commons)/thumb/(.+)/\d+px-[^/]+$",
                 thumb)
    return f"{m.group(1)}/{m.group(2)}" if m else thumb


# --------------------------------------------------------------------- stage
def _materialize(proj: Project, sc, raw: list[dict], limit: int) -> list[Candidate]:
    dest_dir = proj.assets_dir / sc.id
    have = {c.direct_url for c in sc.candidates}
    found: list[Candidate] = []
    for it in raw:
        direct = it.get("direct")
        if not direct or direct in have:
            continue
        cid = _cid(direct)
        path = _download(direct, dest_dir, cid)
        if path is None:
            continue
        dims = _verify_image(path)
        if dims is None:
            path.unlink(missing_ok=True)
            continue
        code = it.get("license_code", "")
        note = "" if not code else (
            " · commercial-safe" if code in COMMERCIAL_OK else " · non-commercial licence")
        found.append(Candidate(
            id=cid, kind="image",
            local_path=str(path.relative_to(proj.dir)),
            thumb_path=str(path.relative_to(proj.dir)),
            source_url=it.get("page", ""), direct_url=direct,
            title=it.get("title", ""), creator=it.get("creator", ""),
            license=it.get("license", ""), license_url=it.get("license_url", ""),
            provider=it.get("provider", ""),
            reason=f"found on {it.get('provider','')} for this scene's search terms{note}",
            width=dims[0], height=dims[1]))
        have.add(direct)
        if len(found) >= limit:
            break
    return found


_STOP_Q = set("the a an and or of to in on at for with from by is are was were it "
              "its this that you your we our they their he she as not so if then "
              "than there here what which who how why when about into over under "
              "more most just can will would could should like".split())


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in _STOP_Q}


def _score(item: dict, scene_tokens: set[str], query: str) -> float:
    """Rank a search hit against what the scene is actually about.

    The first result an API returns is frequently junk for our purposes — a
    query for "close up smartphone" returned a 3D-printed phone stand, and
    "eyes reflecting phone light" returned a toy robot. Position one is what
    the UI pre-selects, so ranking is not cosmetic.

    Three signals, in order of weight:
      * title overlap with the query terms (did we get what we asked for)
      * title overlap with the scene's own vocabulary (is it on-topic)
      * source class — curated stock libraries are far more likely to yield a
        usable editorial image than an arbitrary personal Flickr upload.
    """
    q = _tokens(query)
    title_tokens = _tokens(item.get("title", ""))
    overlap_query = len(title_tokens & q) / max(1, len(q))
    overlap_scene = (len(title_tokens & scene_tokens) /
                     max(1, len(scene_tokens))) if title_tokens else 0.0
    src = (item.get("provider") or "").lower()
    source_bonus = 0.0
    for good in ("stocksnap", "pixabay", "rawpixel", "unsplash", "wikimedia",
                 "nappy", "sciencemuseum", "statensmuseum"):
        if good in src:
            source_bonus = 0.45
            break
    w, h = item.get("width") or 0, item.get("height") or 0
    quality = 0.2 if (w >= 1200 and h >= 700) else (0.1 if w >= 800 else 0.0)
    landscape = 0.1 if (w and h and 1.2 <= w / h <= 2.2) else 0.0
    return overlap_query * 2.0 + overlap_scene * 1.2 + source_bonus + quality + landscape


def _queries(sc, override: str) -> list[str]:
    """One query per search term — NOT all of them joined.

    Openverse (and Commons) AND every word, so "thumb swiping phone close up
    smartphone scrolling screen" matches literally nothing while each of its
    parts returns a full page. Search terms are alternatives, not a filter
    stack. Ordered broad-enough-first, with a single-noun backstop.
    """
    if override:
        return [override]
    qs = [t.strip() for t in sc.search_terms if t.strip()]
    # a two-word cut of the concept is a decent last resort
    if sc.visual_concept:
        words = [w for w in re.findall(r"[a-zA-Z]{4,}", sc.visual_concept)][:2]
        if words:
            qs.append(" ".join(words))
    seen, out = set(), []
    for q in qs:
        k = q.lower()
        if k not in seen:
            seen.add(k)
            out.append(q)
    # Cap the fan-out: Openverse's anonymous tier rate-limits hard, and three
    # queries x N scenes trips it mid-run. Two well-chosen terms plus the
    # Wikimedia browser fallback covers a scene without burning the budget.
    return (out or ["abstract background"])[:2]


def research_scene(proj: Project, scene_id: str, *, limit: int = 0,
                   query_override: str = "", browser=None,
                   commercial_only: bool = True) -> list[Candidate]:
    sc = proj.scene(scene_id)
    limit = limit or config.CANDIDATES_PER_SCENE
    queries = _queries(sc, query_override)
    query = queries[0]

    found: list[Candidate] = []
    scene_tokens = _tokens(f"{sc.narration} {sc.visual_concept} "
                           f"{' '.join(sc.search_terms)}")

    # Pool every query's hits and rank the POOL, rather than taking each query's
    # top-N in turn. Term 3 often has the best image for the scene; ordering by
    # which query found it would bury it below term 1's mediocre first result.
    pool: list[dict] = []
    seen_urls = set()

    def _pool_from(commercial: bool) -> None:
        for q in queries:
            for it in _openverse_api(q, max(6, limit * 2), commercial):
                u = it.get("direct")
                if not u or u in seen_urls:
                    continue
                seen_urls.add(u)
                it["_q"] = q
                it["_score"] = _score(it, scene_tokens, q)
                pool.append(it)

    _pool_from(commercial_only)
    # Openverse's commercial-only filter returns zero hits for some niche
    # queries (e.g. "empty corporate office at night"). Backfill from the
    # full catalogue so a scene is never left with no candidates at all.
    if len(pool) < limit and commercial_only:
        _pool_from(False)
    pool.sort(key=lambda it: it["_score"], reverse=True)
    found = _materialize(proj, sc, pool, limit)
    for c, it in zip(found, pool):
        c.reason = (f"ranked #{pool.index(it) + 1} for {it['_q']!r} "
                    f"(score {it['_score']:.2f}) on {c.provider}")

    if len(found) < limit:
        need = limit - len(found)
        page, owns = None, False
        try:
            if browser is not None:
                page = browser.new_page(user_agent=config.USER_AGENT,
                                        viewport={"width": 1440, "height": 900})
            else:
                from playwright.sync_api import sync_playwright
                pw = sync_playwright().start()
                b = pw.chromium.launch(headless=not HEADFUL, args=_BROWSER_ARGS)
                page = b.new_page(user_agent=config.USER_AGENT,
                                  viewport={"width": 1440, "height": 900})
                owns = (pw, b)
            raw2 = _wikimedia_playwright(page, query, need)
            if HEADFUL and len(raw2) < need:
                raw2 += _openverse_playwright(page, query, need - len(raw2))
            found += _materialize(proj, sc, raw2, need)
        except Exception as e:
            print(f"[research] browser pass failed for {query!r}: {e}")
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass
            if owns:
                owns[1].close(); owns[0].stop()

    sc.candidates.extend(found)
    if sc.selected is None and sc.candidates:
        sc.selected = sc.candidates[0].id
    proj.note(f"{sc.id}: +{len(found)} candidates for {query!r}")
    proj.save()
    return found


def run(project_id: str, *, limit: int = 0, only: list[str] | None = None,
        commercial_only: bool = True) -> Project:
    from playwright.sync_api import sync_playwright

    proj = Project.load(project_id)
    targets = [s.id for s in proj.scenes if (not only or s.id in only)]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not HEADFUL, args=_BROWSER_ARGS)
        try:
            for sid in targets:
                sc = proj.scene(sid)
                print(f"[research] {sid}: {' | '.join(sc.search_terms[:3])}")
                got = research_scene(proj, sid, limit=limit, browser=browser,
                                     commercial_only=commercial_only)
                print(f"[research]   -> {len(got)} new candidate(s), "
                      f"{len(sc.candidates)} total")
        finally:
            browser.close()
    return Project.load(project_id)
