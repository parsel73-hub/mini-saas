"""Verification of Stage 3: survey creation, dashboard, guest filling.

Checks (по ТЗ):
  * создание опроса с 2 вопросами (single с вариантами + text);
  * записи в surveys/questions/options, уникальный slug;
  * /survey/{slug} без авторизации рендерит вопросы;
  * несуществующий slug -> 404;
  * /dashboard только для авторизованных;
  * /survey/{slug}/stats — заглушка для создателя;
  * submit-заглушка редиректит на thank-you.
"""
import time

from fastapi.testclient import TestClient

import main
from database.models import Option, Question, Survey
from database.session import SessionLocal, init_db

init_db()
client = TestClient(main.app)

EMAIL = f"creator3_{int(time.time())}@test.ru"
TITLE = f"Этап 3 — тест {int(time.time())}"

# 1) Register a creator.
r = client.post(
    "/register",
    data={"email": EMAIL, "password": "secret1", "password2": "secret1"},
    follow_redirects=False,
)
print("1. Register:", r.status_code, r.headers.get("location"))
assert r.status_code == 303

# 2) Create a survey with 2 questions (single with 2 options + text).
r = client.post(
    "/surveys/create",
    data={
        "title": TITLE,
        "description": "Проверка создания",
        "question_0_text": "Ваш пол?",
        "question_0_type": "single",
        "question_0_options": "Мужской\nЖенский",
        "question_1_text": "Комментарий",
        "question_1_type": "text",
    },
    follow_redirects=False,
)
print("2. Create survey:", r.status_code, r.headers.get("location"))
assert r.status_code == 303, r.text[:500]
assert r.headers.get("location") == "/dashboard"

# 3) Check DB rows and slug uniqueness.
db = SessionLocal()
survey = (
    db.query(Survey)
    .filter(Survey.title == TITLE)
    .order_by(Survey.id.desc())
    .first()
)
assert survey is not None
questions = db.query(Question).filter(Question.survey_id == survey.id).all()
options = (
    db.query(Option)
    .join(Question, Option.question_id == Question.id)
    .filter(Question.survey_id == survey.id)
    .all()
)
print(
    f"3. DB: survey id={survey.id}, slug={survey.slug!r}, "
    f"questions={len(questions)}, options={len(options)}"
)
assert len(questions) == 2
assert len(options) == 2
assert len(survey.slug) >= 8
assert survey.is_active is True
# Slug must be unique across surveys.
dupes = db.query(Survey).filter(Survey.slug == survey.slug).count()
assert dupes == 1, "slug must be unique"

# 4) Dashboard requires auth and lists the survey.
client.cookies.clear()
r = client.get("/dashboard", follow_redirects=False)
print("4a. Dashboard (guest):", r.status_code, r.headers.get("location"))
assert r.status_code in (302, 303) and r.headers.get("location") == "/login"

client.post(
    "/login", data={"email": EMAIL, "password": "secret1"},
    follow_redirects=False,
)
r = client.get("/dashboard")
print("4b. Dashboard (authed):", r.status_code)
assert r.status_code == 200
assert TITLE in r.text
assert f"/survey/{survey.slug}" in r.text
assert f"/survey/{survey.slug}/stats" in r.text

# 5) Guest can open the fill page (NO auth).
client.cookies.clear()
r = client.get(f"/survey/{survey.slug}")
print("5. Fill page (guest):", r.status_code)
assert r.status_code == 200
assert "Ваш пол?" in r.text
assert "Мужской" in r.text and "Женский" in r.text
assert "Комментарий" in r.text
assert "textarea" in r.text
assert 'type="radio"' in r.text

# 6) Unknown slug -> 404.
r = client.get("/survey/does-not-exist")
print("6. Unknown slug:", r.status_code)
assert r.status_code == 404

# 7) Submit stub redirects to thank-you, which renders for guests.
r = client.post(
    f"/survey/{survey.slug}/submit",
    data={
        f"answer_{questions[0].id}": str(options[0].id),
        f"answer_{questions[1].id}": "Отличный сервис",
    },
    follow_redirects=False,
)
print("7. Submit:", r.status_code, r.headers.get("location"))
assert r.status_code == 303
assert r.headers.get("location") == f"/survey/{survey.slug}/thank-you"

r = client.get(f"/survey/{survey.slug}/thank-you")
print("8. Thank-you (guest):", r.status_code)
assert r.status_code == 200
assert "Спасибо" in r.text

# 9) Stats page requires auth; guest is redirected to /login.
client.cookies.clear()
r = client.get(f"/survey/{survey.slug}/stats", follow_redirects=False)
print("9a. Stats (guest):", r.status_code, r.headers.get("location"))
assert r.status_code in (302, 303) and r.headers.get("location") == "/login"

client.post(
    "/login", data={"email": EMAIL, "password": "secret1"},
    follow_redirects=False,
)
r = client.get(f"/survey/{survey.slug}/stats")
print("9b. Stats (authed):", r.status_code)
assert r.status_code == 200
assert "Статистика" in r.text

# 10) Options submitted as repeated fields (list) — as the real form does.
r = client.post(
    "/surveys/create",
    data={
        "title": TITLE + " (list)",
        "description": "",
        "question_0_text": "Любимый цвет?",
        "question_0_type": "single",
        "question_0_options": ["Красный", "Синий", "Зелёный"],
    },
    follow_redirects=False,
)
print("10. Create (list options):", r.status_code, r.headers.get("location"))
assert r.status_code == 303
list_survey = (
    db.query(Survey)
    .filter(Survey.title == TITLE + " (list)")
    .order_by(Survey.id.desc())
    .first()
)
list_q = db.query(Question).filter(Question.survey_id == list_survey.id).all()
list_opts = (
    db.query(Option)
    .join(Question, Option.question_id == Question.id)
    .filter(Question.survey_id == list_survey.id)
    .all()
)
print(f"    list survey: questions={len(list_q)}, options={len(list_opts)}")
assert len(list_q) == 1 and len(list_opts) == 3

# 11) Validation error re-renders the form and preserves the input.
r = client.post(
    "/surveys/create",
    data={
        "title": "Плохой опрос",
        "question_0_text": "Вопрос с одним вариантом",
        "question_0_type": "single",
        "question_0_options": "Единственный",
    },
    follow_redirects=False,
)
print("11. Validation error:", r.status_code)
assert r.status_code == 422
assert "минимум 2 варианта" in r.text
assert "Вопрос с одним вариантом" in r.text  # input preserved
assert "Единственный" in r.text  # option preserved

# 12) Creation form requires auth.
client.cookies.clear()
r = client.get("/surveys/create", follow_redirects=False)
print("12. Create form (guest):", r.status_code, r.headers.get("location"))
assert r.status_code in (302, 303) and r.headers.get("location") == "/login"

db.close()
print("ALL STAGE 3 CHECKS PASSED")
