from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Call, TranscriptTurn
from app.pipeline import run_pipeline
from app.schemas import (
    CreateCallIn,
    EndCallIn,
    ToolAvailabilityIn,
    ToolBookIn,
    ToolCallbackIn,
    ToolCancelIn,
    ToolClinicIn,
    ToolFindIn,
    ToolRescheduleIn,
    TurnIn,
)
from app.security import require_service
from app.services import booking
from app.services.booking import get_clinic

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/internal", tags=["internal"], dependencies=[Depends(require_service)])


def _call_id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "bad_id"}) from exc


@router.post("/calls")
async def create_call(payload: CreateCallIn, session: AsyncSession = Depends(get_session)):
    clinic = await get_clinic(session)
    call = Call(clinic_id=clinic.id, livekit_room=payload.room, channel=payload.channel, status="in_progress")
    session.add(call)
    await session.commit()
    return {"call_id": str(call.id)}


@router.post("/calls/{call_id}/turns")
async def add_turn(call_id: str, payload: TurnIn, session: AsyncSession = Depends(get_session)):
    call = await session.get(Call, _call_id(call_id))
    if call is None:
        raise HTTPException(status_code=404, detail={"code": "call_not_found"})
    stmt = pg_insert(TranscriptTurn).values(
        call_id=call.id,
        seq=payload.seq,
        speaker=payload.speaker,
        text_bn=payload.text.strip(),
        started_ms=payload.started_ms,
        ended_ms=max(payload.ended_ms, payload.started_ms),
        stt_confidence=payload.stt_confidence,
        language_mix=payload.language_mix,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_turns_call_seq",
        set_={
            "speaker": stmt.excluded.speaker,
            "text_bn": stmt.excluded.text_bn,
            "started_ms": stmt.excluded.started_ms,
            "ended_ms": stmt.excluded.ended_ms,
            "stt_confidence": stmt.excluded.stt_confidence,
            "language_mix": stmt.excluded.language_mix,
        },
    )
    await session.execute(stmt)
    await session.commit()
    return {"ok": True}


@router.post("/calls/{call_id}/end")
async def end_call(
    call_id: str,
    payload: EndCallIn,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    call = await session.get(Call, _call_id(call_id))
    if call is None:
        raise HTTPException(status_code=404, detail={"code": "call_not_found"})
    now = datetime.now(UTC)
    call.ended_at = call.ended_at or now
    call.duration_s = max(0, int((call.ended_at - call.started_at).total_seconds()))
    if payload.incomplete:
        call.incomplete = True
        if call.status == "in_progress":
            call.status = "incomplete"
    if payload.reason and not call.error_reason:
        call.error_reason = payload.reason[:500]
    await session.commit()
    background.add_task(run_pipeline, call.id)
    logger.info("call %s ended incomplete=%s", call.id, call.incomplete)
    return {"ok": True, "status": call.status}


@router.post("/tools/clinic-info")
async def tool_clinic(payload: ToolClinicIn, session: AsyncSession = Depends(get_session)):
    return await booking.clinic_info(session, payload.topic)


@router.post("/tools/availability")
async def tool_availability(payload: ToolAvailabilityIn, session: AsyncSession = Depends(get_session)):
    return await booking.check_availability(session, payload)


@router.post("/tools/book")
async def tool_book(payload: ToolBookIn, session: AsyncSession = Depends(get_session)):
    return await booking.book_appointment(session, payload)


@router.post("/tools/find")
async def tool_find(payload: ToolFindIn, session: AsyncSession = Depends(get_session)):
    return await booking.find_appointments(session, payload.phone)


@router.post("/tools/reschedule")
async def tool_reschedule(payload: ToolRescheduleIn, session: AsyncSession = Depends(get_session)):
    return await booking.reschedule_appointment(session, payload)


@router.post("/tools/cancel")
async def tool_cancel(payload: ToolCancelIn, session: AsyncSession = Depends(get_session)):
    return await booking.cancel_appointment(session, payload)


@router.post("/tools/callback")
async def tool_callback(payload: ToolCallbackIn, session: AsyncSession = Depends(get_session)):
    return await booking.request_callback(session, payload)
