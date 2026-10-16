import json
from datetime import datetime, timedelta, timezone as dt_tz
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import Profile
from units import device
from units.models import Reading, Unit
from web import display
from web.sun import night_info

User = get_user_model()


def make_user(email="j@x.com", temp="F"):
    u = User.objects.create_user(username=email, email=email, password="Plant-Lover-2026", first_name="Jadon")
    Profile.objects.create(user=u, email_verified=True, temp_unit=temp)
    return u


class AppTest(TestCase):
    def setUp(self):
        cache.clear()
        device.LATEST.clear()
        device.LAST_SAVED.clear()
        device.MOIST_WINDOW.clear()
        device.LAST_WATER.clear()
        self.user = make_user()
        self.unit, self.secret = Unit.create_new()
        self.unit.owner = self.user
        self.unit.name = "Basil"
        self.unit.save()
        self.c = Client()
        self.c.force_login(self.user)

    def board(self, **data):
        r = Client().post("/api/device/readings", json.dumps(data), content_type="application/json",
                          HTTP_X_UNIT=self.unit.serial, HTTP_X_SECRET=self.secret)
        self.assertEqual(r.status_code, 200)

    def state(self, **headers):
        d = self.c.get("/api/app/state", **headers).json()
        self.assertTrue(d["ok"])
        return d

    def card(self, plant, k):
        return next((c for c in plant["cards"] if c["k"] == k), None)

    def test_page_has_newest_reading_baked_in(self):
        self.board(light_raw=1500, air_raw=1180, air_base=1225, moisture_raw=40000)
        html = self.c.get("/").content.decode()
        self.assertIn('id="hp-state"', html)
        self.assertIn("75\\u00b0F", html)  # the reading is in the page itself, no loading step
        self.assertIn("Basil", html)

    def test_logged_out_page_has_no_data(self):
        html = Client().get("/").content.decode()
        self.assertIn('<script id="hp-state" type="application/json">null</script>', html)

    def test_fresh_unit_shows_new_not_fake_numbers(self):
        p = self.state()["plants"][0]
        self.assertEqual(p["mood"]["cls"], "fresh")
        self.assertTrue(all(c["value"] == "—" for c in p["cards"]))

    def test_happy_and_words(self):
        self.board(light_raw=1500, air_raw=1180, air_base=1225, moisture_raw=40000, rssi=-50)
        p = self.state()["plants"][0]
        self.assertEqual(self.card(p, "air")["value"], "75°F")
        self.assertEqual(self.card(p, "air")["word"], "Cozy")
        self.assertEqual(self.card(p, "light")["value"], "Golden")
        self.assertEqual(self.card(p, "moist")["value"], "Just right")
        self.assertEqual(self.card(p, "soil")["word"], "Not connected")   # not wired = honest
        self.assertTrue(p["device"]["online"])
        self.assertEqual(p["device"]["wifi"], "Strong")
        if not p["night"]["on"]:
            self.assertEqual(p["mood"]["word"], "Happy")

    def test_dry_soil_makes_it_meh_and_alerts(self):
        self.board(light_raw=1500, air_raw=1180, air_base=1225, moisture_raw=50000)  # Thirsty
        d = self.state()
        p = d["plants"][0]
        self.assertEqual(p["mood"]["word"], "Meh")
        self.assertIn("needs water", p["mood"]["line"])
        self.assertEqual(len(d["alerts"]), 1)

    def test_celsius(self):
        self.c.post("/api/app/settings", json.dumps({"temp_unit": "C"}), content_type="application/json")
        self.board(air_raw=1180, air_base=1225)
        p = self.state()["plants"][0]
        self.assertEqual(self.card(p, "air")["value"], "24°C")
        self.assertEqual(p["wants"]["air"], [16, 29])

    def test_auto_unit_uses_phone_language(self):
        self.user.profile.temp_unit = "A"
        self.user.profile.save()
        self.board(air_raw=1180, air_base=1225)
        p = self.state(HTTP_ACCEPT_LANGUAGE="en-GB")["plants"][0]
        self.assertEqual(self.card(p, "air")["value"], "24°C")
        p = self.state(HTTP_ACCEPT_LANGUAGE="en-US")["plants"][0]
        self.assertEqual(self.card(p, "air")["value"], "75°F")

    def test_save_plant_and_wants_validation(self):
        r = self.c.post(f"/api/app/plant/{self.unit.serial}", json.dumps(
            {"name": "Desk Fern", "where": "Office", "wants": {"air": [60, 75], "soil": [58, 72], "light": [0, 1], "moist": [2, 3]}}),
            content_type="application/json").json()
        self.assertTrue(r["ok"])
        self.unit.refresh_from_db()
        self.assertEqual((self.unit.name, self.unit.where, self.unit.light_hi), ("Desk Fern", "Office", 1))
        bad = self.c.post(f"/api/app/plant/{self.unit.serial}", json.dumps(
            {"wants": {"air": [80, 60], "soil": [58, 72], "light": [0, 1], "moist": [2, 3]}}), content_type="application/json").json()
        self.assertFalse(bad["ok"])
        self.assertIn("Low has to be below high", bad["message"])

    def test_cannot_touch_someone_elses_plant(self):
        other = Client()
        other.force_login(make_user("dad@x.com"))
        self.assertEqual(other.post(f"/api/app/plant/{self.unit.serial}", json.dumps({"name": "x"}),
                                    content_type="application/json").status_code, 404)
        self.assertEqual(other.get("/api/app/state").json()["plants"], [])
        self.assertEqual(other.get(f"/api/app/history?serial={self.unit.serial}&range=day").status_code, 404)

    def test_location_and_night(self):
        r = self.c.post("/api/app/settings", json.dumps({"lat": 29.03, "lon": -81.30}), content_type="application/json").json()
        self.assertTrue(r["settings"]["has_location"])
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.latitude, 29.03)
        ny = ZoneInfo("America/New_York")
        midnight = datetime(2026, 10, 16, 4, 0, tzinfo=dt_tz.utc)     # midnight in Florida
        noon = datetime(2026, 10, 16, 16, 0, tzinfo=dt_tz.utc)
        self.assertTrue(night_info(midnight, 29.03, -81.30, ny)[0])
        self.assertFalse(night_info(noon, 29.03, -81.30, ny)[0])
        self.assertFalse(night_info(midnight, None, None, ny)[0])   # no location = never night

    def test_lookup(self):
        d = self.c.get("/api/app/lookup?name=Basil").json()
        self.assertEqual(d["wants"]["air"], [65, 85])
        self.assertEqual(self.c.get("/api/app/lookup?name=zzzz").status_code, 404)

    def test_photo_round_trip(self):
        png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        self.assertTrue(self.c.post(f"/api/app/plant/{self.unit.serial}", json.dumps({"photo": png}),
                                    content_type="application/json").json()["ok"])
        p = self.state()["plants"][0]
        r = self.c.get(p["photo"].split("?")[0])
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "image/png"))
        bad = self.c.post(f"/api/app/plant/{self.unit.serial}", json.dumps({"photo": "javascript:alert(1)"}),
                          content_type="application/json").json()
        self.assertFalse(bad["ok"])

    def test_history_buckets(self):
        now = timezone.now()
        for i, raw in enumerate([1180, 1200, 1220]):
            Reading.objects.create(unit=self.unit, received_at=now - timedelta(minutes=50 - i * 20), air_f=74 + i,
                                   light_raw=1500, moisture_raw=40000)
        d = self.c.get(f"/api/app/history?serial={self.unit.serial}&range=hour").json()
        self.assertEqual(len(d["buckets"]), 12)
        vals = [b["air"] for b in d["buckets"] if b["air"] is not None]
        self.assertEqual(vals, [74, 75, 76])
        self.assertTrue(all(b["light"] in (None, 2) for b in d["buckets"]))

    def test_watering_detected(self):
        self.board(moisture_raw=52000)          # thirsty
        self.board(moisture_raw=40000)          # big jump wetter = watered
        self.unit.refresh_from_db()
        self.assertIsNotNone(self.unit.last_watered_at)
        self.assertEqual(self.state()["plants"][0]["water"], "Watered today")

    def test_small_wiggle_is_not_watering(self):
        self.board(moisture_raw=47000)
        self.board(moisture_raw=45000)
        self.unit.refresh_from_db()
        self.assertIsNone(self.unit.last_watered_at)

    def test_unplugged_moisture_is_not_connected(self):
        self.board(moisture_raw=65535, light_raw=1500)
        p = self.state()["plants"][0]
        self.assertEqual(self.card(p, "moist")["word"], "Not connected")

    def test_offline_after_a_minute_shows_last_report(self):
        self.board(air_raw=1180, air_base=1225)
        device.LATEST[self.unit.serial]["received_at"] = timezone.now() - timedelta(minutes=5)
        p = self.state()["plants"][0]
        self.assertFalse(p["device"]["online"])
        self.assertIn("last reported 5 min ago", p["stale"])

    def test_time_zone_saved_from_phone(self):
        self.state(HTTP_X_TZ="America/Chicago")
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.time_zone, "America/Chicago")
        self.state(HTTP_X_TZ="Not/AZone")
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.time_zone, "America/Chicago")
