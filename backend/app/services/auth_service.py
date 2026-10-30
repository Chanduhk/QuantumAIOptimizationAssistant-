from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.database.db import get_db
from backend.app.models.auth import AuthSession, User
from backend.app.models.behavior_data import BehaviorData
from backend.app.models.task import Task

SESSION_COOKIE = "heliox_session"
CSRF_COOKIE = "heliox_csrf"
SESSION_TTL = timedelta(days=7)
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@dataclass(frozen=True)
class IssuedSession:
    user: User
    session_token: str
    csrf_token: str
    expires_at: datetime


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_email(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("email must be a valid email address.")
    email = value.strip().lower()
    if len(email) > 320 or not _EMAIL_PATTERN.fullmatch(email):
        raise ValueError("email must be a valid email address.")
    return email


def validate_password(value: str) -> str:
    if not isinstance(value, str) or len(value) < 12 or len(value) > 1024:
        raise ValueError("password must contain between 12 and 1024 characters.")
    return value


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=64, maxmem=64 * 1024 * 1024)
    return "scrypt$16384$8$1${}${}".format(
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


_DUMMY_PASSWORD_HASH = _password_hash("invalid-account-password", salt=b"heliox-auth-dummy")


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_text, digest_text = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p),
            dklen=len(expected), maxmem=64 * 1024 * 1024,
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, UnicodeError):
        return False


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _new_user_id(db: Session) -> int:
    """Choose a fresh identity without adopting legacy numeric user buckets."""
    occupied: set[int] = {row[0] for row in db.query(User.id).all()}
    occupied.update(row[0] for row in db.query(Task.user_id).distinct().all())
    occupied.update(row[0] for row in db.query(BehaviorData.user_id).distinct().all())
    for _ in range(32):
        candidate = 1_000_000_000 + secrets.randbelow(1_000_000_000)
        if candidate not in occupied:
            return candidate
    maximum = max(occupied, default=0)
    if maximum >= 2_147_483_647:
        raise HTTPException(status_code=503, detail="Could not allocate a new user identity safely.")
    return max(1_000_000_000, maximum + 1)


def register_user(db: Session, email: str, password: str) -> IssuedSession:
    try:
        normalized_email = normalize_email(email)
        safe_password = validate_password(password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if db.query(User.id).filter(func.lower(User.email) == normalized_email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = User(
        id=_new_user_id(db),
        email=normalized_email,
        password_hash=_password_hash(safe_password),
        is_active=True,
        created_at=utc_now(),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from exc
    return create_session(db, user)


def authenticate_user(db: Session, email: str, password: str) -> IssuedSession:
    try:
        normalized_email = normalize_email(email)
    except ValueError:
        normalized_email = ""
    user = db.query(User).filter(func.lower(User.email) == normalized_email).one_or_none()
    # Perform the same expensive hash operation for unknown accounts.
    encoded = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    valid = _verify_password(password, encoded) if isinstance(password, str) and len(password) <= 1024 else False
    if user is None or not user.is_active or not valid:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return create_session(db, user)


def create_session(db: Session, user: User) -> IssuedSession:
    session_token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    expires_at = utc_now() + SESSION_TTL
    db.add(AuthSession(
        token_hash=_token_digest(session_token),
        csrf_hash=_token_digest(csrf_token),
        user_id=user.id,
        expires_at=expires_at,
    ))
    db.commit()
    return IssuedSession(user=user, session_token=session_token, csrf_token=csrf_token, expires_at=expires_at)


def _is_public(request: Request) -> bool:
    return (
        not request.url.path.startswith("/api/v1/")
        or request.url.path in {
            "/api/v1/system/health",
            "/api/v1/system/status",
            "/api/v1/system/component-inventory",
            "/api/v1/ml/model-status",
            "/api/v1/quantum/status",
            "/api/v1/ai/provider-status",
            "/api/v1/ai/provider-test",
            "/api/v1/benchmarks/datasets",
            "/api/v1/benchmarks/quantum",
            "/api/v1/benchmarks/rl",
            "/api/v1/benchmarks/vector-memory",
            "/api/v1/auth/register",
            "/api/v1/auth/login",
        }
        or request.method == "OPTIONS"
    )


def _validate_csrf(request: Request, auth_session: AuthSession, csrf_token: str | None) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get("x-csrf-token")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(status_code=403, detail="CSRF validation failed.")
    if csrf_token is None or not hmac.compare_digest(_token_digest(header), auth_session.csrf_hash):
        raise HTTPException(status_code=403, detail="CSRF validation failed.")


def _authenticate_request(request: Request, db: Session) -> tuple[User, AuthSession] | None:
    if _is_public(request):
        return None
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")
    auth_session = db.query(AuthSession).filter(AuthSession.token_hash == _token_digest(token)).one_or_none()
    now = utc_now()
    if auth_session is None or auth_session.revoked_at is not None or auth_session.expires_at <= now:
        raise HTTPException(status_code=401, detail="Session is invalid or expired.")
    user = db.query(User).filter(User.id == auth_session.user_id, User.is_active.is_(True)).one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Session is invalid or expired.")
    _validate_csrf(request, auth_session, request.cookies.get(CSRF_COOKIE))
    return user, auth_session


async def enforce_authenticated_request(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    authenticated = _authenticate_request(request, db)
    if authenticated is None:
        return None
    user, _ = authenticated
    supplied_ids: list[Any] = list(request.query_params.getlist("user_id"))
    path_match = re.search(r"/api/v1/(?:behavior/(?:patterns|report)|ai/recommendations)/(\d+)$", request.url.path)
    if path_match:
        supplied_ids.append(path_match.group(1))
    content_type = request.headers.get("content-type", "")
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type == "application/json" or media_type.endswith("+json"):
        try:
            body = await request.json()
        except (ValueError, UnicodeDecodeError):
            body = None
        if isinstance(body, dict) and body.get("user_id") is not None:
            supplied_ids.append(body["user_id"])
    for claimed_id in supplied_ids:
        try:
            if isinstance(claimed_id, bool):
                raise HTTPException(status_code=403, detail="Authenticated identity does not match requested user.")
            parsed_id = int(claimed_id)
        except (TypeError, ValueError):
            # Let the endpoint's Pydantic/query validation return its normal 422.
            continue
        if parsed_id <= 0:
            continue
        if parsed_id != user.id:
            raise HTTPException(status_code=403, detail="Authenticated identity does not match requested user.")

    task_match = re.fullmatch(r"/api/v1/tasks/(\d+)(?:/(?:start|complete|feedback))?", request.url.path)
    if task_match:
        owned_task = db.query(Task.id).filter(Task.id == int(task_match.group(1)), Task.user_id == user.id).first()
        if owned_task is None:
            raise HTTPException(status_code=404, detail="Task not found.")
    return user


def get_current_user(
    request: Request,
    authenticated: User | None = Depends(enforce_authenticated_request),
) -> User:
    if authenticated is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return authenticated


def revoke_session(request: Request, db: Session) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        auth_session = db.query(AuthSession).filter(AuthSession.token_hash == _token_digest(token)).one_or_none()
        if auth_session is not None and auth_session.revoked_at is None:
            auth_session.revoked_at = utc_now()
            db.commit()


def cookie_secure() -> bool:
    production = any(
        os.environ.get(key, "").strip().lower() in {"production", "prod", "live"}
        for key in ("APP_ENV", "ENVIRONMENT", "DEPLOYMENT_ENV", "QUANTUM_LIFE_ENV")
    )
    if production:
        return True
    configured = os.environ.get("AUTH_COOKIE_SECURE")
    if configured is not None:
        return configured.strip().lower() in {"1", "true", "yes"}
    return False


def set_session_cookies(response: Any, credentials: IssuedSession) -> None:
    max_age = int(SESSION_TTL.total_seconds())
    response.set_cookie(
        SESSION_COOKIE, credentials.session_token, max_age=max_age, httponly=True,
        secure=cookie_secure(), samesite="lax", path="/api/v1",
    )
    response.set_cookie(
        CSRF_COOKIE, credentials.csrf_token, max_age=max_age, httponly=False,
        secure=cookie_secure(), samesite="strict", path="/",
    )


def clear_session_cookies(response: Any) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/api/v1", secure=cookie_secure(), httponly=True, samesite="lax")
    response.delete_cookie(CSRF_COOKIE, path="/", secure=cookie_secure(), httponly=False, samesite="strict")
