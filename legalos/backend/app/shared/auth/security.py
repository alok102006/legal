"""Password hashing and JWT helpers."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt

from app.config import settings
from app.shared.exceptions import UnauthorizedException

_ALGO = "HS256"
MIN_PASSWORD_LENGTH = 8


def hash_password(password: str) -> str:
    # bcrypt only uses the first 72 bytes
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: Optional[str]) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: uuid.UUID, organization_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "org": str(organization_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGO)


def decode_access_token(token: str) -> tuple[uuid.UUID, uuid.UUID]:
    try:
        data = jwt.decode(token, settings.jwt_secret, algorithms=[_ALGO])
        return uuid.UUID(data["sub"]), uuid.UUID(data["org"])
    except jwt.ExpiredSignatureError:
        raise UnauthorizedException("Your session has expired. Please sign in again.")
    except (jwt.PyJWTError, KeyError, ValueError):
        raise UnauthorizedException("Invalid authentication token.")
