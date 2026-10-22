"""
auth.py — email masking + admin gate + token-based admin sessions.

IMPORTANT: provide ADMIN_PASSWORD and ADMIN_TOKEN_SECRET before starting
the application (via environment variables, not hardcoded).
"""

import os
import hmac
import hashlib
import time
import base64
import binascii
import json

ADMIN_PASSWORD = os.environ.get("MESS_ADMIN_PASSWORD")
TOKEN_SECRET = os.environ.get("ADMIN_TOKEN_SECRET")
if not ADMIN_PASSWORD or not TOKEN_SECRET:
    raise RuntimeError("MESS_ADMIN_PASSWORD and ADMIN_TOKEN_SECRET must be configured.")
if ADMIN_PASSWORD == "changeme123" or TOKEN_SECRET == "dev-secret-change-me":
    raise RuntimeError("Development admin credentials are not allowed.")
TOKEN_LIFETIME_SECONDS = 8 * 60 * 60  # 8 hours


def mask_email(email: str) -> str:
    """Never show a raw student email anywhere in the UI — even admins only
    ever see this masked form, e.g. john.doe@college.edu -> jo******@college.edu"""
    if not email or "@" not in email:
        return "****"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[:2] + "*" * (len(local) - 2)
    return f"{masked_local}@{domain}"


def check_admin_password(entered: str) -> bool:
    # constant-time comparison — avoids leaking timing info about how much
    # of the password guess was correct
    return hmac.compare_digest(entered, ADMIN_PASSWORD)


# ---------- Token-based admin sessions ----------
# The real password is only ever sent once, at /admin/login. After that,
# the frontend holds this signed, expiring token instead of the password
# itself — so the password isn't repeatedly transmitted on every request.

def create_admin_token() -> str:
    payload = {"role": "admin", "exp": int(time.time()) + TOKEN_LIFETIME_SECONDS}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature = hmac.new(TOKEN_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def verify_admin_token(token: str) -> bool:
    if not token or "." not in token:
        return False
    payload_b64, _, signature = token.partition(".")

    expected_signature = hmac.new(TOKEN_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return False

    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except Exception:
        return False

    return payload.get("role") == "admin" and payload.get("exp", 0) > time.time()


def create_user_token(email: str) -> str:
    payload = {
        "role": "user",
        "sub": email.strip().lower(),
        "exp": int(time.time()) + TOKEN_LIFETIME_SECONDS,
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature = hmac.new(TOKEN_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def verify_user_token(token: str):
    if not token or "." not in token:
        return None
    payload_b64, _, signature = token.partition(".")
    expected_signature = hmac.new(TOKEN_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, TypeError, json.JSONDecodeError, binascii.Error):
        return None
    email = payload.get("sub")
    if payload.get("role") != "user" or payload.get("exp", 0) <= time.time() or not isinstance(email, str):
        return None
    return email


# ---------- Login attempt rate limiting ----------
# In-memory (per-process) tracking: 5 wrong attempts -> locked out for 6
# hours. Resets on backend restart, which is fine for this scale.

_attempts = {}  # key -> {"count": int, "locked_until": float}
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 6 * 60 * 60  # 6 hours


def check_lockout(key: str):
    """Returns seconds remaining if locked out, else None."""
    entry = _attempts.get(key)
    if not entry:
        return None
    locked_until = entry.get("locked_until")
    if locked_until and locked_until > time.time():
        return int(locked_until - time.time())
    return None


def record_failed_attempt(key: str):
    entry = _attempts.setdefault(key, {"count": 0, "locked_until": None})
    entry["count"] += 1
    if entry["count"] >= MAX_ATTEMPTS:
        entry["locked_until"] = time.time() + LOCKOUT_SECONDS


def reset_attempts(key: str):
    _attempts.pop(key, None)
