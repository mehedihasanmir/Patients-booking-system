from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import Call
from app.pipeline import run_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])
settings = get_settings()


def _name(event, attr: str) -> str:
    current = event
    for part in attr.split("."):
        current = getattr(current, part, None)
        if current is None:
            return ""
    return str(current)


@router.post("/livekit")
async def livekit_webhook(request: Request, background: BackgroundTasks, session: AsyncSession = Depends(get_session)):
    if not settings.livekit_configured:
        raise HTTPException(status_code=400, detail={"code": "livekit_not_configured"})
    body = await request.body()
    auth_header = request.headers.get("authorization", "")
    try:
        from livekit import api

        receiver = api.WebhookReceiver(api.TokenVerifier(settings.livekit_api_key, settings.livekit_api_secret))
        event = receiver.receive(body.decode(), auth_header)
    except Exception as exc:
        logger.warning("rejected livekit webhook: %s", exc)
        raise HTTPException(status_code=401, detail={"code": "bad_webhook"}) from exc

    event_name = getattr(event, "event", "")
    room = _name(event, "room.name") or _name(event, "egress_info.room_name")
    call = await session.scalar(select(Call).where(Call.livekit_room == room)) if room else None
    if call is None:
        return {"ok": True, "ignored": True}

    if event_name in {"room_finished", "participant_left"} and call.ended_at is None and event_name == "room_finished":
        from datetime import UTC, datetime

        call.ended_at = datetime.now(UTC)
        call.duration_s = max(0, int((call.ended_at - call.started_at).total_seconds()))
        await session.commit()
        background.add_task(run_pipeline, call.id)
    elif event_name == "egress_ended":
        filepath = ""
        info = getattr(event, "egress_info", None)
        results = getattr(info, "file_results", None) or []
        if results:
            filepath = getattr(results[0], "filename", "") or ""
        if filepath and settings.r2_public_base_url:
            call.recording_url = settings.r2_public_base_url.rstrip("/") + "/" + filepath.lstrip("/")
            await session.commit()
    return {"ok": True}
