"""The AI providers behind Aurora's take and Ask your data.

Three kinds, picked by AI_PROVIDER:
- `anthropic`: Claude through the Anthropic SDK (needs ANTHROPIC_API_KEY). Recommended.
- `ollama`: a local model through Ollama's chat API. Free, and nothing leaves the machine.
- `openai`: any OpenAI-compatible chat completions API (OpenAI, Gemini, Mistral, LM Studio,
  a self-hosted server ...): OPENAI_BASE_URL, OPENAI_API_KEY and OPENAI_MODEL.

Two kinds of request: `complete_json` (one answer in a fixed JSON schema, for the cards) and
`Chat` (a conversation with tool calls, for Ask your data). Settings come from `conf`, so the
Settings page can override `.env` without a restart.
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field

import anthropic

from .config import conf

PROVIDERS = {
    "anthropic": "Claude (Anthropic API)",
    "ollama": "Local model (Ollama)",
    "openai": "OpenAI-compatible API",
}


class AIUnavailable(Exception):
    """No AI set up, or the provider could not answer. The message is safe to show."""


def provider() -> str:
    name = conf("AI_PROVIDER")
    return name if name in PROVIDERS else "anthropic"


def available() -> bool:
    name = provider()
    if name == "ollama":
        return True
    if name == "openai":
        return bool(conf("OPENAI_BASE_URL") and conf("OPENAI_MODEL"))
    return bool(conf("ANTHROPIC_API_KEY"))


def model_name() -> str:
    """Part of every cache key, so switching model or thinking never reuses an old answer."""
    name = provider()
    if name == "ollama":
        return conf("OLLAMA_MODEL") + (" (thinking)" if conf("OLLAMA_THINK") else "")
    if name == "openai":
        return f"openai:{conf('OPENAI_MODEL')}"
    return conf("AI_MODEL")


def setup_hint() -> str:
    return {
        "anthropic": "Add an Anthropic API key in Settings to turn on AI.",
        "ollama": "Start the Ollama app to use the local model.",
        "openai": "Add the base URL and model of your AI service in Settings.",
    }[provider()]


def claude_client():
    if not conf("ANTHROPIC_API_KEY"):
        raise AIUnavailable(setup_hint())
    return anthropic.Anthropic(api_key=conf("ANTHROPIC_API_KEY"))


def _post_json(url: str, body: dict, timeout: int, headers: dict | None = None) -> dict:
    request = urllib.request.Request(
        url, json.dumps(body).encode(), {"Content-Type": "application/json", **(headers or {})}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _claude_errors(exc: Exception):
    if isinstance(exc, anthropic.AuthenticationError):
        return AIUnavailable("The API key was rejected. Check the Anthropic key in Settings.")
    if isinstance(exc, anthropic.RateLimitError):
        return AIUnavailable("Too many requests right now. Try again in a minute.")
    if isinstance(exc, anthropic.APIConnectionError):
        return AIUnavailable("Could not reach the AI service. Check the internet connection.")
    if isinstance(exc, anthropic.APIStatusError):
        return AIUnavailable(f"The AI service answered with an error ({exc.status_code}).")
    return None


def _http(body: dict, url: str, timeout: int, headers: dict | None = None) -> dict:
    """POST to Ollama or an OpenAI-compatible server, with readable errors."""
    local = provider() == "ollama"
    try:
        return _post_json(url, body, timeout, headers)
    except urllib.error.HTTPError as exc:
        if local and exc.code == 404:
            model = conf("OLLAMA_MODEL")
            raise AIUnavailable(f"Ollama does not have {model}. Run: ollama pull {model}") from exc
        if exc.code in (401, 403):
            raise AIUnavailable("The API key was rejected. Check it in Settings.") from exc
        name = "Ollama" if local else "The AI service"
        raise AIUnavailable(f"{name} answered with an error ({exc.code}).") from exc
    except TimeoutError as exc:
        raise AIUnavailable("The model took too long. Try again.") from exc
    except urllib.error.URLError as exc:
        if local:
            raise AIUnavailable("Could not reach Ollama. Is the Ollama app running?") from exc
        raise AIUnavailable("Could not reach the AI service. Check the base URL.") from exc


def _ollama_url() -> str:
    return conf("OLLAMA_URL").rstrip("/") + "/api/chat"


def _openai_url() -> str:
    return conf("OPENAI_BASE_URL").rstrip("/") + "/chat/completions"


def _openai_headers() -> dict:
    key = conf("OPENAI_API_KEY")
    return {"Authorization": f"Bearer {key}"} if key else {}


# --- one JSON answer (Aurora's take) ------------------------------------------------------


def complete_json(system: str, prompt: str, schema: dict, *, client=None):
    """One answer that follows `schema`. Returns (text, input_tokens, output_tokens)."""
    name = provider()
    if name == "ollama":
        # The language is repeated last: a small model that thinks in English answers in it.
        reminder = f"\n\nWrite the summary and the tips in {conf('AI_LANGUAGE')}."
        body = {
            "model": conf("OLLAMA_MODEL"),
            "stream": False,
            "think": conf("OLLAMA_THINK"),
            "format": schema,
            # Thinking tokens count in num_predict.
            "options": {"temperature": 0.2, "num_ctx": 8192, "num_predict": 6000},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt + reminder},
            ],
        }
        response = _http(body, _ollama_url(), 600)
        if response.get("done_reason") == "length":
            raise AIUnavailable("The AI answer was cut off. Try again.")
        return (
            response.get("message", {}).get("content", ""),
            response.get("prompt_eval_count", 0) or 0,
            response.get("eval_count", 0) or 0,
        )
    if name == "openai":
        body = {
            "model": conf("OPENAI_MODEL"),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "answer", "schema": schema, "strict": True},
            },
        }
        response = _http(body, _openai_url(), 300, _openai_headers())
        choice = (response.get("choices") or [{}])[0]
        if choice.get("finish_reason") == "length":
            raise AIUnavailable("The AI answer was cut off. Try again.")
        usage = response.get("usage") or {}
        return (
            (choice.get("message") or {}).get("content") or "",
            usage.get("prompt_tokens", 0) or 0,
            usage.get("completion_tokens", 0) or 0,
        )
    client = client or claude_client()
    try:
        response = client.beta.messages.create(
            model=conf("AI_MODEL"),
            max_tokens=4000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
            # On a safety decline the API retries on a suitable fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.APIError as exc:
        raise (_claude_errors(exc) or exc) from exc
    if response.stop_reason == "refusal":
        raise AIUnavailable("The AI declined to answer this one.")
    text = next((b.text for b in response.content if b.type == "text"), "")
    usage = response.usage
    return (
        text,
        getattr(usage, "input_tokens", 0) or 0,
        getattr(usage, "output_tokens", 0) or 0,
    )


# --- a conversation with tools (Ask your data) --------------------------------------------


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class Turn:
    text: str
    calls: list[ToolCall]
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class Chat:
    """One conversation. `send()` asks the model; `answer_tools()` adds the tool results.

    `tools` is a list of (name, description, JSON schema). Each provider keeps its own
    message format in `messages`, so a provider's extra fields (Claude's thinking blocks)
    go back to it unchanged.
    """

    system: str
    question: str
    tools: list[tuple[str, str, dict]]
    client: object = None
    messages: list = field(default_factory=list)

    def __post_init__(self):
        self.kind = provider()
        self.messages = [{"role": "user", "content": self.question}]
        if self.kind != "anthropic":
            self.messages.insert(0, {"role": "system", "content": self.system})

    def send(self) -> Turn:
        if self.kind == "anthropic":
            return self._claude()
        return self._openai_style()

    def answer_tools(self, results: list[tuple[ToolCall, str, bool]]):
        """results: (call, content, is_error) for every call in the last turn."""
        if self.kind == "anthropic":
            self.messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": c.id,
                            "content": content,
                            "is_error": error,
                        }
                        for c, content, error in results
                    ],  # fmt: skip
                }
            )
            return
        for call, content, _ in results:
            message = {"role": "tool", "content": content}
            if self.kind == "ollama":
                message["tool_name"] = call.name
            else:
                message["tool_call_id"] = call.id
            self.messages.append(message)

    def _claude(self) -> Turn:
        client = self.client or claude_client()
        try:
            response = client.messages.create(
                model=conf("AI_MODEL"),
                max_tokens=8000,
                system=self.system,
                messages=self.messages,
                tools=[{"name": n, "description": d, "input_schema": s} for n, d, s in self.tools],
                output_config={"effort": "medium"},
            )
        except anthropic.APIError as exc:
            raise (_claude_errors(exc) or exc) from exc
        if response.stop_reason == "refusal":
            raise AIUnavailable("The AI declined to answer this one.")
        if response.stop_reason == "max_tokens":
            raise AIUnavailable("The AI answer was cut off. Try a narrower question.")
        self.messages.append({"role": "assistant", "content": response.content})
        calls = [
            ToolCall(b.id, b.name, b.input if isinstance(b.input, dict) else {})
            for b in response.content
            if b.type == "tool_use"
        ]
        text = "\n\n".join(b.text for b in response.content if b.type == "text").strip()
        usage = response.usage
        return Turn(text, calls, getattr(usage, "input_tokens", 0) or 0,
                    getattr(usage, "output_tokens", 0) or 0)  # fmt: skip

    def _openai_style(self) -> Turn:
        tools = [
            {"type": "function", "function": {"name": n, "description": d, "parameters": s}}
            for n, d, s in self.tools
        ]
        if self.kind == "ollama":
            body = {
                "model": conf("OLLAMA_MODEL"),
                "stream": False,
                "think": conf("OLLAMA_THINK"),
                "messages": self.messages,
                "tools": tools,
                "options": {"temperature": 0.2, "num_ctx": 16384, "num_predict": 6000},
            }
            response = _http(body, _ollama_url(), 600)
            if response.get("done_reason") == "length":
                raise AIUnavailable("The AI answer was cut off. Try a narrower question.")
            message = response.get("message") or {}
            usage = (response.get("prompt_eval_count", 0), response.get("eval_count", 0))
        else:
            body = {"model": conf("OPENAI_MODEL"), "messages": self.messages, "tools": tools}
            response = _http(body, _openai_url(), 300, _openai_headers())
            choice = (response.get("choices") or [{}])[0]
            if choice.get("finish_reason") == "length":
                raise AIUnavailable("The AI answer was cut off. Try a narrower question.")
            message = choice.get("message") or {}
            u = response.get("usage") or {}
            usage = (u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
        calls = []
        for i, raw in enumerate(message.get("tool_calls") or []):
            function = raw.get("function") or {}
            args = function.get("arguments") or {}
            if isinstance(args, str):  # OpenAI sends the arguments as a JSON string
                try:
                    args = json.loads(args or "{}")
                except json.JSONDecodeError:
                    args = {}
            calls.append(ToolCall(raw.get("id") or f"call_{i}", function.get("name", ""), args))
        self.messages.append(
            {k: v for k, v in message.items() if k in ("role", "content", "tool_calls", "thinking")}
            | {"role": "assistant"}
        )
        return Turn((message.get("content") or "").strip(), calls, usage[0] or 0, usage[1] or 0)
