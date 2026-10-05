"""Shared FastAPI dependencies for auth: templates and current user (Этап 2)."""
import os

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from auth import security
from auth.models import User
from config import BASE_DIR
from database.session import get_db

TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

templates = Jinja2Templates(directory=TEMPLATES_DIR)


def get_templates() -> Jinja2Templates:
    """Return the configured Jinja2 templates engine."""
    return templates


def resolve_user(request: Request, db: Session) -> User | None:
    """Return the logged-in user from the signed session cookie, else None."""
    token = request.cookies.get(security.SESSION_COOKIE_NAME)
    if not token:
        return None
    uid = security.read_session_token(token)
    if uid is None:
        return None
    return db.get(User, uid)


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    """FastAPI dependency: the logged-in user, or None for guests."""
    return resolve_user(request, db)
