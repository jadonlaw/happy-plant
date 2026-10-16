"""Units API: pair with a Happy Key, list my units, remove one."""
import re

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from accounts.views import body, fail, is_verified, ok
from .device import latest_for
from .models import KEY_ALPHABET, Unit

PAIR_MAX_FAILS = 10
PAIR_LOCK_SECONDS = 15 * 60


def normalize_key(raw):
    """Accepts 'happy-7k4m-2qxd', '7K4M 2QXD', etc. Returns 'HAPPY-7K4M-2QXD' or None."""
    s = re.sub(r"[^A-Za-z0-9]", "", raw or "").upper()
    if s.startswith("HAPPY"):
        s = s[5:]
    if len(s) != 8 or any(ch not in KEY_ALPHABET for ch in s):
        return None
    return f"HAPPY-{s[:4]}-{s[4:]}"


def unit_data(u):
    return {"serial": u.serial, "name": u.name or "My plant", "power_mode": u.power_mode,
            "paired_at": u.paired_at.isoformat() if u.paired_at else None}


def logged_in(request):
    return request.user.is_authenticated and is_verified(request.user)


def not_logged_in():
    return fail("not_logged_in", "You're not logged in.", status=401)


@require_GET
def my_units(request):
    if not logged_in(request):
        return not_logged_in()
    units = Unit.objects.filter(owner=request.user)
    return ok(units=[unit_data(u) for u in units])


@require_POST
def pair(request):
    if not logged_in(request):
        return not_logged_in()
    fail_key = f"pair_fails:{request.user.pk}"
    if cache.get(fail_key, 0) >= PAIR_MAX_FAILS:
        return fail("locked", "Too many wrong Happy Keys. Try again in 15 minutes.", status=429)

    def wrong():
        cache.set(fail_key, cache.get(fail_key, 0) + 1, PAIR_LOCK_SECONDS)
        return fail("wrong_key", "That Happy Key isn't right. Check the email we sent you.", status=404)

    key = normalize_key(body(request).get("key"))
    if not key:
        return wrong()
    with transaction.atomic():
        unit = Unit.objects.select_for_update().filter(happy_key=key).first()
        if not unit:
            return wrong()
        if unit.owner_id == request.user.pk:
            return ok(unit=unit_data(unit), message="This Happy Plant is already connected to your account.")
        if unit.owner_id:
            return fail("taken", "This Happy Plant is already connected to another account. "
                                 "The owner has to remove it first.", status=409)
        unit.owner = request.user
        unit.paired_at = timezone.now()
        unit.save(update_fields=["owner", "paired_at"])
    cache.delete(fail_key)
    return ok(unit=unit_data(unit), next="home", message="Your Happy Plant is connected!")


@require_POST
def remove(request, serial):
    if not logged_in(request):
        return not_logged_in()
    with transaction.atomic():
        unit = Unit.objects.select_for_update().filter(serial=serial, owner=request.user).first()
        if not unit:
            return fail("not_found", "That Happy Plant isn't on your account.", status=404)
        unit.owner = None
        unit.paired_at = None
        unit.name = ""
        unit.latitude = unit.longitude = None
        unit.save(update_fields=["owner", "paired_at", "name", "latitude", "longitude"])
    return ok(message=f"{serial} was removed. It can now be connected with its Happy Key.")


@require_GET
def live(request, serial):
    """Newest reading for one of MY units, straight from server memory. Step 5 turns this into the home screen."""
    if not logged_in(request):
        return not_logged_in()
    if not Unit.objects.filter(serial=serial, owner=request.user).exists():
        return fail("not_found", "That Happy Plant isn't on your account.", status=404)
    item = latest_for(serial)
    if not item:
        return ok(serial=serial, online=False, reading=None, message="No reading from this Happy Plant since the server started.")
    age = (timezone.now() - item["received_at"]).total_seconds()
    return ok(serial=serial, online=age < 60, seconds_ago=int(age), reading=item["data"])


@require_GET
@ensure_csrf_cookie
def test_page(request):
    if not settings.TEST_PAGES:
        raise Http404
    return render(request, "units/test.html")
