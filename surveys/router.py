"""Survey routes (Этап 3 — создание и прохождение опросов).

URL layout (по ТЗ):
    GET/POST /surveys/create         — creator only
    GET      /dashboard              — creator only ("Мои опросы")
    GET      /survey/{slug}          — respondent, NO auth
    POST     /survey/{slug}/submit   — respondent, NO auth (stub → thank-you)
    GET      /survey/{slug}/thank-you — respondent, NO auth
    GET      /survey/{slug}/stats    — creator only (placeholder for Этап 5)
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from auth.deps import CurrentUser, get_templates
from database.session import get_db
from surveys.services import create_survey, parse_questions

router = APIRouter()


def _get_survey_or_none(db: Session, slug: str):
    """Return an active survey by slug, or None (inactive counts as missing)."""
    from database.models import Survey

    return (
        db.query(Survey)
        .filter(Survey.slug == slug, Survey.is_active.is_(True))
        .first()
    )


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Show the current user's surveys ("Мои опросы")."""
    from database.models import Survey

    surveys = (
        db.query(Survey)
        .filter(Survey.owner_id == current_user.id)
        .order_by(Survey.created_at.desc())
        .all()
    )
    templates = get_templates()
    return templates.TemplateResponse(
        request, "surveys/list.html", {"user": current_user, "surveys": surveys}
    )


@router.get("/surveys/create", response_class=HTMLResponse)
def create_survey_form(
    request: Request,
    current_user: CurrentUser,
):
    """Show the survey creation form."""
    templates = get_templates()
    return templates.TemplateResponse(
        request, "surveys/create.html", {"user": current_user}
    )


@router.post("/surveys/create", response_class=HTMLResponse)
async def create_survey_submit(
    request: Request,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Handle survey creation form submission."""
    form = await request.form()
    # Preserve repeated fields (e.g. question_N_options) as lists instead of
    # letting dict() collapse them to the last value.
    form_data: dict = {}
    for key, value in form.multi_items():
        if key in form_data:
            if isinstance(form_data[key], list):
                form_data[key].append(value)
            else:
                form_data[key] = [form_data[key], value]
        else:
            form_data[key] = value

    title = str(form_data.get("title", "")).strip()
    description = str(form_data.get("description", "")).strip()
    questions = parse_questions(form_data)

    templates = get_templates()

    if not title:
        return templates.TemplateResponse(
            request,
            "surveys/create.html",
            {
                "user": current_user,
                "error": "Название обязательно",
                "title": title,
                "description": description,
                "questions": questions,
            },
            status_code=422,
        )

    if not questions:
        return templates.TemplateResponse(
            request,
            "surveys/create.html",
            {
                "user": current_user,
                "error": "Добавьте хотя бы один вопрос",
                "title": title,
                "description": description,
                "questions": questions,
            },
            status_code=422,
        )

    try:
        survey = create_survey(db, current_user, title, description, questions)
        db.commit()
        db.refresh(survey)
    except ValueError as e:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "surveys/create.html",
            {
                "user": current_user,
                "error": str(e),
                "title": title,
                "description": description,
                "questions": questions,
            },
            status_code=422,
        )

    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/survey/{slug}", response_class=HTMLResponse)
def fill_survey(
    request: Request,
    slug: str,
    db: Session = Depends(get_db),
):
    """Show the survey form for respondents (NO auth, per ТЗ)."""
    survey = _get_survey_or_none(db, slug)
    templates = get_templates()
    if survey is None:
        return templates.TemplateResponse(
            request,
            "404.html",
            {"error": "Опрос не найден или недоступен."},
            status_code=404,
        )
    return templates.TemplateResponse(
        request, "surveys/fill.html", {"survey": survey}
    )


@router.post("/survey/{slug}/submit", response_class=HTMLResponse)
async def submit_survey(
    request: Request,
    slug: str,
    db: Session = Depends(get_db),
):
    """Stub submit handler: real answer saving arrives on Этап 4.

    For now it only redirects the respondent to the thank-you page.
    """
    survey = _get_survey_or_none(db, slug)
    templates = get_templates()
    if survey is None:
        return templates.TemplateResponse(
            request,
            "404.html",
            {"error": "Опрос не найден или недоступен."},
            status_code=404,
        )
    return RedirectResponse(url=f"/survey/{slug}/thank-you", status_code=303)


@router.get("/survey/{slug}/thank-you", response_class=HTMLResponse)
def thank_you(
    request: Request,
    slug: str,
    db: Session = Depends(get_db),
):
    """Show the "Спасибо за ответы" page (NO auth)."""
    survey = _get_survey_or_none(db, slug)
    templates = get_templates()
    return templates.TemplateResponse(
        request, "surveys/thank_you.html", {"survey": survey}
    )


@router.get("/survey/{slug}/stats", response_class=HTMLResponse)
def survey_stats(
    request: Request,
    slug: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Placeholder statistics page for the creator (full version — Этап 5)."""
    survey = _get_survey_or_none(db, slug)
    templates = get_templates()
    if survey is None:
        return templates.TemplateResponse(
            request,
            "404.html",
            {"error": "Опрос не найден или недоступен."},
            status_code=404,
        )
    return templates.TemplateResponse(
        request,
        "surveys/stats.html",
        {"user": current_user, "survey": survey},
    )
