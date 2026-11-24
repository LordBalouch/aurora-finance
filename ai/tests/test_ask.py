"""Ask your data with scripted fake models: Claude, Ollama and an OpenAI-compatible API."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from ai import ask as ask_module
from ai import providers
from ai.ask import MAX_ROUNDS, ask
from ai.providers import AIUnavailable
from ai.tools import Data
from ledger.models import Account, Category, Transaction

pytestmark = pytest.mark.django_db


@pytest.fixture
def data(add_transactions):
    food = Category.objects.create(name="Food", kind="variable")
    groceries = Category.objects.create(name="Groceries", parent=food, kind="variable")
    acc = Account.objects.create(name="Everyday")
    add_transactions(acc, [(date(2026, m, 3), "-1000", groceries) for m in range(1, 11)])
    Transaction.objects.update(description_clean="Rema 1000", merchant="rema")
    return Data(today=date(2026, 11, 1))


def _block(kind, **kw):
    return SimpleNamespace(type=kind, **kw)


class FakeClaude:
    """Plays back a list of turns. A turn is text or a list of (tool name, arguments)."""

    def __init__(self, *turns, stop_reason=None):
        self.turns, self.calls, self.stop_reason = list(turns), [], stop_reason
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kwargs):
        # A copy: the conversation list keeps growing after this call.
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        turn = self.turns.pop(0)
        if isinstance(turn, str):
            content, stop = [_block("text", text=turn)], "end_turn"
        else:
            content = [_block("tool_use", id=f"t{i}", name=n, input=a) for i, (n, a) in
                       enumerate(turn)]  # fmt: skip
            stop = "tool_use"
        return SimpleNamespace(
            content=content,
            stop_reason=self.stop_reason or stop,
            usage=SimpleNamespace(input_tokens=100, output_tokens=20),
        )


@pytest.fixture(autouse=True)
def claude(settings):
    settings.ANTHROPIC_API_KEY = "test-key"
    settings.AI_MODEL = "claude-opus-5-5"


def test_tool_call_then_answer(data):
    client = FakeClaude([("spending", {"group": "Food"})], "You spent **10 000 kr** on food.")
    answer = ask("How much on food?", client=client, data=data)
    assert answer.text == "You spent **10 000 kr** on food." and not answer.cached
    assert [x.tool for x in answer.lookups] == ["spending"]
    assert answer.lookups[0].result["total"] == 10000
    assert answer.chart["kind"] == "bar"
    first, second = client.calls
    assert {t["name"] for t in first["tools"]} >= {"spending", "find_transactions"}
    assert first["output_config"] == {"effort": "medium"}
    assert '"last_complete_month": "2026-10"' in first["system"]
    result = second["messages"][-1]["content"][0]
    assert result["type"] == "tool_result" and result["tool_use_id"] == "t0"
    assert json.loads(result["content"])["total"] == 10000 and result["is_error"] is False


def test_same_question_is_answered_from_the_cache(data):
    client = FakeClaude([("spending", {})], "Answer.")
    ask("How much?", client=client, data=data)
    again = ask("  How   much? ", client=client, data=data)
    assert again.cached and again.lookups[0].tool == "spending" and len(client.calls) == 2


def test_a_bad_argument_goes_back_to_the_model(data):
    client = FakeClaude([("spending", {"group": "Fun"})], [("spending", {"group": "Food"})], "Ok.")
    answer = ask("Fun money?", client=client, data=data)
    assert answer.lookups[0].error.startswith("Unknown group 'Fun'")
    sent = client.calls[1]["messages"][-1]["content"][0]
    assert sent["is_error"] is True and "Unknown group" in sent["content"]


def test_round_limit_asks_for_an_answer_then_gives_up(data):
    loop = [[("monthly_overview", {})]] * (MAX_ROUNDS + 1)
    client = FakeClaude(*loop)
    with pytest.raises(AIUnavailable, match="kept looking"):
        ask("Loop", client=client, data=data)
    last = client.calls[MAX_ROUNDS]["messages"][-1]["content"][-1]["content"]
    assert ask_module.LAST_ROUND in last


@pytest.mark.parametrize(
    "question, message", [("   ", "Write a question"), ("x" * 501, "under 500")]
)
def test_question_is_checked(data, question, message):
    with pytest.raises(AIUnavailable, match=message):
        ask(question, client=FakeClaude("x"), data=data)


def test_refusal_and_no_ai(data, settings):
    with pytest.raises(AIUnavailable, match="declined"):
        ask("Q", client=FakeClaude("no", stop_reason="refusal"), data=data)
    settings.ANTHROPIC_API_KEY = ""
    with pytest.raises(AIUnavailable, match="No AI is set up"):
        ask("Q", data=data)


def _scripted_http(monkeypatch, replies):
    sent = []

    def post(url, body, timeout, headers=None):
        sent.append((url, json.loads(json.dumps(body)), headers))
        return replies.pop(0)

    monkeypatch.setattr(providers, "_post_json", post)
    return sent


def test_ollama_tool_calls(data, settings, monkeypatch):
    settings.AI_PROVIDER, settings.OLLAMA_MODEL, settings.OLLAMA_THINK = "ollama", "m", False
    sent = _scripted_http(monkeypatch, [
        {"message": {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "find_transactions", "arguments": {"text": "rema"}}}]}},
        {"message": {"role": "assistant", "content": "10 000 kr at Rema."}, "eval_count": 5},
    ])  # fmt: skip
    answer = ask("Rema?", data=data)
    assert answer.text == "10 000 kr at Rema." and answer.lookups[0].result["matches"] == 10
    url, body, _ = sent[1]
    assert url.endswith("/api/chat") and body["tools"][0]["type"] == "function"
    assert body["messages"][0]["role"] == "system"
    tool_message = body["messages"][-1]
    assert tool_message["role"] == "tool" and tool_message["tool_name"] == "find_transactions"


def test_openai_compatible_tool_calls(data, settings, monkeypatch):
    settings.AI_PROVIDER = "openai"
    settings.OPENAI_BASE_URL, settings.OPENAI_MODEL = "https://api.example.com/v1/", "gpt-x"
    settings.OPENAI_API_KEY = "sk-test"
    sent = _scripted_http(monkeypatch, [
        {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "spending", "arguments": json.dumps({"group": "Food"})}}]}}]},
        {"choices": [{"message": {"role": "assistant", "content": "Food: 10 000 kr."}}],
         "usage": {"prompt_tokens": 9, "completion_tokens": 3}},
    ])  # fmt: skip
    answer = ask("Food?", data=data)
    assert answer.text == "Food: 10 000 kr."
    url, body, headers = sent[1]
    assert url == "https://api.example.com/v1/chat/completions"
    assert headers == {"Authorization": "Bearer sk-test"} and body["model"] == "gpt-x"
    assert body["messages"][-1] == {
        "role": "tool", "tool_call_id": "c1", "content": body["messages"][-1]["content"]
    }  # fmt: skip


def test_openai_compatible_json_answer_for_the_cards(settings, monkeypatch):
    from ai.advisor import SCHEMA, advise

    settings.AI_PROVIDER = "openai"
    settings.OPENAI_BASE_URL, settings.OPENAI_MODEL = "http://localhost:1234/v1", "local"
    answer = {"summary": "S", "tips": []}
    sent = _scripted_http(
        monkeypatch, [{"choices": [{"message": {"content": json.dumps(answer)}}]}]
    )
    result = advise("debt", "Debt", {"a": 1}, "t")
    assert result.summary == "S"
    _, body, headers = sent[0]
    assert body["response_format"]["json_schema"]["schema"] == SCHEMA and headers == {}
    assert providers.model_name() == "openai:local"
