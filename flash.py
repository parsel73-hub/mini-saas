"""One-shot flash messages stored in a signed cookie (Этап 6 — полировка UI).

A flash message is set on a redirect response (e.g. after creating a survey)
and consumed on the next rendered page. Keeping the message in a short-lived
signed cookie lets us show success feedback without changing redirect URLs.
"""
from typing import Any, Dict, Optional

from fastapi import Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from config import SECRET_KEY

FLASH_COOKIE_NAME = "flash"
# Short lifetime: a flash only needs to survive one redirect.
FLASH_MAX_AGE = 60

_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="flash-message")


def set_flash(response: Response, message: str, category: str = "success") -> None:
    """Attach a flash message to an outgoing response."""
    token = _serializer.dumps({"m": message, "c": category})
    response.set_cookie(
        key=FLASH_COOKIE_NAME,
        value=token,
        max_age=FLASH_MAX_AGE,
        httponly=True,
        samesite="lax",
    )


def read_flash(request: Request) -> Optional[Dict[str, Any]]:
    """Return the pending flash payload ({'m': message, 'c': category}) or None."""
    token = request.cookies.get(FLASH_COOKIE_NAME)
    if not token:
        return None
    try:
        data = _serializer.loads(token, max_age=FLASH_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict) or "m" not in data:
        return None
    return {"m": str(data.get("m", "")), "c": str(data.get("c", "success"))}
