# =============================================================================
#  HAPPY PLANT  --  ESP32-S3 SuperMini firmware  (MicroPython)  --  step 4
# =============================================================================
#  Reads the sensors and sends the RAW numbers to the Happy Plant backend on
#  Railway every 10 seconds. The backend does all the thinking (temperature,
#  words, mood). A sensor that isn't connected is sent as null -- never guessed.
#
#  WIRING (all sensors off the 3V3 pin, nothing on 5V)
#    Photoresistor   one leg -> 3V3, other leg -> GPIO 1, 104 cap GPIO 1 -> GND
#    Air thermistor  one leg -> 3V3, other leg -> GPIO 2, 104 cap GPIO 2 -> GND
#    Soil thermistor same idea on GPIO 3 (not wired yet -> sends null)
#    Moisture        red -> 3V3, black -> GND, yellow -> GPIO 4
#
#  SAVE THIS FILE TO THE BOARD AS  main.py  (boot.py stays empty), press reset.
# =============================================================================

import gc
import json
import time

import machine
import network
from machine import ADC, Pin

try:
    import requests
except ImportError:
    import urequests as requests

# ---------------- settings ----------------
WIFI_NAME = "Law103"
WIFI_PASSWORD = "internet0"

SERVER = "https://happy-plant-production.up.railway.app/api/device/readings"
SERIAL = "HP-0005"                        # must match the unit in /admin
SECRET = "KvGaCKCn1DlX1RUf4XPkDmKJ0z3F65mL"     # this unit's board secret

USE_WATCHDOG = False   # turn on (True) for the demo: auto-restarts the board if it ever freezes

# ---------------- pins ----------------
ldr_pin = Pin(1)
air_pin = Pin(2)
soil_pin = Pin(3)
moisture_adc = ADC(Pin(4))
moisture_adc.atten(ADC.ATTN_11DB)   # full 0-3.3 V range

DISCHARGE_US = 2000
CHARGE_LIMIT_US = 50000   # no rise by now = sensor not connected


def read_timed(pin):
    """Drain the cap, let go, time how long it takes to charge back up."""
    pin.init(Pin.OUT)
    pin.value(0)
    time.sleep_us(DISCHARGE_US)
    pin.init(Pin.IN)
    start = time.ticks_us()
    while not pin.value():
        if time.ticks_diff(time.ticks_us(), start) > CHARGE_LIMIT_US:
            return None
    return time.ticks_diff(time.ticks_us(), start)


def read_median(pin, n=5):
    vals = []
    for _ in range(n):
        v = read_timed(pin)
        if v is not None:
            vals.append(v)
        time.sleep_ms(5)
    if len(vals) < (n // 2 + 1):   # mostly timeouts = not connected
        return None
    vals.sort()
    return vals[len(vals) // 2]


def read_moisture(n=8):
    total = 0
    for _ in range(n):
        total += moisture_adc.read_u16()
        time.sleep_ms(2)
    return total // n


def baseline(pin):
    """Average of many reads at boot. The backend uses it to turn raw reads into degrees."""
    vals = []
    for _ in range(20):
        v = read_timed(pin)
        if v is not None:
            vals.append(v)
        time.sleep_ms(20)
    return int(sum(vals) / len(vals)) if len(vals) >= 15 else None


# ---------------- Wi-Fi ----------------
wlan = network.WLAN(network.STA_IF)


def wifi_connect():
    if wlan.isconnected():
        return True
    wlan.active(True)
    print("Wi-Fi: joining", WIFI_NAME)
    wlan.connect(WIFI_NAME, WIFI_PASSWORD)
    for _ in range(40):          # up to 20 s
        if wlan.isconnected():
            print("Wi-Fi: connected", wlan.ifconfig()[0])
            return True
        time.sleep_ms(500)
    print("Wi-Fi: could not connect")
    return False


def rssi():
    try:
        return wlan.status("rssi")
    except Exception:
        return None


# ---------------- boot ----------------
print("Happy Plant", SERIAL, "booting")
time.sleep_ms(500)
air_base = baseline(air_pin)
soil_base = baseline(soil_pin)
print("air baseline:", air_base, "| soil baseline:", soil_base)

watchdog = machine.WDT(timeout=60000) if USE_WATCHDOG else None
post_every_s = 10
fails = 0

# ---------------- main loop ----------------
while True:
    started = time.ticks_ms()
    try:
        # thermistor plugged in after boot? grab its baseline now
        if air_base is None:
            air_base = baseline(air_pin)
        if soil_base is None:
            soil_base = baseline(soil_pin)

        air_raw = read_median(air_pin) if air_base else None
        soil_raw = read_median(soil_pin) if soil_base else None
        data = {
            "light_raw": read_median(ldr_pin),
            "air_raw": air_raw,
            "air_base": air_base if air_raw is not None else None,
            "soil_raw": soil_raw,
            "soil_base": soil_base if soil_raw is not None else None,
            "moisture_raw": read_moisture(),
            "battery_pct": None,     # no battery hardware yet
            "rssi": None,
            "uptime_s": time.ticks_ms() // 1000,
        }

        if wifi_connect():
            data["rssi"] = rssi()
            r = requests.post(SERVER, data=json.dumps(data),
                              headers={"Content-Type": "application/json", "X-Unit": SERIAL, "X-Secret": SECRET})
            status = r.status_code
            reply = r.json() if status == 200 else {}
            r.close()
            if status == 200:
                post_every_s = reply.get("next_post_s", 10)
                fails = 0
                print("light", data["light_raw"], "| air", air_raw, "/", air_base, "| moist", data["moisture_raw"],
                      "| wifi", data["rssi"], "| sent", "(saved)" if reply.get("saved") else "")
            elif status == 401:
                fails += 1
                print("Server says SERIAL or SECRET is wrong (401). Check the top of main.py.")
            else:
                fails += 1
                print("Server error", status)
        else:
            fails += 1
    except Exception as e:
        fails += 1
        print("Error:", e)

    if fails >= 10:
        print("10 failures in a row, restarting")
        time.sleep_ms(500)
        machine.reset()

    gc.collect()
    while time.ticks_diff(time.ticks_ms(), started) < post_every_s * 1000:
        if watchdog:
            watchdog.feed()
        time.sleep_ms(200)
    if watchdog:
        watchdog.feed()
