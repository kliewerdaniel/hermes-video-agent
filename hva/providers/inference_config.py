"""On-disk persistence for the inference provider configuration.

Security notes (this is where API keys live):
* Keys are written only when the operator explicitly saves them.
* ``load()`` returns the full config (incl. key) for *server-side* use only.
* ``public_view()`` returns the same shape with every secret redacted, and is
  the ONLY form the HTTP layer is allowed to serialize to the client.
* Nothing here ever logs a key, and ``public_view`` guarantees the key cannot
  leak through the API responses.
"""
from __future__ import annotations

import json
from typing import Optional

from .. import config
from . import inference as inf


class InferenceConfig:
    #: shape of the persisted JSON
    def __init__(self, provider: str = "local",
                 settings: Optional[dict] = None):
        self.provider = provider if provider in inf.PROVIDERS else "local"
        self.settings: dict = settings or {}

    # ---- persistence -----------------------------------------------------
    @classmethod
    def load(cls) -> "InferenceConfig":
        try:
            raw = json.loads(config.INFERENCE_CONFIG_PATH.read_text())
        except FileNotFoundError:
            return cls._default()
        except (ValueError, OSError):
            return cls._default()
        cfg = cls(provider=raw.get("provider", "local"),
                  settings=raw.get("settings", {}) or {})
        # Environment variables always win (12-factor + keeps keys out of files
        # when the operator prefers to inject them).
        cfg._apply_env()
        return cfg

    @classmethod
    def _default(cls) -> "InferenceConfig":
        cfg = cls(provider="local", settings={
            "local": {"base_url": config.LLM_URL, "model": config.LLM_MODEL},
            "gemini": {"model": ""},
            "openrouter": {"model": ""},
        })
        cfg._apply_env()
        return cfg

    def save(self) -> None:
        config.INFERENCE_CONFIG_PATH.write_text(json.dumps({
            "provider": self.provider,
            "settings": self.settings,
        }, indent=2))

    def _apply_env(self) -> None:
        if config.LLM_URL:
            self.settings.setdefault("local", {})["base_url"] = config.LLM_URL
        if config.LLM_MODEL:
            self.settings.setdefault("local", {})["model"] = config.LLM_MODEL

    # ---- accessors -------------------------------------------------------
    def provider_settings(self, pid: Optional[str] = None) -> dict:
        key = pid or self.provider
        return self.settings.get(key, {}) or {}

    def active_provider(self) -> inf.InferenceProvider:
        s = self.provider_settings()
        return inf.make_provider(self.provider, **s)

    # ---- public (safe) view ---------------------------------------------
    @staticmethod
    def _redact(d: dict) -> dict:
        out = dict(d)
        for k in ("api_key", "key", "token", "secret"):
            if k in out and out[k]:
                out[k] = "••••••••"
        return out

    def public_view(self) -> dict:
        return {
            "provider": self.provider,
            "providers": inf.list_providers(),
            "settings": {pid: self._redact(s)
                         for pid, s in self.settings.items()},
        }

    # ---- mutation helpers ------------------------------------------------
    def update(self, provider: str, settings: dict) -> None:
        if provider not in inf.PROVIDERS:
            from .inference import InferenceError
            raise InferenceError(InferenceError.CONFIG,
                                 f"Unknown provider: {provider}")
        self.provider = provider
        merged = dict(self.settings.get(provider, {}))
        merged.update(settings)
        self.settings[provider] = merged
