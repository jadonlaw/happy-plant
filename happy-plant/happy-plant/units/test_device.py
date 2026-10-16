import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import Profile
from units import device
from units.models import Reading, Unit

User = get_user_model()


class DeviceTest(TestCase):
    def setUp(self):
        cache.clear()
        device.LATEST.clear()
        device.LAST_SAVED.clear()
        self.unit, self.secret = Unit.create_new()
        self.c = Client(enforce_csrf_checks=True)  # boards don't do CSRF; endpoint must still work

    def send(self, payload, serial=None, secret=None):
        r = self.c.post("/api/device/readings", json.dumps(payload), content_type="application/json",
                        HTTP_X_UNIT=serial or self.unit.serial, HTTP_X_SECRET=secret or self.secret)
        return r.status_code, r.json()

    def test_wrong_secret_or_serial_rejected(self):
        self.assertEqual(self.send({}, secret="nope")[0], 401)
        self.assertEqual(self.send({}, serial="HP-9999")[0], 401)
        self.assertEqual(Reading.objects.count(), 0)

    def test_first_reading_saved_then_waits_for_power_mode(self):
        s, d = self.send({"light_raw": 2300, "air_raw": 1180, "air_base": 1225, "moisture_raw": 41000, "rssi": -60})
        self.assertEqual((s, d["saved"], d["power_mode"], d["next_post_s"]), (200, True, "medium", 10))
        r = Reading.objects.get()
        self.assertEqual(r.air_f, 75.0)  # 74 + (1225-1180)/45
        self.assertEqual((r.light_raw, r.moisture_raw, r.rssi), (2300, 41000, -60))
        self.unit.refresh_from_db()
        self.assertIsNotNone(self.unit.last_seen)

        s, d = self.send({"light_raw": 2400})  # 10 s later: memory only
        self.assertFalse(d["saved"])
        self.assertEqual(Reading.objects.count(), 1)
        self.assertEqual(device.latest_for("HP-0001")["data"]["light_raw"], 2400)

        device.LAST_SAVED["HP-0001"] = timezone.now() - timedelta(minutes=15, seconds=1)
        s, d = self.send({"light_raw": 2500})
        self.assertTrue(d["saved"])
        self.assertEqual(Reading.objects.count(), 2)

    def test_disconnected_sensors_stay_empty(self):
        self.send({"light_raw": None, "air_raw": None, "air_base": None, "moisture_raw": None})
        r = Reading.objects.get()
        self.assertEqual((r.light_raw, r.air_f, r.moisture_raw, r.soil_f), (None, None, None, None))

    def test_junk_values_become_empty_not_guessed(self):
        self.send({"light_raw": "abc", "air_raw": 50000, "air_base": 1200, "moisture_raw": 99999, "rssi": 5})
        r = Reading.objects.get()
        self.assertEqual((r.light_raw, r.air_f, r.moisture_raw, r.rssi), (None, None, None, None))

    def test_secret_check_does_not_hit_database_every_time(self):
        self.send({"light_raw": 1})
        with self.assertNumQueries(0):
            self.send({"light_raw": 2})

    def test_power_mode_change_reaches_board(self):
        self.send({"light_raw": 1})
        self.unit.power_mode = "high"
        self.unit.save()
        s, d = self.send({"light_raw": 2})
        self.assertEqual(d["power_mode"], "high")

    def test_owner_sees_live_reading_others_dont(self):
        owner = User.objects.create_user(username="j@x.com", email="j@x.com", password="Plant-Lover-2026")
        Profile.objects.create(user=owner, email_verified=True)
        other = User.objects.create_user(username="d@x.com", email="d@x.com", password="Plant-Lover-2026")
        Profile.objects.create(user=other, email_verified=True)
        self.unit.owner = owner
        self.unit.save()
        co, cx = Client(), Client()
        co.force_login(owner)
        cx.force_login(other)

        d = co.get("/api/units/HP-0001/live").json()
        self.assertEqual((d["online"], d["reading"]), (False, None))
        self.send({"light_raw": 2300, "air_raw": 1180, "air_base": 1225, "moisture_raw": 41000})
        d = co.get("/api/units/HP-0001/live").json()
        self.assertTrue(d["online"])
        self.assertEqual(d["reading"]["air_f"], 75.0)
        self.assertEqual(cx.get("/api/units/HP-0001/live").status_code, 404)
