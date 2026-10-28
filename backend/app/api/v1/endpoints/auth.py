"""Same-origin cookie login; no public registration or refresh-token surface."""

import logging
import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_session_factory
from app.models.auth import AuthSession
from app.services.auth_service import AuthError, Principal, cookie_name, csrf_token, login

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: SecretStr = Field(min_length=1, max_length=1024)

    @field_validator("password")
    @classmethod
    def bounded_password(cls, value):
        if len(value.get_secret_value().encode()) > 1024:
            raise ValueError("Password exceeds the supported length")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address")
        return value


def auth_db():
    # Auth always uses the private runtime connection, never the public reader.
    with get_session_factory()() as db:
        yield db


def current(request: Request) -> Principal:
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise HTTPException(
            401, detail={"code": "authentication_required", "message": "Authentication required"}
        )
    return principal


def session_response(principal, settings):
    return {
        "user": {"id": principal.id, "email": principal.email, "role": principal.role},
        "expires_at": principal.expires_at,
        "csrf_token": csrf_token(settings, principal.session_id),
    }


@router.post("/login")
def sign_in(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(auth_db),
    settings: Settings = Depends(get_settings),
):
    if not settings.auth_enabled:
        raise HTTPException(503, detail={"code": "auth_disabled", "message": "Login unavailable"})
    try:
        token, principal = login(db, payload.email, payload.password.get_secret_value(), settings)
    except AuthError as exc:
        raise HTTPException(
            exc.status,
            detail={
                "code": exc.code,
                "message": "Invalid credentials"
                if exc.status == 401
                else "Login is temporarily unavailable",
            },
        ) from exc
    response.set_cookie(
        cookie_name(settings),
        token,
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
        path="/",
        max_age=settings.auth_access_token_minutes * 60,
        expires=principal.expires_at,
    )
    return session_response(principal, settings)


@router.get("/me")
def me(principal: Principal = Depends(current), settings: Settings = Depends(get_settings)):
    return session_response(principal, settings)


@router.post("/logout", status_code=204)
def sign_out(
    response: Response,
    principal: Principal = Depends(current),
    db: Session = Depends(auth_db),
    settings: Settings = Depends(get_settings),
):
    row = db.get(AuthSession, principal.session_id)
    if row:
        row.revoked_at = datetime.now(UTC)
        db.commit()
    response.delete_cookie(
        cookie_name(settings),
        path="/",
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
    )
    logger.info("Session revoked user_id=%s", principal.id)
