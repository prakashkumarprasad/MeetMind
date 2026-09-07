# Password hashing, JWT creation/decoding, and refresh-token-family helpers.

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

MAX_PASSWORD_BYTES = 72

def hash_password(plain_password):
    if len(plain_password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError("Password is too long (max 72 bytes).")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def create_access_token(user_id):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def create_refresh_token(user_id, token_family, jti=None):
    """Build a signed refresh token.

    ``jti`` identifies *this specific* refresh token within its family; it is
    recorded server-side (see models/refresh_token_family.py) so that rotation
    and reuse detection can tell the current token apart from an older,
    already-rotated copy. Returns the encoded token string.
    """
    if jti is None:
        jti = uuid.uuid4()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "family": token_family,
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "jti": str(jti),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_token(token):
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
