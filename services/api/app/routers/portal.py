from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal, get_session
from app.domain.phone import PhoneError, normalize_bd_mobile
from app.domain.text import title_name
from app.domain.when import DHAKA, format_slot_bn, format_slot_en
from app.models import (
    Appointment,
    AuditLog,
    Call,
    Callback,
    CallExtraction,
    Doctor,
    Patient,
    Service,
    User,
)
from app.pipeline import run_pipeline
from app.schemas import ExtractionPatch
from app.security import get_current_user

router = APIRouter(tags=["portal"])


def _like(value: str) -> str:
    return f"%{value.strip()}%"


async def _names(session: AsyncSession, clinic_id: uuid.UUID):
    doctors = {row.id: row for row in (await session.scalars(select(Doctor).where(Doctor.clinic_id == clinic_id))).all()}
    services = {row.id: row for row in (await session.scalars(select(Service).where(Service.clinic_id == clinic_id))).all()}
    return doctors, services


@router.get("/stats")
async def stats(session: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)):
    total = await session.scalar(select(func.count()).select_from(Call)) or 0
    finished = await session.scalar(select(func.count()).select_from(Call).where(Call.status != "in_progress")) or 0
    booked = (
        await session.scalar(select(func.count()).select_from(Call).where(Call.status.in_(("booked", "rescheduled"))))
        or 0
    )
    avg = await session.scalar(select(func.avg(Call.duration_s)).where(Call.duration_s.is_not(None)))
    open_callbacks = (
        await session.scalar(select(func.count()).select_from(Callback).where(Callback.status == "open")) or 0
    )
    breakdown_rows = (await session.execute(select(Call.status, func.count()).group_by(Call.status))).all()
    since = datetime.now(UTC) - timedelta(days=13)
    recent = (await session.scalars(select(Call).where(Call.started_at >= since))).all()
    counts: dict[str, int] = {}
    today = datetime.now(DHAKA).date()
    for offset in range(13, -1, -1):
        counts[(today - timedelta(days=offset)).isoformat()] = 0
    for call in recent:
        key = call.started_at.astimezone(DHAKA).date().isoformat()
        if key in counts:
            counts[key] += 1
    return {
        "total_calls": total,
        "booked_percent": round((booked / finished) * 100, 1) if finished else 0,
        "avg_duration_s": round(float(avg), 1) if avg is not None else 0,
        "open_callbacks": open_callbacks,
        "status_breakdown": {status: count for status, count in breakdown_rows},
        "calls_per_day": [{"date": day, "count": count} for day, count in counts.items()],
    }


@router.get("/calls")
async def list_calls(
    q: str = "",
    status: str = "",
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    filters = []
    if status:
        filters.append(Call.status == status)
    if date_from:
        filters.append(Call.started_at >= datetime.combine(date_from, time.min, DHAKA))
    if date_to:
        filters.append(Call.started_at < datetime.combine(date_to + timedelta(days=1), time.min, DHAKA))
    stmt = (
        select(Call, Patient, CallExtraction)
        .outerjoin(Patient, Call.patient_id == Patient.id)
        .outerjoin(CallExtraction, CallExtraction.call_id == Call.id)
    )
    if q.strip():
        like = _like(q)
        digits = "".join(ch for ch in q if ch.isdigit())
        phone_clause = Patient.phone_e164.ilike(f"%{digits[-10:]}%") if digits else None
        name_clause = or_(Patient.full_name_bn.ilike(like), Patient.full_name_en.ilike(like), Patient.phone_e164.ilike(like))
        filters.append(or_(name_clause, phone_clause) if phone_clause is not None else name_clause)
    count_stmt = select(func.count(Call.id)).select_from(Call).outerjoin(Patient, Call.patient_id == Patient.id)
    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)
    total = await session.scalar(count_stmt) or 0
    rows = (
        await session.execute(stmt.order_by(Call.started_at.desc()).offset((page - 1) * page_size).limit(page_size))
    ).all()
    items = []
    for call, patient, extraction in rows:
        clean = ((extraction.raw_json or {}).get("normalised") if extraction else {}) or {}
        items.append(
            {
                "id": str(call.id),
                "started_at": call.started_at.isoformat(),
                "ended_at": call.ended_at.isoformat() if call.ended_at else None,
                "duration_s": call.duration_s,
                "status": call.status,
                "caller_name": (patient.full_name_bn if patient else None) or clean.get("full_name_bn") or None,
                "caller_name_en": (patient.full_name_en if patient else None) or clean.get("full_name_en") or None,
                "phone": (patient.phone_e164 if patient else None) or clean.get("phone_e164") or None,
                "summary_bn": call.summary_bn,
                "needs_review": bool(extraction.needs_review) if extraction else False,
            }
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/calls/stream")
async def stream_calls(_: User = Depends(get_current_user)):
    async def events():
        previous = ""
        while True:
            async with SessionLocal() as session:
                rows = (
                    await session.execute(select(Call.id, Call.status).order_by(Call.started_at.desc()).limit(40))
                ).all()
            signature = "|".join(f"{row.id}:{row.status}" for row in rows)
            if signature != previous:
                yield f"data: {json.dumps({'signature': signature, 'count': len(rows)})}\n\n"
                previous = signature
            else:
                yield ": keepalive\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.get("/calls/{call_id}")
async def call_detail(call_id: uuid.UUID, session: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)):
    call = await session.get(Call, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    patient = await session.get(Patient, call.patient_id) if call.patient_id else None
    extraction = await session.get(CallExtraction, call.id)
    from app.models import TranscriptTurn

    turns = (
        await session.scalars(select(TranscriptTurn).where(TranscriptTurn.call_id == call.id).order_by(TranscriptTurn.seq))
    ).all()
    appointment = await session.scalar(
        select(Appointment).where(Appointment.call_id == call.id).order_by(Appointment.created_at.desc()).limit(1)
    )
    doctors, services = await _names(session, call.clinic_id)
    doctor = doctors.get(appointment.doctor_id) if appointment else None
    if extraction and extraction.requested_doctor_id and doctor is None:
        doctor = doctors.get(extraction.requested_doctor_id)
    service = services.get(appointment.service_id) if appointment and appointment.service_id else None
    clean = ((extraction.raw_json or {}).get("normalised") if extraction else {}) or {}
    return {
        "id": str(call.id),
        "status": call.status,
        "pipeline_status": call.pipeline_status,
        "channel": call.channel,
        "started_at": call.started_at.isoformat(),
        "ended_at": call.ended_at.isoformat() if call.ended_at else None,
        "duration_s": call.duration_s,
        "summary_bn": call.summary_bn,
        "summary_en": call.summary_en,
        "recording_url": call.recording_url,
        "error_reason": call.error_reason,
        "livekit_room": call.livekit_room,
        "patient": None
        if patient is None
        else {
            "id": str(patient.id),
            "full_name_bn": patient.full_name_bn,
            "full_name_en": patient.full_name_en,
            "phone_e164": patient.phone_e164,
        },
        "extraction": None
        if extraction is None
        else {
            "intent": extraction.intent,
            "reason_for_visit": extraction.reason_for_visit,
            "preferred_date": extraction.preferred_date.isoformat() if extraction.preferred_date else None,
            "preferred_time_window": extraction.preferred_time_window,
            "doctor_name_bn": doctor.name_bn if doctor else None,
            "doctor_name_en": doctor.name_en if doctor else None,
            "field_confidence": extraction.field_confidence or {},
            "needs_review": extraction.needs_review,
            "raw_json": extraction.raw_json or {},
            "full_name_bn": (patient.full_name_bn if patient else None) or clean.get("full_name_bn") or "",
            "full_name_en": (patient.full_name_en if patient else None) or clean.get("full_name_en") or "",
            "phone": (patient.phone_e164 if patient else None) or clean.get("phone_e164") or "",
        },
        "appointment": None
        if appointment is None
        else {
            "id": str(appointment.id),
            "status": appointment.status,
            "slot_start": appointment.slot_start.isoformat(),
            "slot_end": appointment.slot_end.isoformat(),
            "doctor_name_bn": doctors[appointment.doctor_id].name_bn if appointment.doctor_id in doctors else "",
            "doctor_name_en": doctors[appointment.doctor_id].name_en if appointment.doctor_id in doctors else "",
            "service_name_bn": service.name_bn if service else None,
            "service_name_en": service.name_en if service else None,
            "label_bn": format_slot_bn(appointment.slot_start),
            "label_en": format_slot_en(appointment.slot_start),
        },
        "turns": [
            {
                "id": str(turn.id),
                "seq": turn.seq,
                "speaker": turn.speaker,
                "text_bn": turn.text_bn,
                "text_en": turn.text_en,
                "started_ms": turn.started_ms,
                "ended_ms": turn.ended_ms,
                "stt_confidence": turn.stt_confidence,
                "language_mix": turn.language_mix,
            }
            for turn in turns
        ],
    }


@router.patch("/calls/{call_id}/extraction")
async def edit_extraction(
    call_id: uuid.UUID,
    payload: ExtractionPatch,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    call = await session.get(Call, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    extraction = await session.get(CallExtraction, call.id)
    if extraction is None:
        extraction = CallExtraction(call_id=call.id, raw_json={}, field_confidence={}, needs_review=False)
        session.add(extraction)
    patient = await session.get(Patient, call.patient_id) if call.patient_id else None
    before = {
        "reason_for_visit": extraction.reason_for_visit,
        "preferred_date": extraction.preferred_date.isoformat() if extraction.preferred_date else None,
        "preferred_time_window": extraction.preferred_time_window,
        "needs_review": extraction.needs_review,
        "name_bn": patient.full_name_bn if patient else None,
        "phone": patient.phone_e164 if patient else None,
    }
    if payload.reason_for_visit is not None:
        extraction.reason_for_visit = payload.reason_for_visit.strip()
    if payload.preferred_date is not None:
        extraction.preferred_date = payload.preferred_date
    if payload.preferred_time_window is not None:
        extraction.preferred_time_window = payload.preferred_time_window.strip()
    if payload.needs_review is not None:
        extraction.needs_review = payload.needs_review
    else:
        extraction.needs_review = False
    phone = patient.phone_e164 if patient else ""
    if payload.phone:
        try:
            phone = normalize_bd_mobile(payload.phone)
        except PhoneError as exc:
            raise HTTPException(status_code=422, detail={"code": exc.code, "say_bn": exc.say_bn}) from exc
    name_bn = payload.full_name_bn.strip() if payload.full_name_bn is not None else (patient.full_name_bn if patient else "")
    name_en = title_name(payload.full_name_en) if payload.full_name_en is not None else (patient.full_name_en if patient else "")
    if phone:
        existing = await session.scalar(select(Patient).where(Patient.clinic_id == call.clinic_id, Patient.phone_e164 == phone))
        if existing is None:
            existing = Patient(clinic_id=call.clinic_id, phone_e164=phone, full_name_bn=name_bn, full_name_en=name_en)
            session.add(existing)
            await session.flush()
        else:
            if name_bn:
                existing.full_name_bn = name_bn
            if name_en:
                existing.full_name_en = name_en
        call.patient_id = existing.id
    confidence = dict(extraction.field_confidence or {})
    for key in ("name", "phone", "reason", "datetime"):
        confidence[key] = {"confidence": 1, "source_turn_seq": None, "source": "staff"}
    extraction.field_confidence = confidence
    session.add(
        AuditLog(
            user_id=user.id,
            entity="call_extraction",
            entity_id=str(call.id),
            action="update",
            before=before,
            after={
                "reason_for_visit": extraction.reason_for_visit,
                "preferred_date": extraction.preferred_date.isoformat() if extraction.preferred_date else None,
                "preferred_time_window": extraction.preferred_time_window,
                "needs_review": extraction.needs_review,
                "name_bn": name_bn,
                "phone": phone,
            },
        )
    )
    await session.commit()
    return {"ok": True}


@router.post("/calls/{call_id}/reprocess")
async def reprocess(
    call_id: uuid.UUID,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail={"code": "admin_only"})
    call = await session.get(Call, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    call.pipeline_status = "pending"
    if call.ended_at is None:
        call.ended_at = datetime.now(UTC)
    await session.commit()
    background.add_task(run_pipeline, call.id)
    return {"ok": True}


@router.get("/appointments")
async def list_appointments(
    start: date,
    end: date,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    start_dt = datetime.combine(start, time.min, DHAKA)
    end_dt = datetime.combine(end + timedelta(days=1), time.min, DHAKA)
    rows = (
        await session.scalars(
            select(Appointment)
            .where(Appointment.slot_start >= start_dt, Appointment.slot_start < end_dt)
            .order_by(Appointment.slot_start)
        )
    ).all()
    if not rows:
        return {"items": []}
    clinic_id = rows[0].clinic_id
    doctors, services = await _names(session, clinic_id)
    patients = {
        row.id: row
        for row in (await session.scalars(select(Patient).where(Patient.id.in_([item.patient_id for item in rows])))).all()
    }
    return {
        "items": [
            {
                "id": str(item.id),
                "status": item.status,
                "slot_start": item.slot_start.isoformat(),
                "slot_end": item.slot_end.isoformat(),
                "label_bn": format_slot_bn(item.slot_start),
                "label_en": format_slot_en(item.slot_start),
                "doctor_name_bn": doctors[item.doctor_id].name_bn if item.doctor_id in doctors else "",
                "doctor_name_en": doctors[item.doctor_id].name_en if item.doctor_id in doctors else "",
                "service_name_en": services[item.service_id].name_en if item.service_id in services else None,
                "patient_name_bn": patients[item.patient_id].full_name_bn if item.patient_id in patients else "",
                "patient_name_en": patients[item.patient_id].full_name_en if item.patient_id in patients else "",
                "phone": patients[item.patient_id].phone_e164 if item.patient_id in patients else "",
                "patient_id": str(item.patient_id),
                "call_id": str(item.call_id) if item.call_id else None,
            }
            for item in rows
        ]
    }


@router.get("/patients")
async def list_patients(
    q: str = "",
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    stmt = select(Patient).order_by(Patient.created_at.desc()).limit(100)
    if q.strip():
        like = _like(q)
        digits = "".join(ch for ch in q if ch.isdigit())
        stmt = select(Patient).where(
            or_(Patient.full_name_bn.ilike(like), Patient.full_name_en.ilike(like), Patient.phone_e164.ilike(f"%{digits or q}%"))
        )
    rows = (await session.scalars(stmt)).all()
    return {
        "items": [
            {
                "id": str(row.id),
                "full_name_bn": row.full_name_bn,
                "full_name_en": row.full_name_en,
                "phone_e164": row.phone_e164,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    }


@router.get("/patients/{patient_id}")
async def patient_detail(patient_id: uuid.UUID, session: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)):
    patient = await session.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    calls = (await session.scalars(select(Call).where(Call.patient_id == patient.id).order_by(Call.started_at.desc()))).all()
    appointments = (
        await session.scalars(select(Appointment).where(Appointment.patient_id == patient.id).order_by(Appointment.slot_start.desc()))
    ).all()
    return {
        "id": str(patient.id),
        "full_name_bn": patient.full_name_bn,
        "full_name_en": patient.full_name_en,
        "phone_e164": patient.phone_e164,
        "calls": [
            {
                "id": str(call.id),
                "started_at": call.started_at.isoformat(),
                "status": call.status,
                "summary_bn": call.summary_bn,
                "duration_s": call.duration_s,
            }
            for call in calls
        ],
        "appointments": [
            {
                "id": str(item.id),
                "status": item.status,
                "label_bn": format_slot_bn(item.slot_start),
                "label_en": format_slot_en(item.slot_start),
                "slot_start": item.slot_start.isoformat(),
                "call_id": str(item.call_id) if item.call_id else None,
            }
            for item in appointments
        ],
    }


@router.get("/callbacks")
async def list_callbacks(
    status: str = "open",
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    stmt = select(Callback).order_by(Callback.created_at.desc()).limit(100)
    if status:
        stmt = stmt.where(Callback.status == status)
    rows = (await session.scalars(stmt)).all()
    patient_ids = [row.patient_id for row in rows if row.patient_id]
    patients = {}
    if patient_ids:
        patients = {row.id: row for row in (await session.scalars(select(Patient).where(Patient.id.in_(patient_ids)))).all()}
    return {
        "items": [
            {
                "id": str(row.id),
                "call_id": str(row.call_id) if row.call_id else None,
                "reason": row.reason,
                "urgency": row.urgency,
                "status": row.status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "patient_name_bn": patients[row.patient_id].full_name_bn if row.patient_id in patients else "",
                "phone": patients[row.patient_id].phone_e164 if row.patient_id in patients else "",
            }
            for row in rows
        ]
    }


@router.post("/callbacks/{callback_id}/done")
async def close_callback(
    callback_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    row = await session.get(Callback, callback_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    before = row.status
    row.status = "done"
    session.add(
        AuditLog(
            user_id=user.id,
            entity="callback",
            entity_id=str(row.id),
            action="done",
            before={"status": before},
            after={"status": "done"},
        )
    )
    await session.commit()
    return {"ok": True}
