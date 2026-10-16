"""6-digit email codes: make them, check them, lock after too many wrong tries."""
import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import EmailCode

CODE_LIFETIME = timedelta(minutes=10)
MAX_WRONG = 5
LOCK_TIME = timedelta(minutes=15)
RESEND_WAIT = timedelta(seconds=60)


class CodeError(Exception):
    def __init__(self, kind, message, **extra):
        super().__init__(message)
        self.kind = kind  # "locked", "wait", "wrong", "expired", "none"
        self.message = message
        self.extra = extra


def _hash(user, purpose, code):
    msg = f"{user.pk}:{purpose}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def _latest(user, purpose):
    return EmailCode.objects.filter(user=user, purpose=purpose).order_by("-created_at").first()


def _minutes(td):
    return max(1, int((td.total_seconds() + 59) // 60))


def _check_lock(latest, now):
    if latest and latest.locked_until and latest.locked_until > now:
        mins = _minutes(latest.locked_until - now)
        raise CodeError("locked", f"Too many wrong codes. Try again in {mins} minute{'s' if mins != 1 else ''}.",
                        retry_after=int((latest.locked_until - now).total_seconds()))


def issue(user, purpose):
    """Make a new code (old ones stop working). Returns the plain code so it can be emailed."""
    now = timezone.now()
    latest = _latest(user, purpose)
    _check_lock(latest, now)
    if latest and latest.used_at is None and now - latest.created_at < RESEND_WAIT:
        secs = int((RESEND_WAIT - (now - latest.created_at)).total_seconds()) + 1
        raise CodeError("wait", f"We just sent a code. You can ask for a new one in {secs} seconds.", retry_after=secs)

    EmailCode.objects.filter(user=user, purpose=purpose, used_at__isnull=True).update(used_at=now)
    code = f"{secrets.randbelow(1_000_000):06d}"
    EmailCode.objects.create(user=user, purpose=purpose, code_hash=_hash(user, purpose, code),
                             expires_at=now + CODE_LIFETIME)
    return code


def check(user, purpose, code):
    """Raises CodeError if the code is wrong, expired or locked. Marks it used when right."""
    now = timezone.now()
    latest = _latest(user, purpose)
    _check_lock(latest, now)
    if latest is None or latest.used_at is not None:
        raise CodeError("none", "That code isn't valid anymore. Ask for a new one.")
    if latest.expires_at <= now:
        raise CodeError("expired", "That code expired. Ask for a new one.")

    code = (code or "").strip().replace(" ", "")
    if hmac.compare_digest(latest.code_hash, _hash(user, purpose, code)):
        latest.used_at = now
        latest.save(update_fields=["used_at"])
        return True

    latest.attempts += 1
    left = MAX_WRONG - latest.attempts
    if left <= 0:
        latest.locked_until = now + LOCK_TIME
        latest.save(update_fields=["attempts", "locked_until"])
        _check_lock(latest, now)
    latest.save(update_fields=["attempts"])
    raise CodeError("wrong", f"That code isn't right. {left} tr{'ies' if left != 1 else 'y'} left.", tries_left=left)
