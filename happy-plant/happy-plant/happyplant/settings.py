"""Happy Plant backend settings.

Secrets never live in this file. Railway provides them as Variables:
  SECRET_KEY    long random string (Railway -> Variables)
  DATABASE_URL  Neon connection string
  DEBUG         leave unset in production
"""
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("DEBUG") == "1"
SECRET_KEY = os.environ.get("SECRET_KEY") or ("dev-only-not-secret" if DEBUG else None)
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not set. Add it in Railway -> Variables.")

# Railway sets RAILWAY_PUBLIC_DOMAIN automatically. EXTRA_HOSTS adds custom domains later.
_hosts = ["localhost", "127.0.0.1", "healthcheck.railway.app"]  # last one: Railway's own health check
if os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
    _hosts.append(os.environ["RAILWAY_PUBLIC_DOMAIN"])
_hosts += [h.strip() for h in os.environ.get("EXTRA_HOSTS", "").split(",") if h.strip()]
ALLOWED_HOSTS = _hosts
CSRF_TRUSTED_ORIGINS = ["https://" + h for h in _hosts if h not in ("localhost", "127.0.0.1", "healthcheck.railway.app")]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "accounts",
    "units",
    "web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "happyplant.urls"
WSGI_APPLICATION = "happyplant.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Neon Postgres in production. Without DATABASE_URL (only on a laptop) it uses a local file.
if os.environ.get("DATABASE_URL"):
    DATABASES = {"default": dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=0, ssl_require=True)}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "local.sqlite3"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# One server process, so an in-memory cache is enough (used for login-attempt limits).
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

SESSION_COOKIE_AGE = 60 * 60 * 24 * 30  # stay logged in 30 days
# Admin messages (like a new board secret) stay on the server, not in a browser cookie.
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

# Email (Twilio Email). Keys live in Railway -> Variables, never in code.
TWILIO_API_KEY_SID = os.environ.get("TWILIO_API_KEY_SID", "")
TWILIO_API_KEY_SECRET = os.environ.get("TWILIO_API_KEY_SECRET", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "hello@happyplant.shop")
EMAIL_FROM_NAME = "Happy Plant"

# Plain test page for accounts at /test/accounts. Only on when TEST_PAGES=1.
TEST_PAGES = os.environ.get("TEST_PAGES") == "1"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_REDIRECT_EXEMPT = [r"^health$"]
