import json
import re
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from accounts.models import EmailCode

SENT = []


def fake_send(to_email, to_name, subject, text, html):
    SENT.append({"to": to_email, "subject": subject, "text": text})
    return True


def last_code(email):
    for m in reversed(SENT):
        if m["to"] == email:
            found = re.search(r"\b(\d{6})\b", m["subject"])
            if found:
                return found.group(1)
    return None


@mock.patch("accounts.emails.send", side_effect=fake_send)
class AccountsTest(TestCase):
    def setUp(self):
        SENT.clear()
        cache.clear()
        self.c = Client()

    def post(self, path, data, client=None):
        r = (client or self.c).post("/api/auth/" + path, json.dumps(data), content_type="application/json")
        return r.status_code, r.json()

    def signup(self, email="jadon@example.com", pw="Plant-Lover-2026"):
        return self.post("signup", {"first_name": "Jadon", "email": email, "password": pw})

    def test_full_signup_verify_login_flow(self, _):
        s, d = self.signup()
        self.assertEqual((s, d["next"]), (200, "verify"))
        code = last_code("jadon@example.com")
        self.assertIsNotNone(code)
        self.assertEqual(self.c.get("/api/auth/me").status_code, 401)  # not in until verified
        s, d = self.post("verify", {"email": "jadon@example.com", "code": code})
        self.assertEqual(s, 200, d)
        self.assertEqual(d["user"]["first_name"], "Jadon")
        self.assertTrue(any("Welcome" in m["subject"] for m in SENT))
        self.assertEqual(self.c.get("/api/auth/me").json()["user"]["email"], "jadon@example.com")
        self.post("logout", {})
        self.assertEqual(self.c.get("/api/auth/me").status_code, 401)
        s, d = self.post("login", {"email": "JADON@example.com ", "password": "Plant-Lover-2026"})
        self.assertEqual(s, 200, d)

    def test_bad_inputs(self, _):
        self.assertEqual(self.post("signup", {"email": "a@b.com", "password": "x"})[1]["error"], "first_name")
        self.assertEqual(self.post("signup", {"first_name": "J", "email": "nope", "password": "x"})[1]["error"], "email")
        s, d = self.post("signup", {"first_name": "J", "email": "a@b.com", "password": "short"})
        self.assertEqual(d["error"], "password")
        s, d = self.post("signup", {"first_name": "J", "email": "a@b.com", "password": "password123"})
        self.assertEqual(d["error"], "password")  # too common

    def test_duplicate_verified_email_rejected(self, _):
        self.signup()
        self.post("verify", {"email": "jadon@example.com", "code": last_code("jadon@example.com")})
        s, d = self.signup()
        self.assertEqual((s, d["error"]), (409, "email_taken"))

    def test_wrong_codes_lock_after_five(self, _):
        self.signup()
        for i in range(4):
            s, d = self.post("verify", {"email": "jadon@example.com", "code": "000000"})
            self.assertEqual(d["error"], "wrong")
        self.assertIn("1 try left", d["message"])
        s, d = self.post("verify", {"email": "jadon@example.com", "code": "000000"})
        self.assertEqual((s, d["error"]), (429, "locked"))
        # even the right code fails while locked
        s, d = self.post("verify", {"email": "jadon@example.com", "code": last_code("jadon@example.com")})
        self.assertEqual(d["error"], "locked")
        # and no new code can be requested while locked
        s, d = self.post("resend", {"email": "jadon@example.com", "purpose": "verify"})
        self.assertEqual(d["error"], "locked")

    def test_code_expires(self, _):
        self.signup()
        EmailCode.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        s, d = self.post("verify", {"email": "jadon@example.com", "code": last_code("jadon@example.com")})
        self.assertEqual(d["error"], "expired")

    def test_resend_wait_and_old_code_dies(self, _):
        self.signup()
        old = last_code("jadon@example.com")
        s, d = self.post("resend", {"email": "jadon@example.com", "purpose": "verify"})
        self.assertEqual((s, d["error"]), (429, "wait"))
        EmailCode.objects.update(created_at=timezone.now() - timedelta(seconds=61))
        s, d = self.post("resend", {"email": "jadon@example.com", "purpose": "verify"})
        self.assertEqual(s, 200, d)
        new = last_code("jadon@example.com")
        if new != old:
            s, d = self.post("verify", {"email": "jadon@example.com", "code": old})
            self.assertEqual(d["error"], "wrong")
        s, d = self.post("verify", {"email": "jadon@example.com", "code": new})
        self.assertEqual(s, 200, d)

    def test_unverified_login_asks_for_code(self, _):
        self.signup()
        s, d = self.post("login", {"email": "jadon@example.com", "password": "Plant-Lover-2026"})
        self.assertEqual((s, d["error"], d["next"]), (403, "verify_email", "verify"))

    def test_wrong_password_and_lockout(self, _):
        self.signup()
        self.post("verify", {"email": "jadon@example.com", "code": last_code("jadon@example.com")})
        for _i in range(10):
            s, d = self.post("login", {"email": "jadon@example.com", "password": "nope"}, Client())
            self.assertEqual(d["error"], "wrong_login")
        s, d = self.post("login", {"email": "jadon@example.com", "password": "Plant-Lover-2026"}, Client())
        self.assertEqual((s, d["error"]), (429, "locked"))

    def test_password_reset(self, _):
        self.signup()
        self.post("verify", {"email": "jadon@example.com", "code": last_code("jadon@example.com")})
        other_device = Client()
        self.post("login", {"email": "jadon@example.com", "password": "Plant-Lover-2026"}, other_device)
        self.assertEqual(other_device.get("/api/auth/me").status_code, 200)

        fresh = Client()
        s, d = self.post("reset/request", {"email": "jadon@example.com"}, fresh)
        self.assertEqual(s, 200)
        code = last_code("jadon@example.com")
        self.assertIn("reset", SENT[-1]["subject"])
        s, d = self.post("reset/confirm", {"email": "jadon@example.com", "code": code,
                                           "new_password": "Brand-New-Leaf-77"}, fresh)
        self.assertEqual(s, 200, d)
        self.assertEqual(other_device.get("/api/auth/me").status_code, 401)  # old devices logged out
        s, d = self.post("login", {"email": "jadon@example.com", "password": "Brand-New-Leaf-77"}, Client())
        self.assertEqual(s, 200)
        s, d = self.post("login", {"email": "jadon@example.com", "password": "Plant-Lover-2026"}, Client())
        self.assertEqual(s, 401)

    def test_reset_unknown_email_gives_same_answer(self, _):
        s, d = self.post("reset/request", {"email": "ghost@example.com"})
        self.assertEqual(s, 200)
        self.assertIn("If ghost@example.com has an account", d["message"])
        self.assertEqual(SENT, [])

    def test_csrf_required(self, _):
        c = Client(enforce_csrf_checks=True)
        r = c.post("/api/auth/signup", "{}", content_type="application/json")
        self.assertEqual(r.status_code, 403)
        c.get("/api/auth/csrf")
        token = c.cookies["csrftoken"].value
        r = c.post("/api/auth/signup", json.dumps({"first_name": "J", "email": "x@y.com", "password": "Plant-Lover-2026"}),
                   content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(r.status_code, 200)

    def test_test_page_off_by_default(self, _):
        self.assertEqual(self.c.get("/test/accounts").status_code, 404)
        with override_settings(TEST_PAGES=True):
            self.assertEqual(self.c.get("/test/accounts").status_code, 200)


class TwilioPayloadTest(TestCase):
    @override_settings(TWILIO_API_KEY_SID="SKtest", TWILIO_API_KEY_SECRET="sec", EMAIL_FROM="hello@happyplant.shop")
    def test_payload_matches_twilio_docs(self):
        captured = {}

        class Resp:
            status = 202
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return b"{}"

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            captured["auth"] = req.get_header("Authorization")
            captured["body"] = json.loads(req.data)
            return Resp()

        from accounts import emails
        with mock.patch("urllib.request.urlopen", fake_urlopen):
            self.assertTrue(emails.send("a@b.com", "Al", "Hi", "text", "<p>html</p>"))
        self.assertEqual(captured["url"], "https://comms.twilio.com/v1/Emails")
        self.assertTrue(captured["auth"].startswith("Basic "))
        b = captured["body"]
        self.assertEqual(b["from"], {"address": "hello@happyplant.shop", "name": "Happy Plant"})
        self.assertEqual(b["to"], [{"address": "a@b.com", "name": "Al"}])
        self.assertEqual(set(b["content"]), {"subject", "text", "html"})
