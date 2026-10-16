import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from accounts.models import Profile
from units.models import KEY_ALPHABET, Unit
from units.views import normalize_key

User = get_user_model()


def make_user(email, verified=True):
    u = User.objects.create_user(username=email, email=email, password="Plant-Lover-2026", first_name="T")
    Profile.objects.create(user=u, email_verified=verified)
    return u


class UnitsTest(TestCase):
    def setUp(self):
        cache.clear()
        self.jadon = make_user("jadon@example.com")
        self.dad = make_user("dad@example.com")
        self.unit, self.secret = Unit.create_new()

    def client_for(self, user):
        c = Client()
        c.force_login(user)
        return c

    def post(self, c, path, data=None):
        r = c.post("/api/units/" + path, json.dumps(data or {}), content_type="application/json")
        return r.status_code, r.json()

    def test_new_unit_identity(self):
        u2, s2 = Unit.create_new()
        self.assertEqual((self.unit.serial, u2.serial), ("HP-0001", "HP-0002"))
        self.assertRegex(self.unit.happy_key, r"^HAPPY-[A-Z2-9]{4}-[A-Z2-9]{4}$")
        self.assertTrue(all(ch in KEY_ALPHABET for ch in self.unit.happy_key[6:].replace("-", "")))
        self.assertNotIn(self.secret, self.unit.secret_hash)  # only the hash is stored
        self.assertTrue(self.unit.check_secret(self.secret))
        self.assertFalse(self.unit.check_secret("wrong"))
        self.assertNotEqual(self.secret, s2)

    def test_key_normalizing(self):
        k = self.unit.happy_key
        for typed in (k, k.lower(), k[6:].replace("-", ""), " " + k[6:10] + " " + k[11:] + " "):
            self.assertEqual(normalize_key(typed), k)
        self.assertIsNone(normalize_key("HAPPY-0000-1111"))  # 0 and 1 never used
        self.assertIsNone(normalize_key("abc"))

    def test_must_be_logged_in(self):
        s, d = self.post(Client(), "pair", {"key": self.unit.happy_key})
        self.assertEqual((s, d["error"]), (401, "not_logged_in"))
        unverified = make_user("new@example.com", verified=False)
        s, d = self.post(self.client_for(unverified), "pair", {"key": self.unit.happy_key})
        self.assertEqual(s, 401)

    def test_pair_list_remove_and_repair_by_someone_else(self):
        cj, cd = self.client_for(self.jadon), self.client_for(self.dad)
        s, d = self.post(cj, "pair", {"key": self.unit.happy_key.lower()})
        self.assertEqual((s, d["unit"]["serial"]), (200, "HP-0001"))
        self.assertEqual([u["serial"] for u in cj.get("/api/units/").json()["units"]], ["HP-0001"])
        self.assertEqual(cd.get("/api/units/").json()["units"], [])  # dad sees nothing

        s, d = self.post(cj, "pair", {"key": self.unit.happy_key})  # again: fine, already yours
        self.assertEqual(s, 200)
        s, d = self.post(cd, "pair", {"key": self.unit.happy_key})  # dad can't take it
        self.assertEqual((s, d["error"]), (409, "taken"))
        s, d = self.post(cd, "HP-0001/remove")  # and can't remove it
        self.assertEqual(s, 404)

        s, d = self.post(cj, "HP-0001/remove")
        self.assertEqual(s, 200)
        s, d = self.post(cd, "pair", {"key": self.unit.happy_key})  # same permanent key works for new owner
        self.assertEqual(s, 200)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.owner, self.dad)

    def test_wrong_keys_lock(self):
        c = self.client_for(self.jadon)
        for _ in range(10):
            s, d = self.post(c, "pair", {"key": "HAPPY-AAAA-AAAA"})
            self.assertEqual(d["error"], "wrong_key")
        s, d = self.post(c, "pair", {"key": self.unit.happy_key})
        self.assertEqual((s, d["error"]), (429, "locked"))

    def test_make_admin_command(self):
        call_command("make_admin", "JADON@example.com")
        self.jadon.refresh_from_db()
        self.assertTrue(self.jadon.is_staff and self.jadon.is_superuser)

    @override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                                 "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_admin_add_unit_shows_secret_once_and_emails_key(self):
        call_command("make_admin", "jadon@example.com")
        c = self.client_for(self.jadon)
        r = c.post("/admin/units/unit/add/", {"buyer_email": "buyer@example.com", "name": "", "power_mode": "medium",
                                              "notes": ""}, follow=True)
        self.assertEqual(r.status_code, 200)
        page = r.content.decode()
        self.assertIn("HP-0002", page)
        self.assertIn("BOARD SECRET", page)
        new = Unit.objects.get(serial="HP-0002")
        with mock.patch("units.admin.send_happy_key", return_value=True) as sender:
            c.post("/admin/units/unit/", {"action": "email_happy_key", "_selected_action": [new.pk]}, follow=True)
        sender.assert_called_once_with("buyer@example.com", new.happy_key)
        new.refresh_from_db()
        self.assertIsNotNone(new.key_sent_at)
        # the secret is not shown again on the unit page
        r = c.get(f"/admin/units/unit/{new.pk}/change/")
        self.assertNotIn("BOARD SECRET", r.content.decode())
