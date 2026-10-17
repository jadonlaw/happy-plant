"""POST /api/waitlist  {"email": "...", "source": "reddit"}  — called from the happyplant.shop website."""
import json
import re

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from accounts.emails import send_waitlist_confirmation
from .models import Signup

MAX_PER_IP_PER_HOUR = 8


def _cors(resp):
    # Public form on another domain, no cookies involved, so any origin may post.
    resp["Access-Control-Allow-Origin"] = "*"
    resp["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    resp["Access-Control-Allow-Headers"] = "Content-Type"
    resp["Access-Control-Max-Age"] = "86400"
    return resp


def _reply(ok, message, status=200, **extra):
    return _cors(JsonResponse({"ok": ok, "message": message, **extra}, status=status))


def _client_ip(request):
    fwd = request.headers.get("X-Forwarded-For", "")
    return fwd.split(",")[0].strip() if fwd else request.META.get("REMOTE_ADDR", "")


@csrf_exempt
def join(request):
    if request.method == "OPTIONS":
        return _cors(HttpResponse(status=204))
    if request.method != "POST":
        return _reply(False, "Use POST.", status=405)
    try:
        d = json.loads(request.body or b"{}")
        if not isinstance(d, dict):
            raise ValueError
    except ValueError:
        return _reply(False, "Something went wrong. Try again.", status=400)

    if d.get("website"):  # hidden field only bots fill in; pretend it worked
        return _reply(True, "You're on the list. Check your inbox for a confirmation.")

    email = (d.get("email") or "").strip().lower()[:254]
    try:
        validate_email(email)
    except ValidationError:
        return _reply(False, "That email doesn't look right. Check it and try again.", status=400)

    key = f"waitlist_ip:{_client_ip(request)}"
    if cache.get(key, 0) >= MAX_PER_IP_PER_HOUR:
        return _reply(False, "Too many signups from here. Try again in an hour.", status=429)
    cache.set(key, cache.get(key, 0) + 1, 3600)

    source = re.sub(r"[^a-z0-9_-]", "", (d.get("source") or "").lower())[:60]
    signup, created = Signup.objects.get_or_create(email=email, defaults={"source": source})
    if not created and signup.confirmation_sent_at:
        return _reply(True, "You're already on the list. We'll email you when Happy Plant launches.", already=True)

    if send_waitlist_confirmation(email, signup.token):
        signup.confirmation_sent_at = timezone.now()
        signup.save(update_fields=["confirmation_sent_at"])
        return _reply(True, "You're on the list. Check your inbox for a confirmation.")
    return _reply(True, "You're on the list. We'll email you when Happy Plant launches.")


def leave(request):
    """One-click remove from the waitlist (link in every email)."""
    t = (request.GET.get("t") or "")[:40]
    removed = bool(t) and Signup.objects.filter(token=t).delete()[0] > 0
    msg = "You're off the Happy Plant waitlist. You won't get any more emails." if removed else \
        "That link has already been used, so you're not on the list."
    page = ("<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Happy Plant</title><body style='margin:0;font-family:system-ui,sans-serif;background:#F3F6F1;"
            "color:#16301D;display:grid;place-items:center;min-height:100vh;padding:24px;text-align:center'>"
            f"<div><h1 style='font-size:28px;margin:0 0 10px'>Done</h1><p style='color:#4C6352'>{msg}</p></div>")
    return HttpResponse(page)
