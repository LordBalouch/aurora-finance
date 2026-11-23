"""Ask Claude to explain numbers that `insights` already computed.

The model never computes: it gets the facts of one card as JSON and returns a short summary
and 2–3 tips that cite those numbers. Answers are cached by the exact request, so asking
the same thing twice costs nothing. Tests pass a fake client; without an API key the feature
is off.
"""

import hashlib
import json
from dataclasses import dataclass

import anthropic
from django.conf import settings

from ledger.models import AIAdvice

SYSTEM = """You are a calm, practical personal-finance coach for one person in Norway who \
runs a small physiotherapy practice as a sole proprietorship (enkeltpersonforetak).

You get the figures behind one view of their finance app as JSON. Rules:
- Use only the numbers given. Never invent amounts, rates or dates. If something you would
  need is missing, say what is missing instead of guessing.
- Amounts are Norwegian kroner (kr). Write them like 12 345 kr.
- Be concrete: each tip names the number it rests on and one action that can be done this
  month. No generic advice ("make a budget") unless the numbers point to it.
- Friends & family money and transfers between own accounts are not income or spending.
- Be honest about risks (debt, interest, shortfalls) without moralising.
- Write in {language}. Keep it short: a 1–2 sentence summary and 2–3 tips."""

SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "tips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                    "numbers": {"type": "string", "description": "The figures the tip uses"},
                },
                "required": ["title", "detail", "numbers"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "tips"],
    "additionalProperties": False,
}


class AIUnavailable(Exception):
    """No API key, or the API could not answer. The message is safe to show."""


@dataclass
class Advice:
    summary: str
    tips: list[dict]
    facts: str
    cached: bool
    created_at: object


def available() -> bool:
    return bool(settings.ANTHROPIC_API_KEY)


def _client():
    if not available():
        raise AIUnavailable("Add ANTHROPIC_API_KEY to .env to turn on AI tips.")
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def build_prompt(title: str, facts: dict, task: str) -> str:
    # sort_keys: the same facts always give the same bytes, so the cache key is stable.
    body = json.dumps(facts, ensure_ascii=False, sort_keys=True, indent=1, default=str)
    return f"View: {title}\nTask: {task}\n\nFigures (JSON):\n{body}"


def advise(card: str, title: str, facts: dict, task: str, *, client=None, refresh=False) -> Advice:
    """Summary + tips for one card. Reuses a stored answer for an identical request."""
    system = SYSTEM.format(language=settings.AI_LANGUAGE)
    prompt = build_prompt(title, facts, task)
    key = hashlib.sha256(f"{settings.AI_MODEL}\n{system}\n{prompt}".encode()).hexdigest()
    stored = AIAdvice.objects.filter(key=key).first()
    if stored and not refresh:
        return Advice(
            stored.answer["summary"], stored.answer["tips"], stored.facts, True, stored.created_at
        )

    client = client or _client()
    try:
        response = client.beta.messages.create(
            model=settings.AI_MODEL,
            max_tokens=4000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            # On a safety decline the API retries on a suitable fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError as exc:
        raise AIUnavailable("The API key was rejected. Check ANTHROPIC_API_KEY in .env.") from exc
    except anthropic.RateLimitError as exc:
        raise AIUnavailable("Too many requests right now. Try again in a minute.") from exc
    except anthropic.APIConnectionError as exc:
        raise AIUnavailable(
            "Could not reach the AI service. Check the internet connection."
        ) from exc
    except anthropic.APIStatusError as exc:
        raise AIUnavailable(f"The AI service answered with an error ({exc.status_code}).") from exc

    if response.stop_reason == "refusal":
        raise AIUnavailable("The AI declined to answer this one.")
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        answer = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIUnavailable("The AI answer was cut off. Try again.") from exc
    answer["tips"] = answer.get("tips", [])[:3]
    usage = response.usage
    saved, _ = AIAdvice.objects.update_or_create(
        key=key,
        defaults={
            "card": card,
            "model": settings.AI_MODEL,
            "facts": prompt,
            "answer": answer,
            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
        },
    )
    return Advice(answer["summary"], answer["tips"], prompt, False, saved.created_at)
