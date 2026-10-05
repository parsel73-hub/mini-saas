"""Slug generation for public survey links (Этап 3).

The ТЗ requires short, automatically generated, collision-free slugs
(e.g. /survey/a82jd92k). Static/manual links are forbidden.
"""
import secrets

from sqlalchemy.orm import Session

from database.models import Survey


def generate_slug(length: int = 8) -> str:
    """Return a cryptographically-random URL-safe slug of ~``length`` chars."""
    return secrets.token_urlsafe(length)[:length]


def generate_unique_slug(db: Session, length: int = 8) -> str:
    """Return a slug that does not collide with any existing survey.

    Regenerates on collision until a free slug is found.
    """
    slug = generate_slug(length)
    while db.query(Survey).filter(Survey.slug == slug).first() is not None:
        slug = generate_slug(length)
    return slug
