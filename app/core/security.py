import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends

from app.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
http_bearer = HTTPBearer()

_fernet: Fernet | None = None


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(settings.encryption_key.encode())
    return _fernet


# ── Password hashing ──────────────────────────────────────────────────────────

def hash_password(plain: str):
    if len(plain.encode("utf-8")) > 72:
        raise ValueError("Password too long")
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Email helpers ─────────────────────────────────────────────────────────────

def hash_email(email: str) -> str:
    """Deterministic SHA-256 hash used for DB lookup (not for security)."""
    return hashlib.sha256(email.lower().strip().encode()).hexdigest()


# ── Fernet encryption ─────────────────────────────────────────────────────────

def encrypt(value: str) -> bytes:
    return get_fernet().encrypt(value.encode())


def decrypt(ciphertext: bytes) -> str:
    return get_fernet().decrypt(ciphertext).decode()


def encrypt_bytes(data: bytes) -> bytes:
    return get_fernet().encrypt(data)


def decrypt_bytes(ciphertext: bytes) -> bytes:
    return get_fernet().decrypt(ciphertext)


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(data: dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc), "type": "access"})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict[str, Any]) -> str:
    """Create a 7-day refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc), "type": "refresh"})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_token_pair(data: dict[str, Any]) -> tuple[str, str]:
    """Return (access_token, refresh_token) pair."""
    return create_access_token(data), create_refresh_token(data)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
        )


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> str:
    payload = decode_token(credentials.credentials)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    return user_id


async def get_current_user_payload(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> dict:
    return decode_token(credentials.credentials)
