import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import jwt

from app.config import get_settings

settings = get_settings()


def create_access_token(
    user_id: uuid.UUID,
    org_id: Optional[uuid.UUID] = None,
    org_role: Optional[str] = None,
    is_platform_admin: bool = False,
    expires_delta: Optional[timedelta] = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": now,
        "exp": expire,
        "type": "access",
        "is_platform_admin": is_platform_admin,
    }
    if org_id:
        payload["org_id"] = str(org_id)
    if org_role:
        payload["org_role"] = org_role

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(
    user_id: uuid.UUID,
    org_id: Optional[uuid.UUID] = None,
    expires_delta: Optional[timedelta] = None,
) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))
    jti = str(uuid.uuid4())

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "jti": jti,
        "iat": now,
        "exp": expire,
        "type": "refresh",
    }
    if org_id:
        payload["org_id"] = str(org_id)

    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, jti


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["exp", "sub", "type"]},
    )
