from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import engine, get_session
from app.logging_conf import setup_logging
from app.routers import auth, internal, livekit_routes, portal, public, webhooks
from app.seed import seed

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    if settings.app_env == "production":
        if settings.jwt_secret.startswith("dev-") or settings.service_token.startswith("dev-"):
            raise RuntimeError("Set JWT_SECRET and SERVICE_TOKEN before production")
    if settings.seed_on_start:
        await seed()
    yield
    await engine.dispose()


app = FastAPI(title="ByteVoice Bangla API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router, prefix="/api")
app.include_router(livekit_routes.router, prefix="/api")
app.include_router(public.router, prefix="/api")
app.include_router(portal.router, prefix="/api")
app.include_router(internal.router)
app.include_router(webhooks.router)


@app.get("/health")
async def health(session: AsyncSession = Depends(get_session)):
    await session.execute(text("select 1"))
    return {"ok": True, "service": "bytevoice-api"}
