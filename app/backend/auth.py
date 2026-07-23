"""Single-user authentication for EASM Dashboard.

Credentials (password hash and TOTP secret) are persisted in the database
under the "credentials" setting and cached in memory. Environment variables
(EASM_ADMIN_PASSWORD, EASM_ADMIN_PASSWORD_HASH) are used only as a one-time
seed when no credentials row exists yet.

Sessions are in-memory (survive page reload, not backend restart).
"""

import base64
import os
import secrets
import threading
import time
from io import BytesIO

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

SESSION_COOKIE = "easm_session"
SESSION_TTL = 24 * 3600

RATE_LIMIT_ATTEMPTS = 5
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_BLOCK = 300

CREDENTIALS_KEY = "credentials"
DEFAULT_USERNAME = "admin"

_ph = PasswordHasher()

_password_hash: str = ""
_totp_secret: str = ""
_pending_totp_secret: str = ""

_sessions: dict[str, float] = {}
_failed: dict[str, list[float]] = {}
_blocked: dict[str, float] = {}
_lock = threading.Lock()


def _load_setting(key: str) -> dict:
    """Load a settings row by key. Import here to avoid circular imports."""
    from db import SessionLocal, Setting

    session = SessionLocal()
    try:
        row = session.get(Setting, key)
        return dict(row.value) if row and row.value else {}
    finally:
        session.close()


def _save_setting(key: str, value: dict) -> None:
    """Save (upsert) a settings row by key."""
    from db import SessionLocal, Setting

    session = SessionLocal()
    try:
        row = session.get(Setting, key)
        if row:
            row.value = value
        else:
            session.add(Setting(key=key, value=value))
        session.commit()
    finally:
        session.close()


def _seed_from_env() -> tuple[str, str]:
    """Return (password_hash, totp_secret) from env for initial seeding."""
    hash_env = os.environ.get("EASM_ADMIN_PASSWORD_HASH", "").strip()
    pw_env = os.environ.get("EASM_ADMIN_PASSWORD", "").strip()

    if hash_env:
        password_hash = hash_env
    elif pw_env:
        password_hash = _ph.hash(pw_env)
    else:
        generated = secrets.token_urlsafe(16)
        password_hash = _ph.hash(generated)
        print("=" * 64, flush=True)
        print("EASM: Kein Admin-Passwort konfiguriert.", flush=True)
        print(f"EASM: Generiertes Erststart-Passwort: {generated}", flush=True)
        print("EASM: Setze EASM_ADMIN_PASSWORD oder EASM_ADMIN_PASSWORD_HASH.", flush=True)
        print("=" * 64, flush=True)

    # EASM_TOTP_SECRET is read only during the migration; auth never reads it.
    return password_hash, ""


def load_credentials() -> None:
    """Load credentials from DB into the in-memory cache. Call once at startup."""
    global _password_hash, _totp_secret

    stored = _load_setting(CREDENTIALS_KEY)

    if stored.get("password_hash"):
        with _lock:
            _password_hash = stored["password_hash"]
            _totp_secret = stored.get("totp_secret", "")
        print("EASM: Credentials aus DB geladen.", flush=True)
        return

    # No credentials in DB yet: seed from env or generate.
    password_hash, totp_secret = _seed_from_env()
    _save_setting(
        CREDENTIALS_KEY,
        {
            "password_hash": password_hash,
            "totp_secret": totp_secret,
        },
    )
    with _lock:
        _password_hash = password_hash
        _totp_secret = totp_secret


def hash_password(password: str) -> str:
    return _ph.hash(password)


def set_password_hash(password_hash: str) -> None:
    global _password_hash
    with _lock:
        _password_hash = password_hash
    stored = _load_setting(CREDENTIALS_KEY)
    stored["password_hash"] = password_hash
    _save_setting(CREDENTIALS_KEY, stored)


def set_totp_secret(secret: str | None) -> None:
    global _totp_secret
    secret = (secret or "").strip()
    with _lock:
        _totp_secret = secret
    stored = _load_setting(CREDENTIALS_KEY)
    stored["totp_secret"] = secret
    _save_setting(CREDENTIALS_KEY, stored)


def clear_all_sessions() -> None:
    with _lock:
        _sessions.clear()


def totp_enabled() -> bool:
    with _lock:
        return bool(_totp_secret)


def verify_password(password: str) -> bool:
    if not password:
        return False
    try:
        with _lock:
            return _ph.verify(_password_hash, password)
    except (VerifyMismatchError, VerificationError, Exception):
        return False


def verify_totp(code: str) -> bool:
    with _lock:
        secret = _totp_secret
    if not secret:
        return True
    if not code:
        return False
    import pyotp

    try:
        normalized = code.strip().replace(" ", "")
        return bool(pyotp.TOTP(secret).verify(normalized, valid_window=1))
    except Exception:
        return False


def _provisioning_uri(secret: str) -> str:
    import pyotp

    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=DEFAULT_USERNAME,
        issuer_name="EASM",
    )


def _build_qr_data_uri(provisioning_uri: str) -> str:
    import qrcode
    import qrcode.image.svg

    img = qrcode.make(provisioning_uri, image_factory=qrcode.image.svg.SvgPathImage)
    buf = BytesIO()
    img.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def generate_totp_setup() -> dict:
    """Generate a new pending TOTP secret and return secret + QR data URI."""
    global _pending_totp_secret
    import pyotp

    secret = pyotp.random_base32()
    _pending_totp_secret = secret
    uri = _provisioning_uri(secret)
    return {"secret": secret, "qr_uri": _build_qr_data_uri(uri)}


def verify_pending_totp(code: str) -> bool:
    if not _pending_totp_secret or not code:
        return False
    import pyotp

    try:
        normalized = code.strip().replace(" ", "")
        return bool(pyotp.TOTP(_pending_totp_secret).verify(normalized, valid_window=1))
    except Exception:
        return False


def commit_pending_totp_secret() -> None:
    global _pending_totp_secret
    secret = _pending_totp_secret
    _pending_totp_secret = ""
    if secret:
        set_totp_secret(secret)


def clear_pending_totp_secret() -> None:
    global _pending_totp_secret
    _pending_totp_secret = ""


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    with _lock:
        _sessions[token] = time.time() + SESSION_TTL
        expired = [t for t, exp in _sessions.items() if exp < time.time()]
        for t in expired:
            _sessions.pop(t, None)
    return token


def destroy_session(token: str | None) -> None:
    if not token:
        return
    with _lock:
        _sessions.pop(token, None)


def valid_session(token: str | None) -> bool:
    if not token:
        return False
    with _lock:
        exp = _sessions.get(token)
        if exp is None:
            return False
        if exp < time.time():
            _sessions.pop(token, None)
            return False
    return True


def is_blocked(ip: str) -> bool:
    with _lock:
        return _blocked.get(ip, 0) > time.time()


def register_failure(ip: str) -> None:
    now = time.time()
    with _lock:
        attempts = [t for t in _failed.get(ip, []) if now - t < RATE_LIMIT_WINDOW]
        attempts.append(now)
        _failed[ip] = attempts
        if len(attempts) >= RATE_LIMIT_ATTEMPTS:
            _blocked[ip] = now + RATE_LIMIT_BLOCK
            _failed[ip] = []


def clear_failures(ip: str) -> None:
    with _lock:
        _failed.pop(ip, None)
        _blocked.pop(ip, None)
