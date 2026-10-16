"""Turns raw sensor numbers into levels and words. Calibration lives here, on the backend, not on the board or in the app.

Light   = capacitor charge time in microseconds (bigger = darker)
Moisture = ADC 0-65535 from the capacitive probe (bigger = drier)
"""

LIGHT_WORDS = ["Gloomy", "Dim", "Golden", "Blazing"]
MOIST_WORDS = ["Parched", "Thirsty", "Just right", "Soggy", "Drowning"]

# Light thresholds (from the bench calibration)
DARK_US, SHADE_US, SUN_US = 8000, 3000, 400

# Moisture thresholds. 48000 = dry, 32000 = wet on the bench probe.
PARCHED_RAW, THIRSTY_RAW, JUST_RIGHT_RAW, SOGGY_RAW = 55000, 48000, 32000, 25000
MOIST_UNPLUGGED_HIGH, MOIST_UNPLUGGED_LOW = 65000, 100   # pinned at the rails = probe not connected


def light_level(raw):
    if raw is None:
        return None
    if raw >= DARK_US:
        return 0
    if raw >= SHADE_US:
        return 1
    if raw >= SUN_US:
        return 2
    return 3


def moisture_connected(raw):
    return raw is not None and MOIST_UNPLUGGED_LOW < raw < MOIST_UNPLUGGED_HIGH


def moist_level(raw):
    if not moisture_connected(raw):
        return None
    if raw > PARCHED_RAW:
        return 0
    if raw > THIRSTY_RAW:
        return 1
    if raw > JUST_RIGHT_RAW:
        return 2
    if raw > SOGGY_RAW:
        return 3
    return 4
