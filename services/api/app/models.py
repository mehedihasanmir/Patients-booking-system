from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CallStatus(str, enum.Enum):
    booked = "booked"
    rescheduled = "rescheduled"
    cancelled = "cancelled"
    enquiry = "enquiry"
    follow_up_needed = "follow_up_needed"
    incomplete = "incomplete"
    failed = "failed"
    in_progress = "in_progress"


class AppointmentStatus(str, enum.Enum):
    booked = "booked"
    rescheduled = "rescheduled"
    cancelled = "cancelled"
    completed = "completed"


class Speaker(str, enum.Enum):
    agent = "agent"
    caller = "caller"


class Urgency(str, enum.Enum):
    normal = "normal"
    urgent = "urgent"


class CallbackStatus(str, enum.Enum):
    open = "open"
    done = "done"


class UserRole(str, enum.Enum):
    admin = "admin"
    staff = "staff"


class PipelineStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Clinic(Base):
    __tablename__ = "clinics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name_bn: Mapped[str] = mapped_column(String(200))
    name_en: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(Text)
    directions_bn: Mapped[str] = mapped_column(Text, default="")
    directions_en: Mapped[str] = mapped_column(Text, default="")
    phone: Mapped[str] = mapped_column(String(32))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Dhaka")
    opening_hours: Mapped[dict] = mapped_column(JSONB)


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    clinic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clinics.id"))
    name_bn: Mapped[str] = mapped_column(String(200))
    name_en: Mapped[str] = mapped_column(String(200))
    specialty: Mapped[str] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Service(Base):
    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    clinic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clinics.id"))
    name_bn: Mapped[str] = mapped_column(String(200))
    name_en: Mapped[str] = mapped_column(String(200))
    duration_min: Mapped[int] = mapped_column(Integer, default=30)
    fee_min_bdt: Mapped[int] = mapped_column(Integer)
    fee_max_bdt: Mapped[int] = mapped_column(Integer)
    prep_notes: Mapped[str] = mapped_column(Text, default="")


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("clinic_id", "phone_e164", name="uq_patients_clinic_phone"),
        Index("ix_patients_phone", "phone_e164"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    clinic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clinics.id"))
    full_name_bn: Mapped[str] = mapped_column(String(200), default="")
    full_name_en: Mapped[str] = mapped_column(String(200), default="")
    phone_e164: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Call(Base):
    __tablename__ = "calls"
    __table_args__ = (
        Index("ix_calls_started_at", "started_at"),
        Index("ix_calls_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    clinic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clinics.id"))
    patient_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("patients.id"), nullable=True)
    livekit_room: Mapped[str] = mapped_column(String(120), unique=True)
    channel: Mapped[str] = mapped_column(String(16), default="web")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=CallStatus.in_progress.value)
    pipeline_status: Mapped[str] = mapped_column(String(16), default=PipelineStatus.pending.value)
    summary_bn: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    recording_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    incomplete: Mapped[bool] = mapped_column(Boolean, default=False)


class TranscriptTurn(Base):
    __tablename__ = "transcript_turns"
    __table_args__ = (UniqueConstraint("call_id", "seq", name="uq_turns_call_seq"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    call_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(16))
    text_bn: Mapped[str] = mapped_column(Text)
    text_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_ms: Mapped[int] = mapped_column(Integer, default=0)
    ended_ms: Mapped[int] = mapped_column(Integer, default=0)
    stt_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    language_mix: Mapped[bool] = mapped_column(Boolean, default=False)


class CallExtraction(Base):
    __tablename__ = "call_extractions"

    call_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), primary_key=True)
    intent: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason_for_visit: Mapped[str | None] = mapped_column(String(200), nullable=True)
    preferred_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    preferred_time_window: Mapped[str | None] = mapped_column(String(32), nullable=True)
    requested_doctor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("doctors.id"), nullable=True)
    raw_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    field_confidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (Index("ix_appointments_doctor_slot", "doctor_id", "slot_start"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    clinic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clinics.id"))
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"))
    doctor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("doctors.id"))
    service_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("services.id"), nullable=True)
    call_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("calls.id"), nullable=True)
    slot_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    slot_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default=AppointmentStatus.booked.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Callback(Base):
    __tablename__ = "callbacks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    call_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("calls.id"), nullable=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("patients.id"), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    urgency: Mapped[str] = mapped_column(String(16), default=Urgency.normal.value)
    status: Mapped[str] = mapped_column(String(16), default=CallbackStatus.open.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Holiday(Base):
    __tablename__ = "holidays"
    __table_args__ = (UniqueConstraint("clinic_id", "day", name="uq_holidays_clinic_day"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    clinic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clinics.id"))
    day: Mapped[date] = mapped_column(Date)
    name: Mapped[str] = mapped_column(String(200))


class DemoRequest(Base):
    __tablename__ = "demo_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(32), default="")
    clinic_name: Mapped[str] = mapped_column(String(200), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    entity: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    before: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
