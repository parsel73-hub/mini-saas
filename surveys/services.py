"""Survey service layer (Этап 3 — создание опроса).

Provides slug generation (re-exported), dynamic form parsing, validation and
transactional survey creation with questions and options.
"""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.models import Answer, Option, Question, Survey
from surveys.service.slug_service import generate_slug, generate_unique_slug

__all__ = [
    "generate_slug",
    "generate_unique_slug",
    "parse_questions",
    "validate_questions",
    "create_survey",
    "save_submission",
]


def parse_questions(form_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse dynamic question fields from FastAPI form data.

    Expected field names (``N`` is the 0-based question index):
        question_N_text     — question text
        question_N_type     — "single" | "multiple" | "text"
        question_N_options  — one or more option values (list) or a
                              newline/comma separated string

    Returns a list of dicts: {"text": str, "type": str, "options": [str, ...]}.
    """
    questions: List[Dict[str, Any]] = []
    index = 0

    while True:
        text_key = f"question_{index}_text"
        type_key = f"question_{index}_type"

        # Questions are indexed consecutively; stop at the first gap.
        if text_key not in form_data or type_key not in form_data:
            break

        text = str(form_data.get(text_key, "")).strip()
        q_type = str(form_data.get(type_key, "single"))
        options_raw = form_data.get(f"question_{index}_options", "")

        # Options may arrive as a list (repeated fields) or as a single
        # textarea string with one option per line (optionally comma-separated).
        if isinstance(options_raw, list):
            raw_items = options_raw
        else:
            raw_items = str(options_raw).replace(",", "\n").splitlines()

        options = [str(item).strip() for item in raw_items if str(item).strip()]

        if text:
            questions.append({"text": text, "type": q_type, "options": options})
        index += 1

    return questions


def validate_questions(questions: List[Dict[str, Any]]) -> Optional[str]:
    """Validate parsed questions.

    Returns an error message if validation fails, or None when valid.
    Rules (per ТЗ): at least one question; "single" needs at least 2 options.
    """
    if not questions:
        return "Добавьте хотя бы один вопрос."

    for i, q in enumerate(questions):
        q_type = q.get("type")
        if q_type not in ("single", "multiple", "text"):
            return f"В вопросе {i + 1} указан неизвестный тип."
        if q_type == "single" and len(q.get("options", [])) < 2:
            return (
                f"В вопросе {i + 1} типа «один вариант» "
                f"должно быть минимум 2 варианта."
            )

    return None


def create_survey(
    db: Session,
    user: Any,
    title: str,
    description: Optional[str],
    questions: List[Dict[str, Any]],
) -> Survey:
    """Persist a survey with its questions and options in one transaction.

    Adds the objects to the session and flushes so that generated ids are
    available; the caller is responsible for committing. Raises ``ValueError``
    when validation fails.
    """
    error = validate_questions(questions)
    if error:
        raise ValueError(error)

    survey = Survey(
        title=title,
        description=description or "",
        slug=generate_unique_slug(db),
        owner_id=user.id,
        is_active=True,
    )
    db.add(survey)
    db.flush()  # Assign survey.id.

    for position, q in enumerate(questions, start=1):
        question = Question(
            survey_id=survey.id,
            text=q["text"],
            type=q["type"],
            position=position,
        )
        db.add(question)
        db.flush()  # Assign question.id.

        for opt_pos, opt_text in enumerate(q.get("options", []), start=1):
            db.add(
                Option(
                    question_id=question.id,
                    text=opt_text,
                    position=opt_pos,
                )
            )

    return survey


def _normalize_values(raw: Any) -> List[str]:
    """Return repeated form values as a flat list of strings."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(v) for v in raw if str(v).strip() != ""]
    return [str(raw)] if str(raw).strip() != "" else []


def save_submission(
    db: Session,
    survey: Survey,
    form_data: Dict[str, Any],
    respondent_session: str,
) -> List[Answer]:
    """Validate and persist all answers of one submission.

    ``form_data`` maps ``answer_{question_id}`` to the submitted value (a
    string, or a list of strings for checkbox questions). Every row of the
    submission shares the same ``respondent_session`` and is flushed in a
    single transaction (the caller commits).

    Validation (per ТЗ):
      * every "single" question must be answered;
      * every chosen option id must belong to its question.

    Raises ``ValueError`` with a friendly message when validation fails.
    """
    errors: List[str] = []
    answers: List[Answer] = []

    for question in survey.questions:
        raw = form_data.get(f"answer_{question.id}")
        valid_option_ids = {opt.id for opt in question.options}

        if question.type == "single":
            if not _normalize_values(raw):
                errors.append(f"Ответьте на вопрос «{question.text}».")
                continue
            try:
                option_id = int(raw)
            except (TypeError, ValueError):
                errors.append(f"Недопустимый вариант в вопросе «{question.text}».")
                continue
            if option_id not in valid_option_ids:
                errors.append(f"Недопустимый вариант в вопросе «{question.text}».")
                continue
            answers.append(
                Answer(
                    survey_id=survey.id,
                    question_id=question.id,
                    option_id=option_id,
                    respondent_session=respondent_session,
                )
            )

        elif question.type == "multiple":
            for value in _normalize_values(raw):
                try:
                    option_id = int(value)
                except (TypeError, ValueError):
                    errors.append(
                        f"Недопустимый вариант в вопросе «{question.text}»."
                    )
                    continue
                if option_id not in valid_option_ids:
                    errors.append(
                        f"Недопустимый вариант в вопросе «{question.text}»."
                    )
                    continue
                answers.append(
                    Answer(
                        survey_id=survey.id,
                        question_id=question.id,
                        option_id=option_id,
                        respondent_session=respondent_session,
                    )
                )

        elif question.type == "text":
            for value in _normalize_values(raw):
                answers.append(
                    Answer(
                        survey_id=survey.id,
                        question_id=question.id,
                        text_value=value,
                        respondent_session=respondent_session,
                    )
                )

    if errors:
        raise ValueError(" ".join(errors))

    for answer in answers:
        db.add(answer)
    db.flush()

    return answers
