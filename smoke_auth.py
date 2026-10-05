"""Temporary smoke test: boots uvicorn, exercises auth flow, shuts down."""
import os
import subprocess
import sys
import time

import httpx

DB_PATH = os.path.abspath("smoke_auth.db")
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

env = dict(os.environ, DATABASE_URL=f"sqlite:///{DB_PATH}", PYTHONUNBUFFERED="1")

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--port", "8123"],
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

base = "http://127.0.0.1:8123"
try:
    # Wait for server readiness.
    ready = False
    for _ in range(50):
        try:
            r = httpx.get(base + "/register", timeout=1.0)
            if r.status_code == 200:
                ready = True
                break
        except Exception:
            time.sleep(0.2)
    print("server ready:", ready)

    client = httpx.Client(base_url=base, follow_redirects=False)

    r = client.get("/register")
    print("GET /register ->", r.status_code)

    r = client.post("/register", data={"email": "demo@test.ru", "password": "secret1", "password2": "secret1"})
    print("POST /register ->", r.status_code, "| Location:", r.headers.get("location"),
          "| cookie set:", "session" in r.headers.get("set-cookie", ""))

    r = client.get("/account")
    print("GET /account (authed) ->", r.status_code)

    r = client.post("/logout")
    print("POST /logout ->", r.status_code, "| Location:", r.headers.get("location"))

    r = client.get("/account")
    print("GET /account (after logout) ->", r.status_code, "| Location:", r.headers.get("location"))

    # Login flow.
    client.post("/register", data={"email": "two@test.ru", "password": "secret2", "password2": "secret2"})
    client.post("/logout")
    r = client.post("/login", data={"email": "two@test.ru", "password": "secret2"})
    print("POST /login ->", r.status_code, "| Location:", r.headers.get("location"))
    r = client.get("/account")
    print("GET /account (after login) ->", r.status_code)

    client.post("/logout")
    r = client.post("/login", data={"email": "two@test.ru", "password": "WRONG"})
    print("POST /login wrong pw ->", r.status_code)

    print("SMOKE TEST DONE")
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
