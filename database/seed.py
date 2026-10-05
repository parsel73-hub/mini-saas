"""Demo data seeding for the final delivery stage (Этап 6 — сдача).

Creates a demo creator, a ready-made satisfaction survey with questions of
different types and ~10 fake submissions with distinct respondent sessions and
dates. The script is idempotent: running it again does not duplicate rows.

Run with:
    python -m database.seed
"""
from __future__ import annotations

from datetime import datetime, timedelta
from random import Random
from uuid import uuid4

from auth import security
from auth.models import User
from database.models import Answer, Survey
from database.session import SessionLocal, init_db
from surveys.services import create_survey

# Credentials printed to the console after seeding.
DEMO_EMAIL = "demo@survey.local"
DEMO_PASSWORD = "demo1234"

DEMO_TITLE = "Опрос удовлетворённости"
DEMO_DESCRIPTION = "Помогите нам стать лучше — ответьте на несколько вопросов."

# Questions of different types (single / multiple / text).
DEMO_QUESTIONS = [
    {
        "text": "Насколько вы удовлетворены нашим сервисом?",
        "type": "single",
        "options": [
            "Полностью доволен",
            "Скорее доволен",
            "Нейтрально",
            "Скорее недоволен",
            "Полностью недоволен",
        ],
    },
    {
        "text": "Что вам понравилось больше всего?",
        "type": "multiple",
        "options": [
            "Скорость работы",
            "Удобный интерфейс",
            "Качество поддержки",
            "Цена",
            "Надёжность",
        ],
    },
    {
        "text": "Что мы можем улучшить?",
        "type": "text",
        "options": [],
    },
]

# Free-text answers used for the demo submissions.
TEXT_ANSWERS = [
    "Всё отлично, спасибо!",
    "Хотелось бы больше интеграций.",
    "Сделайте тёмную тему.",
    "Быстрее бы выгрузку отчётов.",
    "Пока всё устраивает.",
    "Добавьте мобильное приложение.",
    "Нужна более гибкая настройка тарифов.",
    "Отличная поддержка, так держать!",
    "Иногда подвисает интерфейс.",
    "Спасибо за оперативные ответы.",
]

SUBMISSION_COUNT = 10


def _print_credentials(slug: str) -> None:
    """Print demo credentials and the public survey link."""
    print("\n" + "=" * 56)
    print("Демо-доступ создателя:")
    print(f"  email:    {DEMO_EMAIL}")
    print(f"  password: {DEMO_PASSWORD}")
    print(f"\nТестовый опрос: {DEMO_TITLE}")
    print(f"  ссылка:   http://127.0.0.1:8000/survey/{slug}")
    print(f"  статистика: http://127.0.0.1:8000/survey/{slug}/stats")
    print("=" * 56 + "\n")


def _make_answers(db, survey: Survey, seed_value: int = 42) -> int:
    """Create ``SUBMISSION_COUNT`` fake submissions and return the row count.

    Each submission uses its own ``respondent_session`` and a distinct date so
    the statistics page shows a realistic distribution and history.
    """
    rng = Random(seed_value)
    questions = sorted(survey.questions, key=lambda q: q.position)
    now = datetime.now()
    rows = 0

    for index in range(SUBMISSION_COUNT):
        session_id = uuid4().hex
        # Spread submissions over the last SUBMISSION_COUNT days.
        created_at = now - timedelta(
            days=SUBMISSION_COUNT - index,
            hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59),
        )

        for question in questions:
            if question.type == "single":
                option = rng.choice(question.options)
                db.add(
                    Answer(
                        survey_id=survey.id,
                        question_id=question.id,
                        option_id=option.id,
                        respondent_session=session_id,
                        created_at=created_at,
                    )
                )
                rows += 1
            elif question.type == "multiple":
                picks = rng.sample(
                    question.options, rng.randint(1, min(2, len(question.options)))
                )
                for option in picks:
                    db.add(
                        Answer(
                            survey_id=survey.id,
                            question_id=question.id,
                            option_id=option.id,
                            respondent_session=session_id,
                            created_at=created_at,
                        )
                    )
                    rows += 1
            elif question.type == "text":
                db.add(
                    Answer(
                        survey_id=survey.id,
                        question_id=question.id,
                        text_value=rng.choice(TEXT_ANSWERS),
                        respondent_session=session_id,
                        created_at=created_at,
                    )
                )
                rows += 1

    return rows


def seed() -> None:
    """Seed demo data. Safe to call repeatedly (idempotent)."""
    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if user is None:
            user = User(
                email=DEMO_EMAIL,
                password_hash=security.hash_password(DEMO_PASSWORD),
            )
            db.add(user)
            db.flush()
            print(f"Создан демо-пользователь {DEMO_EMAIL}.")

        survey = (
            db.query(Survey)
            .filter(Survey.title == DEMO_TITLE, Survey.owner_id == user.id)
            .first()
        )

        if survey is not None:
            db.rollback()
            print("Демо-опрос уже существует — повторное создание пропущено.")
            _print_credentials(survey.slug)
            return

        survey = create_survey(
            db, user, DEMO_TITLE, DEMO_DESCRIPTION, DEMO_QUESTIONS
        )
        db.flush()

        rows = _make_answers(db, survey)
        db.commit()
        db.refresh(survey)

        print(
            f"Создан опрос «{survey.title}» "
            f"({len(survey.questions)} вопроса, {rows} строк ответов)."
        )
        _print_credentials(survey.slug)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
