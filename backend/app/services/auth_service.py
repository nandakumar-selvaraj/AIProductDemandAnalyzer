"""Argon2id passwords, strict JWT validation and immediate DB session revocation."""

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import BoundedSemaphore
from uuid import UUID

import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.core.config import Settings
from app.db.session import get_session_factory
from app.models.auth import AuthSession, User

logger = logging.getLogger(__name__)
PASSWORDS = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, type=Type.ID)
DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(32))
LOGIN_GATE = BoundedSemaphore(2)


class AuthError(Exception):
    def __init__(self, status=401, code="authentication_required"):
        self.status, self.code = status, code


def cookie_name(settings):
    return "__Host-demand_session" if settings.environment == "production" else "demand_session"


def csrf_token(settings, session_id):
    return hmac.new(
        settings.jwt_signing_secret.get_secret_value().encode(),
        ("csrf:" + session_id).encode(),
        hashlib.sha256,
    ).hexdigest()


def aware(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@dataclass(frozen=True)
class Principal:
    id: str
    email: str
    role: str
    session_id: str
    expires_at: datetime


def issue_session(db: Session, user: User, settings: Settings):
    now = datetime.now(UTC).replace(microsecond=0)
    expires = now + timedelta(minutes=settings.auth_access_token_minutes)
    session_id = secrets.token_hex(32)
    session = AuthSession(id=session_id, user_id=user.id, expires_at=expires)
    db.add(session)
    db.commit()
    token = jwt.encode(
        {
            "sub": user.id,
            "jti": session_id,
            "iat": now,
            "nbf": now,
            "exp": expires,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        },
        settings.jwt_signing_secret.get_secret_value(),
        algorithm="HS256",
    )
    return token, Principal(user.id, user.email, user.role, session_id, expires)


def decode_token(token: str, settings: Settings):
    try:
        claims = jwt.decode(
            token,
            settings.jwt_signing_secret.get_secret_value(),
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={
                "require": ["sub", "jti", "iat", "nbf", "exp", "iss", "aud"],
                "strict_aud": True,
            },
        )
        UUID(claims["sub"])
        if any(type(claims[field]) is not int for field in ("exp", "iat", "nbf")):
            raise ValueError("Invalid JWT time claims")
        if claims["exp"] <= claims["iat"] or claims["nbf"] > claims["exp"]:
            raise ValueError("Invalid JWT time ordering")
        if (
            not isinstance(claims["jti"], str)
            or len(claims["jti"]) != 64
            or any(c not in "0123456789abcdef" for c in claims["jti"])
        ):
            raise ValueError("Invalid session ID")
        return claims
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError) as exc:
        raise AuthError() from exc


def authenticate_request(scope, settings: Settings):
    request = Request(scope)
    raw = request.cookies.get(cookie_name(settings))
    if not raw:
        return None
    if len(raw) > 4096:
        raise AuthError()
    claims = decode_token(raw, settings)
    with get_session_factory()() as db:
        row = db.get(AuthSession, claims["jti"])
        user = db.get(User, claims["sub"])
        if (
            not row
            or not user
            or not user.is_active
            or row.user_id != user.id
            or row.revoked_at is not None
            or aware(row.expires_at) <= datetime.now(UTC)
            or user.role not in {"admin", "viewer"}
        ):
            raise AuthError()
        return Principal(user.id, user.email, user.role, row.id, aware(row.expires_at))


def login(db: Session, email: str, password: str, settings: Settings):
    if not LOGIN_GATE.acquire(blocking=False):
        raise AuthError(429, "login_rate_limit")
    try:
        user = db.scalar(select(User).where(User.email == email))
        try:
            valid = PASSWORDS.verify(user.password_hash if user else DUMMY_HASH, password)
        except (VerificationError, InvalidHashError):
            valid = False
        if not valid or not user or not user.is_active:
            logger.info("Authentication denied")
            raise AuthError(401, "invalid_credentials")
        if PASSWORDS.check_needs_rehash(user.password_hash):
            user.password_hash = PASSWORDS.hash(password)
        result = issue_session(db, user, settings)
        logger.info("Authentication accepted user_id=%s", user.id)
        return result
    finally:
        LOGIN_GATE.release()
