import json
from unittest import mock

from django.core.cache import cache
from django.test import Client, TestCase

from waitlist.models import Signup


class WaitlistTest(TestCase):
    def setUp(self):
        cache.clear()
        self.c = Client(enforce_csrf_checks=True)

    def post(self, data, **kw):
        r = self.c.post("/api/waitlist", json.dumps(data), content_type="application/json", **kw)
        return r, r.json()

    @mock.patch("waitlist.views.send_waitlist_confirmation", return_value=True)
    def test_join_once_one_email(self, send):
        r, d = self.post({"email": " Fan@Example.com ", "source": "Reddit-Houseplants!"})
        self.assertTrue(d["ok"])
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")
        s = Signup.objects.get()
        self.assertEqual((s.email, s.source), ("fan@example.com", "reddit-houseplants"))
        self.assertIsNotNone(s.confirmation_sent_at)
        r, d = self.post({"email": "fan@example.com"})
        self.assertTrue(d.get("already"))
        self.assertEqual(send.call_count, 1)  # never a second confirmation

    @mock.patch("waitlist.views.send_waitlist_confirmation", return_value=True)
    def test_bad_email_and_bot(self, send):
        r, d = self.post({"email": "nope"})
        self.assertEqual(r.status_code, 400)
        r, d = self.post({"email": "bot@example.com", "website": "spam.com"})
        self.assertTrue(d["ok"])
        self.assertEqual(Signup.objects.count(), 0)
        send.assert_not_called()

    def test_preflight(self):
        r = self.c.options("/api/waitlist", HTTP_ORIGIN="https://happyplant.shop")
        self.assertEqual(r.status_code, 204)
        self.assertIn("POST", r["Access-Control-Allow-Methods"])

    @mock.patch("waitlist.views.send_waitlist_confirmation", return_value=True)
    def test_rate_limit(self, send):
        for i in range(8):
            self.post({"email": f"a{i}@example.com"})
        r, d = self.post({"email": "z@example.com"})
        self.assertEqual(r.status_code, 429)

    @mock.patch("waitlist.views.send_waitlist_confirmation", return_value=False)
    def test_email_failure_still_saves_without_claiming_inbox(self, send):
        r, d = self.post({"email": "x@example.com"})
        self.assertTrue(d["ok"])
        self.assertNotIn("inbox", d["message"])
        self.assertIsNone(Signup.objects.get().confirmation_sent_at)


class LeaveTest(TestCase):
    def test_leave_link(self):
        s = Signup.objects.create(email="bye@example.com")
        r = Client().get(f"/api/waitlist/leave?t={s.token}")
        self.assertIn("off the Happy Plant waitlist", r.content.decode())
        self.assertFalse(Signup.objects.exists())
        r = Client().get(f"/api/waitlist/leave?t={s.token}")
        self.assertIn("already been used", r.content.decode())
