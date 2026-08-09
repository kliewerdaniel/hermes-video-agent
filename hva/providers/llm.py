"""LLM facade used by the pipeline stages (script / storyboard / research).

This thin layer delegates to the active :mod:`hva.providers.inference`
provider. It keeps the simple ``chat`` / ``chat_json`` surface the stages
already depend on, so the rest of the app does NOT change — only the backend
that actually talks to a model did.

The selected provider is whatever ``InferenceConfig`` resolved to (local by
default). We never silently fall back to a cloud provider when the operator
picked local; if local is down, callers get ``LLMUnavailable`` and surface it.
"""
from __future__ import annotations

import json
import re

from .. import config
from . import inference as inf
from .inference import InferenceError, InferenceProvider
from .inference_config import InferenceConfig

# Kept for API/back-compat: the rest of the app still raises LLMUnavailable.
# We map a normalized InferenceError onto it so the UI story is unchanged.
class LLMUnavailable(RuntimeError):
    pass


def _provider() -> InferenceProvider:
    return InferenceConfig.load().active_provider()


def _wrap(fn):
    try:
        return fn()
    except InferenceError as e:
        # Surface as the legacy error type with a clean message.
        raise LLMUnavailable(e.message) from e


def available() -> bool:
    try:
        p = _provider()
        # A cheap reachability probe: list models if possible, else a tiny gen.
        p.list_models()
        return True
    except Exception:
        return False


def model_name() -> str:
    try:
        p = _provider()
        cfg = InferenceConfig.load()
        if cfg.provider_settings().get("model"):
            return cfg.provider_settings()["model"]
        models = p.list_models()
        return models[0].id if models else config.LLM_MODEL
    except Exception:
        return config.LLM_MODEL


def chat(system: str, user: str, *, temperature: float = 0.7,
         max_tokens: int = 4096) -> str:
    """One chat turn. Returns the assistant's visible content."""
    msgs = []
    if system:
        msgs.append(inf.ConversationMessage("system", system))
    msgs.append(inf.ConversationMessage("user", user))
    return _wrap(lambda: _provider().generate(
        msgs, temperature=temperature, max_tokens=max_tokens))


def _extract_json(text: str):
    """Pull the first JSON object/array out of a model reply."""
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1)
    text = text.strip()
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start == -1:
            continue
        depth, in_str, esc = 0, False, False
        for i, ch in enumerate(text[start:], start):
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
    raise ValueError(f"no parseable JSON in model reply: {text[:400]}")


def chat_json(system: str, user: str, *, temperature: float = 0.4,
              max_tokens: int = 8000, retries: int = 2):
    """Chat and parse JSON, retrying with a stricter nudge on failure."""
    last = None
    for attempt in range(retries + 1):
        extra = "" if attempt == 0 else (
            "\n\nYour previous reply was not valid JSON. Reply with RAW JSON ONLY. "
            "No prose, no markdown fences.")
        budget = max_tokens * (attempt + 1)
        raw = chat(system + extra, user, temperature=temperature,
                   max_tokens=budget)
        try:
            return _extract_json(raw)
        except ValueError as e:
            last = e
    raise LLMUnavailable(f"model never returned valid JSON: {last}")
