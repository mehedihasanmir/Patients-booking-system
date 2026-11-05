from __future__ import annotations

import hmac
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import User

bearer = HTTPBearer(auto_error=False)
settings = get_settings()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_access_token(*, user_id: str, email: str, role: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "email": email, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail={"code": "unauthorized"}) from exc


async def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    raw = creds.credentials if creds else request.cookies.get("bv_token")
    if not raw:
        raise HTTPException(status_code=401, detail={"code": "unauthorized"})
    payload = decode_token(raw)
    try:
        user_id = uuid.UUID(str(payload.get("sub")))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail={"code": "unauthorized"}) from exc
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail={"code": "unauthorized"})
    return user


def require_service(request: Request) -> None:
    provided = request.headers.get("x-service-token", "")
    expected = settings.service_token
    if not provided or not expected or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail={"code": "bad_service_token"})


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client is None:
        return "unknown"
    return request.client.host
