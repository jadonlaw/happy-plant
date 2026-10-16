from django.conf import settings
from django.db import models


class Profile(models.Model):
    """Extra info for each account. The login itself is Django's built-in User (username = email)."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    email_verified = models.BooleanField(default=False)
    temp_unit = models.CharField(max_length=1, choices=[("A", "Auto"), ("F", "Fahrenheit"), ("C", "Celsius")],
                                 default="A")
    time_zone = models.CharField(max_length=64, blank=True, help_text="From the phone, for sunrise/sunset times.")
    latitude = models.FloatField(null=True, blank=True, help_text="From the phone. Used for new units.")
    longitude = models.FloatField(null=True, blank=True)
    push_alerts = models.BooleanField(default=True)
    daily_checkin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.email


class EmailCode(models.Model):
    """A 6-digit code emailed to the user. Only a hash is stored, never the code itself."""

    VERIFY = "verify"
    RESET = "reset"
    PURPOSES = [(VERIFY, "Verify email"), (RESET, "Reset password")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_codes")
    purpose = models.CharField(max_length=10, choices=PURPOSES)
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "purpose", "-created_at"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} {self.purpose} {self.created_at:%Y-%m-%d %H:%M}"
