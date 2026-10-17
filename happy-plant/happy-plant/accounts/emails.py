"""Sends email through Twilio Email (https://comms.twilio.com/v1/Emails)."""
import base64
import json
import logging
import urllib.error
import urllib.request
from html import escape

from django.conf import settings

log = logging.getLogger(__name__)
TWILIO_EMAIL_URL = "https://comms.twilio.com/v1/Emails"
GREEN = "#2f7d32"


def send(to_email, to_name, subject, text, html):
    """Returns True if Twilio accepted the email. Never raises."""
    sid, secret = settings.TWILIO_API_KEY_SID, settings.TWILIO_API_KEY_SECRET
    if not sid or not secret:
        if settings.DEBUG:  # laptop testing only: print instead of sending
            log.warning("EMAIL (not sent, no Twilio keys) to %s: %s\n%s", to_email, subject, text)
            return True
        log.error("Email not sent: TWILIO_API_KEY_SID / TWILIO_API_KEY_SECRET missing in Railway Variables")
        return False

    recipient = {"address": to_email}
    if to_name:
        recipient["name"] = to_name
    body = {
        "from": {"address": settings.EMAIL_FROM, "name": settings.EMAIL_FROM_NAME},
        "to": [recipient],
        "content": {"subject": subject, "text": text, "html": html},
    }
    auth = base64.b64encode(f"{sid}:{secret}".encode()).decode()
    req = urllib.request.Request(
        TWILIO_EMAIL_URL, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status in (200, 201, 202):
                return True
            log.error("Twilio Email returned %s: %s", r.status, r.read()[:500])
    except urllib.error.HTTPError as e:
        log.error("Twilio Email error %s: %s", e.code, e.read()[:500])
    except Exception as e:  # network trouble
        log.error("Twilio Email failed: %s", e)
    return False


def _wrap(title, inner_html):
    return f"""<!doctype html><html><body style="margin:0;background:#f4f7f2;font-family:Arial,Helvetica,sans-serif;color:#111">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;background:#fff;border-radius:20px;padding:32px">
<tr><td style="font-size:22px;font-weight:bold;color:{GREEN};padding-bottom:16px">Happy Plant</td></tr>
<tr><td style="font-size:20px;font-weight:bold;padding-bottom:12px">{escape(title)}</td></tr>
<tr><td style="font-size:16px;line-height:1.5">{inner_html}</td></tr>
</table></td></tr></table></body></html>"""


def _code_block(code):
    return (f'<div style="font-size:36px;font-weight:bold;letter-spacing:8px;text-align:center;'
            f'background:#eef6ec;border-radius:16px;padding:16px;margin:20px 0">{code}</div>')


def send_verify_code(user, code):
    name = user.first_name or "there"
    subject = f"{code} is your Happy Plant code"
    text = (f"Hi {name},\n\nYour Happy Plant verification code is: {code}\n\n"
            "It expires in 10 minutes. If you didn't sign up, you can ignore this email.\n\n- Happy Plant")
    html = _wrap("Confirm your email", f"<p>Hi {escape(name)},</p><p>Enter this code in the Happy Plant app:</p>"
                 f"{_code_block(code)}<p style='color:#555;font-size:14px'>It expires in 10 minutes. "
                 "If you didn't sign up, you can ignore this email.</p>")
    return send(user.email, user.first_name, subject, text, html)


def send_reset_code(user, code):
    name = user.first_name or "there"
    subject = f"{code} is your Happy Plant reset code"
    text = (f"Hi {name},\n\nYour password reset code is: {code}\n\n"
            "It expires in 10 minutes. If you didn't ask to reset your password, you can ignore this email.\n\n"
            "- Happy Plant")
    html = _wrap("Reset your password", f"<p>Hi {escape(name)},</p><p>Enter this code in the Happy Plant app:</p>"
                 f"{_code_block(code)}<p style='color:#555;font-size:14px'>It expires in 10 minutes. "
                 "If you didn't ask to reset your password, you can ignore this email.</p>")
    return send(user.email, user.first_name, subject, text, html)


def send_happy_key(to_email, key):
    subject = "Your Happy Key"
    text = (f"Your Happy Plant is on the way!\n\nYour Happy Key is: {key}\n\n"
            "Open the Happy Plant app, sign in, and enter this key to connect your plant.\n"
            "Keep this email. The key stays with your Happy Plant.\n\n- Happy Plant")
    html = _wrap("Your Happy Plant is on the way!",
                 f"<p>Your Happy Key is:</p>{_code_block(escape(key))}"
                 "<p>Open the Happy Plant app, sign in, and enter this key to connect your plant.</p>"
                 "<p style='color:#555;font-size:14px'>Keep this email. The key stays with your Happy Plant.</p>")
    return send(to_email, "", subject, text, html)


LEAVE_URL = "https://happy-plant-production.up.railway.app/api/waitlist/leave?t="


def send_waitlist_confirmation(to_email, token):
    subject = "You're on the Happy Plant waitlist"
    text = ("Thanks for joining the Happy Plant waitlist!\n\n"
            "Happy Plant is a small sensor that sits in your plant's pot and checks light, temperature and soil "
            "moisture. Your phone shows a face, so you can tell at a glance if your plant is happy.\n\n"
            "This is one of only two emails you'll get from us. The next one comes when Happy Plant launches.\n\n"
            "- Jadon, Happy Plant\n\nDon't want these? Remove yourself: " + LEAVE_URL + token)
    html = _wrap("You're on the list!",
                 "<p>Thanks for joining the Happy Plant waitlist.</p>"
                 "<p>Happy Plant is a small sensor that sits in your plant's pot and checks light, temperature and "
                 "soil moisture. Your phone shows a face, so you can tell at a glance if your plant is happy.</p>"
                 "<p>This is one of only two emails you'll get from us. The next one comes when Happy Plant "
                 "launches.</p><p>— Jadon, Happy Plant</p>"
                 f"<p style='color:#777;font-size:12px;margin-top:24px'>Don't want these? "
                 f"<a href='{LEAVE_URL}{token}' style='color:#777'>Remove me from the list</a>.</p>")
    return send(to_email, "", subject, text, html)


def send_welcome(user):
    name = user.first_name or "there"
    subject = "Welcome to Happy Plant!"
    text = (f"Welcome to Happy Plant, {name}!\n\nYour account is ready.\n\n"
            "Next: enter the Happy Key from your email to connect your plant.\n\n- Happy Plant")
    html = _wrap(f"Welcome to Happy Plant, {name}!",
                 "<p>Your account is ready.</p><p><b>Next:</b> enter the Happy Key from your email to connect "
                 "your plant.</p>")
    return send(user.email, user.first_name, subject, text, html)
