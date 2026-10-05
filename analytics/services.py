"""Analytics service layer (Этап 5 — статистика).

Aggregates answers stored in the ``answers`` table into a view model used by
the creator's statistics page: total submissions, per-question breakdowns and
the latest submissions.
"""
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import Answer, Option, Question

# Number of latest submissions shown in the "recent" table.
RECENT_LIMIT = 10


def _mask_session(session: Optional[str]) -> str:
    """Shorten a respondent session id for display (privacy-friendly)."""
    if not session:
        return "—"
    return session[:8] + "…" if len(session) > 8 else session


def _total_submissions(db: Session, survey_id: int) -> int:
    """Count distinct respondent sessions (one per submission)."""
    return (
        db.query(func.count(func.distinct(Answer.respondent_session)))
        .filter(Answer.survey_id == survey_id)
        .scalar()
        or 0
    )


def _single_breakdown(db: Session, question: Question) -> List[Dict[str, Any]]:
    """Distribution of options for a "single"/"multiple" question.

    Uses GROUP BY on the options and merges with the full option list so that
    options with zero answers are still shown. ``percent`` is relative to the
    total number of answers for this question (so they sum to ~100%).
    """
    rows = (
        db.query(Option.id, func.count(Answer.id))
        .outerjoin(
            Answer,
            (Answer.option_id == Option.id) & (Answer.survey_id == question.survey_id),
        )
        .filter(Option.question_id == question.id)
        .group_by(Option.id)
        .all()
    )
    counts = {option_id: count for option_id, count in rows}
    total = sum(counts.values())

    breakdown: List[Dict[str, Any]] = []
    for option in question.options:
        count = counts.get(option.id, 0)
        percent = round(count / total * 100, 1) if total else 0.0
        breakdown.append({"text": option.text, "count": count, "percent": percent})
    return breakdown


def _text_answers(db: Session, question: Question) -> List[str]:
    """List of non-empty free-text answers for a "text" question."""
    rows = (
        db.query(Answer.text_value)
        .filter(
            Answer.question_id == question.id,
            Answer.text_value.isnot(None),
            Answer.text_value != "",
        )
        .order_by(Answer.id.desc())
        .all()
    )
    return [value for (value,) in rows]


def _recent_submissions(
    db: Session, survey_id: int, questions: List[Question]
) -> List[Dict[str, Any]]:
    """Latest submissions: masked session, date and a short answer summary."""
    sessions = (
        db.query(
            Answer.respondent_session,
            func.max(Answer.created_at).label("submitted_at"),
        )
        .filter(
            Answer.survey_id == survey_id,
            Answer.respondent_session.isnot(None),
        )
        .group_by(Answer.respondent_session)
        .order_by(func.max(Answer.created_at).desc())
        .limit(RECENT_LIMIT)
        .all()
    )

    questions_by_id = {q.id: q for q in questions}
    recent: List[Dict[str, Any]] = []

    for session, submitted_at in sessions:
        answers = (
            db.query(Answer)
            .filter(
                Answer.survey_id == survey_id,
                Answer.respondent_session == session,
            )
            .all()
        )
        # Group answers by question for the summary string.
        by_question: Dict[int, List[str]] = {}
        for answer in answers:
            question = questions_by_id.get(answer.question_id)
            if question is None:
                continue
            if answer.option_id is not None:
                option = db.get(Option, answer.option_id)
                label = option.text if option else str(answer.option_id)
            else:
                label = answer.text_value or ""
            by_question.setdefault(answer.question_id, []).append(label)

        summary_parts = []
        for question in questions:
            labels = by_question.get(question.id)
            if not labels:
                continue
            joined = ", ".join(labels)
            if len(joined) > 60:
                joined = joined[:57] + "…"
            summary_parts.append(f"{question.text}: {joined}")

        recent.append(
            {
                "session": _mask_session(session),
                "submitted_at": submitted_at,
                "summary": "; ".join(summary_parts) or "—",
            }
        )

    return recent


def survey_stats(db: Session, survey_id: int) -> Dict[str, Any]:
    """Build the full statistics view model for a survey.

    Returns a dict with:
      * ``total_submissions`` — COUNT(DISTINCT respondent_session);
      * ``questions`` — per-question breakdown (options with count/percent for
        single/multiple, list of texts for open questions);
      * ``recent`` — the latest submissions (masked session, date, summary).
    """
    questions = (
        db.query(Question)
        .filter(Question.survey_id == survey_id)
        .order_by(Question.position, Question.id)
        .all()
    )

    question_stats: List[Dict[str, Any]] = []
    for question in questions:
        entry: Dict[str, Any] = {
            "id": question.id,
            "text": question.text,
            "type": question.type,
        }
        if question.type in ("single", "multiple"):
            entry["options"] = _single_breakdown(db, question)
        elif question.type == "text":
            entry["answers"] = _text_answers(db, question)
        question_stats.append(entry)

    return {
        "total_submissions": _total_submissions(db, survey_id),
        "questions": question_stats,
        "recent": _recent_submissions(db, survey_id, questions),
    }
