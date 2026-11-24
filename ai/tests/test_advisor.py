import json
import urllib.error
from types import SimpleNamespace

import pytest

from ai import advisor, providers
from ai.advisor import AIUnavailable, advise, build_prompt
from ledger.models import AIAdvice

pytestmark = pytest.mark.django_db

ANSWER = {
    "summary": "Rentene er høye.",
    "tips": [{"title": t, "detail": t.lower(), "numbers": "1 kr"} for t in "ABCD"],
}


class FakeClient:
    """Stands in for anthropic.Anthropic: records each request, returns a fixed answer."""

    def __init__(self, answer=ANSWER, stop_reason="end_turn"):
        self.calls = []
        self.answer, self.stop_reason = answer, stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(self.answer))],
            stop_reason=self.stop_reason,
            usage=SimpleNamespace(input_tokens=120, output_tokens=80),
        )


@pytest.fixture(autouse=True)
def key(settings):
    settings.AI_PROVIDER = "anthropic"
    settings.ANTHROPIC_API_KEY = "test-key"
    settings.AI_MODEL = "claude-opus-5-5"
    settings.AI_LANGUAGE = "Norwegian (bokmål)"


def test_request_shape_and_answer():
    client = FakeClient()
    result = advise("debt", "Debt", {"rate": 7.6, "debt": 512400}, "Give tips.", client=client)
    call = client.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["output_config"]["effort"] == "low"
    assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]
    assert "Norwegian (bokmål)" in call["system"] and "Never invent" in call["system"]
    assert '"debt": 512400' in call["messages"][0]["content"]
    assert result.summary == "Rentene er høye." and len(result.tips) == 3  # capped at 3
    assert not result.cached


def test_same_request_is_answered_from_the_cache():
    client = FakeClient()
    advise("debt", "Debt", {"a": 1}, "t", client=client)
    again = advise("debt", "Debt", {"a": 1}, "t", client=client)
    assert len(client.calls) == 1 and again.cached
    assert AIAdvice.objects.get().input_tokens == 120
    advise("debt", "Debt", {"a": 1}, "t", client=client, refresh=True)
    assert len(client.calls) == 2 and AIAdvice.objects.count() == 1


def test_prompt_is_stable_regardless_of_key_order():
    assert build_prompt("T", {"b": 1, "a": 2}, "x") == build_prompt("T", {"a": 2, "b": 1}, "x")


def test_refusal_and_bad_json_raise_a_readable_error():
    with pytest.raises(AIUnavailable, match="declined"):
        advise("x", "X", {}, "t", client=FakeClient(stop_reason="refusal"))
    broken = FakeClient()
    broken.create = lambda **kw: SimpleNamespace(
        content=[SimpleNamespace(type="text", text='{"summary": "cut')],
        stop_reason="max_tokens", usage=None)  # fmt: skip
    broken.beta = SimpleNamespace(messages=SimpleNamespace(create=broken.create))
    with pytest.raises(AIUnavailable, match="cut off"):
        advise("y", "Y", {}, "t", client=broken)


def test_without_a_key_the_feature_is_off(settings):
    settings.ANTHROPIC_API_KEY = ""
    assert not advisor.available()
    with pytest.raises(AIUnavailable, match="No AI is set up"):
        advise("z", "Z", {}, "t")


@pytest.fixture
def ollama(settings, monkeypatch):
    """Local model: records each request to Ollama's chat API, returns a fixed answer."""
    settings.AI_PROVIDER = "ollama"
    settings.ANTHROPIC_API_KEY = ""
    settings.OLLAMA_URL = "http://localhost:11434/"
    settings.OLLAMA_MODEL = "qwen3:8b"
    settings.OLLAMA_THINK = True
    calls = []

    def post(url, body, timeout, headers=None):
        calls.append((url, body))
        return {
            "message": {"content": json.dumps(ANSWER)},
            "done_reason": "stop",
            "prompt_eval_count": 700,
            "eval_count": 300,
        }

    monkeypatch.setattr(providers, "_post_json", post)
    return calls


def test_ollama_needs_no_key_and_sends_the_same_schema(ollama):
    assert advisor.available()
    result = advise("debt", "Debt", {"debt": 512400}, "Give tips.")
    url, body = ollama[0]
    assert url == "http://localhost:11434/api/chat"
    assert body["model"] == "qwen3:8b" and body["format"] == advisor.SCHEMA
    assert body["stream"] is False and body["think"] is True
    assert "Never invent" in body["messages"][0]["content"]
    assert '"debt": 512400' in body["messages"][1]["content"]
    assert body["messages"][1]["content"].endswith("in Norwegian (bokmål).")
    assert result.summary == "Rentene er høye." and len(result.tips) == 3
    saved = AIAdvice.objects.get()
    assert saved.model == "qwen3:8b (thinking)" and saved.input_tokens == 700


def test_ollama_and_claude_answers_are_cached_apart(ollama, settings):
    advise("debt", "Debt", {"a": 1}, "t")
    settings.AI_PROVIDER, settings.ANTHROPIC_API_KEY = "anthropic", "test-key"
    client = FakeClient()
    assert not advise("debt", "Debt", {"a": 1}, "t", client=client).cached
    assert len(client.calls) == 1 and AIAdvice.objects.count() == 2


@pytest.mark.parametrize(
    "error, message",
    [
        (urllib.error.URLError("refused"), "Is the Ollama app running"),
        (urllib.error.HTTPError("u", 404, "not found", {}, None), "ollama pull qwen3:8b"),
        (urllib.error.HTTPError("u", 500, "boom", {}, None), "error \\(500\\)"),
        (TimeoutError(), "took too long"),
    ],
)
def test_ollama_errors_are_readable(ollama, monkeypatch, error, message):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(providers, "_post_json", fail)
    with pytest.raises(AIUnavailable, match=message):
        advise("x", "X", {}, "t")


def test_ollama_answer_cut_off(ollama, monkeypatch):
    monkeypatch.setattr(
        providers,
        "_post_json",
        lambda *a, **k: {"message": {"content": "{"}, "done_reason": "length"},
    )
    with pytest.raises(AIUnavailable, match="cut off"):
        advise("x", "X", {}, "t")
