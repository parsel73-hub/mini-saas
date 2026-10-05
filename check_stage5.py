"""Verification of Stage 5: creator statistics page.

Checks (по ТЗ):
  * total submissions equals the real number of distinct respondent sessions;
  * option percents for a single question sum to ~100%;
  * free-text answers are listed;
  * the latest-submissions table is populated (masked session + date);
  * a different user cannot open someone else's stats (403/404);
  * the page renders with Chart.js + embedded JSON chart data;
  * the /static/js helper is served.
"""
import time

from fastapi.testclient import TestClient

import main
from database.models import Answer, Option, Question, Survey
from database.session import SessionLocal, init_db

init_db()
BASE = int(time.time())

creator_email = f"creator5_{BASE}@test.ru"
other_email = f"other5_{BASE}@test.ru"
title = f"Этап 5 — статистика {BASE}"


def new_client() -> TestClient:
    return TestClient(main.app)


def register(client, email):
    return client.post(
        "/register",
        data={"email": email, "password": "secret1", "password2": "secret1"},
        follow_redirects=False,
    )


# ---------------------------------------------------------------------------
# Setup: creator, survey with one single question (2 options) and one text.
# ---------------------------------------------------------------------------
creator = new_client()
assert register(creator, creator_email).status_code in (302, 303)

r = creator.post(
    "/surveys/create",
    data={
        "title": title,
        "description": "Проверка статистики",
        "question_0_text": "Ваш пол?",
        "question_0_type": "single",
        "question_0_options": ["Мужской", "Женский"],
        "question_1_text": "Комментарий",
        "question_1_type": "text",
    },
    follow_redirects=False,
)
assert r.status_code == 303, r.text[:500]

db = SessionLocal()
survey = (
    db.query(Survey)
    .filter(Survey.title == title)
    .order_by(Survey.id.desc())
    .first()
)
questions = (
    db.query(Question)
    .filter(Question.survey_id == survey.id)
    .order_by(Question.position)
    .all()
)
q_single, q_text = questions
opts = (
    db.query(Option)
    .filter(Option.question_id == q_single.id)
    .order_by(Option.position)
    .all()
)
print(f"0. survey id={survey.id} slug={survey.slug!r} questions={len(questions)}")

# ---------------------------------------------------------------------------
# Submit 3 responses from clean browsers: 2x first option, 1x second option.
# ---------------------------------------------------------------------------
payloads = [
    {f"answer_{q_single.id}": str(opts[0].id), f"answer_{q_text.id}": "Отлично"},
    {f"answer_{q_single.id}": str(opts[0].id), f"answer_{q_text.id}": "Хорошо"},
    {f"answer_{q_single.id}": str(opts[1].id), f"answer_{q_text.id}": "Нормально"},
]
for i, payload in enumerate(payloads, start=1):
    browser = new_client()
    r = browser.post(
        f"/survey/{survey.slug}/submit", data=payload, follow_redirects=False
    )
    print(f"1.{i} submit:", r.status_code)
    assert r.status_code == 303

rows = db.query(Answer).filter(Answer.survey_id == survey.id).all()
sessions = {a.respondent_session for a in rows}
print(f"2. answers rows={len(rows)} distinct sessions={len(sessions)}")
assert len(sessions) == 3

# ---------------------------------------------------------------------------
# 3) Stats page renders for the owner.
# ---------------------------------------------------------------------------
r = creator.get(f"/survey/{survey.slug}/stats")
print("3a. GET stats (owner):", r.status_code)
assert r.status_code == 200
text = r.text
assert title in text
assert "3" in text  # total submissions displayed
assert "Ваш пол?" in text and "Комментарий" in text
# Chart.js and embedded JSON chart data.
assert "cdn.jsdelivr.net/npm/chart.js" in text
assert 'data-chart' in text and 'type="application/json"' in text
assert "chart-q{}".format(q_single.id) in text
# Recent submissions table shows masked sessions.
assert "Последние отправки" in text
assert "…" in text  # masked session id

# Static helper is served.
r = creator.get("/static/js/chart_init.js")
print("3b. GET /static/js/chart_init.js:", r.status_code)
assert r.status_code == 200 and "Chart" in r.text

# ---------------------------------------------------------------------------
# 4) Verify aggregation numbers directly from the service.
# ---------------------------------------------------------------------------
from analytics.services import survey_stats

stats = survey_stats(db, survey.id)
print("4a. total_submissions:", stats["total_submissions"])
assert stats["total_submissions"] == 3

single = next(q for q in stats["questions"] if q["id"] == q_single.id)
print("4b. single breakdown:", single["options"])
assert single["options"][0]["count"] == 2
assert single["options"][1]["count"] == 1
assert single["options"][0]["percent"] == 66.7
assert single["options"][1]["percent"] == 33.3
percent_sum = sum(o["percent"] for o in single["options"])
print("4c. percent sum:", percent_sum)
assert abs(percent_sum - 100.0) < 0.5

text_q = next(q for q in stats["questions"] if q["id"] == q_text.id)
print("4d. text answers:", text_q["answers"])
assert set(text_q["answers"]) == {"Отлично", "Хорошо", "Нормально"}

print("4e. recent rows:", len(stats["recent"]))
assert len(stats["recent"]) == 3
assert all(row["session"] and row["summary"] for row in stats["recent"])

# ---------------------------------------------------------------------------
# 5) Another user cannot open someone else's stats (403/404).
# ---------------------------------------------------------------------------
other = new_client()
assert register(other, other_email).status_code in (302, 303)
r = other.get(f"/survey/{survey.slug}/stats", follow_redirects=False)
print("5a. GET stats (other user):", r.status_code)
assert r.status_code in (403, 404)

# Guest is redirected to /login by the auth dependency.
guest = new_client()
r = guest.get(f"/survey/{survey.slug}/stats", follow_redirects=False)
print("5b. GET stats (guest):", r.status_code, r.headers.get("location"))
assert r.status_code in (302, 303) and r.headers.get("location") == "/login"

# Unknown slug -> 404 for an authed user.
r = creator.get("/survey/does-not-exist/stats", follow_redirects=False)
print("5c. GET stats (unknown slug):", r.status_code)
assert r.status_code == 404

db.close()
print("\nALL STAGE 5 CHECKS PASSED")
