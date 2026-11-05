from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class LiveKitTokenOut(BaseModel):
    token: str
    url: str
    room: str
    call_id: uuid.UUID


class DemoRequestIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    email: str = Field(min_length=3, max_length=200)
    phone: str = ""
    clinic_name: str = ""
    message: str = Field(default="", max_length=2000)


class TurnIn(BaseModel):
    seq: int = Field(ge=1)
    speaker: Literal["agent", "caller"]
    text: str = Field(min_length=1, max_length=4000)
    started_ms: int = Field(ge=0)
    ended_ms: int = Field(ge=0)
    stt_confidence: float | None = None
    language_mix: bool = False


class EndCallIn(BaseModel):
    incomplete: bool = False
    reason: str | None = None


class CreateCallIn(BaseModel):
    room: str = Field(min_length=3, max_length=120)
    channel: Literal["web", "phone"] = "web"


class ToolClinicIn(BaseModel):
    topic: str = "about"


class ToolAvailabilityIn(BaseModel):
    date_text: str = ""
    time_pref: str = ""
    doctor: str = ""
    doctor_id: str = ""
    service: str = ""


class ToolBookIn(BaseModel):
    call_id: uuid.UUID
    full_name_bn: str = ""
    full_name_en: str = ""
    phone: str
    reason: str = ""
    slot_start_iso: str
    doctor: str = ""
    doctor_id: str = ""
    service: str = ""
    service_id: str = ""


class ToolFindIn(BaseModel):
    phone: str


class ToolRescheduleIn(BaseModel):
    call_id: uuid.UUID
    appointment_id: uuid.UUID
    slot_start_iso: str
    doctor_id: str = ""


class ToolCancelIn(BaseModel):
    call_id: uuid.UUID
    appointment_id: uuid.UUID
    reason: str = ""


class ToolCallbackIn(BaseModel):
    call_id: uuid.UUID
    phone: str = ""
    full_name_bn: str = ""
    full_name_en: str = ""
    reason: str
    urgency: Literal["normal", "urgent"] = "normal"


class ExtractionPatch(BaseModel):
    full_name_bn: str | None = None
    full_name_en: str | None = None
    phone: str | None = None
    reason_for_visit: str | None = None
    preferred_date: date | None = None
    preferred_time_window: str | None = None
    needs_review: bool | None = None


class CallListItem(BaseModel):
    id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None
    duration_s: int | None
    status: str
    caller_name: str | None
    caller_name_en: str | None
    phone: str | None
    summary_bn: str | None
    needs_review: bool = False


class PageOut(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
