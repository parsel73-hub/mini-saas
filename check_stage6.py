"""Final acceptance scenario for Stage 6 (Этап 6 — сдача и полировка).

Runs the full flow on a clean database:
    init_db -> seed -> register -> create survey -> fill -> stats

Also verifies:
  * seed is idempotent (second run adds nothing);
  * the demo survey has questions of all three types and 10 submissions;
  * the unified CSS is served;
  * friendly 404 / 403 pages are rendered instead of JSON;
  * a flash message appears after creating a survey.

Run against a clean database, e.g.:
    $env:DATABASE_URL="sqlite:///./acceptance_check.db"; python check_stage6.py
"""
import os
import time

from fastapi.testclient import TestClient

import main
from database.models import Answer, Question, Survey
from database.session import SessionLocal, init_db
from database.seed import DEMO_EMAIL, DEMO_TITLE, seed

# Fail fast if the caller forgot to point at a clean database.
DB_URL = os.getenv("DATABASE_URL", "")
assert DB_URL, "Set DATABASE_URL to a clean database before running this script"

init_db()

# ---------------------------------------------------------------------------
# 0) Seed demo data twice to prove idempotency.
# ---------------------------------------------------------------------------
seed()
seed()

db = SessionLocal()
demo_survey = (
    db.query(Survey).filter(Survey.title == DEMO_TITLE).order_by(Survey.id.desc()).first()
)
assert demo_survey is not None, "seed must create the demo survey"
demo_questions = (
    db.query(Question).filter(Question.survey_id == demo_survey.id).all()
)
demo_sessions = {
    a.respondent_session
    for a in db.query(Answer).filter(Answer.survey_id == demo_survey.id).all()
}
types = {q.type for q in demo_questions}
print(
    f"0. seed: user={DEMO_EMAIL}, slug={demo_survey.slug!r}, "
    f"questions={len(demo_questions)}, types={sorted(types)}, "
    f"submissions={len(demo_sessions)}"
)
assert len(demo_questions) == 3
assert types == {"single", "multiple", "text"}
assert len(demo_sessions) == 10

# Second seed call must not duplicate anything.
assert (
    db.query(Survey).filter(Survey.title == DEMO_TITLE).count() == 1
), "seed must be idempotent"

# ---------------------------------------------------------------------------
# 1) Register a new creator.
# ---------------------------------------------------------------------------
BASE = int(time.time())
email = f"accept6_{BASE}@test.ru"
client = TestClient(main.app)
r = client.post(
    "/register",
    data={"email": email, "password": "secret1", "password2": "secret1"},
    follow_redirects=False,
)
print("1. register:", r.status_code)
assert r.status_code in (302, 303)

# ---------------------------------------------------------------------------
# 2) Create a survey with questions of all three types.
# ---------------------------------------------------------------------------
title = f"Приёмочный опрос {BASE}"
r = client.post(
    "/surveys/create",
    data={
        "title": title,
        "description": "Сквозная проверка",
        "question_0_text": "Оцените сервис",
        "question_0_type": "single",
        "question_0_options": ["Отлично", "Хорошо", "Плохо"],
        "question_1_text": "Что понравилось?",
        "question_1_type": "multiple",
        "question_1_options": ["Скорость", "Дизайн", "Цена"],
        "question_2_text": "Комментарий",
        "question_2_type": "text",
    },
    follow_redirects=False,
)
print("2a. create survey:", r.status_code, r.headers.get("location"))
assert r.status_code == 303 and r.headers.get("location") == "/dashboard"

# Flash message is shown on the next page (dashboard).
r = client.get("/dashboard")
assert r.status_code == 200 and "Опрос создан" in r.text, "flash must appear"
print("2b. flash on dashboard: OK")

survey = (
    db.query(Survey)
    .filter(Survey.title == title)
    .order_by(Survey.id.desc())
    .first()
)
assert survey is not None and survey.slug
questions = (
    db.query(Question)
    .filter(Question.survey_id == survey.id)
    .order_by(Question.position)
    .all()
)
assert len(questions) == 3
q_single, q_multi, q_text = questions
opts_single = q_single.options
opts_multi = q_multi.options
print(f"2c. survey id={survey.id} slug={survey.slug!r} questions=3")

# ---------------------------------------------------------------------------
# 3) A guest fills the survey by public link.
# ---------------------------------------------------------------------------
guest = TestClient(main.app)
r = guest.get(f"/survey/{survey.slug}")
assert r.status_code == 200 and "Оцените сервис" in r.text
r = guest.post(
    f"/survey/{survey.slug}/submit",
    data={
        f"answer_{q_single.id}": str(opts_single[0].id),
        f"answer_{q_multi.id}": [str(opts_multi[0].id), str(opts_multi[2].id)],
        f"answer_{q_text.id}": "Всё хорошо",
    },
    follow_redirects=False,
)
print("3. guest submit:", r.status_code, r.headers.get("location"))
assert r.status_code == 303
assert r.headers.get("location") == f"/survey/{survey.slug}/thank-you"

rows = db.query(Answer).filter(Answer.survey_id == survey.id).all()
assert len(rows) == 4, "1 single + 2 multiple + 1 text"
print(f"   saved answers: {len(rows)}")

# ---------------------------------------------------------------------------
# 4) Owner sees statistics.
# ---------------------------------------------------------------------------
r = client.get(f"/survey/{survey.slug}/stats")
assert r.status_code == 200
assert "всего отправок" in r.text and "Последние отправки" in r.text
assert "cdn.jsdelivr.net/npm/chart.js" in r.text
print("4. stats page: OK")

# ---------------------------------------------------------------------------
# 5) Friendly error pages + static CSS.
# ---------------------------------------------------------------------------
r = client.get("/survey/does-not-exist")
assert r.status_code == 404 and "Страница не найдена" in r.text
r = client.get("/totally-unknown-route")
assert r.status_code == 404 and "Страница не найдена" in r.text
print("5a. 404 pages: OK")

other = TestClient(main.app)
other.post(
    "/register",
    data={
        "email": f"other6_{BASE}@test.ru",
        "password": "secret1",
        "password2": "secret1",
    },
    follow_redirects=False,
)
r = other.get(f"/survey/{survey.slug}/stats")
assert r.status_code == 403 and "Доступ запрещён" in r.text
print("5b. 403 page: OK")

r = client.get("/static/css/style.css")
assert r.status_code == 200 and ".btn" in r.text
print("5c. unified CSS served: OK")

db.close()
print("\nALL STAGE 6 ACCEPTANCE CHECKS PASSED")
