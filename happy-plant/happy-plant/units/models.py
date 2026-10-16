import hashlib
import secrets

from django.conf import settings
from django.db import models

# No 0/O or 1/I so people don't mistype keys.
KEY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_happy_key():
    s = "".join(secrets.choice(KEY_ALPHABET) for _ in range(8))
    return f"HAPPY-{s[:4]}-{s[4:]}"


def hash_secret(secret):
    return hashlib.sha256(secret.encode()).hexdigest()


class Unit(models.Model):
    POWER_MODES = [("high", "High (every 5 min)"), ("medium", "Medium (every 15 min)"), ("low", "Low (every 45 min)")]

    serial = models.CharField(max_length=12, unique=True, editable=False)
    happy_key = models.CharField(max_length=16, unique=True, editable=False,
                                 help_text="Permanent pairing code for this unit.")
    secret_hash = models.CharField(max_length=64, editable=False,
                                   help_text="Hash of the hidden board secret. The secret itself is never stored.")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="units")
    paired_at = models.DateTimeField(null=True, blank=True)
    name = models.CharField(max_length=40, blank=True, help_text="Plant name the owner sees.")
    power_mode = models.CharField(max_length=6, choices=POWER_MODES, default="medium")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    battery_pct = models.PositiveSmallIntegerField(null=True, blank=True)
    buyer_email = models.EmailField(blank=True, help_text="Where 'Email Happy Key' sends this unit's key.")
    key_sent_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=200, blank=True, help_text="Admin-only notes.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["serial"]

    def __str__(self):
        return self.serial

    def check_secret(self, secret):
        return secrets.compare_digest(self.secret_hash, hash_secret(secret or ""))

    def assign_identity(self):
        """Give a brand-new unit its serial, permanent Happy Key and board secret. Returns the board secret
        (shown once, never stored)."""
        last = Unit.objects.order_by("-id").first()
        number = (int(last.serial.split("-")[1]) + 1) if last else 1
        key = new_happy_key()
        while Unit.objects.filter(happy_key=key).exists():
            key = new_happy_key()
        board_secret = secrets.token_urlsafe(24)
        self.serial = f"HP-{number:04d}"
        self.happy_key = key
        self.secret_hash = hash_secret(board_secret)
        return board_secret

    @classmethod
    def create_new(cls, **fields):
        unit = cls(**fields)
        board_secret = unit.assign_identity()
        unit.save()
        return unit, board_secret
