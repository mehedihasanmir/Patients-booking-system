from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal
from app.domain.when import DHAKA
from app.models import (
    Appointment,
    Call,
    Callback,
    CallExtraction,
    Clinic,
    Doctor,
    Holiday,
    Patient,
    Service,
    TranscriptTurn,
    User,
)
from app.security import hash_password

CLINIC_ID = uuid.UUID("c1111111-1111-4111-8111-111111111111")
FARHANA = uuid.UUID("d1111111-1111-4111-8111-111111111111")
TANVIR = uuid.UUID("d2222222-2222-4222-8222-222222222222")
SABRINA = uuid.UUID("d3333333-3333-4333-8333-333333333333")

SERVICES = {
    "checkup": uuid.UUID("51111111-1111-4111-8111-111111111111"),
    "scaling": uuid.UUID("52222222-2222-4222-8222-222222222222"),
    "filling": uuid.UUID("53333333-3333-4333-8333-333333333333"),
    "root": uuid.UUID("54444444-4444-4444-8444-444444444444"),
    "extraction": uuid.UUID("55555555-5555-4555-8555-555555555555"),
    "braces": uuid.UUID("56666666-6666-4666-8666-666666666666"),
    "toothache": uuid.UUID("57777777-7777-4777-8777-777777777777"),
    "follow": uuid.UUID("58888888-8888-4888-8888-888888888888"),
}

OPENING = {
    "saturday": ["10:00", "20:00"],
    "sunday": ["10:00", "20:00"],
    "monday": ["10:00", "20:00"],
    "tuesday": ["10:00", "20:00"],
    "wednesday": ["10:00", "20:00"],
    "thursday": ["10:00", "20:00"],
    "friday": None,
}


def _at(day, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), DHAKA)


def _next_open(start, index: int):
    day = start + timedelta(days=1)
    seen = 0
    while True:
        if day.weekday() != 4:
            if seen == index:
                return day
            seen += 1
        day += timedelta(days=1)


async def _upsert(session, model, ident, **fields):
    row = await session.get(model, ident)
    if row is None:
        row = model(id=ident, **fields)
        session.add(row)
    else:
        for key, value in fields.items():
            setattr(row, key, value)
    return row


async def seed() -> None:
    settings = get_settings()
    async with SessionLocal() as session:
        await _upsert(
            session,
            Clinic,
            CLINIC_ID,
            name_bn="স্ট্রাটেজিবাইট ডেন্টাল কেয়ার",
            name_en="StrategyByte Dental Care",
            address="House 42, Road 7, Dhanmondi, Dhaka 1205",
            directions_bn="ধানমন্ডি লেক রোড ৮ এর পাশে, পপুলার ডায়াগনস্টিকের উল্টো দিকে। বাড়ি ৪২, রোড ৭।",
            directions_en="Beside Dhanmondi Lake Road 8, opposite Popular Diagnostics. House 42, Road 7.",
            phone="+8801711002233",
            timezone="Asia/Dhaka",
            opening_hours=OPENING,
        )
        await _upsert(session, Doctor, FARHANA, clinic_id=CLINIC_ID, name_bn="ডা. ফারহানা ইসলাম", name_en="Dr. Farhana Islam", specialty="Orthodontist", active=True)
        await _upsert(session, Doctor, TANVIR, clinic_id=CLINIC_ID, name_bn="ডা. তানভীর আহমেদ", name_en="Dr. Tanvir Ahmed", specialty="Endodontist", active=True)
        await _upsert(session, Doctor, SABRINA, clinic_id=CLINIC_ID, name_bn="ডা. সাবরিনা চৌধুরী", name_en="Dr. Sabrina Chowdhury", specialty="General dentist", active=True)
        catalog = [
            (SERVICES["checkup"], "চেক-আপ", "Check-up", 500, 800, "সাধারণ খাবার খেয়ে আসতে পারেন।"),
            (SERVICES["scaling"], "স্কেলিং", "Scaling", 1500, 2500, "স্কেলিংয়ের আগে ভারী খাবার না খেলেই হয়।"),
            (SERVICES["filling"], "ফিলিং", "Filling", 1200, 3000, "কোনো অ্যালার্জি থাকলে ডাক্তারকে জানাবেন।"),
            (SERVICES["root"], "রুট ক্যানাল", "Root canal", 8000, 15000, "আসার আগে হালকা কিছু খেয়ে আসুন। ব্যথার ওষুধ নিজে থেকে শুরু করবেন না।"),
            (SERVICES["extraction"], "দাঁত তোলা", "Extraction", 2000, 5000, "খালি পেটে আসবেন না। রক্ত পাতলা করার ওষুধ চললে আগে জানাবেন।"),
            (SERVICES["braces"], "ব্রেসেস পরামর্শ", "Braces consultation", 1000, 2000, "আগের এক্স-রে থাকলে সাথে আনবেন।"),
            (SERVICES["toothache"], "দাঁত ব্যথা", "Toothache consult", 700, 1500, "ব্যথা কখন বাড়ে, সেটা ডাক্তারকে বলবেন।"),
            (SERVICES["follow"], "ফলো-আপ", "Follow-up", 300, 500, "আগের প্রেসক্রিপশন থাকলে সাথে আনবেন।"),
        ]
        for ident, bn, en, low, high, prep in catalog:
            await _upsert(
                session,
                Service,
                ident,
                clinic_id=CLINIC_ID,
                name_bn=bn,
                name_en=en,
                duration_min=30,
                fee_min_bdt=low,
                fee_max_bdt=high,
                prep_notes=prep,
            )
        for day, name in (
            (datetime(2026, 12, 16).date(), "বিজয় দিবস"),
            (datetime(2027, 2, 21).date(), "শহীদ দিবস"),
            (datetime(2027, 3, 26).date(), "স্বাধীনতা দিবস"),
            (datetime(2027, 4, 14).date(), "পহেলা বৈশাখ"),
        ):
            existing = await session.scalar(select(Holiday).where(Holiday.clinic_id == CLINIC_ID, Holiday.day == day))
            if existing is None:
                session.add(Holiday(clinic_id=CLINIC_ID, day=day, name=name))

        for email, password, role in (
            (settings.seed_admin_email, settings.seed_admin_password, "admin"),
            (settings.seed_staff_email, settings.seed_staff_password, "staff"),
        ):
            found = await session.scalar(select(User).where(User.email == email.lower()))
            if found is None:
                session.add(User(email=email.lower(), password_hash=hash_password(password), role=role))

        call_count = await session.scalar(select(func.count()).select_from(Call))
        if not call_count:
            await _samples(session)
        await session.commit()


def _turn(speaker: str, bn: str, en: str, start: int, end: int, mix: bool = False, confidence: float | None = 0.9):
    return {
        "speaker": speaker,
        "text_bn": bn,
        "text_en": en,
        "started_ms": start,
        "ended_ms": end,
        "language_mix": mix,
        "stt_confidence": confidence if speaker == "caller" else None,
    }


async def _samples(session) -> None:
    today = datetime.now(DHAKA).date()
    days = [_next_open(today, index) for index in range(6)]
    people = [
        ("সাবরিনা আক্তার", "Sabrina Akter", "+8801711111111"),
        ("রাকিব হোসেন", "Rakib Hossain", "+8801812223333"),
        ("নাদিয়া রহমান", "Nadia Rahman", "+8801613334444"),
        ("ইমরান কবির", "Imran Kabir", "+8801914445555"),
        ("মেহজাবিন সুলতানা", "Mehzabin Sultana", "+8801515556666"),
        ("তানভীরুল ইসলাম", "Tanvirul Islam", "+8801717778888"),
        ("লুবনা চৌধুরী", "Lubna Chowdhury", "+8801818889999"),
        ("ফারজানা হক", "Farzana Haque", "+8801316667777"),
    ]
    patients = []
    for bn, en, phone in people:
        patient = Patient(clinic_id=CLINIC_ID, full_name_bn=bn, full_name_en=en, phone_e164=phone)
        session.add(patient)
        patients.append(patient)
    await session.flush()

    specs = [
        _booked_scaling(patients[0], days[1]),
        _booked_root(patients[1], days[2]),
        _rescheduled(patients[2], days[3]),
        _cancelled(patients[3], days[4]),
        _enquiry(patients[4]),
        _incomplete(),
        _urgent(patients[5]),
        _braces(patients[6], days[5]),
    ]
    pending = [_add_call(session, spec) for spec in specs]
    await session.flush()
    for call, spec in pending:
        _add_children(session, call, spec)

    session.add(
        Appointment(
            clinic_id=CLINIC_ID,
            patient_id=patients[7].id,
            doctor_id=SABRINA,
            service_id=SERVICES["checkup"],
            call_id=None,
            slot_start=_at(days[0], 10, 0),
            slot_end=_at(days[0], 10, 30),
            status="booked",
        )
    )


def _add_call(session, spec: dict) -> tuple[Call, dict]:
    started = datetime.now(UTC) - timedelta(days=spec["days_ago"], hours=spec.get("hour_shift", 2))
    last_ms = spec["turns"][-1]["ended_ms"] if spec["turns"] else 20000
    call = Call(
        id=uuid.uuid4(),
        clinic_id=CLINIC_ID,
        patient_id=spec.get("patient_id"),
        livekit_room=f"seed-{uuid.uuid4()}",
        channel="web",
        started_at=started,
        ended_at=started + timedelta(milliseconds=last_ms),
        duration_s=max(1, last_ms // 1000),
        status=spec["status"],
        pipeline_status="done",
        summary_bn=spec["summary_bn"],
        summary_en=spec["summary_en"],
        incomplete=spec.get("incomplete", False),
    )
    session.add(call)
    return call, spec


def _add_children(session, call: Call, spec: dict) -> None:
    for index, turn in enumerate(spec["turns"], start=1):
        session.add(TranscriptTurn(call_id=call.id, seq=index, **turn))
    if spec.get("extraction"):
        session.add(CallExtraction(call_id=call.id, **spec["extraction"]))
    if spec.get("appointment"):
        session.add(Appointment(clinic_id=CLINIC_ID, call_id=call.id, patient_id=spec["patient_id"], **spec["appointment"]))
    if spec.get("callback"):
        session.add(Callback(call_id=call.id, patient_id=spec.get("patient_id"), **spec["callback"]))


def _booked_scaling(patient, day) -> dict:
    return {
        "days_ago": 1,
        "status": "booked",
        "patient_id": patient.id,
        "summary_bn": "সাবরিনা আক্তার আগামী স্কেলিংয়ের জন্য ডা. সাবরিনা চৌধুরীর কাছে বুক করেছেন।",
        "summary_en": "Sabrina Akter booked a scaling visit with Dr. Sabrina Chowdhury.",
        "turns": [
            _turn("agent", "আসসালামু আলাইকুম, স্ট্রাটেজিবাইট ডেন্টাল কেয়ারে আপনাকে স্বাগতম। আমি নুসরাত, কীভাবে সাহায্য করতে পারি?", "Assalamu alaikum, welcome to StrategyByte Dental Care. I'm Nusrat, how can I help?", 0, 5000),
            _turn("caller", "জি, আমার নাম সাবরিনা আক্তার। একটা scaling এর appointment লাগবে।", "Yes, my name is Sabrina Akter. I need a scaling appointment.", 5600, 9800, True, 0.94),
            _turn("agent", "জি, সাবরিনা আক্তার। মোবাইল নম্বরটা বলবেন?", "Yes, Sabrina Akter. May I have your mobile number?", 10400, 13000),
            _turn("caller", "০১৭১১-১১১-১১১", "01711-111-111", 13600, 16000, False, 0.97),
            _turn("agent", "নম্বরটা ০১৭১১-১১১-১১১ — ঠিক আছে? কোন দিন সুবিধা?", "The number is 01711-111-111, is that right? Which day suits you?", 16600, 20000),
            _turn("caller", "জি ঠিক আছে। আগামী যেদিন সকালে ফাঁকা থাকে।", "Yes that's right. Whichever morning is free next.", 20600, 24000, False, 0.9),
            _turn("agent", "একটু দেখে নিচ্ছি। ডা. সাবরিনা চৌধুরী সকাল সাড়ে এগারোটায় আছেন। রাখব?", "Let me check. Dr. Sabrina Chowdhury is free at 11:30 in the morning. Shall I book it?", 24600, 30000),
            _turn("caller", "জি, রাখেন।", "Yes, please book it.", 30600, 32000, False, 0.96),
            _turn("agent", "জি, বুক হয়ে গেছে। আল্লাহ হাফেজ।", "Done, it's booked. Allah hafez.", 32600, 36000),
        ],
        "extraction": {
            "intent": "book",
            "reason_for_visit": "Scaling",
            "preferred_date": day,
            "preferred_time_window": "morning",
            "requested_doctor_id": SABRINA,
            "raw_json": {"source": "seed"},
            "field_confidence": {"name": {"confidence": 0.95, "source_turn_seq": 2}, "phone": {"confidence": 0.97, "source_turn_seq": 4}},
            "needs_review": False,
        },
        "appointment": {
            "doctor_id": SABRINA,
            "service_id": SERVICES["scaling"],
            "slot_start": _at(day, 11, 30),
            "slot_end": _at(day, 12, 0),
            "status": "booked",
        },
    }


def _booked_root(patient, day) -> dict:
    return {
        "days_ago": 2,
        "status": "booked",
        "patient_id": patient.id,
        "summary_bn": "রাকিব হোসেন রুট ক্যানালের জন্য ডা. তানভীর আহমেদের কাছে সন্ধ্যায় বুক করেছেন।",
        "summary_en": "Rakib Hossain booked an evening root canal visit with Dr. Tanvir Ahmed.",
        "turns": [
            _turn("agent", "আসসালামু আলাইকুম, স্ট্রাটেজিবাইট ডেন্টাল কেয়ারে আপনাকে স্বাগতম। আমি নুসরাত।", "Assalamu alaikum, welcome to StrategyByte Dental Care. I'm Nusrat.", 0, 4200),
            _turn("caller", "আমার নাম রাকিব হোসেন। নিচে একটা দাঁতে root canal লাগতে পারে।", "My name is Rakib Hossain. I may need a root canal on a lower tooth.", 5000, 9800, True, 0.91),
            _turn("agent", "জি। আমি রোগ ধরব না, ডাক্তার দেখবেন। নম্বরটা বলবেন?", "Of course. I won't diagnose it; the doctor will look. Your number?", 10400, 14000),
            _turn("caller", "০১৮১২-২২২-৩৩৩। আগামী সন্ধ্যায় পারলে ভালো হয়।", "01812-222-333. Evening would be better if possible.", 14600, 19000, True, 0.93),
            _turn("agent", "নম্বর ০১৮১২-২২২-৩৩৩। ডা. তানভীর আহমেদ সন্ধ্যা পাঁচটায় আছেন। বুক করব?", "Number 01812-222-333. Dr. Tanvir Ahmed is free at 5 in the evening. Shall I book?", 19600, 25000),
            _turn("caller", "জি।", "Yes.", 25600, 26800, False, 0.98),
            _turn("agent", "ঠিক আছে, রাখা হলো। আল্লাহ হাফেজ।", "Alright, it's booked. Allah hafez.", 27400, 31000),
        ],
        "extraction": {
            "intent": "book",
            "reason_for_visit": "Root canal",
            "preferred_date": day,
            "preferred_time_window": "evening",
            "requested_doctor_id": TANVIR,
            "raw_json": {"source": "seed"},
            "field_confidence": {"name": {"confidence": 0.93, "source_turn_seq": 2}, "phone": {"confidence": 0.93, "source_turn_seq": 4}},
            "needs_review": False,
        },
        "appointment": {
            "doctor_id": TANVIR,
            "service_id": SERVICES["root"],
            "slot_start": _at(day, 17, 0),
            "slot_end": _at(day, 17, 30),
            "status": "booked",
        },
    }


def _rescheduled(patient, day) -> dict:
    return {
        "days_ago": 3,
        "status": "rescheduled",
        "patient_id": patient.id,
        "summary_bn": "নাদিয়া রহমান চেক-আপের সময় বিকেল সাড়ে তিনটায় সরিয়েছেন।",
        "summary_en": "Nadia Rahman moved her check-up to 3:30 in the afternoon.",
        "turns": [
            _turn("agent", "আসসালামু আলাইকুম, নুসরাত বলছি। কীভাবে সাহায্য করব?", "Assalamu alaikum, this is Nusrat. How can I help?", 0, 3600),
            _turn("caller", "আমি নাদিয়া। নম্বর ০১৬১৩-৩৩৩-৪৪৪। অ্যাপয়েন্টমেন্টটা একদিন পরে দিন।", "I'm Nadia. Number 01613-333-444. Please move my appointment one day later.", 4200, 9800, True, 0.9),
            _turn("agent", "একটু দেখে নিচ্ছি। বিকেল সাড়ে তিনটায় ডা. সাবরিনা চৌধুরী খালি। সরাব?", "Let me look. Dr. Sabrina Chowdhury is free at 3:30 in the afternoon. Shall I move it?", 10400, 16000),
            _turn("caller", "অবশ্যই।", "Yes please.", 16600, 17800, False, 0.95),
            _turn("agent", "জি, সরিয়ে দিয়েছি। আল্লাহ হাফেজ।", "Done, I've moved it. Allah hafez.", 18400, 22000),
        ],
        "extraction": {
            "intent": "reschedule",
            "reason_for_visit": "Check-up",
            "preferred_date": day,
            "preferred_time_window": "afternoon",
            "requested_doctor_id": SABRINA,
            "raw_json": {"source": "seed"},
            "field_confidence": {"phone": {"confidence": 0.9, "source_turn_seq": 2}},
            "needs_review": False,
        },
        "appointment": {
            "doctor_id": SABRINA,
            "service_id": SERVICES["checkup"],
            "slot_start": _at(day, 15, 30),
            "slot_end": _at(day, 16, 0),
            "status": "rescheduled",
        },
    }


def _cancelled(patient, day) -> dict:
    return {
        "days_ago": 4,
        "status": "cancelled",
        "patient_id": patient.id,
        "summary_bn": "ইমরান কবির দাঁত তোলার অ্যাপয়েন্টমেন্ট বাতিল করেছেন।",
        "summary_en": "Imran Kabir cancelled his extraction appointment.",
        "turns": [
            _turn("agent", "আসসালামু আলাইকুম, নুসরাত বলছি।", "Assalamu alaikum, this is Nusrat.", 0, 2500),
            _turn("caller", "ইমরান কবির বলছি, ০১৯১৪-৪৪৪-৫৫৫। আগের extraction টা cancel করতে চাই।", "This is Imran Kabir, 01914-444-555. I want to cancel the extraction.", 3200, 8000, True, 0.92),
            _turn("agent", "জি, খুঁজে পেয়েছি। বাতিল করে দেব?", "Yes, I found it. Shall I cancel it?", 8600, 11000),
            _turn("caller", "জি।", "Yes.", 11600, 12400, False, 0.99),
            _turn("agent", "বাতিল করা হলো। আল্লাহ হাফেজ।", "It's cancelled. Allah hafez.", 13000, 16000),
        ],
        "extraction": {
            "intent": "cancel",
            "reason_for_visit": "Extraction",
            "preferred_date": day,
            "preferred_time_window": "morning",
            "requested_doctor_id": SABRINA,
            "raw_json": {"source": "seed"},
            "field_confidence": {"phone": {"confidence": 0.92, "source_turn_seq": 2}},
            "needs_review": False,
        },
        "appointment": {
            "doctor_id": SABRINA,
            "service_id": SERVICES["extraction"],
            "slot_start": _at(day, 12, 0),
            "slot_end": _at(day, 12, 30),
            "status": "cancelled",
        },
    }


def _enquiry(patient) -> dict:
    return {
        "days_ago": 1,
        "hour_shift": 6,
        "status": "enquiry",
        "patient_id": patient.id,
        "summary_bn": "মেহজাবিন সুলতানা ক্লিনিকের সময় আর ঠিকানা জানতে চেয়েছেন।",
        "summary_en": "Mehzabin Sultana asked about opening hours and the address.",
        "turns": [
            _turn("agent", "আসসালামু আলাইকুম, নুসরাত বলছি। কীভাবে সাহায্য করব?", "Assalamu alaikum, this is Nusrat. How can I help?", 0, 3600),
            _turn("caller", "আপনারা কয়টা পর্যন্ত খোলা? আর ঠিকানাটা কোথায়?", "Until what time are you open? And where is the address?", 4200, 8000, False, 0.94),
            _turn("agent", "শনিবার থেকে বৃহস্পতিবার সকাল দশটা থেকে রাত আটটা। শুক্রবার বন্ধ। আমরা ধানমন্ডি রোড ৭, বাড়ি ৪২।", "Saturday to Thursday, 10 in the morning until 8 at night. Closed Friday. House 42, Road 7, Dhanmondi.", 8600, 15000),
            _turn("caller", "আচ্ছা, ধন্যবাদ।", "Alright, thank you.", 15600, 17000, False, 0.96),
            _turn("agent", "আল্লাহ হাফেজ।", "Allah hafez.", 17600, 19000),
        ],
        "extraction": {
            "intent": "faq",
            "reason_for_visit": None,
            "preferred_date": None,
            "preferred_time_window": None,
            "requested_doctor_id": None,
            "raw_json": {"source": "seed"},
            "field_confidence": {"reason": {"confidence": 0.4, "source_turn_seq": 2}},
            "needs_review": False,
        },
    }


def _incomplete() -> dict:
    return {
        "days_ago": 2,
        "hour_shift": 8,
        "status": "incomplete",
        "incomplete": True,
        "summary_bn": "কলার নাম বলার পর আর কথা বলেননি।",
        "summary_en": "The caller went quiet after starting to give a name.",
        "turns": [
            _turn("agent", "আসসালামু আলাইকুম, স্ট্রাটেজিবাইট ডেন্টাল কেয়ারে আপনাকে স্বাগতম। আমি নুসরাত।", "Assalamu alaikum, welcome to StrategyByte Dental Care. I'm Nusrat.", 0, 4500),
            _turn("caller", "হ্যালো... আমার নাম...", "Hello... my name is...", 6000, 8000, False, 0.42),
            _turn("agent", "আপনি কি আমাকে শুনতে পাচ্ছেন?", "Can you hear me?", 15000, 17500),
            _turn("agent", "মনে হচ্ছে লাইনটা চুপ হয়ে আছে। আল্লাহ হাফেজ।", "The line seems to have gone quiet. Allah hafez.", 28000, 32000),
        ],
        "extraction": {
            "intent": "other",
            "reason_for_visit": None,
            "preferred_date": None,
            "preferred_time_window": None,
            "requested_doctor_id": None,
            "raw_json": {"source": "seed"},
            "field_confidence": {"name": {"confidence": 0.3, "source_turn_seq": 2}},
            "needs_review": True,
        },
    }


def _urgent(patient) -> dict:
    return {
        "days_ago": 0,
        "hour_shift": 1,
        "status": "follow_up_needed",
        "patient_id": patient.id,
        "summary_bn": "তানভীরুল ইসলামের মুখ ফুলেছে আর জ্বর, জরুরি কলব্যাক খোলা আছে। তাকে ইমার্জেন্সিতে যেতে বলা হয়েছে।",
        "summary_en": "Tanvirul Islam reported swelling with fever. An urgent callback is open, and he was told to go to emergency.",
        "turns": [
            _turn("agent", "আসসালামু আলাইকুম, নুসরাত বলছি।", "Assalamu alaikum, this is Nusrat.", 0, 2500),
            _turn("caller", "আমার নাম তানভীরুল। গাল অনেক ফুলে গেছে, জ্বরও আছে।", "My name is Tanvirul. My cheek is badly swollen and I have a fever.", 3200, 8000, False, 0.9),
            _turn("agent", "এটা জরুরি। এখনই কাছের হাসপাতালের ইমার্জেন্সিতে যান। আমি কলব্যাক লিখে রাখছি। নম্বরটা বলবেন?", "This is urgent. Please go to the nearest hospital emergency now. I'll log a callback. Your number?", 8600, 14000),
            _turn("caller", "০১৭১৭-৭৭৭-৮৮৮", "01717-777-888", 14600, 17000, False, 0.95),
            _turn("agent", "লিখে রাখলাম। আপনি এখন ইমার্জেন্সিতে যান। আল্লাহ হাফেজ।", "I've logged it. Please go to emergency now. Allah hafez.", 17600, 22000),
        ],
        "extraction": {
            "intent": "callback",
            "reason_for_visit": "Swelling with fever",
            "preferred_date": None,
            "preferred_time_window": None,
            "requested_doctor_id": None,
            "raw_json": {"source": "seed"},
            "field_confidence": {"phone": {"confidence": 0.95, "source_turn_seq": 4}, "reason": {"confidence": 0.88, "source_turn_seq": 2}},
            "needs_review": False,
        },
        "callback": {"reason": "গাল ফোলা ও জ্বর — ইমার্জেন্সিতে যেতে বলা হয়েছে", "urgency": "urgent", "status": "open"},
    }


def _braces(patient, day) -> dict:
    return {
        "days_ago": 5,
        "status": "booked",
        "patient_id": patient.id,
        "summary_bn": "লুবনা চৌধুরী ব্রেসেস পরামর্শের জন্য ডা. ফারহানা ইসলামের কাছে বুক করেছেন।",
        "summary_en": "Lubna Chowdhury booked a braces consultation with Dr. Farhana Islam.",
        "turns": [
            _turn("agent", "আসসালামু আলাইকুম, নুসরাত বলছি। কীভাবে সাহায্য করব?", "Assalamu alaikum, this is Nusrat. How can I help?", 0, 3600),
            _turn("caller", "লুবনা চৌধুরী বলছি। মেয়ের জন্য braces দেখাতে চাই।", "This is Lubna Chowdhury. I want a braces consultation for my daughter.", 4200, 9000, True, 0.93),
            _turn("agent", "জি। ডা. ফারহানা ইসলাম অর্থোডন্টিস্ট। নম্বরটা বলবেন?", "Yes. Dr. Farhana Islam is our orthodontist. Your number?", 9600, 13000),
            _turn("caller", "০১৮১৮-৮৮৮-৯৯৯। আগামী সন্ধ্যা হলে ভালো।", "01818-888-999. Evening would be good.", 13600, 18000, True, 0.91),
            _turn("agent", "সন্ধ্যা ছয়টায় ডা. ফারহানা খালি। রাখব?", "Dr. Farhana is free at 6 in the evening. Shall I book it?", 18600, 22000),
            _turn("caller", "জি রাখেন।", "Yes, book it.", 22600, 24000, False, 0.97),
            _turn("agent", "বুক হয়ে গেছে। আল্লাহ হাফেজ।", "It's booked. Allah hafez.", 24600, 28000),
        ],
        "extraction": {
            "intent": "book",
            "reason_for_visit": "Braces consultation",
            "preferred_date": day,
            "preferred_time_window": "evening",
            "requested_doctor_id": FARHANA,
            "raw_json": {"source": "seed"},
            "field_confidence": {"name": {"confidence": 0.93, "source_turn_seq": 2}, "phone": {"confidence": 0.91, "source_turn_seq": 4}},
            "needs_review": False,
        },
        "appointment": {
            "doctor_id": FARHANA,
            "service_id": SERVICES["braces"],
            "slot_start": _at(day, 18, 0),
            "slot_end": _at(day, 18, 30),
            "status": "booked",
        },
    }


if __name__ == "__main__":
    import asyncio

    asyncio.run(seed())
