from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.domain.outcomes import classify_call, merge_status
from app.domain.phone import PhoneError, normalize_bd_mobile
from app.domain.text import looks_mixed, title_name
from app.domain.when import DHAKA, format_slot_bn, format_slot_en, parse_when
from app.models import Appointment, Call, Callback, CallExtraction, Doctor, Patient, Service, TranscriptTurn
from app.pipeline.llm import draft_from_turns, summarise, translate_turns
from app.services.booking import _patient, opening_map

logger = logging.getLogger(__name__)
REVIEW_BELOW = 0.65


def _conf(score: float, seq: int) -> dict:
    return {"confidence": max(0.0, min(1.0, float(score or 0))), "source_turn_seq": seq or None}


async def _load(session: AsyncSession, call_id: uuid.UUID):
    call = await session.get(Call, call_id)
    if call is None:
        raise RuntimeError("call_not_found")
    turns = (
        await session.scalars(select(TranscriptTurn).where(TranscriptTurn.call_id == call_id).order_by(TranscriptTurn.seq))
    ).all()
    extraction = await session.get(CallExtraction, call_id)
    patient = await session.get(Patient, call.patient_id) if call.patient_id else None
    appointment = await session.scalar(
        select(Appointment)
        .where(Appointment.call_id == call_id)
        .order_by(Appointment.created_at.desc())
        .limit(1)
    )
    callbacks = (await session.scalars(select(Callback).where(Callback.call_id == call_id))).all()
    doctors = (await session.scalars(select(Doctor).where(Doctor.clinic_id == call.clinic_id))).all()
    services = (await session.scalars(select(Service).where(Service.clinic_id == call.clinic_id))).all()
    return call, list(turns), extraction, patient, appointment, list(callbacks), list(doctors), list(services)


async def node_load(state: dict) -> dict:
    async with SessionLocal() as session:
        call, turns, *_rest = await _load(session, uuid.UUID(state["call_id"]))
        if not turns and call.ended_at is None:
            logger.info("pipeline waiting, call %s has no turns yet", call.id)
    return {}


async def node_extract(state: dict) -> dict:
    call_id = uuid.UUID(state["call_id"])
    async with SessionLocal() as session:
        call, turns, extraction, *_rest, doctors, _services = await _load(session, call_id)
        if extraction and (extraction.raw_json or {}).get("llm"):
            return {}
        payload = [
            {"seq": turn.seq, "speaker": turn.speaker, "text": turn.text_bn}
            for turn in turns
        ]
        doctor_lines = "; ".join(f"{d.name_bn} / {d.name_en} ({d.specialty})" for d in doctors)
        draft = await draft_from_turns(payload, doctor_lines)
        if extraction is None:
            extraction = CallExtraction(call_id=call.id, raw_json={}, field_confidence={}, needs_review=True)
            session.add(extraction)
        raw = dict(extraction.raw_json or {})
        raw["llm"] = draft
        extraction.raw_json = raw
        call_ref = call.id
        await session.commit()
        logger.info("extracted call %s intent=%s", call_ref, draft.get("intent"))
    return {}


async def node_validate(state: dict) -> dict:
    call_id = uuid.UUID(state["call_id"])
    async with SessionLocal() as session:
        call, _turns, extraction, _patient_row, _appt, _cbs, doctors, services = await _load(session, call_id)
        draft = (extraction.raw_json or {}).get("llm") if extraction else None
        if extraction is None or not draft:
            return {}
        from app.models import Clinic, Holiday

        clinic = await session.get(Clinic, call.clinic_id)
        holidays = set((await session.scalars(select(Holiday.day).where(Holiday.clinic_id == call.clinic_id))).all())
        opening = opening_map(clinic.opening_hours if clinic else {})
        phone_e164 = ""
        phone_error = ""
        if draft.get("phone_raw"):
            try:
                phone_e164 = normalize_bd_mobile(draft["phone_raw"])
            except PhoneError as exc:
                phone_error = exc.code
        parsed = None
        when_text = " ".join(part for part in (draft.get("date_text"), draft.get("time_text")) if part)
        if when_text:
            parsed = parse_when(when_text, now=datetime.now(DHAKA), holidays=holidays, opening=opening)
        doctor = None
        wanted = (draft.get("requested_doctor") or "").lower()
        for item in doctors:
            if wanted and (wanted in item.name_en.lower() or wanted in item.name_bn or item.name_en.split()[-1].lower() in wanted):
                doctor = item
                break
        service_name = draft.get("service_name") or draft.get("reason_for_visit") or ""
        conf = {
            "name": _conf(draft.get("confidence_name"), draft.get("source_seq_name")),
            "phone": _conf(draft.get("confidence_phone"), draft.get("source_seq_phone")),
            "reason": _conf(draft.get("confidence_reason"), draft.get("source_seq_reason")),
            "datetime": _conf(draft.get("confidence_datetime"), draft.get("source_seq_datetime")),
            "doctor": _conf(draft.get("confidence_doctor"), draft.get("source_seq_doctor")),
        }
        needs_review = any(item["confidence"] < REVIEW_BELOW for item in conf.values() if item["confidence"] > 0)
        if phone_error or (draft.get("phone_raw") and not phone_e164):
            needs_review = True
        if parsed is not None and not parsed.ok:
            needs_review = True
        clean = {
            "intent": draft.get("intent") or extraction.intent,
            "full_name_bn": " ".join((draft.get("full_name_bn") or "").split()),
            "full_name_en": title_name(draft.get("full_name_en") or ""),
            "phone_e164": phone_e164,
            "phone_error": phone_error,
            "reason_for_visit": draft.get("reason_for_visit") or service_name,
            "preferred_date": parsed.day.isoformat() if parsed and parsed.ok and parsed.day else None,
            "preferred_time_window": parsed.window if parsed and parsed.ok else None,
            "doctor_id": str(doctor.id) if doctor else None,
            "needs_review": needs_review,
            "field_confidence": conf,
            "urgency": draft.get("urgency") or "none",
        }
        raw = dict(extraction.raw_json or {})
        raw["normalised"] = clean
        extraction.raw_json = raw
        extraction.field_confidence = conf
        extraction.needs_review = needs_review or extraction.needs_review
        if clean["intent"] and not extraction.intent:
            extraction.intent = clean["intent"]
        if clean["reason_for_visit"] and (not extraction.reason_for_visit or conf["reason"]["confidence"] >= 0.75):
            extraction.reason_for_visit = clean["reason_for_visit"]
        if clean["preferred_date"] and (extraction.preferred_date is None or conf["datetime"]["confidence"] >= 0.75):
            extraction.preferred_date = datetime.fromisoformat(clean["preferred_date"]).date()
        if clean["preferred_time_window"] and (not extraction.preferred_time_window or conf["datetime"]["confidence"] >= 0.75):
            extraction.preferred_time_window = clean["preferred_time_window"]
        if clean["doctor_id"] and (extraction.requested_doctor_id is None or conf["doctor"]["confidence"] >= 0.75):
            extraction.requested_doctor_id = uuid.UUID(clean["doctor_id"])
        await session.commit()
        _ = services
    return {}


async def node_upsert_patient(state: dict) -> dict:
    call_id = uuid.UUID(state["call_id"])
    async with SessionLocal() as session:
        call, _turns, extraction, patient, *_rest = await _load(session, call_id)
        clean = ((extraction.raw_json or {}).get("normalised") if extraction else None) or {}
        phone = clean.get("phone_e164") or (patient.phone_e164 if patient else "")
        name_bn = clean.get("full_name_bn") or ""
        name_en = clean.get("full_name_en") or ""
        if phone and (name_bn or name_en or patient is None):
            try:
                saved = await _patient(session, call.clinic_id, phone, name_bn, name_en)
            except Exception:
                logger.exception("patient upsert skipped")
                saved = patient
            if saved is not None and call.patient_id is None:
                call.patient_id = saved.id
            if saved is not None and name_bn and not saved.full_name_bn:
                saved.full_name_bn = name_bn
            if saved is not None and name_en and not saved.full_name_en:
                saved.full_name_en = name_en
            await session.commit()
    return {}


async def node_persist(state: dict) -> dict:
    # Validation already wrote the extraction row. This node is the explicit checkpoint.
    call_id = uuid.UUID(state["call_id"])
    async with SessionLocal() as session:
        extraction = await session.get(CallExtraction, call_id)
        if extraction is None:
            session.add(CallExtraction(call_id=call_id, raw_json={"source": "pipeline"}, field_confidence={}, needs_review=True))
            await session.commit()
    return {}


async def node_classify(state: dict) -> dict:
    call_id = uuid.UUID(state["call_id"])
    async with SessionLocal() as session:
        call, turns, extraction, patient, appointment, callbacks, *_rest = await _load(session, call_id)
        urgency = None
        if any(item.urgency == "urgent" for item in callbacks):
            urgency = "urgent"
        elif callbacks:
            urgency = "normal"
        clean = ((extraction.raw_json or {}).get("normalised") if extraction else None) or {}
        proposed = classify_call(
            appointment_status=appointment.status if appointment else None,
            callback_urgency=urgency,
            incomplete=call.incomplete,
            caller_turns=sum(1 for turn in turns if turn.speaker == "caller"),
            intent=(extraction.intent if extraction else None) or clean.get("intent"),
            has_phone=bool(patient or clean.get("phone_e164")),
            has_name=bool((patient and (patient.full_name_bn or patient.full_name_en)) or clean.get("full_name_bn")),
        )
        call.status = merge_status(call.status, proposed)
        await session.commit()
        logger.info("classified call %s as %s", call_id, call.status)
    return {}


def _fallback_summary(call: Call, patient: Patient | None, appointment: Appointment | None, doctor: Doctor | None) -> tuple[str, str]:
    name_bn = patient.full_name_bn if patient and patient.full_name_bn else "কলার"
    name_en = patient.full_name_en if patient and patient.full_name_en else "The caller"
    if appointment and call.status in {"booked", "rescheduled"}:
        who = doctor.name_bn if doctor else ""
        label = format_slot_bn(appointment.slot_start)
        label_en = format_slot_en(appointment.slot_start)
        verb = "বুক হয়েছে" if call.status == "booked" else "সরিয়ে রাখা হয়েছে"
        en_verb = "booked" if call.status == "booked" else "rescheduled"
        return (
            f"{name_bn}-এর অ্যাপয়েন্টমেন্ট {label} এ {who} এর কাছে {verb}।".replace("  ", " "),
            f"{name_en} was {en_verb} for {label_en}.",
        )
    if call.status == "cancelled":
        return (f"{name_bn} অ্যাপয়েন্টমেন্ট বাতিল করেছেন।", f"{name_en} cancelled an appointment.")
    if call.status == "follow_up_needed":
        return (f"{name_bn}-কে পরে ফোন করতে হবে।", f"{name_en} needs a callback.")
    if call.status == "incomplete":
        return ("কল শেষ হওয়ার আগেই কথা থেমে গেছে।", "The call ended before a request was completed.")
    return ("কলার ক্লিনিক সম্পর্কে জিজ্ঞেস করেছেন।", "The caller asked about the clinic.")


async def node_summarise(state: dict) -> dict:
    call_id = uuid.UUID(state["call_id"])
    async with SessionLocal() as session:
        call, turns, extraction, patient, appointment, *_rest, doctors, _services = await _load(session, call_id)
        doctor = next((item for item in doctors if appointment and item.id == appointment.doctor_id), None)
        transcript = "\n".join(f"{turn.speaker}: {turn.text_bn}" for turn in turns)
        facts = f"status={call.status}; patient={patient.full_name_bn if patient else ''}; reason={(extraction.reason_for_visit if extraction else '')}"
        if appointment:
            facts += f"; slot={format_slot_en(appointment.slot_start)}; doctor={doctor.name_en if doctor else ''}"
        summary_bn, summary_en = await summarise(transcript, facts)
        if not summary_bn or not summary_en:
            summary_bn, summary_en = _fallback_summary(call, patient, appointment, doctor)
        call.summary_bn = summary_bn
        call.summary_en = summary_en
        await session.commit()
    return {}


async def node_translate(state: dict) -> dict:
    call_id = uuid.UUID(state["call_id"])
    async with SessionLocal() as session:
        turns = (
            await session.scalars(select(TranscriptTurn).where(TranscriptTurn.call_id == call_id).order_by(TranscriptTurn.seq))
        ).all()
        missing = [turn for turn in turns if not turn.text_en]
        translated = await translate_turns([{"seq": turn.seq, "text": turn.text_bn} for turn in missing])
        for turn in missing:
            text_en = translated.get(turn.seq)
            if text_en:
                turn.text_en = text_en
            elif not looks_mixed(turn.text_bn) and all(ord(ch) < 128 or ch.isspace() for ch in turn.text_bn):
                turn.text_en = turn.text_bn
        await session.commit()
    return {}


async def node_done(state: dict) -> dict:
    call_id = uuid.UUID(state["call_id"])
    async with SessionLocal() as session:
        call = await session.get(Call, call_id)
        if call:
            call.pipeline_status = "done"
            if call.error_reason and call.error_reason.startswith("pipeline"):
                call.error_reason = None
            await session.commit()
    return {}
