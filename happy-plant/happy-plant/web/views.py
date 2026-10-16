import base64
import json
import re
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.http import HttpResponse, Http404
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from accounts.views import body, fail, is_verified, ok
from units.levels import LIGHT_WORDS, MOIST_WORDS, light_level, moist_level
from units.models import Reading, Unit

from . import display
from .plantlib import find

MAX_PHOTO_CHARS = 400_000  # ~300 KB image; the app shrinks photos to 256px so they're far smaller


def logged_in(request):
    return request.user.is_authenticated and is_verified(request.user)


def note_time_zone(request):
    tz = (request.headers.get("X-TZ") or "")[:64]
    p = request.user.profile
    if tz and tz != p.time_zone:
        try:
            ZoneInfo(tz)
        except Exception:
            return
        p.time_zone = tz
        p.save(update_fields=["time_zone"])


@require_GET
@ensure_csrf_cookie
def index(request):
    state = display.app_state(request.user, request) if logged_in(request) else None
    return render(request, "web/app.html", {"state": state})


@require_GET
def state(request):
    if not logged_in(request):
        return fail("not_logged_in", "You're not logged in.", status=401)
    note_time_zone(request)
    return ok(**{k: v for k, v in display.app_state(request.user, request).items() if k != "ok"})


def _my_unit(request, serial):
    return Unit.objects.filter(serial=serial, owner=request.user).first()


def _num(v):
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if n == n else None


@require_POST
def save_plant(request, serial):
    if not logged_in(request):
        return fail("not_logged_in", "You're not logged in.", status=401)
    u = _my_unit(request, serial)
    if not u:
        return fail("not_found", "That Happy Plant isn't on your account.", status=404)
    d = body(request)
    fields = []

    if "name" in d:
        name = (d.get("name") or "").strip()[:40]
        if not name:
            return fail("name", "Give the plant a name.")
        u.name = name
        fields.append("name")
    if "where" in d:
        u.where = (d.get("where") or "").strip()[:40]
        fields.append("where")
    if "photo" in d:
        photo = d.get("photo") or ""
        if photo and (len(photo) > MAX_PHOTO_CHARS or not re.match(r"^data:image/(jpeg|png|webp);base64,", photo)):
            return fail("photo", "That photo didn't work. Try a different one.")
        u.photo = photo
        fields.append("photo")
    if "lat" in d and "lon" in d:
        lat, lon = _num(d.get("lat")), _num(d.get("lon"))
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return fail("location", "Couldn't read that location.")
        u.latitude, u.longitude = round(lat, 3), round(lon, 3)
        fields += ["latitude", "longitude"]
    if "wants" in d:
        w = d.get("wants") or {}
        unit = display.resolve_unit(request.user.profile, request)
        to_f = (lambda c: c * 9 / 5 + 32) if unit == "C" else (lambda f: f)
        names = {"air": "air temp", "soil": "soil temp", "light": "sunlight", "moist": "moisture"}
        parsed = {}
        for k, top in (("air", None), ("soil", None), ("light", 3), ("moist", 4)):
            pair = w.get(k)
            if not isinstance(pair, list) or len(pair) != 2:
                return fail("wants", f"Set a low and high for {names[k]}.")
            lo, hi = _num(pair[0]), _num(pair[1])
            if lo is None or hi is None:
                return fail("wants", f"Set a low and high for {names[k]}.")
            if lo > hi:
                return fail("wants", f"Low has to be below high for {names[k]}.")
            if top is None:
                lo, hi = to_f(lo), to_f(hi)
                if not (-20 <= lo <= 140 and -20 <= hi <= 140):
                    return fail("wants", f"That {names[k]} range doesn't look right.")
            else:
                lo, hi = int(lo), int(hi)
                if not (0 <= lo <= top and 0 <= hi <= top):
                    return fail("wants", f"That {names[k]} range doesn't look right.")
            parsed[k] = (lo, hi)
        u.air_lo, u.air_hi = parsed["air"]
        u.soil_lo, u.soil_hi = parsed["soil"]
        u.light_lo, u.light_hi = parsed["light"]
        u.moist_lo, u.moist_hi = parsed["moist"]
        fields += ["air_lo", "air_hi", "soil_lo", "soil_hi", "light_lo", "light_hi", "moist_lo", "moist_hi"]

    if fields:
        u.save(update_fields=fields)
    return ok(message="Saved.", **{k: v for k, v in display.app_state(request.user, request).items() if k != "ok"})


@require_POST
def save_settings(request):
    if not logged_in(request):
        return fail("not_logged_in", "You're not logged in.", status=401)
    d = body(request)
    p = request.user.profile
    fields = []
    if d.get("temp_unit") in ("A", "F", "C"):
        p.temp_unit = d["temp_unit"]
        fields.append("temp_unit")
    for k in ("push_alerts", "daily_checkin"):
        if isinstance(d.get(k), bool):
            setattr(p, k, d[k])
            fields.append(k)
    if "lat" in d and "lon" in d:
        lat, lon = _num(d.get("lat")), _num(d.get("lon"))
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return fail("location", "Couldn't read that location.")
        p.latitude, p.longitude = round(lat, 3), round(lon, 3)
        fields += ["latitude", "longitude"]
        Unit.objects.filter(owner=request.user).update(latitude=p.latitude, longitude=p.longitude)
    if fields:
        p.save(update_fields=fields)
    return ok(message="Saved.", **{k: v for k, v in display.app_state(request.user, request).items() if k != "ok"})


@require_GET
def lookup(request):
    if not logged_in(request):
        return fail("not_logged_in", "You're not logged in.", status=401)
    name = request.GET.get("name", "")
    if not name.strip():
        return fail("name", "Type the plant name first.")
    hit = find(name)
    if not hit:
        return fail("not_found", "Not in the library yet — set it yourself below.", status=404)
    unit = display.resolve_unit(request.user.profile, request)
    t = lambda f: display.temp_out(f, unit)  # noqa: E731
    return ok(message="Filled in from the plant library. Adjust anything below.", about=hit["about"],
              wants={"air": [t(hit["air"][0]), t(hit["air"][1])], "soil": [t(hit["soil"][0]), t(hit["soil"][1])],
                     "light": hit["light"], "moist": hit["moist"]})


@require_GET
def photo(request, serial):
    if not logged_in(request):
        raise Http404
    u = _my_unit(request, serial)
    if not u or not u.photo:
        raise Http404
    m = re.match(r"^data:(image/[a-z]+);base64,(.*)$", u.photo, re.S)
    if not m:
        raise Http404
    resp = HttpResponse(base64.b64decode(m.group(2)), content_type=m.group(1))
    resp["Cache-Control"] = "private, max-age=86400"
    return resp


RANGES = {  # bucket size, number of buckets
    "hour": (timedelta(minutes=5), 12),
    "day": (timedelta(hours=1), 24),
    "week": (timedelta(days=1), 7),
    "month": (timedelta(days=1), 30),
    "year": (timedelta(days=30), 12),
}


@require_GET
def history(request):
    if not logged_in(request):
        return fail("not_logged_in", "You're not logged in.", status=401)
    u = _my_unit(request, request.GET.get("serial", ""))
    if not u:
        return fail("not_found", "That Happy Plant isn't on your account.", status=404)
    rng = request.GET.get("range", "day")
    if rng not in RANGES:
        return fail("range", "Unknown range.")
    step, n = RANGES[rng]
    unit = display.resolve_unit(request.user.profile, request)
    now = timezone.now()
    start = now - step * n
    rows = Reading.objects.filter(unit=u, received_at__gt=start).order_by("received_at").values_list(
        "received_at", "air_f", "soil_f", "light_raw", "moisture_raw")
    sums = [{"air": [], "soil": [], "light": [], "moist": []} for _ in range(n)]
    for at, air, soil, lr, mr in rows:
        i = min(n - 1, int((at - start) / step))
        if air is not None:
            sums[i]["air"].append(display.temp_out(air, unit) if unit == "C" else air)
        if soil is not None:
            sums[i]["soil"].append(display.temp_out(soil, unit) if unit == "C" else soil)
        lv, mv = light_level(lr), moist_level(mr)
        if lv is not None:
            sums[i]["light"].append(lv)
        if mv is not None:
            sums[i]["moist"].append(mv)
    avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else None  # noqa: E731
    buckets = [{"t": int((start + step * (i + 1)).timestamp()), **{k: avg(v) for k, v in b.items()}}
               for i, b in enumerate(sums)]
    w = u.wants
    t = lambda f: display.temp_out(f, unit)  # noqa: E731
    return ok(range=rng, buckets=buckets, unit_label=f"°{unit}", light_words=LIGHT_WORDS, moist_words=MOIST_WORDS,
              wants={"air": [t(w["air"][0]), t(w["air"][1])], "soil": [t(w["soil"][0]), t(w["soil"][1])],
                     "light": w["light"], "moist": w["moist"]})
