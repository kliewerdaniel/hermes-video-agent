"""Provider-agnostic inference abstraction.

The application talks to this layer and *nothing else* about LLMs. Three
adapters ship today:

    LocalProvider     -> any OpenAI-compatible /v1 server (Ollama, llama.cpp,
                         vLLM, LM Studio, …). We deliberately do NOT name or
                         special-case any of them — "localhost:11434" is just
                         one possible OpenAI-compatible endpoint.
    GeminiProvider    -> Google Generative Language API (REST, not the SDK).
    OpenRouterProvider-> OpenRouter's OpenAI-compatible API.

Every adapter implements the same interface:

    generate(messages, **opts) -> str
    stream(messages, **opts)   -> Iterator[str]   (yielded token deltas)
    list_models()              -> list[ModelInfo]
    test_connection()          -> TestResult

Errors are normalized into InferenceError with a `category` so the UI can show
a useful message instead of "connection failed". Categories:
    auth | connection | timeout | model | rate_limit | context_length |
    provider | malformed | config
"""
from __future__ import annotations

import json
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator, Optional

import requests

from .. import config


# --------------------------------------------------------------------------- #
# Normalized error
# --------------------------------------------------------------------------- #
class InferenceError(Exception):
    """A normalized inference failure.

    `category` is one of the constants below and is safe to show to the user.
    `detail` is a human-readable message with NO secrets in it.
    """

    AUTH = "auth"
    CONNECTION = "connection"
    TIMEOUT = "timeout"
    MODEL = "model"
    RATE_LIMIT = "rate_limit"
    CONTEXT_LENGTH = "context_length"
    PROVIDER = "provider"
    MALFORMED = "malformed"
    CONFIG = "config"

    def __init__(self, category: str, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.category = category
        self.message = message
        self.status = status

    def __str__(self) -> str:  # never leak secrets — message is already safe
        return self.message


def _safe(msg: str) -> str:
    """Strip anything that looks like a key/token before it reaches the UI."""
    msg = re.sub(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", r"\1<redacted>", msg)
    msg = re.sub(r"(sk-[A-Za-z0-9]{4})[A-Za-z0-9]{12,}", r"\1<redacted>", msg)
    msg = re.sub(r"(AIza[0-9A-Za-z_\-]{4})[A-Za-z0-9\-_]{20,}", r"\1<redacted>", msg)
    return msg


# --------------------------------------------------------------------------- #
# Data shapes
# --------------------------------------------------------------------------- #
@dataclass
class ModelInfo:
    id: str
    label: str = ""
    description: str = ""
    free: bool = False       # OpenRouter: true when the model is free
    context_length: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label or self.id,
            "description": self.description,
            "free": self.free,
            "context_length": self.context_length,
        }


@dataclass
class TestResult:
    ok: bool
    provider: str
    model: str
    message: str = ""
    latency_ms: Optional[float] = None
    category: Optional[str] = None


@dataclass
class ConversationMessage:
    role: str          # "system" | "user" | "assistant"
    content: str


def _as_messages(system: str, user: str) -> list[ConversationMessage]:
    msgs = []
    if system:
        msgs.append(ConversationMessage("system", system))
    msgs.append(ConversationMessage("user", user))
    return msgs


# --------------------------------------------------------------------------- #
# Base adapter
# --------------------------------------------------------------------------- #
class InferenceProvider(ABC):
    """Common interface + shared helpers for every adapter."""

    #: short stable id used in config + the UI radio group
    id: str = "base"
    #: human label
    label: str = "Base"

    def __init__(self, model: str = "", api_key: str = "", **_extra):
        self.model = model
        self.api_key = api_key or ""

    # ---- required surface -------------------------------------------------
    @abstractmethod
    def generate(self, messages: list[ConversationMessage], *,
                 temperature: float = 0.7, max_tokens: int = 4096) -> str:
        ...

    @abstractmethod
    def stream(self, messages: list[ConversationMessage], *,
               temperature: float = 0.7, max_tokens: int = 4096) -> Iterator[str]:
        ...

    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        ...

    @abstractmethod
    def test_connection(self) -> TestResult:
        ...

    # ---- shared helpers ---------------------------------------------------
    def _require_model(self) -> str:
        if not self.model:
            raise InferenceError(
                InferenceError.CONFIG,
                "No model selected for this provider.")
        return self.model

    def _classify_http(self, exc: requests.RequestException) -> InferenceError:
        """Turn a requests exception / HTTPError into a normalized error."""
        if isinstance(exc, requests.exceptions.ConnectionError):
            return InferenceError(
                InferenceError.CONNECTION,
                "Could not reach the endpoint. Check the URL/port and that the "
                "server is running, then confirm CORS if this is a browser→local call.")
        if isinstance(exc, requests.exceptions.Timeout):
            return InferenceError(InferenceError.TIMEOUT,
                                  "The request timed out. The model may be too "
                                  "slow or the network is congested.")
        if isinstance(exc, requests.exceptions.HTTPError):
            resp = exc.response
            status = resp.status_code if resp is not None else None
            return self._classify_status(status, _body_text(resp))
        return InferenceError(InferenceError.PROVIDER,
                              _safe(f"Network error: {exc}"))

    def _classify_status(self, status: Optional[int], body: str) -> InferenceError:
        body = _safe(body or "")
        if status in (401, 403):
            return InferenceError(InferenceError.AUTH,
                                  "Authentication failed — check your API key.")
        if status == 404:
            return InferenceError(InferenceError.MODEL,
                                  "The model was not found on this provider. "
                                  "Pick an available model from the list.")
        if status == 408:
            return InferenceError(InferenceError.TIMEOUT, "Request timed out.")
        if status == 413 or "context" in body.lower() and "length" in body.lower():
            return InferenceError(InferenceError.CONTEXT_LENGTH,
                                  "Context length exceeded — the prompt is too long "
                                  "for this model.")
        if status == 429:
            return InferenceError(InferenceError.RATE_LIMIT,
                                  "Rate limited — wait a moment and retry.")
        if status and 500 <= status < 600:
            return InferenceError(InferenceError.PROVIDER,
                                  f"Provider error ({status}): {body[:200]}")
        if status == 400:
            if "model" in body.lower():
                return InferenceError(InferenceError.MODEL,
                                      f"Model error: {body[:200]}")
            return InferenceError(InferenceError.CONFIG,
                                  f"Bad request: {body[:200]}")
        return InferenceError(InferenceError.PROVIDER,
                              f"HTTP {status}: {body[:200]}")

    def _content_from_choice(self, choice: dict, msg: dict) -> str:
        """Return visible content, falling back to reasoning_content for
        reasoning models (gpt-oss, deepseek-r1, gemma-thinking, …)."""
        content = (msg.get("content") or "").strip()
        if content:
            return content
        reasoning = (msg.get("reasoning_content") or "").strip()
        if choice.get("finish_reason") == "length" and not reasoning:
            raise InferenceError(
                InferenceError.CONTEXT_LENGTH,
                f"model hit the token limit before producing output")
        if not reasoning:
            raise InferenceError(InferenceError.MALFORMED,
                                 "model returned an empty message")
        return reasoning


def _body_text(resp) -> str:
    try:
        return resp.text or ""
    except Exception:
        return ""


# --------------------------------------------------------------------------- #
# Local / OpenAI-compatible endpoint
# --------------------------------------------------------------------------- #
class LocalProvider(InferenceProvider):
    id = "local"
    label = "Local Endpoint"

    def __init__(self, base_url: str = "", model: str = "", api_key: str = "",
                 **_extra):
        super().__init__(model=model, api_key=api_key)
        self.base_url = (base_url or config.LLM_URL).rstrip("/")
        # Normalize so we can append /chat/completions and /models.
        if not re.search(r"/v\d+$", self.base_url) and not self.base_url.endswith("/v1"):
            self.base_url = self.base_url.rstrip("/")
            if not self.base_url.endswith("/v1"):
                # Allow the user to paste either ".../v1" or the bare host:port.
                if "/v1" not in self.base_url:
                    self.base_url = self.base_url + "/v1"

    # -- requests ----------------------------------------------------------
    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _chat_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    # -- interface ---------------------------------------------------------
    def generate(self, messages, *, temperature=0.7, max_tokens=4096) -> str:
        payload = {
            "model": self._require_model(),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        try:
            r = requests.post(self._chat_url(), headers=self._headers(),
                              json=payload, timeout=config.LLM_TIMEOUT)
            r.raise_for_status()
        except requests.RequestException as e:
            raise self._classify_http(e)
        try:
            data = r.json()
            choice = data["choices"][0]
            return self._content_from_choice(choice, choice.get("message", {}))
        except (KeyError, IndexError, ValueError) as e:
            raise InferenceError(InferenceError.MALFORMED,
                                 f"Malformed response from local endpoint: {e}")

    def stream(self, messages, *, temperature=0.7, max_tokens=4096) -> Iterator[str]:
        payload = {
            "model": self._require_model(),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        try:
            r = requests.post(self._chat_url(), headers=self._headers(),
                              json=payload, timeout=config.LLM_TIMEOUT, stream=True)
            r.raise_for_status()
        except requests.RequestException as e:
            raise self._classify_http(e)
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            line = line.strip()
            if not line.startswith("data:"):
                continue
            chunk = line[len("data:"):].strip()
            if chunk == "[DONE]":
                break
            try:
                obj = json.loads(chunk)
                delta = obj["choices"][0]["delta"]
                tok = delta.get("content") or ""
                if tok:
                    yield tok
            except (ValueError, KeyError, IndexError):
                continue

    def list_models(self) -> list[ModelInfo]:
        try:
            r = requests.get(f"{self.base_url}/models", headers=self._headers(),
                             timeout=5)
            r.raise_for_status()
            data = r.json()
        except requests.RequestException as e:
            raise self._classify_http(e)
        out = []
        for m in data.get("data", []):
            mid = m.get("id") or m.get("name") or ""
            if mid:
                out.append(ModelInfo(id=mid, label=mid,
                                     context_length=m.get("context_length")))
        return out

    def test_connection(self) -> TestResult:
        t0 = time.time()
        # 1) reachability + model listing (validates endpoint + key)
        try:
            models = self.list_models()
        except InferenceError as e:
            return TestResult(False, self.id, self.model, e.message, category=e.category)
        # 2) optional model existence check when a model is chosen
        if self.model and models and not any(m.id == self.model for m in models):
            return TestResult(False, self.id, self.model,
                              f"Model '{self.model}' was not found on this endpoint.")
        # 3) minimal completion round-trip
        try:
            out = self.generate(_as_messages(
                "Reply in one word.", "ping"), temperature=0, max_tokens=8)
        except InferenceError as e:
            return TestResult(False, self.id, self.model, e.message, category=e.category)
        return TestResult(True, self.id, self.model,
                          f"OK — endpoint reachable, model responded.",
                          latency_ms=int((time.time() - t0) * 1000))


# --------------------------------------------------------------------------- #
# Google Gemini
# --------------------------------------------------------------------------- #
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(InferenceProvider):
    id = "gemini"
    label = "Google Gemini"

    def __init__(self, model: str = "", api_key: str = "", base_url: str = "",
                 **_extra):
        super().__init__(model=model, api_key=api_key)
        self.base_url = (base_url or GEMINI_BASE).rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path}?key={self.api_key}"

    def generate(self, messages, *, temperature=0.7, max_tokens=4096) -> str:
        if not self.api_key:
            raise InferenceError(InferenceError.AUTH,
                                 "A Google AI Studio API key is required.")
        payload = {
            "contents": [{"role": _gem_role(m.role), "parts": [{"text": m.content}]}
                         for m in messages if m.content],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        try:
            r = requests.post(
                self._url(f"models/{self._require_model()}:generateContent"),
                json=payload, timeout=config.LLM_TIMEOUT)
            r.raise_for_status()
        except requests.RequestException as e:
            raise self._classify_http(e)
        return self._extract_text(r.json())

    def stream(self, messages, *, temperature=0.7, max_tokens=4096) -> Iterator[str]:
        if not self.api_key:
            raise InferenceError(InferenceError.AUTH,
                                 "A Google AI Studio API key is required.")
        payload = {
            "contents": [{"role": _gem_role(m.role), "parts": [{"text": m.content}]}
                         for m in messages if m.content],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        try:
            r = requests.post(
                self._url(f"models/{self._require_model()}:streamGenerateContent"),
                json=payload, timeout=config.LLM_TIMEOUT, stream=True)
            r.raise_for_status()
        except requests.RequestException as e:
            raise self._classify_http(e)
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            line = line.strip()
            if line == "[" or line == "]":
                continue
            try:
                obj = json.loads(line)
                for c in obj.get("candidates", []):
                    parts = c.get("content", {}).get("parts", [])
                    for p in parts:
                        if p.get("text"):
                            yield p["text"]
            except (ValueError, KeyError):
                continue

    def list_models(self) -> list[ModelInfo]:
        if not self.api_key:
            raise InferenceError(InferenceError.AUTH,
                                 "An API key is required to list Gemini models.")
        try:
            r = requests.get(self._url("models"), timeout=10)
            r.raise_for_status()
        except requests.RequestException as e:
            raise self._classify_http(e)
        out = []
        for m in r.json().get("models", []):
            name = m.get("name", "")  # "models/gemini-1.5-flash"
            mid = name.split("/")[-1]
            caps = m.get("supportedGenerationMethods", [])
            if "generateContent" not in caps:
                continue
            out.append(ModelInfo(
                id=mid, label=mid,
                description=m.get("description", ""),
                context_length=m.get("inputTokenLimit")))
        return out

    def test_connection(self) -> TestResult:
        t0 = time.time()
        try:
            out = self.generate(_as_messages("Reply in one word.", "ping"),
                                temperature=0, max_tokens=8)
        except InferenceError as e:
            return TestResult(False, self.id, self.model, e.message, category=e.category)
        return TestResult(True, self.id, self.model,
                          "OK — Gemini responded.",
                          latency_ms=int((time.time() - t0) * 1000))

    def _extract_text(self, data: dict) -> str:
        try:
            cands = data["candidates"]
            if not cands:
                # blocked prompt / safety
                if data.get("promptFeedback", {}).get("blockReason"):
                    raise InferenceError(
                        InferenceError.PROVIDER,
                        f"Request blocked: {data['promptFeedback']['blockReason']}")
                raise InferenceError(InferenceError.MALFORMED,
                                     "Gemini returned no candidates.")
            return "".join(p.get("text", "")
                           for p in cands[0]["content"]["parts"])
        except (KeyError, IndexError, ValueError) as e:
            raise InferenceError(InferenceError.MALFORMED,
                                 f"Malformed Gemini response: {e}")


def _gem_role(role: str) -> str:
    return "model" if role == "assistant" else "user"


# --------------------------------------------------------------------------- #
# OpenRouter (OpenAI-compatible)
# --------------------------------------------------------------------------- #
OPENROUTER_BASE = "https://openrouter.ai/api/v1"


class OpenRouterProvider(InferenceProvider):
    id = "openrouter"
    label = "OpenRouter"

    def __init__(self, model: str = "", api_key: str = "", base_url: str = "",
                 **_extra):
        super().__init__(model=model, api_key=api_key)
        self.base_url = (base_url or OPENROUTER_BASE).rstrip("/")

    def _headers(self) -> dict:
        h = {
            "Content-Type": "application/json",
            "HTTP-Referer": "https://hermes-video-agent.local",
            "X-Title": "Hermes Video Agent",
        }
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def generate(self, messages, *, temperature=0.7, max_tokens=4096) -> str:
        if not self.api_key:
            raise InferenceError(InferenceError.AUTH,
                                 "An OpenRouter API key is required.")
        payload = {
            "model": self._require_model(),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        try:
            r = requests.post(f"{self.base_url}/chat/completions",
                              headers=self._headers(), json=payload,
                              timeout=config.LLM_TIMEOUT)
            r.raise_for_status()
        except requests.RequestException as e:
            raise self._classify_http(e)
        try:
            data = r.json()
            choice = data["choices"][0]
            return self._content_from_choice(choice, choice.get("message", {}))
        except (KeyError, IndexError, ValueError) as e:
            raise InferenceError(InferenceError.MALFORMED,
                                 f"Malformed OpenRouter response: {e}")

    def stream(self, messages, *, temperature=0.7, max_tokens=4096) -> Iterator[str]:
        if not self.api_key:
            raise InferenceError(InferenceError.AUTH,
                                 "An OpenRouter API key is required.")
        payload = {
            "model": self._require_model(),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        try:
            r = requests.post(f"{self.base_url}/chat/completions",
                              headers=self._headers(), json=payload,
                              timeout=config.LLM_TIMEOUT, stream=True)
            r.raise_for_status()
        except requests.RequestException as e:
            raise self._classify_http(e)
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            line = line.strip()
            if not line.startswith("data:"):
                continue
            chunk = line[len("data:"):].strip()
            if chunk == "[DONE]":
                break
            try:
                obj = json.loads(chunk)
                delta = obj["choices"][0]["delta"]
                tok = delta.get("content") or ""
                if tok:
                    yield tok
            except (ValueError, KeyError, IndexError):
                continue

    def list_models(self) -> list[ModelInfo]:
        if not self.api_key:
            raise InferenceError(InferenceError.AUTH,
                                 "An API key is required to list OpenRouter models.")
        try:
            r = requests.get(f"{self.base_url}/models", headers=self._headers(),
                             timeout=10)
            r.raise_for_status()
        except requests.RequestException as e:
            raise self._classify_http(e)
        out = []
        for m in r.json().get("data", []):
            mid = m.get("id", "")
            if not mid:
                continue
            pricing = m.get("pricing", {})
            try:
                prompt_cost = float(pricing.get("prompt", "0") or "0")
            except (TypeError, ValueError):
                prompt_cost = 0.0
            out.append(ModelInfo(
                id=mid,
                label=m.get("name", mid),
                description=m.get("description", ""),
                free=(prompt_cost == 0.0),
                context_length=m.get("context_length")))
        # free first, then by name
        out.sort(key=lambda x: (not x.free, x.label.lower()))
        return out

    def test_connection(self) -> TestResult:
        t0 = time.time()
        try:
            out = self.generate(_as_messages("Reply in one word.", "ping"),
                                temperature=0, max_tokens=8)
        except InferenceError as e:
            return TestResult(False, self.id, self.model, e.message, category=e.category)
        return TestResult(True, self.id, self.model,
                          "OK — OpenRouter responded.",
                          latency_ms=int((time.time() - t0) * 1000))


# --------------------------------------------------------------------------- #
# Registry + active provider resolution
# --------------------------------------------------------------------------- #
PROVIDERS: dict[str, type[InferenceProvider]] = {
    LocalProvider.id: LocalProvider,
    GeminiProvider.id: GeminiProvider,
    OpenRouterProvider.id: OpenRouterProvider,
}


def provider_class(id_: str) -> type[InferenceProvider]:
    try:
        return PROVIDERS[id_]
    except KeyError:
        raise InferenceError(InferenceError.CONFIG,
                             f"Unknown inference provider: {id_}")


def make_provider(id_: str, **kwargs) -> InferenceProvider:
    return provider_class(id_)(**kwargs)


def list_providers() -> list[dict]:
    return [{"id": p.id, "label": p.label} for p in PROVIDERS.values()]
