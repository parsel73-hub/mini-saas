"""Verification of Stage 4: answer saving, PRG and double-submit protection.

Checks (по ТЗ):
  * submit saves one answers row per answer with a shared respondent_session;
  * repeated submit from the same browser is rejected (409);
  * a "clean" browser can submit successfully;
  * a foreign option_id is rejected by validation (422);
  * PRG: after submit the redirect lands on thank-you and Back/refresh
    does not re-record answers;
  * respondents are anonymous (no auth needed).
"""
import time

from fastapi.testclient import TestClient

import main
from database.models import Answer, Option, Question, Survey
from database.session import SessionLocal, init_db

init_db()

EMAIL = f"creator4_{int(time.time())}@test.ru"
TITLE = f"Этап 4 — тест {int(time.time())}"


def new_client() -> TestClient:
    """Return a fresh client (empty cookie jar = 'clean browser')."""
    return TestClient(main.app)


def answers_for(db, survey_id):
    return (
        db.query(Answer)
        .filter(Answer.survey_id == survey_id)
        .order_by(Answer.id)
        .all()
    )


# ---------------------------------------------------------------------------
# Setup: register a creator and build a survey with single + multiple + text.
# ---------------------------------------------------------------------------
creator = new_client()
r = creator.post(
    "/register",
    data={"email": EMAIL, "password": "secret1", "password2": "secret1"},
    follow_redirects=False,
)
print("0. Register creator:", r.status_code)
assert r.status_code in (302, 303)

r = creator.post(
    "/surveys/create",
    data={
        "title": TITLE,
        "description": "Проверка сохранения ответов",
        "question_0_text": "Вам понравилось?",
        "question_0_type": "single",
        "question_0_options": ["Да", "Нет"],
        "question_1_text": "Что понравилось?",
        "question_1_type": "multiple",
        "question_1_options": ["Скорость", "Дизайн", "Поддержка"],
        "question_2_text": "Комментарий",
        "question_2_type": "text",
    },
    follow_redirects=False,
)
assert r.status_code == 303, r.text[:500]

db = SessionLocal()
survey = (
    db.query(Survey)
    .filter(Survey.title == TITLE)
    .order_by(Survey.id.desc())
    .first()
)
assert survey is not None
questions = (
    db.query(Question)
    .filter(Question.survey_id == survey.id)
    .order_by(Question.position)
    .all()
)
q_single, q_multi, q_text = questions
opts_single = (
    db.query(Option)
    .filter(Option.question_id == q_single.id)
    .order_by(Option.position)
    .all()
)
opts_multi = (
    db.query(Option)
    .filter(Option.question_id == q_multi.id)
    .order_by(Option.position)
    .all()
)
print(
    f"   survey id={survey.id} slug={survey.slug!r} "
    f"questions={len(questions)}"
)
assert len(questions) == 3
assert len(opts_single) == 2 and len(opts_multi) == 3

form_payload = {
    f"answer_{q_single.id}": str(opts_single[0].id),
    f"answer_{q_multi.id}": [str(opts_multi[0].id), str(opts_multi[2].id)],
    f"answer_{q_text.id}": "Всё отлично",
}

# ---------------------------------------------------------------------------
# 1) Anonymous respondent submits the form.
# ---------------------------------------------------------------------------
browser = new_client()
r = browser.get(f"/survey/{survey.slug}")
print("1a. GET fill (guest):", r.status_code)
assert r.status_code == 200
assert "Вам понравилось?" in r.text
assert 'type="checkbox"' in r.text
assert "textarea" in r.text

r = browser.post(
    f"/survey/{survey.slug}/submit",
    data=form_payload,
    follow_redirects=False,
)
print("1b. POST submit:", r.status_code, r.headers.get("location"))
assert r.status_code == 303
assert r.headers.get("location") == f"/survey/{survey.slug}/thank-you"
assert any(
    c.startswith("respondent_") for c in browser.cookies.keys()
), "respondent cookie must be set"

rows = answers_for(db, survey.id)
print(f"1c. answers rows after submit: {len(rows)}")
assert len(rows) == 4  # 1 single + 2 multiple + 1 text

sessions = {a.respondent_session for a in rows}
assert len(sessions) == 1 and None not in sessions, "shared respondent_session"

by_q = {}
for a in rows:
    by_q.setdefault(a.question_id, []).append(a)

assert by_q[q_single.id][0].option_id == opts_single[0].id
assert {a.option_id for a in by_q[q_multi.id]} == {
    opts_multi[0].id,
    opts_multi[2].id,
}
assert by_q[q_text.id][0].text_value == "Всё отлично"
assert all(a.survey_id == survey.id for a in rows)
print("1d. row values verified: option_id / text_value / survey_id / session OK")

# ---------------------------------------------------------------------------
# 2) Repeated submit from the same browser is rejected, no new rows.
# ---------------------------------------------------------------------------
before = len(answers_for(db, survey.id))
r = browser.post(
    f"/survey/{survey.slug}/submit",
    data=form_payload,
    follow_redirects=False,
)
print("2a. Repeat submit (same browser):", r.status_code)
assert r.status_code == 409
assert "уже прошли" in r.text.lower()
assert len(answers_for(db, survey.id)) == before, "no duplicate rows"

r = browser.get(f"/survey/{survey.slug}")
print("2b. GET fill after submit (same browser):", r.status_code)
assert r.status_code == 200 and "уже прошли" in r.text.lower()

# ---------------------------------------------------------------------------
# 3) A "clean" browser can submit successfully.
# ---------------------------------------------------------------------------
clean = new_client()
r = clean.post(
    f"/survey/{survey.slug}/submit",
    data=form_payload,
    follow_redirects=False,
)
print("3. Submit from clean browser:", r.status_code)
assert r.status_code == 303
rows = answers_for(db, survey.id)
assert len(rows) == before + 4
new_sessions = {a.respondent_session for a in rows}
assert len(new_sessions) == 2, "each submission gets its own session id"

# ---------------------------------------------------------------------------
# 4) A foreign option_id is rejected by validation.
# ---------------------------------------------------------------------------
other = Survey(
    title=f"Другой опрос {int(time.time())}",
    description="",
    slug=f"other{int(time.time()) % 100000}",
    is_active=True,
)
db.add(other)
db.flush()
other_q = Question(
    survey_id=other.id, text="Чужой вопрос", type="single", position=1
)
db.add(other_q)
db.flush()
foreign_opt = Option(question_id=other_q.id, text="Чужой вариант", position=1)
db.add(foreign_opt)
db.commit()

bad = new_client()
bad_payload = dict(form_payload)
bad_payload[f"answer_{q_single.id}"] = str(foreign_opt.id)
count_before = len(answers_for(db, survey.id))
r = bad.post(
    f"/survey/{survey.slug}/submit",
    data=bad_payload,
    follow_redirects=False,
)
print("4a. Foreign option_id:", r.status_code)
assert r.status_code == 422
assert "Недопустимый вариант" in r.text
assert len(answers_for(db, survey.id)) == count_before, "nothing saved"
# Entered answers are preserved on the re-rendered form.
assert "Всё отлично" in r.text, "entered text answer preserved"

# Unanswered required single question is rejected too.
bad2 = new_client()
r = bad2.post(
    f"/survey/{survey.slug}/submit",
    data={f"answer_{q_text.id}": "только текст"},
    follow_redirects=False,
)
print("4b. Unanswered single:", r.status_code)
assert r.status_code == 422
assert "Ответьте на вопрос" in r.text

# ---------------------------------------------------------------------------
# 5) PRG: follow the redirect, land on thank-you, no extra rows.
# ---------------------------------------------------------------------------
prg = new_client()
r = prg.post(
    f"/survey/{survey.slug}/submit",
    data=form_payload,
    follow_redirects=True,
)
print("5a. Submit with redirects followed:", r.status_code)
assert r.status_code == 200
assert "Спасибо" in r.text
rows_after = len(answers_for(db, survey.id))
r = prg.get(f"/survey/{survey.slug}/thank-you")
assert r.status_code == 200
assert len(answers_for(db, survey.id)) == rows_after, "GET must not write rows"
print("5b. Thank-you GET does not create rows (PRG OK)")

# ---------------------------------------------------------------------------
# Snippet of the answers table.
# ---------------------------------------------------------------------------
print("\n--- answers table (survey id={}) ---".format(survey.id))
print(
    f"{'id':>4} | {'survey_id':>9} | {'question_id':>11} | "
    f"{'option_id':>9} | {'text_value':<14} | respondent_session"
)
for a in answers_for(db, survey.id):
    print(
        f"{a.id:>4} | {a.survey_id:>9} | {a.question_id:>11} | "
        f"{str(a.option_id):>9} | {str(a.text_value):<14} | "
        f"{a.respondent_session}"
    )

db.close()
print("\nALL STAGE 4 CHECKS PASSED")
