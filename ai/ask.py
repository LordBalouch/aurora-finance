"""Ask your data: a question in plain language, answered with the tools in `ai.tools`.

The model looks things up with tool calls (at most MAX_ROUNDS rounds), then writes the
answer. Every lookup is kept, so the page can show what the AI looked up and a chart of the
last result. Answers are cached by question + model + a fingerprint of the data, so asking
again costs nothing until new transactions arrive.
"""

import hashlib
import json
from dataclasses import dataclass, field

from ledger.models import AIAdvice, Transaction

from . import tools
from .advisor import about_me
from .config import conf
from .providers import AIUnavailable, Chat, available, model_name

MAX_ROUNDS = 5
MAX_QUESTION = 500
LAST_ROUND = "Lookup limit reached. Answer now with what you have; do not call more tools."

SYSTEM = """You answer questions about one person's own finances in Norway, using their \
bank data through the tools you are given.{about}

Rules:
- Look numbers up with the tools. For a named shop, service or person, use
  find_transactions; spending is for whole groups and categories.
- Never invent or estimate amounts, dates or rates, and do not do your own arithmetic
  beyond simple differences of numbers the tools returned.
- Pick dates from the context below. "This year", "last summer" and so on are relative to
  today. A month that is still running is not complete.
- If the tools cannot answer the question, say so and say what is missing.
- Spending is positive kroner. Transfers between own accounts and money between friends and
  family are neither income nor spending.
- Amounts are Norwegian kroner (kr). Write them like 12 345 kr.
- Answer in {language}: first the direct answer in one or two sentences, then at most a few
  short lines with the numbers behind it. No tables, no headings.

Context (JSON):
{context}"""


@dataclass
class Lookup:
    tool: str
    arguments: dict
    result: dict | None = None
    error: str | None = None


@dataclass
class Answer:
    question: str
    text: str
    lookups: list[Lookup] = field(default_factory=list)
    chart: dict | None = None
    cached: bool = False
    created_at: object = None


def _fingerprint() -> str:
    """Changes whenever transactions or their categories change."""
    last = Transaction.objects.order_by("-id").values_list("id", flat=True).first()
    return (
        f"{Transaction.objects.count()}-{last}-{Transaction.objects.filter(category=None).count()}"
    )


def _key(question: str) -> str:
    """Changes with the question, the model, the data and the instructions or tools."""
    schema = json.dumps([(t.name, t.description, t.schema()) for t in tools.TOOLS.values()])
    raw = "\n".join(
        ["ask", model_name(), _fingerprint(), conf("AI_LANGUAGE"), about_me(), SYSTEM, schema,
         question]
    )  # fmt: skip
    return hashlib.sha256(raw.encode()).hexdigest()


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def ask(question: str, *, client=None, refresh: bool = False, data=None) -> Answer:
    question = " ".join(str(question or "").split())
    if not question:
        raise AIUnavailable("Write a question first.")
    if len(question) > MAX_QUESTION:
        raise AIUnavailable(f"Keep the question under {MAX_QUESTION} characters.")
    if not available():
        raise AIUnavailable("No AI is set up. Choose one in Settings.")
    key = _key(question)
    stored = AIAdvice.objects.filter(key=key).first()
    if stored and not refresh:
        saved = stored.answer
        return Answer(
            question,
            saved["text"],
            [Lookup(**x) for x in saved["lookups"]],
            saved.get("chart"),
            cached=True,
            created_at=stored.created_at,
        )

    data = data or tools.Data()
    system = SYSTEM.format(
        about=about_me(),
        language=conf("AI_LANGUAGE"),
        context=json.dumps(data.context(), ensure_ascii=False, indent=1),
    )
    chat = Chat(
        system,
        question,
        [(t.name, t.description, t.schema()) for t in tools.TOOLS.values()],
        client=client,
    )
    lookups, chart, used_in, used_out = [], None, 0, 0
    for round_ in range(1, MAX_ROUNDS + 2):
        turn = chat.send()
        used_in, used_out = used_in + turn.input_tokens, used_out + turn.output_tokens
        if not turn.calls:
            break
        if round_ > MAX_ROUNDS:
            raise AIUnavailable("The AI kept looking things up without answering. Try again.")
        results = []
        for call in turn.calls:
            lookup = Lookup(call.name, call.arguments)
            try:
                lookup.result, spec = tools.run(data, call.name, call.arguments)
                chart = spec or chart
                results.append((call, _dump(lookup.result), False))
            except tools.ToolError as exc:
                lookup.error = str(exc)
                results.append((call, f"Error: {exc}", True))
            lookups.append(lookup)
        if round_ == MAX_ROUNDS:
            # Last round: say so in the last result, so the model answers with what it has.
            call, content, error = results[-1]
            results[-1] = (call, content + "\n\n" + LAST_ROUND, error)
        chat.answer_tools(results)
    if not turn.text:
        raise AIUnavailable("The AI gave no answer. Try again or rephrase the question.")

    saved, _ = AIAdvice.objects.update_or_create(
        key=key,
        defaults={
            "card": "ask",
            "model": model_name(),
            "facts": question,
            "answer": {
                "text": turn.text,
                "lookups": [vars(x) for x in lookups],
                "chart": chart,
            },
            "input_tokens": used_in,
            "output_tokens": used_out,
        },
    )
    return Answer(question, turn.text, lookups, chart, created_at=saved.created_at)
