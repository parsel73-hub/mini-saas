"""Auth HTML routes: register, login, logout (Этап 2 — Auth)."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from auth import security
from auth.deps import get_current_user, get_templates, resolve_user
from auth.models import User
from database.session import get_db
from flash import set_flash

router = APIRouter(tags=["auth"])


@router.get("/register", response_class=HTMLResponse)
def register_form(
    request: Request, user: User | None = Depends(get_current_user)
) -> HTMLResponse:
    """Render the registration page."""
    templates = get_templates()
    return templates.TemplateResponse(request, "auth/register.html", {"user": user})


@router.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    """Validate and create a user, then start a signed session."""
    templates = get_templates()
    email = email.strip().lower()

    error = None
    if not email or "@" not in email:
        error = "Укажите корректный email."
    elif len(password) < 6:
        error = "Пароль должен быть не короче 6 символов."
    elif password != password2:
        error = "Пароли не совпадают."
    elif db.query(User).filter(User.email == email).first():
        error = "Пользователь с таким email уже существует."

    if error:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {"user": user, "error": error, "email": email},
            status_code=400,
        )

    new_user = User(email=email, password_hash=security.hash_password(password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    response = RedirectResponse(url="/account", status_code=303)
    response.set_cookie(
        key=security.SESSION_COOKIE_NAME,
        value=security.create_session_token(new_user.id),
        max_age=security.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    set_flash(response, "Аккаунт создан. Добро пожаловать!", "success")
    return response


@router.get("/login", response_class=HTMLResponse)
def login_form(
    request: Request, user: User | None = Depends(get_current_user)
) -> HTMLResponse:
    """Render the login page."""
    templates = get_templates()
    return templates.TemplateResponse(request, "auth/login.html", {"user": user})


@router.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    """Authenticate a user and start a signed session."""
    templates = get_templates()
    email = email.strip().lower()
    user_row = db.query(User).filter(User.email == email).first()

    if not user_row or not user_row.password_hash or not security.verify_password(
        password, user_row.password_hash
    ):
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "user": user,
                "error": "Неверный email или пароль.",
                "email": email,
            },
            status_code=401,
        )

    response = RedirectResponse(url="/account", status_code=303)
    response.set_cookie(
        key=security.SESSION_COOKIE_NAME,
        value=security.create_session_token(user_row.id),
        max_age=security.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    set_flash(response, "Вы вошли в аккаунт.", "success")
    return response


@router.post("/logout")
def logout() -> RedirectResponse:
    """Clear the session cookie and redirect home."""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key=security.SESSION_COOKIE_NAME)
    set_flash(response, "Вы вышли из аккаунта.", "info")
    return response


@router.get("/account", response_class=HTMLResponse)
def account(
    request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    """Simple authenticated area to prove the session works (Этап 2)."""
    user = resolve_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    templates = get_templates()
    return templates.TemplateResponse(request, "auth/account.html", {"user": user})
