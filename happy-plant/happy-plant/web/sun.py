"""Sunrise / sunset from latitude + longitude (standard sunrise equation, no network)."""
import math
from datetime import date, datetime, timedelta, timezone as dt_tz


def sun_times(day: date, lat: float, lon: float):
    """Returns (sunrise, sunset) as UTC datetimes, or None near the poles."""
    rad = math.pi / 180
    n = (date(day.year, day.month, day.day) - date(2000, 1, 1)).days + 0.0008
    j_star = n - lon / 360
    m = ((357.5291 + 0.98560028 * j_star) % 360) * rad
    c = 1.9148 * math.sin(m) + 0.02 * math.sin(2 * m) + 0.0003 * math.sin(3 * m)
    lam = ((m / rad + c + 180 + 102.9372) % 360) * rad
    j_transit = 2451545 + j_star + 0.0053 * math.sin(m) - 0.0069 * math.sin(2 * lam)
    dec = math.asin(math.sin(lam) * math.sin(23.4397 * rad))
    cos_h = (math.sin(-0.833 * rad) - math.sin(lat * rad) * math.sin(dec)) / (math.cos(lat * rad) * math.cos(dec))
    if cos_h >= 1 or cos_h <= -1:
        return None
    h = math.acos(cos_h) / rad

    def to_dt(j):
        return datetime(1970, 1, 1, tzinfo=dt_tz.utc) + timedelta(days=j - 2440587.5)

    return to_dt(j_transit - h / 360), to_dt(j_transit + h / 360)


def night_info(now_utc: datetime, lat, lon, tz):
    """(is_night, next_sunrise_utc). Without a location it's never night."""
    if lat is None or lon is None:
        return False, None
    local_day = now_utc.astimezone(tz).date()
    today = sun_times(local_day, lat, lon)
    if not today:
        return False, None
    rise, sset = today
    if now_utc < rise:
        return True, rise
    if now_utc > sset:
        tomorrow = sun_times(local_day + timedelta(days=1), lat, lon)
        return True, tomorrow[0] if tomorrow else None
    return False, None
