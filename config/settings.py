"""Aurora settings. Local, single-user app; secrets and data live in .env and data/."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

env = environ.Env(DEBUG=(bool, True))
environ.Env.read_env(BASE_DIR / ".env")

DEBUG = env("DEBUG")
SECRET_KEY = env("SECRET_KEY", default="dev-only-not-secret" if DEBUG else environ.Env.NOTSET)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "ledger",
    "web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "web.context_processors.ai",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": env("DB_PATH", default=str(DATA_DIR / "aurora.sqlite3")),
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Europe/Oslo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# AI tips (phase 5). Without a key the feature is off and the app works as before.
# AI_PROVIDER=ollama uses a local model instead: free, and nothing leaves the machine.
AI_PROVIDER = env("AI_PROVIDER", default="anthropic")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
AI_MODEL = env("AI_MODEL", default="claude-opus-5-5")
OLLAMA_URL = env("OLLAMA_URL", default="http://localhost:11434")
OLLAMA_MODEL = env("OLLAMA_MODEL", default="qwen3:8b")
# Thinking first: slower (about a minute), but small models then misread the numbers less.
OLLAMA_THINK = env.bool("OLLAMA_THINK", default=True)
AI_LANGUAGE = env("AI_LANGUAGE", default="Norwegian (bokmål)")
# Optional context for the AI, e.g. "self-employed, two children". Set it in Settings.
AI_ABOUT_ME = env("AI_ABOUT_ME", default="")
# Any OpenAI-compatible chat API (AI_PROVIDER=openai): OpenAI, Gemini, Mistral, LM Studio ...
OPENAI_BASE_URL = env("OPENAI_BASE_URL", default="")
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
OPENAI_MODEL = env("OPENAI_MODEL", default="")
# The Settings page stores its choices here; they win over .env.
LOCAL_SETTINGS_FILE = env("LOCAL_SETTINGS_FILE", default=str(DATA_DIR / "settings.json"))
