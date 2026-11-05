from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.phone import PhoneError, grouped_bangla, normalize_bd_mobile, phone_confirmation, to_bangla_digits
from app.domain.text import title_name
from app.domain.when import (
    DHAKA,
    format_slot_bn,
    format_slot_en,
    in_window,
    iter_slots,
    parse_when,
    slot_containing,
    window_of,
)
from app.models import Appointment, Call, Callback, CallExtraction, Clinic, Doctor, Holiday, Patient, Service

ACTIVE = ("booked", "rescheduled")
LOW_CONFIDENCE = 0.65


def tool_ok(**payload):
    return {"ok": True, **payload}


def tool_err(code: str, say_bn: str, **payload):
    return {"ok": False, "code": code, "say_bn": say_bn, **payload}


def bdt(amount: int) -> str:
    return to_bangla_digits(f"{amount:,}")


def _uuid_or_none(value: str) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def opening_map(raw: dict) -> dict[str, tuple[time, time] | None]:
    parsed: dict[str, tuple[time, time] | None] = {}
    for key, value in (raw or {}).items():
        if not value:
            parsed[key.lower()] = None
            continue
        start, end = value
        sh, sm = str(start).split(":")
        eh, em = str(end).split(":")
        parsed[key.lower()] = (time(int(sh), int(sm)), time(int(eh), int(em)))
    return parsed


def _slot_key(doctor_id: uuid.UUID, start: datetime) -> tuple[uuid.UUID, datetime]:
    return doctor_id, start.astimezone(UTC).replace(microsecond=0)


async def get_clinic(session: AsyncSession) -> Clinic:
    clinic = await session.scalar(select(Clinic).order_by(Clinic.name_en).limit(1))
    if clinic is None:
        raise HTTPException(status_code=500, detail={"code": "clinic_missing"})
    return clinic


async def _doctors(session: AsyncSession, clinic_id: uuid.UUID) -> list[Doctor]:
    rows = await session.scalars(select(Doctor).where(Doctor.clinic_id == clinic_id, Doctor.active.is_(True)))
    return list(rows)


async def _services(session: AsyncSession, clinic_id: uuid.UUID) -> list[Service]:
    rows = await session.scalars(select(Service).where(Service.clinic_id == clinic_id))
    return list(rows)


async def _holidays(session: AsyncSession, clinic_id: uuid.UUID) -> set[date]:
    rows = await session.scalars(select(Holiday.day).where(Holiday.clinic_id == clinic_id))
    return set(rows)


def match_service(services: list[Service], text: str) -> Service | None:
    blob = (text or "").lower()
    if not blob.strip():
        return None
    hints = [
        ("root", "root canal"),
        ("রুট", "root canal"),
        ("scaling", "scaling"),
        ("cleaning", "scaling"),
        ("পরিষ্কার", "scaling"),
        ("filling", "filling"),
        ("ফিলিং", "filling"),
        ("extraction", "extraction"),
        ("তুলতে", "extraction"),
        ("brace", "braces"),
        ("ব্রেস", "braces"),
        ("follow", "follow-up"),
        ("ফলো", "follow-up"),
        ("check", "check-up"),
        ("চেক", "check-up"),
        ("toothache", "toothache"),
        ("ব্যথা", "toothache"),
    ]
    for needle, name in hints:
        if needle in blob:
            for service in services:
                if name in service.name_en.lower():
                    return service
    for service in services:
        if service.name_en.lower() in blob or service.name_bn in text:
            return service
    return None


def specialty_for(service: Service | None) -> str | None:
    if service is None:
        return None
    name = service.name_en.lower()
    if "brace" in name:
        return "Orthodontist"
    if "root" in name:
        return "Endodontist"
    return "General dentist"


def match_doctor(doctors: list[Doctor], text: str, doctor_id: str = "") -> Doctor | None:
    wanted = _uuid_or_none(doctor_id)
    if wanted:
        for doctor in doctors:
            if doctor.id == wanted:
                return doctor
    blob = (text or "").strip().lower()
    if not blob:
        return None
    for doctor in doctors:
        if blob in doctor.name_en.lower() or doctor.name_en.lower() in blob or blob in doctor.name_bn:
            return doctor
        last = doctor.name_en.split()[-1].lower()
        if last and last in blob:
            return doctor
    if any(word in blob for word in ("ortho", "braces", "ব্রেস")):
        return next((d for d in doctors if d.specialty == "Orthodontist"), None)
    if any(word in blob for word in ("endo", "root", "রুট")):
        return next((d for d in doctors if d.specialty == "Endodontist"), None)
    return None


def _rank_doctors(doctors: list[Doctor], preferred: Doctor | None, service: Service | None) -> list[Doctor]:
    if preferred is not None:
        return [preferred]
    specialty = specialty_for(service)
    return sorted(doctors, key=lambda doctor: (doctor.specialty != specialty, doctor.specialty != "General dentist", doctor.name_en))


async def _busy(
    session: AsyncSession,
    clinic_id: uuid.UUID,
    start: datetime,
    end: datetime,
    ignore_id: uuid.UUID | None = None,
) -> set[tuple[uuid.UUID, datetime]]:
    rows = (
        await session.scalars(
            select(Appointment).where(
                Appointment.clinic_id == clinic_id,
                Appointment.status.in_(ACTIVE),
                Appointment.slot_start < end,
                Appointment.slot_end > start,
            )
        )
    ).all()
    busy: set[tuple[uuid.UUID, datetime]] = set()
    for row in rows:
        if ignore_id and row.id == ignore_id:
            continue
        busy.add(_slot_key(row.doctor_id, row.slot_start))
    return busy


def _slot_payload(start: datetime, end: datetime, doctor: Doctor, service: Service | None) -> dict:
    return {
        "slot_start_iso": start.isoformat(),
        "slot_end_iso": end.isoformat(),
        "doctor_id": str(doctor.id),
        "doctor_name_bn": doctor.name_bn,
        "doctor_name_en": doctor.name_en,
        "service_id": str(service.id) if service else "",
        "service_name_bn": service.name_bn if service else "",
        "label_bn": format_slot_bn(start),
        "label_en": format_slot_en(start),
    }


async def clinic_info(session: AsyncSession, topic: str) -> dict:
    clinic = await get_clinic(session)
    doctors = await _doctors(session, clinic.id)
    services = await _services(session, clinic.id)
    key = (topic or "about").strip().lower()
    if key in {"hour", "hours", "time", "সময়", "সময়"}:
        say = "আমরা শনিবার থেকে বৃহস্পতিবার সকাল দশটা থেকে রাত আটটা খোলা। শুক্রবার বন্ধ।"
    elif key in {"location", "address", "directions", "ঠিকানা"}:
        say = f"{clinic.address}। {clinic.directions_bn}"
    elif key in {"doctor", "doctors", "ডাক্তার"}:
        lines = [f"{d.name_bn}, {d.specialty}" for d in doctors]
        say = "আমাদের ডাক্তাররা: " + "। ".join(lines) + "।"
    elif key in {"fee", "fees", "price", "ফি"}:
        lines = [f"{s.name_en} {bdt(s.fee_min_bdt)} থেকে {bdt(s.fee_max_bdt)} টাকা" for s in services]
        say = "ফি আনুমানিক। " + "। ".join(lines) + "। ডাক্তার দেখে চূড়ান্ত বলবেন।"
    elif key in {"service", "services", "সেবা"}:
        say = "আমাদের সেবা: " + ", ".join(s.name_en for s in services) + "।"
    elif key in {"prep", "preparation", "প্রস্তুতি"}:
        notes = [f"{s.name_en}: {s.prep_notes}" for s in services if s.prep_notes]
        say = " ".join(notes) if notes else "বিশেষ প্রস্তুতি নেই। অ্যালার্জি থাকলে ডাক্তারকে বলবেন।"
    elif key in {"about", "clinic"}:
        say = f"{clinic.name_bn}, {clinic.address}। আমি অ্যাপয়েন্টমেন্ট, সময় বদল, বাতিল, আর ক্লিনিকের তথ্য দিতে পারি।"
    else:
        return tool_err(
            "unknown_topic",
            "এটা আমার কাছে এখন নেই। চাইলে একজন মানুষ আপনাকে পরে ফোন করতে পারে।",
            topic=key,
        )
    return tool_ok(topic=key, say_bn=say, clinic=clinic.name_en, phone=clinic.phone)


async def check_availability(session: AsyncSession, payload) -> dict:
    clinic = await get_clinic(session)
    doctors = await _doctors(session, clinic.id)
    services = await _services(session, clinic.id)
    holidays = await _holidays(session, clinic.id)
    opening = opening_map(clinic.opening_hours)
    service = match_service(services, payload.service)
    preferred = match_doctor(doctors, payload.doctor, payload.doctor_id)
    if payload.doctor.strip() and preferred is None and not payload.doctor_id:
        return tool_err("unknown_doctor", "এই নামে ডাক্তার খুঁজে পাইনি। ডা. ফারহানা, ডা. তানভীর, বা ডা. সাবরিনা — কার কাছে যাবেন?")
    parsed = parse_when(
        f"{payload.date_text} {payload.time_pref}".strip(),
        now=datetime.now(DHAKA),
        holidays=holidays,
        opening=opening,
    )
    if not parsed.ok or parsed.day is None:
        return tool_err(parsed.error or "unparsed", parsed.say_bn or "আরেকটা দিন বলবেন?")

    duration = service.duration_min if service else 30
    ranked = _rank_doctors(doctors, preferred, service)
    range_start = datetime.combine(parsed.day, time(0, 0), DHAKA)
    range_end = range_start + timedelta(days=14)
    busy = await _busy(session, clinic.id, range_start, range_end)
    now = datetime.now(DHAKA)
    found: list[dict] = []

    def consider(start: datetime, end: datetime) -> None:
        if len(found) >= 2 or start <= now:
            return
        if parsed.window and not in_window(start, parsed.window):
            return
        for doctor in ranked:
            if _slot_key(doctor.id, start) in busy:
                continue
            found.append(_slot_payload(start, end, doctor, service))
            return

    if parsed.slot_start is not None:
        snapped = slot_containing(parsed.slot_start, opening, duration)
        if snapped:
            consider(*snapped)

    for offset in range(14):
        if len(found) >= 2:
            break
        day = parsed.day + timedelta(days=offset)
        if day in holidays:
            continue
        for start, end in iter_slots(day, opening, duration):
            if parsed.slot_start and start == parsed.slot_start:
                continue
            consider(start, end)
            if len(found) >= 2:
                break

    if not found:
        return tool_err("no_slot", "আগামী কয়েক দিনে ফাঁকা সময় পাচ্ছি না। অন্য দিন বা অন্য ডাক্তার বলবেন?")
    if len(found) == 1:
        say = f"একটা সময় পাচ্ছি, {found[0]['label_bn']}, {found[0]['doctor_name_bn']}। এটা রাখব?"
    else:
        say = (
            f"দুটো সময় পাচ্ছি। এক, {found[0]['label_bn']}, {found[0]['doctor_name_bn']}। "
            f"দুই, {found[1]['label_bn']}, {found[1]['doctor_name_bn']}। কোনটা রাখব?"
        )
    return tool_ok(say_bn=say, slots=found, service_id=str(service.id) if service else "")


async def _patient(session: AsyncSession, clinic_id: uuid.UUID, phone: str, name_bn: str, name_en: str) -> Patient:
    try:
        e164 = normalize_bd_mobile(phone)
    except PhoneError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "say_bn": exc.say_bn}) from exc
    name_bn = " ".join(name_bn.split())
    name_en = title_name(name_en)
    existing = await session.scalar(select(Patient).where(Patient.clinic_id == clinic_id, Patient.phone_e164 == e164))
    if existing:
        if name_bn and not existing.full_name_bn:
            existing.full_name_bn = name_bn
        if name_en and not existing.full_name_en:
            existing.full_name_en = name_en
        return existing
    patient = Patient(clinic_id=clinic_id, full_name_bn=name_bn, full_name_en=name_en, phone_e164=e164)
    session.add(patient)
    await session.flush()
    return patient


async def _touch_extraction(session: AsyncSession, call_id: uuid.UUID, **fields) -> None:
    row = await session.get(CallExtraction, call_id)
    if row is None:
        row = CallExtraction(call_id=call_id, raw_json={"source": "tool"}, field_confidence={}, needs_review=False)
        session.add(row)
    for key, value in fields.items():
        if value not in (None, ""):
            setattr(row, key, value)


async def _call(session: AsyncSession, call_id: uuid.UUID) -> Call:
    call = await session.get(Call, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail={"code": "call_not_found"})
    return call


async def book_appointment(session: AsyncSession, payload) -> dict:
    clinic = await get_clinic(session)
    call = await _call(session, payload.call_id)
    if not payload.full_name_bn.strip() and not payload.full_name_en.strip():
        return tool_err("need_name", "বুক করার আগে আপনার নামটা আরেকবার বলবেন?")
    try:
        normalize_bd_mobile(payload.phone)
    except PhoneError as exc:
        return tool_err(exc.code, exc.say_bn)

    try:
        requested = datetime.fromisoformat(payload.slot_start_iso.replace("Z", "+00:00"))
    except ValueError:
        return tool_err("bad_slot", "সময়টা আরেকবার মিলিয়ে নিতে হবে। কোন স্লটটা রাখব?")
    if requested.tzinfo is None:
        requested = requested.replace(tzinfo=DHAKA)

    opening = opening_map(clinic.opening_hours)
    holidays = await _holidays(session, clinic.id)
    services = await _services(session, clinic.id)
    doctors = await _doctors(session, clinic.id)
    service = None
    if _uuid_or_none(payload.service_id):
        service = next((item for item in services if item.id == _uuid_or_none(payload.service_id)), None)
    service = service or match_service(services, f"{payload.service} {payload.reason}")
    doctor = match_doctor(doctors, payload.doctor, payload.doctor_id)
    if doctor is None:
        return tool_err("unknown_doctor", "কোন ডাক্তারের কাছে রাখব? ডা. ফারহানা, ডা. তানভীর, না ডা. সাবরিনা?")
    duration = service.duration_min if service else 30
    snapped = slot_containing(requested, opening, duration)
    if snapped is None:
        return tool_err("outside_hours", "এই সময়টা আমাদের খোলার সময়ের বাইরে। অন্য একটা স্লট বলবেন?")
    start, end = snapped
    if start.date() in holidays or start.date().weekday() == 4:
        return tool_err("closed", "ওই দিন ক্লিনিক বন্ধ। অন্য দিন বলবেন?")
    if start <= datetime.now(DHAKA):
        return tool_err("past", "এই সময়টা পার হয়ে গেছে। আরেকটা সময় বলবেন?")

    existing = (
        await session.scalars(
            select(Appointment).where(Appointment.call_id == call.id, Appointment.status.in_(ACTIVE))
        )
    ).all()
    for row in existing:
        if _slot_key(row.doctor_id, row.slot_start) == _slot_key(doctor.id, start):
            return tool_ok(
                say_bn=f"এই সময়টা আগেই রাখা আছে। {format_slot_bn(start)}, {doctor.name_bn}।",
                appointment_id=str(row.id),
                already=True,
            )
    if existing:
        return tool_err("already_booked", "এই কলে একটা অ্যাপয়েন্টমেন্ট আছে। বদলাতে চাইলে বলুন, আমি সরিয়ে দেব।")

    busy = await _busy(session, clinic.id, start, end)
    if _slot_key(doctor.id, start) in busy:
        return tool_err("slot_taken", "এই সময়টা এইমাত্র পূর্ণ হয়ে গেছে। আরেকটা সময় দেখি?")

    try:
        patient = await _patient(session, clinic.id, payload.phone, payload.full_name_bn, payload.full_name_en)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        return tool_err(detail.get("code", "invalid_phone"), detail.get("say_bn", "নম্বরটা আরেকবার বলবেন?"))

    appointment = Appointment(
        clinic_id=clinic.id,
        patient_id=patient.id,
        doctor_id=doctor.id,
        service_id=service.id if service else None,
        call_id=call.id,
        slot_start=start,
        slot_end=end,
        status="booked",
    )
    session.add(appointment)
    await _touch_extraction(
        session,
        call.id,
        intent="book",
        reason_for_visit=payload.reason or (service.name_en if service else ""),
        preferred_date=start.date(),
        preferred_time_window=window_of(start),
        requested_doctor_id=doctor.id,
    )
    call.patient_id = patient.id
    if call.status in {"in_progress", "enquiry", "incomplete", "failed"}:
        call.status = "booked"
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return tool_err("slot_taken", "এই সময়টা এইমাত্র পূর্ণ হয়ে গেছে। আরেকটা সময় দেখি?")

    say = (
        f"জি, বুক হয়ে গেছে। {format_slot_bn(start)}, {doctor.name_bn}।"
        f" নম্বর {grouped_bangla(patient.phone_e164)}।"
    )
    return tool_ok(
        say_bn=say,
        appointment_id=str(appointment.id),
        patient_id=str(patient.id),
        label_bn=format_slot_bn(start),
        label_en=format_slot_en(start),
        phone_readback=phone_confirmation(patient.phone_e164),
    )


async def find_appointments(session: AsyncSession, phone: str) -> dict:
    clinic = await get_clinic(session)
    try:
        e164 = normalize_bd_mobile(phone)
    except PhoneError as exc:
        return tool_err(exc.code, exc.say_bn)
    patient = await session.scalar(select(Patient).where(Patient.clinic_id == clinic.id, Patient.phone_e164 == e164))
    if patient is None:
        return tool_ok(say_bn="এই নম্বরে কোনো অ্যাপয়েন্টমেন্ট পাচ্ছি না।", appointments=[], phone_readback=phone_confirmation(e164))
    now = datetime.now(UTC) - timedelta(days=1)
    rows = (
        await session.scalars(
            select(Appointment)
            .where(
                Appointment.patient_id == patient.id,
                Appointment.status.in_(ACTIVE),
                Appointment.slot_start >= now,
            )
            .order_by(Appointment.slot_start)
        )
    ).all()
    doctors = {d.id: d for d in await _doctors(session, clinic.id)}
    items = []
    for row in rows:
        doctor = doctors.get(row.doctor_id)
        items.append(
            {
                "appointment_id": str(row.id),
                "label_bn": format_slot_bn(row.slot_start),
                "label_en": format_slot_en(row.slot_start),
                "doctor_name_bn": doctor.name_bn if doctor else "",
                "status": row.status,
                "slot_start_iso": row.slot_start.isoformat(),
            }
        )
    if not items:
        say = "এই নম্বরে সামনের কোনো অ্যাপয়েন্টমেন্ট নেই।"
    elif len(items) == 1:
        say = f"একটা অ্যাপয়েন্টমেন্ট আছে। {items[0]['label_bn']}, {items[0]['doctor_name_bn']}।"
    else:
        bits = [f"{item['label_bn']}, {item['doctor_name_bn']}" for item in items[:3]]
        say = "কয়েকটা অ্যাপয়েন্টমেন্ট আছে। " + "। ".join(bits) + "। কোনটা বদলাবেন?"
    return tool_ok(say_bn=say, appointments=items, phone_readback=phone_confirmation(e164), patient_name_bn=patient.full_name_bn)


async def reschedule_appointment(session: AsyncSession, payload) -> dict:
    clinic = await get_clinic(session)
    call = await _call(session, payload.call_id)
    appointment = await session.get(Appointment, payload.appointment_id)
    if appointment is None or appointment.clinic_id != clinic.id or appointment.status not in ACTIVE:
        return tool_err("not_found", "অ্যাপয়েন্টমেন্টটা খুঁজে পাইনি। নম্বরটা দিয়ে আরেকবার দেখি?")
    try:
        requested = datetime.fromisoformat(payload.slot_start_iso.replace("Z", "+00:00"))
    except ValueError:
        return tool_err("bad_slot", "নতুন সময়টা আরেকবার বলবেন?")
    if requested.tzinfo is None:
        requested = requested.replace(tzinfo=DHAKA)
    opening = opening_map(clinic.opening_hours)
    snapped = slot_containing(requested, opening)
    if snapped is None:
        return tool_err("outside_hours", "এই সময়টা খোলার সময়ের বাইরে।")
    start, end = snapped
    holidays = await _holidays(session, clinic.id)
    if start.date() in holidays or start <= datetime.now(DHAKA):
        return tool_err("closed", "ওই দিন বা সময়টা হয় না। অন্য একটা বলবেন?")
    doctor_id = _uuid_or_none(payload.doctor_id) or appointment.doctor_id
    busy = await _busy(session, clinic.id, start, end, ignore_id=appointment.id)
    if _slot_key(doctor_id, start) in busy:
        return tool_err("slot_taken", "নতুন সময়টা খালি নেই। আরেকটা দেখি?")
    appointment.slot_start = start
    appointment.slot_end = end
    appointment.doctor_id = doctor_id
    appointment.status = "rescheduled"
    await _touch_extraction(
        session,
        call.id,
        intent="reschedule",
        preferred_date=start.date(),
        preferred_time_window=window_of(start),
        requested_doctor_id=doctor_id,
    )
    call.patient_id = appointment.patient_id
    call.status = "rescheduled"
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return tool_err("slot_taken", "নতুন সময়টা এইমাত্র পূর্ণ হয়ে গেছে।")
    doctor = await session.get(Doctor, doctor_id)
    name = doctor.name_bn if doctor else ""
    return tool_ok(say_bn=f"জি, সময় বদলে দিয়েছি। এখন {format_slot_bn(start)}, {name}।", appointment_id=str(appointment.id))


async def cancel_appointment(session: AsyncSession, payload) -> dict:
    clinic = await get_clinic(session)
    call = await _call(session, payload.call_id)
    appointment = await session.get(Appointment, payload.appointment_id)
    if appointment is None or appointment.clinic_id != clinic.id or appointment.status not in ACTIVE:
        return tool_err("not_found", "বাতিল করার মতো অ্যাপয়েন্টমেন্ট খুঁজে পাইনি।")
    appointment.status = "cancelled"
    await _touch_extraction(session, call.id, intent="cancel")
    call.patient_id = appointment.patient_id
    call.status = "cancelled"
    await session.commit()
    return tool_ok(say_bn=f"জি, {format_slot_bn(appointment.slot_start)} এর অ্যাপয়েন্টমেন্ট বাতিল করা হলো।")


async def request_callback(session: AsyncSession, payload) -> dict:
    clinic = await get_clinic(session)
    call = await _call(session, payload.call_id)
    patient = None
    if payload.phone.strip():
        try:
            patient = await _patient(session, clinic.id, payload.phone, payload.full_name_bn, payload.full_name_en)
            call.patient_id = patient.id
        except HTTPException:
            patient = None
    callback = Callback(
        call_id=call.id,
        patient_id=patient.id if patient else None,
        reason=payload.reason.strip() or "callback",
        urgency=payload.urgency,
        status="open",
    )
    session.add(callback)
    await _touch_extraction(session, call.id, intent="callback", reason_for_visit=payload.reason.strip())
    if payload.urgency == "urgent" or call.status in {"in_progress", "enquiry", "incomplete", "failed"}:
        call.status = "follow_up_needed"
    await session.commit()
    if payload.urgency == "urgent":
        say = "জি, জরুরি কলব্যাক লিখে রাখলাম। এখন কাছের হাসপাতালের ইমার্জেন্সিতে যান।"
    else:
        say = "জি, কলব্যাক লিখে রাখলাম। একজন আপনাকে পরে ফোন করবে।"
    return tool_ok(say_bn=say, callback_id=str(callback.id))
