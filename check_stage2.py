"""Verification of Stage 2 points 4-6: templates, navigation, protection."""
import time

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)
EMAIL = f"test2_{int(time.time())}@test.ru"

# 1) Register a user.
r = client.post(
    "/register",
    data={"email": EMAIL, "password": "secret1", "password2": "secret1"},
    follow_redirects=False,
)
print("Register:", r.status_code, "redirect to:", r.headers.get("location"))
assert r.status_code in (302, 303)

# 2) Dashboard without auth -> redirect to /login.
client.cookies.clear()
r = client.get("/dashboard", follow_redirects=False)
print("Dashboard (guest):", r.status_code, "redirect to:", r.headers.get("location"))
assert r.status_code in (302, 303) and r.headers.get("location") == "/login"

# 3) Login and open dashboard.
client.post(
    "/login", data={"email": EMAIL, "password": "secret1"}, follow_redirects=False
)
r = client.get("/dashboard")
print("Dashboard (authed):", r.status_code)
assert r.status_code == 200

# 4) Navigation for guests: show login/register links only.
client.cookies.clear()
r = client.get("/login")
text = r.text
assert "Мои опросы" not in text, "guest nav must not contain 'My surveys'"
assert "Войти" in text and "Регистрация" in text
print("Nav (guest): OK")

# 5) Navigation for authed users: "My surveys" + logout.
client.post(
    "/login", data={"email": EMAIL, "password": "secret1"}, follow_redirects=False
)
r = client.get("/account")
text = r.text
assert "Мои опросы" in text, "authed nav must contain 'My surveys' link"
assert "Выйти" in text
assert "/dashboard" in text
print("Nav (authed): OK")

# 6) Validation errors render on the forms (point 4).
r = client.post(
    "/register",
    data={"email": "bad-email", "password": "secret1", "password2": "secret1"},
    follow_redirects=False,
)
assert r.status_code == 400 and "корректный email" in r.text
r = client.post(
    "/register",
    data={"email": "x@y.ru", "password": "123", "password2": "456"},
    follow_redirects=False,
)
assert r.status_code == 400
r = client.post(
    "/login", data={"email": EMAIL, "password": "WRONG"}, follow_redirects=False
)
assert r.status_code == 401 and "Неверный" in r.text
print("Validation errors: OK")

# 7) Survey-filling page is guest-open: no /s/ routes yet (Stage 4),
# but require_login must NOT be used on such future routes.
from auth.deps import CurrentUser, OptionalUser, require_login  # noqa: F401

print("Protection helpers available: CurrentUser, OptionalUser, get_current_user")

print("ALL CHECKS PASSED")
