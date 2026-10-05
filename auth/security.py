"""Password hashing and signed session-cookie helpers (Этап 2 — Auth).

Uses bcrypt directly (passlib is unmaintained and breaks with bcrypt>=4.1)
and itsdangerous for tamper-proof session cookies, mirroring the
signed-cookie pattern from the task plan.
"""
import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from config import SECRET_KEY

# Session cookie name and max age (7 days), as specified in the plan.
SESSION_COOKIE_NAME = "session"
SESSION_MAX_AGE = 7 * 24 * 3600

_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="auth-session")


def hash_password(password: str) -> str:
    """Return a bcrypt hash of the given plaintext password."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Malformed hash in DB — treat as failed verification.
        return False


def create_session_token(user_id: int) -> str:
    """Sign a user id into a timed, tamper-proof session token."""
    return _serializer.dumps({"uid": user_id})


def read_session_token(token: str) -> int | None:
    """Return the user id from a valid session token, else None."""
    try:
        data = _serializer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    uid = data.get("uid")
    return int(uid) if uid is not None else None
