"""AI settings: the Settings page writes them to a small local JSON file, which wins over
`.env`. The file lives next to the database (gitignored) and is never part of an export.
"""

import json
import os
from pathlib import Path

from django.conf import settings

KEYS = (
    "AI_PROVIDER",
    "AI_LANGUAGE",
    "AI_ABOUT_ME",
    "ANTHROPIC_API_KEY",
    "AI_MODEL",
    "OLLAMA_URL",
    "OLLAMA_MODEL",
    "OLLAMA_THINK",
    "OPENAI_BASE_URL",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
)
SECRETS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")


def _path() -> Path:
    return Path(settings.LOCAL_SETTINGS_FILE)


def saved() -> dict:
    """What the Settings page stored; {} when there is no file or it is unreadable."""
    try:
        data = json.loads(_path().read_text())
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if k in KEYS} if isinstance(data, dict) else {}


def conf(name: str):
    """A setting: the Settings page's value if set, else `.env` / settings.py."""
    if name not in KEYS:
        raise KeyError(name)
    stored = saved()
    if name in stored and stored[name] not in (None, ""):
        return stored[name]
    return getattr(settings, name)


def save(values: dict) -> None:
    """Merge `values` into the file. An empty secret keeps the stored one."""
    data = saved()
    for key, value in values.items():
        if key not in KEYS:
            continue
        if key in SECRETS and not value:
            continue
        data[key] = value
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    os.chmod(tmp, 0o600)  # keys inside: readable by the owner only
    tmp.replace(path)
