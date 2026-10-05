"""FastAPI application entrypoint.

Run with:
    uvicorn main:app --reload
"""
from contextlib import asynccontextmanager
import os

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from analytics.router import router as analytics_router
from auth.deps import _LoginRequired
from auth.router import router as auth_router
from config import BASE_DIR
from database.session import get_db, init_db
from surveys.router import router as surveys_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (Этап 1: "проверить, что БД создаётся").
    init_db()
    yield


app = FastAPI(title="Мини-SaaS для опросов", lifespan=lifespan)

# Static assets (Chart.js init helper and friends).
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


@app.exception_handler(_LoginRequired)
async def login_required_handler(request: Request, exc: _LoginRequired) -> RedirectResponse:
    """Redirect guests to /login when a creator-only route requires auth."""
    return RedirectResponse(url="/login", status_code=302)


@app.get("/", response_class=HTMLResponse)
def index(db: Session = Depends(get_db)) -> str:
    """Health check page. Full landing appears on Этапе 3."""
    try:
        db.execute(text("SELECT 1"))
        status = "ok"
    except OperationalError:
        status = "db error"
    return (
        "<!doctype html><html lang='ru'><meta charset='utf-8'>"
        "<title>Мини-SaaS для опросов</title>"
        "<h1>Мини-SaaS для опросов</h1>"
        f"<p>Статус: {status}</p>"
        "<p>Каркас и БД готовы. Следующий этап — Auth.</p>"
        "</html>"
    )
