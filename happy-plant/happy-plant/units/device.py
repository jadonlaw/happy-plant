"""The board talks to this. POST /api/device/readings

Headers:  X-Unit: HP-0001      X-Secret: <board secret>
Body:     {"light_raw": 2310, "air_raw": 1180, "air_base": 1205, "moisture_raw": 41000,
           "soil_raw": null, "soil_base": null, "battery_pct": null, "rssi": -58, "uptime_s": 360}
          null = that sensor isn't connected.

The newest reading lives in server memory (what the app shows instantly). It's written to the database
only on the unit's power-mode schedule, so Neon can sleep in between and stay inside the free tier.
"""
import json
import threading

from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .levels import moist_level, moisture_connected
from .models import Reading, Unit

WALL_POST_EVERY_S = 10
AUTH_CACHE_SECONDS = 15 * 60  # long enough that checking the secret doesn't wake the database every 10 s

# Air-temperature calibration (same math the board used before).
KNOWN_TEMP_F = 74.0     # room temperature when the board boots
TEMP_DIVISOR = 45.0     # microseconds of charge-time change per degree F

_lock = threading.Lock()
LATEST = {}       # serial -> {"data": {...}, "received_at": datetime}
LAST_SAVED = {}   # serial -> datetime of last database save


MOIST_WINDOW = {}         # serial -> [(time, raw), ...] for the last 30 minutes
LAST_WATER = {}           # serial -> time we last marked a watering
WATER_DROP = 6000         # raw has to fall this much (wetter) to count as watering
WATER_WINDOW_S = 30 * 60


def _watering_check(serial, raw, now):
    """Watering = moisture suddenly a lot wetter than anything in the last 30 minutes, ending at Just right or wetter.
    Call while holding _lock."""
    if not moisture_connected(raw):
        return False
    win = [(t, r) for (t, r) in MOIST_WINDOW.get(serial, []) if (now - t).total_seconds() <= WATER_WINDOW_S]
    driest = max((r for _, r in win), default=None)
    win.append((now, raw))
    MOIST_WINDOW[serial] = win[-200:]
    if driest is None or driest - raw < WATER_DROP or (moist_level(raw) or 0) < 2:
        return False
    last = LAST_WATER.get(serial)
    if last and (now - last).total_seconds() < 3600:
        return False
    LAST_WATER[serial] = now
    MOIST_WINDOW[serial] = [(now, raw)]
    return True


def latest_for(serial):
    with _lock:
        item = LATEST.get(serial)
        return dict(item) if item else None


def forget_unit_cache(serial):
    """Call when a unit's settings change (power mode, deleted) so the board picks it up right away."""
    cache.delete(f"unit_auth:{serial}")


def _auth(serial, secret):
    key = f"unit_auth:{serial}"
    info = cache.get(key)
    if info is None:
        unit = Unit.objects.filter(serial=serial).only("id", "secret_hash", "power_mode").first()
        if not unit:
            return None
        info = {"id": unit.id, "secret_hash": unit.secret_hash, "power_mode": unit.power_mode,
                "save_every": unit.save_every_seconds}
        cache.set(key, info, AUTH_CACHE_SECONDS)
    probe = Unit(secret_hash=info["secret_hash"])
    return info if probe.check_secret(secret) else None


def _int(v, lo, hi):
    if v is None or isinstance(v, bool):
        return None
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if lo <= n <= hi else None


def _temp_f(raw, base):
    if raw is None or base is None:
        return None
    return round(KNOWN_TEMP_F + (base - raw) / TEMP_DIVISOR, 1)


def clean(payload):
    air_raw = _int(payload.get("air_raw"), 1, 49_999)
    air_base = _int(payload.get("air_base"), 1, 49_999)
    soil_raw = _int(payload.get("soil_raw"), 1, 49_999)
    soil_base = _int(payload.get("soil_base"), 1, 49_999)
    return {
        "light_raw": _int(payload.get("light_raw"), 1, 49_999),
        "air_raw": air_raw,
        "air_f": _temp_f(air_raw, air_base),
        "moisture_raw": _int(payload.get("moisture_raw"), 0, 65_535),
        "soil_f": _temp_f(soil_raw, soil_base),
        "battery_pct": _int(payload.get("battery_pct"), 0, 100),
        "rssi": _int(payload.get("rssi"), -127, 0),
        "uptime_s": _int(payload.get("uptime_s"), 0, 10**9),
    }


@csrf_exempt
@require_POST
def readings(request):
    serial = (request.headers.get("X-Unit") or "").strip().upper()
    info = _auth(serial, request.headers.get("X-Secret") or "")
    if not info:
        return JsonResponse({"ok": False, "error": "bad_unit"}, status=401)
    try:
        payload = json.loads(request.body or b"{}")
        if not isinstance(payload, dict):
            raise ValueError
    except ValueError:
        return JsonResponse({"ok": False, "error": "bad_json"}, status=400)

    data = clean(payload)
    now = timezone.now()
    with _lock:
        LATEST[serial] = {"data": data, "received_at": now}
        last = LAST_SAVED.get(serial)
        due = last is None or (now - last).total_seconds() >= info["save_every"]
        if due:
            LAST_SAVED[serial] = now
        watered = _watering_check(serial, data["moisture_raw"], now)

    if watered:
        Unit.objects.filter(id=info["id"]).update(last_watered_at=now)
    if due:
        Reading.objects.create(unit_id=info["id"], received_at=now, light_raw=data["light_raw"], air_f=data["air_f"],
                               air_raw=data["air_raw"], moisture_raw=data["moisture_raw"], soil_f=data["soil_f"],
                               battery_pct=data["battery_pct"], rssi=data["rssi"])
        Unit.objects.filter(id=info["id"]).update(last_seen=now, battery_pct=data["battery_pct"])

    return JsonResponse({"ok": True, "saved": due, "power_mode": info["power_mode"],
                         "next_post_s": WALL_POST_EVERY_S})
