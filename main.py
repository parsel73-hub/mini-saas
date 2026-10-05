"""FastAPI application entrypoint.

Run with:
    uvicorn main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from auth.router import router as auth_router
from database.session import get_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (Этап 1: "проверить, что БД создаётся").
    init_db()
    yield


app = FastAPI(title="Мини-SaaS для опросов", lifespan=lifespan)

# Auth routes: register / login / logout / account (Этап 2).
app.include_router(auth_router)


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
