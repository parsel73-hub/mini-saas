"""FastAPI application entrypoint.

Run with:
    uvicorn main:app --reload
"""
from contextlib import asynccontextmanager
import os

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from analytics.router import router as analytics_router
from auth.deps import OptionalUser, _LoginRequired, get_templates
from auth.router import router as auth_router
from config import BASE_DIR
from database.session import get_db, init_db
from flash import FLASH_COOKIE_NAME, read_flash
from surveys.router import router as surveys_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (Этап 1: "проверить, что БД создаётся").
    init_db()
    yield


app = FastAPI(title="Мини-SaaS для опросов", lifespan=lifespan)

# Static assets (unified CSS, Chart.js init helper and friends).
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static")),
    name="static",
)

# Auth routes: register / login / logout / account (Этап 2).
app.include_router(auth_router)

# Survey routes: create / dashboard / fill / submit (Этап 3).
app.include_router(surveys_router)

# Analytics routes: /survey/{slug}/stats (Этап 5, owner-only).
app.include_router(analytics_router)


@app.middleware("http")
async def flash_middleware(request: Request, call_next):
    """Expose the pending flash message and clear its cookie after use."""
    request.state.flash = read_flash(request)
    response = await call_next(request)
    if FLASH_COOKIE_NAME in request.cookies:
        response.delete_cookie(FLASH_COOKIE_NAME)
    return response


@app.exception_handler(_LoginRequired)
async def login_required_handler(request: Request, exc: _LoginRequired) -> RedirectResponse:
    """Redirect guests to /login when a creator-only route requires auth."""
    return RedirectResponse(url="/login", status_code=302)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Render friendly HTML pages instead of the default JSON errors."""
    templates = get_templates()
    if exc.status_code == 404:
        return templates.TemplateResponse(
            request,
            "404.html",
            {"error": "Страница или опрос не найдены."},
            status_code=404,
        )
    if exc.status_code == 403:
        return templates.TemplateResponse(
            request,
            "403.html",
            {"error": "У вас нет доступа к этой странице."},
            status_code=403,
        )
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    user: OptionalUser,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Landing page with a quick database health check."""
    try:
        db.execute(text("SELECT 1"))
        status = "ok"
    except OperationalError:
        status = "db error"

    templates = get_templates()
    return templates.TemplateResponse(
        request, "index.html", {"user": user, "status": status}
    )
