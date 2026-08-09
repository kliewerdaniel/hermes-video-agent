"""Tests for the provider-agnostic inference abstraction.

Everything is mocked with unittest.mock.patch on requests — no network, no
live API keys, no credentials. Covers: provider init, config validation,
model discovery, successful request, streaming, auth failure, connection
failure, rate limiting, malformed responses.

Run: env -u PYTHONPATH -u PYTHONHOME ./.venv/bin/python -m pytest tests -q
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from hva.providers import inference as inf
from hva.providers.inference import (
    GeminiProvider,
    InferenceError,
    InferenceProvider,
    LocalProvider,
    ModelInfo,
    OpenRouterProvider,
)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _resp(status=200, json_data=None, text="", raise_exc=None):
    r = MagicMock()
    r.status_code = status
    r.ok = 200 <= status < 300
    if json_data is not None:
        r.json.return_value = json_data
    r.text = text
    if raise_exc is not None:
        r.raise_for_status.side_effect = raise_exc
    else:
        r.raise_for_status.return_value = None
    return r


def _http_error(status, body=""):
    e = requests.exceptions.HTTPError(response=_resp(status, text=body))
    return e


# --------------------------------------------------------------------------- #
# provider init + registry
# --------------------------------------------------------------------------- #
def test_registry_has_three_providers():
    assert set(inf.PROVIDERS) == {"local", "gemini", "openrouter"}
    assert inf.list_providers()[0]["id"] == "local"


def test_make_provider_returns_correct_adapter():
    assert isinstance(inf.make_provider("local", model="x"), LocalProvider)
    assert isinstance(inf.make_provider("gemini", model="x"), GeminiProvider)
    assert isinstance(inf.make_provider("openrouter", model="x"), OpenRouterProvider)


def test_unknown_provider_raises_config_error():
    with pytest.raises(InferenceError) as ei:
        inf.make_provider("nope")
    assert ei.value.category == InferenceError.CONFIG


def test_local_normalizes_base_url():
    # paste bare host:port -> /v1 appended
    p = inf.make_provider("local", base_url="http://192.168.1.100:8000", model="m")
    assert p.base_url == "http://192.168.1.100:8000/v1"  # type: ignore[attr-defined]
    # explicit /v1 preserved
    p2 = inf.make_provider("local", base_url="http://localhost:11434/v1", model="m")
    assert p2.base_url == "http://localhost:11434/v1"  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# config validation
# --------------------------------------------------------------------------- #
def test_inference_config_rejects_unknown_provider():
    from hva.providers import inference_config
    cfg = inference_config.InferenceConfig.load()
    with pytest.raises(InferenceError) as ei:
        cfg.update("bogus", {})
    assert ei.value.category == InferenceError.CONFIG


def test_public_view_redacts_api_keys():
    from hva.providers import inference_config
    cfg = inference_config.InferenceConfig.load()
    cfg.settings["gemini"] = {"api_key": "AIzaSECRET", "model": "gemini-1.5-flash"}
    view = cfg.public_view()
    assert view["settings"]["gemini"]["api_key"] == "••••••••"
    assert view["settings"]["gemini"]["model"] == "gemini-1.5-flash"


# --------------------------------------------------------------------------- #
# model discovery
# --------------------------------------------------------------------------- #
def test_local_list_models_parses_openai_format():
    data = {"data": [{"id": "llama3"}, {"id": "qwen2", "context_length": 32000}]}
    with patch("hva.providers.inference.requests.get",
               return_value=_resp(200, json_data=data)) as g:
        p = inf.make_provider("local", base_url="http://x/v1", model="llama3")
        models = p.list_models()
    assert [m.id for m in models] == ["llama3", "qwen2"]
    assert models[1].context_length == 32000
    g.assert_called_once()


def test_gemini_list_models_only_generatecontent():
    data = {"models": [
        {"name": "models/gemini-1.5-flash",
         "supportedGenerationMethods": ["generateContent"],
         "inputTokenLimit": 1000, "description": "fast"},
        {"name": "models/embedding", "supportedGenerationMethods": ["embedContent"]},
    ]}
    with patch("hva.providers.inference.requests.get",
               return_value=_resp(200, json_data=data)):
        p = inf.make_provider("gemini", model="gemini-1.5-flash", api_key="k")
        models = p.list_models()
    assert [m.id for m in models] == ["gemini-1.5-flash"]
    assert models[0].context_length == 1000


def test_openrouter_flags_free_models():
    data = {"data": [
        {"id": "openai/gpt-4o", "name": "GPT-4o",
         "pricing": {"prompt": "0.000005", "completion": "0.000015"}},
        {"id": "meta-llama/llama-3.1-8b", "name": "Llama 3.1 8B",
         "pricing": {"prompt": "0", "completion": "0"}},
    ]}
    with patch("hva.providers.inference.requests.get",
               return_value=_resp(200, json_data=data)):
        p = inf.make_provider("openrouter", model="x", api_key="k")
        models = p.list_models()
    assert models[0].id == "meta-llama/llama-3.1-8b"  # free sorted first
    assert models[0].free is True
    assert models[1].free is False


# --------------------------------------------------------------------------- #
# successful request
# --------------------------------------------------------------------------- #
def test_local_generate_success():
    data = {"choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}]}
    with patch("hva.providers.inference.requests.post",
               return_value=_resp(200, json_data=data)):
        p = inf.make_provider("local", base_url="http://x/v1", model="m")
        assert p.generate([inf.ConversationMessage("user", "hi")]) == "hello"


def test_local_generate_falls_back_to_reasoning():
    data = {"choices": [{"message": {"reasoning_content": "thinking…", "content": ""},
                         "finish_reason": "stop"}]}
    with patch("hva.providers.inference.requests.post",
               return_value=_resp(200, json_data=data)):
        p = inf.make_provider("local", base_url="http://x/v1", model="m")
        assert p.generate([inf.ConversationMessage("user", "hi")]) == "thinking…"


def test_gemini_generate_extracts_text():
    data = {"candidates": [{"content": {"parts": [{"text": "hi there"}]}}]}
    with patch("hva.providers.inference.requests.post",
               return_value=_resp(200, json_data=data)):
        p = inf.make_provider("gemini", model="gemini-1.5-flash", api_key="k")
        assert p.generate([inf.ConversationMessage("user", "hi")]) == "hi there"


# --------------------------------------------------------------------------- #
# streaming
# --------------------------------------------------------------------------- #
def test_local_stream_yields_tokens():
    lines = [
        'data: {"choices":[{"delta":{"content":"He"}}]}',
        'data: {"choices":[{"delta":{"content":"llo"}}]}',
        "data: [DONE]",
    ]
    r = _resp(200)
    r.iter_lines.return_value = iter(lines)
    with patch("hva.providers.inference.requests.post", return_value=r):
        p = inf.make_provider("local", base_url="http://x/v1", model="m")
        out = "".join(p.stream([inf.ConversationMessage("user", "hi")]))
    assert out == "Hello"


def test_gemini_stream_yields_text():
    lines = [
        '{"candidates":[{"content":{"parts":[{"text":"a"}]}}]}',
        '{"candidates":[{"content":{"parts":[{"text":"b"}]}}]}',
    ]
    r = _resp(200)
    r.iter_lines.return_value = iter(lines)
    with patch("hva.providers.inference.requests.post", return_value=r):
        p = inf.make_provider("gemini", model="g", api_key="k")
        out = "".join(p.stream([inf.ConversationMessage("user", "hi")]))
    assert out == "ab"


# --------------------------------------------------------------------------- #
# error handling
# --------------------------------------------------------------------------- #
def test_auth_failure_401():
    with patch("hva.providers.inference.requests.post",
               return_value=_resp(401, raise_exc=_http_error(401, "bad key"))):
        p = inf.make_provider("openrouter", model="m", api_key="k")
        with pytest.raises(InferenceError) as ei:
            p.generate([inf.ConversationMessage("user", "hi")])
    assert ei.value.category == InferenceError.AUTH


def test_connection_failure():
    with patch("hva.providers.inference.requests.post",
               side_effect=requests.exceptions.ConnectionError("refused")):
        p = inf.make_provider("local", base_url="http://x/v1", model="m")
        with pytest.raises(InferenceError) as ei:
            p.generate([inf.ConversationMessage("user", "hi")])
    assert ei.value.category == InferenceError.CONNECTION


def test_timeout_failure():
    with patch("hva.providers.inference.requests.post",
               side_effect=requests.exceptions.Timeout("too slow")):
        p = inf.make_provider("local", base_url="http://x/v1", model="m")
        with pytest.raises(InferenceError) as ei:
            p.generate([inf.ConversationMessage("user", "hi")])
    assert ei.value.category == InferenceError.TIMEOUT


def test_rate_limit_429():
    with patch("hva.providers.inference.requests.post",
               return_value=_resp(429, raise_exc=_http_error(429, "slow down"))):
        p = inf.make_provider("openrouter", model="m", api_key="k")
        with pytest.raises(InferenceError) as ei:
            p.generate([inf.ConversationMessage("user", "hi")])
    assert ei.value.category == InferenceError.RATE_LIMIT


def test_model_not_found_404():
    with patch("hva.providers.inference.requests.post",
               return_value=_resp(404, raise_exc=_http_error(404, "no model"))):
        p = inf.make_provider("local", base_url="http://x/v1", model="ghost")
        with pytest.raises(InferenceError) as ei:
            p.generate([inf.ConversationMessage("user", "hi")])
    assert ei.value.category == InferenceError.MODEL


def test_context_length_413():
    with patch("hva.providers.inference.requests.post",
               return_value=_resp(413, raise_exc=_http_error(413, "too long"))):
        p = inf.make_provider("local", base_url="http://x/v1", model="m")
        with pytest.raises(InferenceError) as ei:
            p.generate([inf.ConversationMessage("user", "hi")])
    assert ei.value.category == InferenceError.CONTEXT_LENGTH


def test_malformed_response():
    with patch("hva.providers.inference.requests.post",
               return_value=_resp(200, json_data={"unexpected": True})):
        p = inf.make_provider("local", base_url="http://x/v1", model="m")
        with pytest.raises(InferenceError) as ei:
            p.generate([inf.ConversationMessage("user", "hi")])
    assert ei.value.category == InferenceError.MALFORMED


def test_missing_api_key_for_cloud():
    p = inf.make_provider("gemini", model="g", api_key="")
    with pytest.raises(InferenceError) as ei:
        p.generate([inf.ConversationMessage("user", "hi")])
    assert ei.value.category == InferenceError.AUTH


def test_safe_does_not_leak_keys_in_message():
    redacted = inf._safe("Bearer sk-1234567890abcdefghijklmnop is here")
    assert "sk-1234567890" not in redacted
    assert "<redacted>" in redacted


# --------------------------------------------------------------------------- #
# test_connection
# --------------------------------------------------------------------------- #
def test_local_test_connection_success():
    models_resp = _resp(200, json_data={"data": [{"id": "m"}]})
    gen_resp = {"choices": [{"message": {"content": "pong"},
                              "finish_reason": "stop"}]}
    with patch("hva.providers.inference.requests.get", return_value=models_resp), \
         patch("hva.providers.inference.requests.post",
               return_value=_resp(200, json_data=gen_resp)):
        p = inf.make_provider("local", base_url="http://x/v1", model="m")
        r = p.test_connection()
    assert r.ok is True
    assert r.model == "m"


def test_local_test_connection_model_mismatch():
    models_resp = _resp(200, json_data={"data": [{"id": "other"}]})
    with patch("hva.providers.inference.requests.get", return_value=models_resp):
        p = inf.make_provider("local", base_url="http://x/v1", model="missing")
        r = p.test_connection()
    assert r.ok is False
    assert "not found" in r.message


def test_test_connection_propagates_auth_error():
    with patch("hva.providers.inference.requests.get",
               return_value=_resp(401, raise_exc=_http_error(401, "nope"))):
        p = inf.make_provider("openrouter", model="m", api_key="k")
        r = p.test_connection()
    assert r.ok is False
    assert r.category == InferenceError.AUTH
