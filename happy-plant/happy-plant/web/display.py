"""Builds everything the app shows. The app only puts these values on screen; every decision is made here."""
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from units.device import latest_for
from units.levels import LIGHT_WORDS, MOIST_WORDS, light_level, moist_level, moisture_connected
from units.models import Reading, Unit

from .plantlib import tips_for
from .sun import night_info

ONLINE_SECONDS = 60          # wall power posts every 10 s; a minute of silence = offline
KEYS = ["air", "soil", "light", "moist"]
LABELS = {"air": "Air temp", "soil": "Soil temp", "light": "Sunlight", "moist": "Moisture"}
CLS = ["", "warn", "bad"]
MOUTHS = {"happy": "M32 60c6 10 30 10 36 0", "meh": "M32 62h36", "sad": "M32 66c6-10 30-10 36 0",
          "asleep": "M40 63c3 3 17 3 20 0", "fresh": "M40 63h20"}
F_COUNTRIES = {"US", "LR", "MM", "BS", "BZ", "KY", "PW"}


# ---------- user settings ----------
def resolve_unit(profile, request):
    if profile.temp_unit in ("F", "C"):
        return profile.temp_unit
    lang = (request.headers.get("Accept-Language") or "en-US").split(",")[0]
    country = lang.split("-")[1].upper() if "-" in lang else "US"
    return "F" if country in F_COUNTRIES else "C"


def user_tz(profile):
    try:
        return ZoneInfo(profile.time_zone) if profile.time_zone else ZoneInfo("America/New_York")
    except Exception:
        return ZoneInfo("America/New_York")


def temp_out(f, unit):
    return round((f - 32) * 5 / 9) if unit == "C" else round(f)


def fmt_temp(f, unit):
    return f"{temp_out(f, unit)}°{unit}"


def clock(dt, tz):
    t = dt.astimezone(tz)
    h = t.hour % 12 or 12
    return f"{h}:{t.minute:02d} {'PM' if t.hour >= 12 else 'AM'}"


def ago(seconds):
    s = int(seconds)
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{s // 60} min ago"
    if s < 86400:
        return f"{s // 3600} h ago"
    d = s // 86400
    return "yesterday" if d == 1 else f"{d} days ago"


# ---------- readings ----------
def newest_reading(unit_obj):
    """Newest reading: from memory if the board is talking, otherwise the last one saved. Never invented."""
    mem = latest_for(unit_obj.serial)
    if mem:
        d = mem["data"]
        return {"air": d["air_f"], "soil": d["soil_f"], "light": light_level(d["light_raw"]),
                "moist": moist_level(d["moisture_raw"]), "rssi": d["rssi"], "battery": d["battery_pct"]}, mem["received_at"]
    r = Reading.objects.filter(unit=unit_obj).order_by("-received_at").first()
    if not r:
        return None, None
    return {"air": r.air_f, "soil": r.soil_f, "light": light_level(r.light_raw), "moist": moist_level(r.moisture_raw),
            "rssi": r.rssi, "battery": r.battery_pct}, r.received_at


def judge(k, v, w):
    """0 good, 1 a little off, 2 way off. Missing reading = not judged."""
    if v is None:
        return 0
    lo, hi = w
    if lo <= v <= hi:
        return 0
    if k in ("air", "soil"):
        return 2 if (v < lo - 8 or v > hi + 8) else 1
    if k == "light":
        return 1
    return 2 if v in (0, 4) else 1


def temp_word(v, lo, hi):
    if v < lo - 8:
        return "Freezing"
    if v < lo:
        return "Chilly"
    if v <= hi:
        return "Cozy"
    if v <= hi + 8:
        return "Toasty"
    return "Roasting"


def value_text(k, v, unit):
    if v is None:
        return "—"
    if k in ("air", "soil"):
        return fmt_temp(v, unit)
    return LIGHT_WORDS[v] if k == "light" else MOIST_WORDS[v]


def word_text(k, v, w):
    if v is None:
        return "Not connected"
    if k in ("air", "soil"):
        return temp_word(v, w[0], w[1])
    return LIGHT_WORDS[v] if k == "light" else MOIST_WORDS[v]


def bar_pct(k, v):
    if v is None:
        return 0
    if k in ("air", "soil"):
        return round(max(4, min(100, (v - 40) / 70 * 100)))
    return round((v + 1) / 4 * 100) if k == "light" else round((v + 1) / 5 * 100)


def wants_text(k, w, unit):
    if k in ("air", "soil"):
        return f"{fmt_temp(w[0], unit)} – {fmt_temp(w[1], unit)}"
    words = LIGHT_WORDS if k == "light" else MOIST_WORDS
    return f"{words[w[0]]} – {words[w[1]]}"


def mood_line(now, wants, night):
    bits = []
    for k in ["moist", "air", "soil", "light"]:
        if k == "light" and night:
            continue
        v, w = now[k], wants[k]
        if judge(k, v, w):
            if k == "moist":
                bits.append("needs water" if v < w[0] else "too wet")
            elif k == "light":
                bits.append("not enough sun" if v < w[0] else "too much sun")
            else:
                bits.append(("air" if k == "air" else "soil") + (" is cold" if v < w[0] else " is hot"))
    return " · ".join(bits[:2])


def wifi_bars(rssi, online):
    if not online or rssi is None:
        return 0
    return 4 if rssi > -55 else 3 if rssi > -65 else 2 if rssi > -75 else 1


WIFI_WORDS = ["Offline", "Weak", "Fair", "Good", "Strong"]


# ---------- one plant ----------
def plant_state(u, unit, tz, now_utc):
    now, at = newest_reading(u)
    age = (now_utc - at).total_seconds() if at else None
    online = age is not None and age < ONLINE_SECONDS
    fresh = now is None
    night, sunrise = night_info(now_utc, u.latitude, u.longitude, tz)
    wants = u.wants
    name = u.name or "My plant"

    if fresh:
        level, cls, word, line, mouth = 0, "fresh", "New here", f"Waiting on the first reading from {u.serial}", MOUTHS["fresh"]
    else:
        level = max(judge(k, now[k], wants[k]) for k in KEYS if not (k == "light" and night))
        if night and level == 0:
            cls, word, line, mouth = "night", "Sleeping", "", MOUTHS["asleep"]
        else:
            cls = ["", "mid", "sad"][level]
            word = ["Happy", "Meh", "Sad"][level]
            line = "Everything is in range. Nothing to do." if level == 0 else mood_line(now, wants, night)
            mouth = MOUTHS[["happy", "meh", "sad"][level]]

    cards = []
    for k in KEYS:
        if k == "light" and night:
            continue
        v = None if fresh else now[k]
        j = judge(k, v, wants[k])
        cards.append({"k": k, "label": LABELS[k], "value": value_text(k, v, unit),
                      "word": "No reading yet" if fresh else word_text(k, v, wants[k]),
                      "cls": CLS[j], "pct": bar_pct(k, v), "off": v is None,
                      "wants": wants_text(k, wants[k], unit)})

    if u.last_watered_at:
        days = (now_utc.astimezone(tz).date() - u.last_watered_at.astimezone(tz).date()).days
        water = "Watered today" if days <= 0 else "Watered yesterday" if days == 1 else f"Watered {days} days ago"
    else:
        water = "No watering seen yet"

    bars = wifi_bars(now["rssi"] if now else None, online)
    battery = now["battery"] if now else None
    return {
        "serial": u.serial, "name": name, "where": u.where, "sub": " · ".join(x for x in [u.where, u.serial] if x),
        "photo": f"/api/app/photo/{u.serial}?v={int(u.photo.__len__())}" if u.photo else "",
        "mood": {"level": level, "cls": cls, "word": word, "line": line, "mouth": mouth,
                 "asleep": cls == "night", "logo": ["", "mid", "sad"][level] if not fresh else ""},
        "night": {"on": night, "text": f"Night · sunrise {clock(sunrise, tz)}" if night and sunrise else ""},
        "stale": "" if online or not at else f"{u.serial} last reported {ago(age)}",
        "updated": ago(age) if at else "—",
        "cards": cards,
        "water": water,
        "has_location": u.latitude is not None,
        "wants": {"air": [temp_out(wants["air"][0], unit), temp_out(wants["air"][1], unit)],
                  "soil": [temp_out(wants["soil"][0], unit), temp_out(wants["soil"][1], unit)],
                  "light": wants["light"], "moist": wants["moist"]},
        "device": {"serial": u.serial, "online": online, "status": "Online" if online else "Offline",
                   "wifi_bars": bars, "wifi": WIFI_WORDS[bars],
                   "battery": "—" if battery is None else f"{battery}%", "battery_pct": battery or 0,
                   "rows": [["Serial", u.serial], ["Power", "Wall (USB)" if battery is None else "Battery"],
                            ["Sends readings", "every 10 seconds" if online else "—"],
                            ["Last report", ago(age) if at else "Never"]]},
        "tips": tips_for(name, wants, unit),
        "alert": None if fresh or level == 0 else {"cls": "cold" if level == 2 else "warn",
                                                   "t": f"{name} · {line}", "s": f"From {u.serial}, updated {ago(age)}.",
                                                   "when": "Now"},
    }


def app_state(user, request):
    profile = user.profile
    unit = resolve_unit(profile, request)
    tz = user_tz(profile)
    now_utc = timezone.now()
    plants = [plant_state(u, unit, tz, now_utc) for u in Unit.objects.filter(owner=user).order_by("paired_at", "id")]
    return {
        "ok": True,
        "user": {"email": user.email, "first_name": user.first_name},
        "settings": {"temp_unit": profile.temp_unit, "unit_label": f"°{unit}", "push_alerts": profile.push_alerts,
                     "daily_checkin": profile.daily_checkin, "has_location": profile.latitude is not None},
        "plants": plants,
        "alerts": [p["alert"] for p in plants if p["alert"]],
        "plant_count": f"{len(plants)} plant{'s' if len(plants) != 1 else ''}",
        "device_count": f"{len(plants)} unit{'s' if len(plants) != 1 else ''}",
    }
