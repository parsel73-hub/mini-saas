"""Slug service (Этап 3 — генерация публичных ссылок /s/{slug}).

ТЗ требует, чтобы опросы были доступны только по коротким slug-ссылкам.
"""
import secrets

# Алфавит без неоднозначных символов (0/O, 1/l/I).
_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"


def generate_slug(length: int = 8) -> str:
    """Return a cryptographically-random URL-safe slug."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))
