from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import DemoRequest
from app.rate_limit import demo_limiter
from app.schemas import DemoRequestIn
from app.security import client_ip

router = APIRouter(tags=["public"])
settings = get_settings()


@router.post("/demo-requests")
async def create_demo_request(payload: DemoRequestIn, request: Request, session: AsyncSession = Depends(get_session)):
    if not demo_limiter.allow(f"demo:{client_ip(request)}", 5, 60):
        raise HTTPException(status_code=429, detail={"code": "rate_limited"})
    email = payload.email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status_code=422, detail={"code": "invalid_email"})
    row = DemoRequest(
        name=payload.name.strip(),
        email=email,
        phone=payload.phone.strip()[:32],
        clinic_name=payload.clinic_name.strip()[:200],
        message=payload.message.strip(),
    )
    session.add(row)
    await session.commit()
    return {"ok": True, "id": str(row.id)}
