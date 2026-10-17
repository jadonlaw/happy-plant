import secrets

from django.db import models


def new_token():
    return secrets.token_urlsafe(24)


class Signup(models.Model):
    """One person on the pre-launch waitlist. They get exactly two emails: confirmation, then launch."""

    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=60, blank=True, help_text="Where they came from, e.g. reddit-houseplants.")
    confirmation_sent_at = models.DateTimeField(null=True, blank=True)
    launch_sent_at = models.DateTimeField(null=True, blank=True)
    token = models.CharField(max_length=40, default=new_token, unique=True, editable=False,
                             help_text="For the one-click remove-me link in emails.")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email
