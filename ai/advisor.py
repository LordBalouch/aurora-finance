"""Ask an AI to explain numbers that `insights` already computed.

The model never computes: it gets the facts of one card as JSON and returns a short summary
and 2–3 tips that cite those numbers. Answers are cached by the exact request, so asking
the same thing twice costs nothing. The provider (Claude, a local model or any
OpenAI-compatible API) is in `providers`. Tests pass a fake client; without an AI set up the
feature is off.
"""

import hashlib
import json
from dataclasses import dataclass

from ledger.models import AIAdvice

from .config import conf
from .providers import AIUnavailable, available, complete_json, model_name

__all__ = ["AIUnavailable", "Advice", "advise", "available", "build_prompt"]

SYSTEM = """You are a calm, practical personal-finance coach for one person in Norway.{about}

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


@dataclass
class Advice:
    summary: str
    tips: list[dict]
    facts: str
    cached: bool
    created_at: object


def about_me() -> str:
    """The optional 'About you' text from Settings, as one line of the system prompt."""
    about = str(conf("AI_ABOUT_ME") or "").strip()
    return f"\nAbout them (their own words): {about}" if about else ""


def build_prompt(title: str, facts: dict, task: str) -> str:
    # sort_keys: the same facts always give the same bytes, so the cache key is stable.
    body = json.dumps(facts, ensure_ascii=False, sort_keys=True, indent=1, default=str)
    return f"View: {title}\nTask: {task}\n\nFigures (JSON):\n{body}"


def advise(card: str, title: str, facts: dict, task: str, *, client=None, refresh=False) -> Advice:
    """Summary + tips for one card. Reuses a stored answer for an identical request."""
    if not available():
        raise AIUnavailable("No AI is set up. Choose one in Settings.")
    system = SYSTEM.format(language=conf("AI_LANGUAGE"), about=about_me())
    prompt = build_prompt(title, facts, task)
    key = hashlib.sha256(f"{model_name()}\n{system}\n{prompt}".encode()).hexdigest()
    stored = AIAdvice.objects.filter(key=key).first()
    if stored and not refresh:
        return Advice(
            stored.answer["summary"], stored.answer["tips"], stored.facts, True, stored.created_at
        )
    text, input_tokens, output_tokens = complete_json(system, prompt, SCHEMA, client=client)
    try:
        answer = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIUnavailable("The AI answer was cut off. Try again.") from exc
    answer["tips"] = answer.get("tips", [])[:3]
    saved, _ = AIAdvice.objects.update_or_create(
        key=key,
        defaults={
            "card": card,
            "model": model_name(),
            "facts": prompt,
            "answer": answer,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    )
    return Advice(answer["summary"], answer["tips"], prompt, False, saved.created_at)
