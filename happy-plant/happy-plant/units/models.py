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

    # The plant this unit watches (one unit = one plant)
    where = models.CharField(max_length=40, blank=True, help_text="Where the plant lives, e.g. Kitchen window.")
    photo = models.TextField(blank=True, help_text="Small JPEG as a data URL (the app shrinks it to 256px).")
    last_watered_at = models.DateTimeField(null=True, blank=True)
    # What the plant needs. Temps in °F. Light 0-3 (Gloomy..Blazing). Moisture 0-4 (Parched..Drowning).
    air_lo = models.FloatField(default=60)
    air_hi = models.FloatField(default=85)
    soil_lo = models.FloatField(default=55)
    soil_hi = models.FloatField(default=80)
    light_lo = models.PositiveSmallIntegerField(default=1)
    light_hi = models.PositiveSmallIntegerField(default=2)
    moist_lo = models.PositiveSmallIntegerField(default=2)
    moist_hi = models.PositiveSmallIntegerField(default=3)

    class Meta:
        ordering = ["serial"]

    @property
    def wants(self):
        return {"air": [self.air_lo, self.air_hi], "soil": [self.soil_lo, self.soil_hi],
                "light": [self.light_lo, self.light_hi], "moist": [self.moist_lo, self.moist_hi]}

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

    SAVE_EVERY_MIN = {"high": 5, "medium": 15, "low": 45}

    @property
    def save_every_seconds(self):
        return self.SAVE_EVERY_MIN.get(self.power_mode, 15) * 60

    @classmethod
    def create_new(cls, **fields):
        unit = cls(**fields)
        board_secret = unit.assign_identity()
        unit.save()
        return unit, board_secret


class Reading(models.Model):
    """One saved reading from a board. Empty (null) means that sensor wasn't connected. Never filled in or guessed."""

    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="readings")
    received_at = models.DateTimeField(db_index=True)
    light_raw = models.PositiveIntegerField(null=True, blank=True, help_text="Light charge time in microseconds. Bigger = darker.")
    air_f = models.FloatField(null=True, blank=True)
    air_raw = models.PositiveIntegerField(null=True, blank=True)
    moisture_raw = models.PositiveIntegerField(null=True, blank=True, help_text="0-65535. Bigger = drier.")
    soil_f = models.FloatField(null=True, blank=True)
    battery_pct = models.PositiveSmallIntegerField(null=True, blank=True)
    rssi = models.SmallIntegerField(null=True, blank=True, help_text="Wi-Fi signal in dBm.")

    class Meta:
        ordering = ["-received_at"]
        indexes = [models.Index(fields=["unit", "-received_at"])]

    def __str__(self):
        return f"{self.unit.serial} {self.received_at:%Y-%m-%d %H:%M}"


# When a unit changes or is deleted, drop its cached board login so the board sees the change right away.
from django.db.models.signals import post_delete, post_save  # noqa: E402
from django.dispatch import receiver  # noqa: E402


@receiver([post_save, post_delete], sender=Unit)
def _forget_unit_cache(sender, instance, **kwargs):
    from django.core.cache import cache
    cache.delete(f"unit_auth:{instance.serial}")
