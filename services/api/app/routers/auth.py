from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.schemas import LoginIn, TokenOut, UserOut
from app.security import create_access_token, get_current_user, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _email(value: str) -> str:
    cleaned = value.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", cleaned):
        raise HTTPException(status_code=422, detail={"code": "invalid_email"})
    return cleaned


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn, session: AsyncSession = Depends(get_session)):
    email = _email(payload.email)
    user = await session.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail={"code": "invalid_login"})
    token = create_access_token(user_id=str(user.id), email=user.email, role=user.role)
    return TokenOut(access_token=token, user=UserOut(id=user.id, email=user.email, role=user.role))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut(id=user.id, email=user.email, role=user.role)
