"""Settings: the AI provider, model and language, and the data (where it lives, backup and
restore). AI choices go to a local file next to the database (`ai.config`), never into the
database itself, so a backup never carries an API key."""

import tempfile
from pathlib import Path

from django import forms
from django.conf import settings
from django.contrib import messages
from django.http import FileResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ai import config
from ai.providers import PROVIDERS, AIUnavailable, complete_json, model_name
from ledger.models import Account, Transaction

from .backup import RestoreError, backup_file, restore


class AISettingsForm(forms.Form):
    provider = forms.ChoiceField(label="AI", choices=list(PROVIDERS.items()))
    language = forms.CharField(label="Answer language", max_length=60)
    about_me = forms.CharField(
        label="About you (optional)", required=False, max_length=300,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="A line of context for the AI, e.g. “self-employed, two children”. "
        "Stored on this machine only.",
    )  # fmt: skip
    anthropic_key = forms.CharField(
        label="Anthropic API key", required=False, widget=forms.PasswordInput,
        help_text="From console.anthropic.com. Leave empty to keep the stored key.",
    )  # fmt: skip
    ai_model = forms.CharField(label="Claude model", max_length=60)
    ollama_url = forms.URLField(label="Ollama address", assume_scheme="http")
    ollama_model = forms.CharField(label="Local model", max_length=60,
                                   help_text="Install it first: ollama pull <model>")  # fmt: skip
    ollama_think = forms.BooleanField(
        label="Let the local model think first (slower, fewer mistakes)", required=False
    )
    openai_base_url = forms.URLField(
        label="OpenAI-compatible base URL", required=False, assume_scheme="https",
        help_text="e.g. https://api.openai.com/v1 or http://localhost:1234/v1 (LM Studio)",
    )  # fmt: skip
    openai_key = forms.CharField(label="API key for that service", required=False,
                                 widget=forms.PasswordInput,
                                 help_text="Leave empty to keep the stored key.")  # fmt: skip
    openai_model = forms.CharField(label="Its model", required=False, max_length=80)
    forget_keys = forms.BooleanField(label="Forget the stored API keys", required=False)

    FIELDS = {
        "provider": "AI_PROVIDER",
        "language": "AI_LANGUAGE",
        "about_me": "AI_ABOUT_ME",
        "anthropic_key": "ANTHROPIC_API_KEY",
        "ai_model": "AI_MODEL",
        "ollama_url": "OLLAMA_URL",
        "ollama_model": "OLLAMA_MODEL",
        "ollama_think": "OLLAMA_THINK",
        "openai_base_url": "OPENAI_BASE_URL",
        "openai_key": "OPENAI_API_KEY",
        "openai_model": "OPENAI_MODEL",
    }

    @classmethod
    def current(cls):
        """Initial values from the settings file / .env. Keys are never sent to the page."""
        return {
            field: config.conf(key)
            for field, key in cls.FIELDS.items()
            if key not in config.SECRETS
        }

    def clean(self):
        data = super().clean()
        if data.get("provider") == "openai" and not (
            data.get("openai_base_url") and data.get("openai_model")
        ):
            raise forms.ValidationError("An OpenAI-compatible API needs a base URL and a model.")
        return data

    def save(self):
        data = self.cleaned_data
        values = {key: data[field] for field, key in self.FIELDS.items()}
        if data["forget_keys"]:
            config.forget(config.SECRETS)
        config.save(values)


def _key_status(name: str) -> str:
    value = config.conf(name)
    if not value:
        return "not set"
    source = "settings" if config.saved().get(name) else ".env"
    return f"set ({source}, ends in …{str(value)[-4:]})"


def _db_info() -> dict:
    path = settings.DATABASES["default"]["NAME"]
    size = Path(path).stat().st_size if Path(str(path)).is_file() else None
    return {
        "path": path,
        "size_mb": round(size / 1e6, 1) if size else None,
        "transactions": Transaction.objects.count(),
        "accounts": Account.objects.count(),
        "settings_file": settings.LOCAL_SETTINGS_FILE,
    }


def settings_page(request):
    form = AISettingsForm(request.POST or None, initial=AISettingsForm.current())
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request, f"Settings saved. AI: {PROVIDERS[form.cleaned_data['provider']]}."
        )
        return redirect("web:settings")
    context = {
        "form": form,
        "anthropic_status": _key_status("ANTHROPIC_API_KEY"),
        "openai_status": _key_status("OPENAI_API_KEY"),
        "db": _db_info(),
    }
    return render(request, "web/settings.html", context)


TEST_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}, "reply": {"type": "string"}},
    "required": ["ok", "reply"],
    "additionalProperties": False,
}


@require_POST
def test_ai(request):
    """HTMX: one tiny request to the chosen AI, to check the settings work."""
    try:
        complete_json(
            "You check that a connection works. Reply with ok=true and a short greeting.",
            "Hello from Aurora's settings page.",
            TEST_SCHEMA,
        )
        result = {"ok": True, "text": f"It works: {model_name()} answered."}
    except AIUnavailable as exc:
        result = {"ok": False, "text": str(exc)}
    return render(request, "web/_settings_test.html", result)


def download_backup(request):
    path = backup_file()
    name = f"aurora-backup-{timezone.localtime():%Y-%m-%d}.sqlite3"
    response = FileResponse(path.open("rb"), as_attachment=True, filename=name)
    path.unlink()  # the open handle keeps the data until the response is sent
    return response


@require_POST
def restore_backup(request):
    upload = request.FILES.get("backup")
    if not upload or request.POST.get("confirm") != "yes":
        messages.error(request, "Choose a backup file and tick the box to confirm.")
        return redirect("web:settings")
    with tempfile.NamedTemporaryFile(suffix=".sqlite3") as tmp:
        for chunk in upload.chunks():
            tmp.write(chunk)
        tmp.flush()
        try:
            info = restore(Path(tmp.name))
        except RestoreError as exc:
            messages.error(request, str(exc))
            return redirect("web:settings")
    messages.success(
        request,
        f"Backup restored: {info['transactions']} transactions. The previous database was "
        f"saved as {info['safety_copy']}.",
    )
    return redirect("web:settings")
