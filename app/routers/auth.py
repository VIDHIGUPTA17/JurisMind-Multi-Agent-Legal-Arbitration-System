import uuid
import logging
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, RefreshTokenRequest
from app.core.security import (
    hash_password, verify_password, hash_email,
    encrypt, create_access_token, create_token_pair, decode_token,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    email_hash = hash_email(body.email)

    existing = await db.execute(select(User).where(User.email_hash == email_hash))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        email_encrypted=encrypt(body.email),
        email_hash=email_hash,
        hashed_password=hash_password(body.password),
        full_name_encrypted=encrypt(body.full_name),
        role=UserRole(body.role),
    )
    db.add(user)
    await db.flush()

    access_token, refresh_token = create_token_pair({"sub": user.id, "role": user.role.value})
    logger.info("user_registered", extra={"user_id": user.id, "role": user.role.value})
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        role=user.role.value,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    email_hash = hash_email(body.email)

    result = await db.execute(select(User).where(User.email_hash == email_hash))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token, refresh_token = create_token_pair({"sub": user.id, "role": user.role.value})
    logger.info("user_logged_in", extra={"user_id": user.id})
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        role=user.role.value,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a valid refresh token for a new access token + refresh token pair."""
    payload = decode_token(body.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=400, detail="Not a refresh token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    access_token, new_refresh_token = create_token_pair({"sub": user.id, "role": user.role.value})
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user_id=user.id,
        role=user.role.value,
    )
