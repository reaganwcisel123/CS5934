"""Password hashing + JWT sessions (pure functions, no DB)."""

from __future__ import annotations

import os
import time

import bcrypt
import jwt

ALGORITHM = "HS256"
TOKEN_TTL_SECONDS = 60 * 60 * 24  # 24h


def _secret() -> str:
    # Set JWT_SECRET in the environment; the default is only for local dev.
    return os.environ.get("JWT_SECRET", "dev-insecure-secret-change-me")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except (ValueError, TypeError):
        return False


def create_token(subject: str, role: str = "viewer", ttl: int = TOKEN_TTL_SECONDS) -> str:
    now = int(time.time())
    return jwt.encode({"sub": subject, "role": role, "iat": now, "exp": now + ttl},
                      _secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Return the JWT claims, or raise jwt.PyJWTError if invalid/expired."""
    return jwt.decode(token, _secret(), algorithms=[ALGORITHM])
