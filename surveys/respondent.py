"""Signed-cookie helpers for anonymous respondents (Этап 4).

Respondents never register (ТЗ requirement). To protect against double
submission we store a tamper-proof flag cookie named ``respondent_{slug}``
after a successful submission. A repeated submit from the same browser is
then rejected with a friendly page.
"""
from typing import Optional

from fastapi import Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from config import SECRET_KEY

RESPONDENT_COOKIE_PREFIX = "respondent_"
RESPONDENT_MAX_AGE = 30 * 24 * 3600  # 30 days

_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="survey-respondent")


def cookie_name(slug: str) -> str:
    """Return the per-survey respondent cookie name."""
    return f"{RESPONDENT_COOKIE_PREFIX}{slug}"


def create_flag(survey_id: int) -> str:
    """Sign the survey id into a timed, tamper-proof flag token."""
    return _serializer.dumps({"sid": survey_id})


def read_flag(token: str) -> Optional[int]:
    """Return the survey id from a valid flag token, else None."""
    try:
        data = _serializer.loads(token, max_age=RESPONDENT_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    sid = data.get("sid")
    return int(sid) if sid is not None else None


def has_submitted(request: Request, slug: str, survey_id: int) -> bool:
    """Whether this browser already submitted the given survey."""
    token = request.cookies.get(cookie_name(slug))
    if not token:
        return False
    return read_flag(token) == survey_id


def set_submitted_flag(response: Response, slug: str, survey_id: int) -> None:
    """Mark this browser as having submitted the given survey."""
    response.set_cookie(
        key=cookie_name(slug),
        value=create_flag(survey_id),
        max_age=RESPONDENT_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
