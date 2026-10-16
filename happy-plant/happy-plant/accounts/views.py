"""Account API. Every reply is JSON the app shows as-is: {"ok": true/false, "message": ..., ...}."""
import json

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from . import codes, emails
from .models import EmailCode, Profile

User = get_user_model()
LOGIN_MAX_FAILS = 10
LOGIN_LOCK_SECONDS = 15 * 60


# ---------- helpers ----------
def ok(status=200, **data):
    return JsonResponse({"ok": True, **data}, status=status)


def fail(error, message, status=400, **data):
    return JsonResponse({"ok": False, "error": error, "message": message, **data}, status=status)


def body(request):
    try:
        data = json.loads(request.body or b"{}")
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


def clean_email(raw):
    email = (raw or "").strip().lower()
    try:
        validate_email(email)
    except ValidationError:
        return None
    return email


def find_user(email):
    return User.objects.filter(username=email).select_related("profile").first() if email else None


def is_verified(user):
    return hasattr(user, "profile") and user.profile.email_verified


def me_data(user):
    return {"email": user.email, "first_name": user.first_name, "temp_unit": user.profile.temp_unit}


def code_fail(e):
    status = 429 if e.kind in ("locked", "wait") else 400
    return fail(e.kind, e.message, status=status, **e.extra)


def password_problem(password, user=None):
    try:
        validate_password(password, user)
    except ValidationError as e:
        return " ".join(e.messages)
    return None


# ---------- endpoints ----------
@require_GET
@ensure_csrf_cookie
def test_page(request):
    if not settings.TEST_PAGES:
        raise Http404
    return render(request, "accounts/test.html")



@require_GET
@ensure_csrf_cookie
def csrf(request):
    """App calls this once on start so it has the security cookie for POSTs."""
    return ok()


@require_GET
def me(request):
    if not request.user.is_authenticated or not is_verified(request.user):
        return fail("not_logged_in", "You're not logged in.", status=401)
    return ok(user=me_data(request.user))


@require_POST
def signup(request):
    d = body(request)
    email = clean_email(d.get("email"))
    first_name = (d.get("first_name") or "").strip()[:30]
    password = d.get("password") or ""

    if not first_name:
        return fail("first_name", "Enter your first name.")
    if not email:
        return fail("email", "Enter a real email address.")
    existing = find_user(email)
    if existing and is_verified(existing):
        return fail("email_taken", "There's already an account with this email. Try logging in.", status=409)

    probe = existing or User(username=email, email=email, first_name=first_name)
    problem = password_problem(password, probe)
    if problem:
        return fail("password", problem)

    with transaction.atomic():
        if existing:  # signed up before but never verified: start over with the new details
            user = existing
            user.first_name = first_name
            user.set_password(password)
            user.save()
        else:
            user = User.objects.create_user(username=email, email=email, password=password, first_name=first_name)
            Profile.objects.create(user=user)

    try:
        code = codes.issue(user, EmailCode.VERIFY)
    except codes.CodeError as e:
        if e.kind == "wait":  # a code went out seconds ago, it still works
            return ok(next="verify", email=email, message=f"We sent a 6-digit code to {email}.")
        return code_fail(e)
    if not emails.send_verify_code(user, code):
        return fail("email_failed", "We couldn't send the email. Try again in a minute.", status=502)
    return ok(next="verify", email=email, message=f"We sent a 6-digit code to {email}.")


@require_POST
def verify(request):
    d = body(request)
    email = clean_email(d.get("email"))
    user = find_user(email)
    if not user:
        return fail("none", "That code isn't valid anymore. Ask for a new one.")
    if is_verified(user):
        return fail("already_verified", "This email is already confirmed. Log in.", status=409)
    try:
        codes.check(user, EmailCode.VERIFY, d.get("code"))
    except codes.CodeError as e:
        return code_fail(e)

    user.profile.email_verified = True
    user.profile.save(update_fields=["email_verified"])
    login(request, user)
    emails.send_welcome(user)  # nice to have; signup still worked if this one fails
    return ok(next="home", user=me_data(user), message=f"You're in, {user.first_name}!")


@require_POST
def resend(request):
    d = body(request)
    email = clean_email(d.get("email"))
    purpose = d.get("purpose") or EmailCode.VERIFY
    if purpose not in (EmailCode.VERIFY, EmailCode.RESET):
        return fail("purpose", "Unknown code type.")
    generic = ok(message=f"If {email or 'that email'} has an account, a new code is on its way.")
    user = find_user(email)
    if not user:
        return generic
    if purpose == EmailCode.VERIFY and is_verified(user):
        return fail("already_verified", "This email is already confirmed. Log in.", status=409)
    if purpose == EmailCode.RESET and not is_verified(user):
        return generic
    try:
        code = codes.issue(user, purpose)
    except codes.CodeError as e:
        return code_fail(e)
    sender = emails.send_verify_code if purpose == EmailCode.VERIFY else emails.send_reset_code
    if not sender(user, code):
        return fail("email_failed", "We couldn't send the email. Try again in a minute.", status=502)
    return ok(message=f"New code sent to {email}.")


@require_POST
def login_view(request):
    d = body(request)
    email = clean_email(d.get("email"))
    password = d.get("password") or ""
    if not email or not password:
        return fail("missing", "Enter your email and password.")

    fail_key = f"login_fails:{email}"
    if cache.get(fail_key, 0) >= LOGIN_MAX_FAILS:
        return fail("locked", "Too many tries. Try again in 15 minutes, or reset your password.", status=429)

    user = authenticate(request, username=email, password=password)
    if user is None:
        fails = cache.get(fail_key, 0) + 1
        cache.set(fail_key, fails, LOGIN_LOCK_SECONDS)
        return fail("wrong_login", "Email or password is wrong.", status=401)
    cache.delete(fail_key)

    if not is_verified(user):
        if not hasattr(user, "profile"):
            Profile.objects.create(user=user)
        try:
            code = codes.issue(user, EmailCode.VERIFY)
            emails.send_verify_code(user, code)
        except codes.CodeError:
            pass  # a recent code is still valid, or they're locked; the verify screen shows that
        return fail("verify_email", f"Confirm your email first. We sent a 6-digit code to {email}.",
                    status=403, next="verify", email=email)

    login(request, user)
    return ok(next="home", user=me_data(user))


@require_POST
def logout_view(request):
    logout(request)
    return ok(next="login")


@require_POST
def reset_request(request):
    d = body(request)
    email = clean_email(d.get("email"))
    if not email:
        return fail("email", "Enter a real email address.")
    generic = ok(next="reset_confirm", email=email,
                 message=f"If {email} has an account, we sent a 6-digit code.")
    user = find_user(email)
    if not user or not is_verified(user):
        return generic
    try:
        code = codes.issue(user, EmailCode.RESET)
    except codes.CodeError as e:
        if e.kind == "wait":
            return generic
        return code_fail(e)
    if not emails.send_reset_code(user, code):
        return fail("email_failed", "We couldn't send the email. Try again in a minute.", status=502)
    return generic


@require_POST
def reset_confirm(request):
    d = body(request)
    email = clean_email(d.get("email"))
    new_password = d.get("new_password") or ""
    user = find_user(email)
    if not user or not is_verified(user):
        return fail("wrong", "That code isn't right.")
    problem = password_problem(new_password, user)
    if problem:
        return fail("password", problem)
    try:
        codes.check(user, EmailCode.RESET, d.get("code"))
    except codes.CodeError as e:
        return code_fail(e)

    user.set_password(new_password)  # this also logs out every other device
    user.save()
    cache.delete(f"login_fails:{email}")
    login(request, user)
    return ok(next="home", user=me_data(user), message="Password changed. You're logged in.")
