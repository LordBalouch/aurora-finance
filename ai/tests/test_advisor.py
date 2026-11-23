import json
from types import SimpleNamespace

import pytest

from ai import advisor
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
    with pytest.raises(AIUnavailable, match="ANTHROPIC_API_KEY"):
        advise("z", "Z", {}, "t")
