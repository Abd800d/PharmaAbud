"""Password hashing and JWT token handling.

Passwords are hashed with PBKDF2-HMAC-SHA256 (stdlib, FIPS-friendly,
no native dependencies). Tokens are signed JWTs (PyJWT).
Secrets never reach the Flutter client.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from typing import Any, Dict, Optional

import jwt

from app.core.config import get_settings

PBKDF2_ITERATIONS = 390_000  # OWASP 2023+ recommendation for PBKDF2-HMAC-SHA256


# ---------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt_b64, digest_b64 = encoded.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def needs_rehash(encoded: str) -> bool:
    try:
        _, iterations, _, _ = encoded.split("$")
        return int(iterations) < PBKDF2_ITERATIONS
    except Exception:
        return True


# ---------------------------------------------------------------- tokens
def _now() -> int:
    return int(time.time())


def create_access_token(subject: str, extra: Optional[Dict[str, Any]] = None) -> str:
    settings = get_settings()
    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": _now(),
        "exp": _now() + settings.access_token_expire_minutes * 60,
        "type": "access",
        "jti": secrets.token_hex(8),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    settings = get_settings()
    payload = {
        "sub": subject,
        "iat": _now(),
        "exp": _now() + settings.refresh_token_expire_days * 24 * 3600,
        "type": "refresh",
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: str = "access") -> Dict[str, Any]:
    """Decode and validate a JWT. Raises jwt.PyJWTError on failure."""
    settings = get_settings()
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("wrong token type")
    return payload


def generate_password_reset_token() -> tuple[str, str]:
    """Return (raw_token, hashed_token). Only the hash is stored."""
    raw = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def hash_reset_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_api_key() -> str:
    return "aph_" + secrets.token_urlsafe(32)


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def secure_filename(filename: str) -> str:
    """Sanitize an uploaded filename; never trust user-supplied names."""
    name = os.path.basename(filename or "")
    keep = []
    for ch in name:
        if ch.isalnum() or ch in ("-", "_", "."):
            keep.append(ch)
        else:
            keep.append("_")
    cleaned = "".join(keep).strip("._") or "upload"
    return cleaned[:120]
