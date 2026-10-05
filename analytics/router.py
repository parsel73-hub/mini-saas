"""Analytics routes (Этап 5 — статистика создателя).

GET /survey/{slug}/stats is owner-only: the current user must own the survey,
otherwise a 403 (guest) / 404 (unknown slug) is returned.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from analytics.services import survey_stats
from auth.deps import CurrentUser, get_templates
from database.models import Survey
from database.session import get_db

router = APIRouter()


@router.get("/survey/{slug}/stats", response_class=HTMLResponse)
def survey_stats_page(
    request: Request,
    slug: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Render the statistics page for a survey owned by the current user."""
    templates = get_templates()
    survey = db.query(Survey).filter(Survey.slug == slug).first()

    if survey is None:
        return templates.TemplateResponse(
            request,
            "404.html",
            {"error": "Опрос не найден."},
            status_code=404,
        )

    # Owner-only access (task spec: only the survey owner may view stats).
    if survey.owner_id != current_user.id:
        return templates.TemplateResponse(
            request,
            "404.html",
            {"error": "Опрос не найден."},
            status_code=404,
        )

    stats = survey_stats(db, survey.id)
    return templates.TemplateResponse(
        request,
        "analytics/stats.html",
        {"user": current_user, "survey": survey, "stats": stats},
    )
