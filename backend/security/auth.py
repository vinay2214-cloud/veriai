"""JWT auth helpers with public-route passthrough behavior."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from .retention import lazy_cleanup

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 60
REFRESH_TOKEN_DAYS = 7

PUBLIC_ROUTE_PREFIXES = (
    "/",
    "/health",
    "/api/demo",
    "/api/dashboard",
    "/api/audit",
    "/api/reports",
    "/api/report",
    "/api/review",
)


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "").strip()
    if not secret:
        raise RuntimeError("JWT_SECRET is not configured.")
    return secret


def _is_public_route(path: str) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in PUBLIC_ROUTE_PREFIXES)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _make_token(payload: Dict[str, Any], expires_delta: timedelta, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    body = dict(payload)
    body.update(
        {
            "type": token_type,
            "iat": int(now.timestamp()),
            "exp": int((now + expires_delta).timestamp()),
        }
    )
    return jwt.encode(body, _jwt_secret(), algorithm=JWT_ALGORITHM)


def make_access_token(payload: Dict[str, Any]) -> str:
    return _make_token(payload, timedelta(minutes=ACCESS_TOKEN_MINUTES), token_type="access")


def make_refresh_token(payload: Dict[str, Any]) -> str:
    return _make_token(payload, timedelta(days=REFRESH_TOKEN_DAYS), token_type="refresh")


def _unauthorized(detail: str = "Unauthorized") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[Dict[str, Any]]:
    """Return decoded JWT payload for private routes.

    Public routes: missing/invalid auth is ignored (returns None).
    Private routes: missing/invalid auth raises HTTP 401.
    """
    try:
        lazy_cleanup()
    except Exception as exc:
        # Retention must never block auth flow in request path.
        print(f"WARNING: lazy_cleanup failed: {exc}")

    is_public = _is_public_route(request.url.path)

    if credentials is None or not credentials.credentials:
        if is_public:
            return None
        raise _unauthorized("Missing bearer token")

    try:
        payload = jwt.decode(credentials.credentials, _jwt_secret(), algorithms=[JWT_ALGORITHM])
        token_type = payload.get("type")
        if token_type not in {"access", "refresh"}:
            raise JWTError("Invalid token type")
        return payload
    except Exception:
        if is_public:
            return None
        raise _unauthorized("Invalid or expired token")
