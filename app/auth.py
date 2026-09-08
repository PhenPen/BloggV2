"""Password hashing, JWT access tokens, and the ``get_current_user`` dependency.

Passwords use pwdlib's recommended hash (argon2 for new hashes, with
automatic verification of legacy variants). Access tokens are HS256 JWTs that
exchange their ``sub`` (subject) claim for a ``User`` row.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.config import settings
from app.database import get_db_session

password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/users/token", auto_error=False)


def hash_password(plain_password: str) -> str:
    return password_hash.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def generate_reset_token() -> str:
    """Return a URL-safe random token safe to embed in a link's query string."""
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    """SHA-256 hex digest of a reset token; only this hash is stored in the DB."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(data: dict, minutes: timedelta | None = None) -> str:
    """Encode ``data`` into a signed JWT with an ``exp`` claim."""
    data_to_encode = data.copy()

    if minutes:
        access_token_expiry = datetime.now(timezone.utc) + minutes
    else:
        access_token_expiry = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_token_expiry_mins
        )

    data_to_encode.update({"exp": access_token_expiry})

    return jwt.encode(
        data_to_encode,
        key=settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def verify_access_token(token: str) -> str | None:
    """Decode and validate a JWT, returning its ``sub`` (user id as string).

    Returns ``None`` for any invalid/expired token.
    """
    try:
        payload = jwt.decode(
            token,
            key=settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.InvalidTokenError:
        return None
    else:
        return payload.get("sub")


def set_access_token_cookie(response: Response, token: str) -> None:
    """Attach the JWT as an httpOnly SameSite cookie on ``response``."""
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        max_age=settings.jwt_token_expiry_mins * 60,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        path="/",
    )


def clear_access_token_cookie(response: Response) -> None:
    """Force-expire the auth cookie by matching its name/path and max_age=0."""
    response.delete_cookie(
        key=settings.cookie_name,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        path="/",
    )


async def get_current_user(
    jwt_token: Annotated[str | None, Depends(oauth2_scheme)],
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> models.User:
    """Resolve the JWT into a User, raising 401 when invalid.

    Sources, in order: ``Authorization: Bearer`` header, then the
    ``access_token`` httpOnly cookie (set by the login endpoint).
    """
    if not jwt_token:
        jwt_token = request.cookies.get(settings.cookie_name)

    user_id = verify_access_token(jwt_token) if jwt_token else None
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(models.User).where(models.User.id == user_id_int))
    current_user_exists = result.scalars().first()

    if not current_user_exists:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return current_user_exists


CurrentUser = Annotated[models.User, Depends(get_current_user)]