from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import Call
from app.rate_limit import token_limiter
from app.security import client_ip
from app.services.booking import get_clinic

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/livekit", tags=["livekit"])
settings = get_settings()


def _token(room: str, identity: str, call_id: uuid.UUID) -> str:
    from livekit import api

    metadata = json.dumps({"call_id": str(call_id)})
    token = api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
    token.with_identity(identity).with_name("Caller").with_grants(
        api.VideoGrants(
            room_join=True,
            room=room,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
        )
    )
    if hasattr(api, "RoomConfiguration") and hasattr(api, "RoomAgentDispatch"):
        token.with_room_config(
            api.RoomConfiguration(
                agents=[api.RoomAgentDispatch(agent_name=settings.livekit_agent_name, metadata=metadata)]
            )
        )
    return token.to_jwt()


async def _start_egress(room: str, call_id: uuid.UUID) -> None:
    if not settings.r2_configured:
        return
    try:
        from livekit import api

        lk = api.LiveKitAPI(settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret)
        try:
            request = api.RoomCompositeEgressRequest(
                room_name=room,
                audio_only=True,
                file_outputs=[
                    api.EncodedFileOutput(
                        file_type=api.EncodedFileType.OGG,
                        filepath=f"calls/{call_id}.ogg",
                        s3=api.S3Upload(
                            access_key=settings.r2_access_key_id,
                            secret=settings.r2_secret_access_key,
                            bucket=settings.r2_bucket,
                            endpoint=settings.r2_endpoint,
                            force_path_style=True,
                            region="auto",
                        ),
                    )
                ],
            )
            await lk.egress.start_room_composite_egress(request)
            logger.info("egress started for %s", room)
        finally:
            await lk.aclose()
    except Exception:
        logger.exception("recording skipped for %s", room)


@router.post("/token")
async def issue_token(request: Request, session: AsyncSession = Depends(get_session)):
    ip = client_ip(request)
    if not token_limiter.allow(f"token:{ip}", settings.token_rate_limit, settings.token_rate_window_s):
        raise HTTPException(status_code=429, detail={"code": "rate_limited"})
    if not settings.livekit_configured:
        raise HTTPException(status_code=503, detail={"code": "livekit_not_configured"})

    clinic = await get_clinic(session)
    call_id = uuid.uuid4()
    room = f"call-{call_id}"
    call = Call(
        id=call_id,
        clinic_id=clinic.id,
        livekit_room=room,
        channel="web",
        status="in_progress",
        pipeline_status="pending",
    )
    session.add(call)
    await session.commit()
    identity = f"caller-{str(call_id)[:8]}"
    try:
        jwt = _token(room, identity, call_id)
    except Exception as exc:
        logger.exception("livekit token failed")
        raise HTTPException(status_code=503, detail={"code": "quota_or_livekit"}) from exc
    await _start_egress(room, call_id)
    logger.info("issued livekit room %s for call %s", room, call_id)
    return {"token": jwt, "url": settings.livekit_url, "room": room, "call_id": str(call_id)}
