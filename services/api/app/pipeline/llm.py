from __future__ import annotations

import logging
import re

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.config import get_settings
from app.domain.phone import to_english_digits

logger = logging.getLogger(__name__)


class DraftModel(BaseModel):
    intent: str = "other"
    full_name_bn: str = ""
    full_name_en: str = ""
    phone_raw: str = ""
    reason_for_visit: str = ""
    date_text: str = ""
    time_text: str = ""
    requested_doctor: str = ""
    service_name: str = ""
    urgency: str = "none"
    confidence_name: float = 0
    confidence_phone: float = 0
    confidence_reason: float = 0
    confidence_datetime: float = 0
    confidence_doctor: float = 0
    source_seq_name: int = 0
    source_seq_phone: int = 0
    source_seq_reason: int = 0
    source_seq_datetime: int = 0
    source_seq_doctor: int = 0


class SummaryModel(BaseModel):
    summary_bn: str = ""
    summary_en: str = ""


class TurnEn(BaseModel):
    seq: int
    text_en: str


class TranslationModel(BaseModel):
    turns: list[TurnEn] = Field(default_factory=list)


def _client() -> AsyncOpenAI | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    return AsyncOpenAI(api_key=settings.openai_api_key)


def heuristic_draft(turns: list[dict]) -> dict:
    caller_turns = [turn for turn in turns if turn["speaker"] == "caller"]
    blob = "\n".join(turn["text"] for turn in caller_turns)
    latin = to_english_digits(blob)
    intent = "other"
    if any(word in blob for word in ("বাতিল",)) or "cancel" in latin.lower():
        intent = "cancel"
    elif any(word in blob for word in ("বদল", "পাল্ট")) or "reschedule" in latin.lower():
        intent = "reschedule"
    elif any(word in blob for word in ("অ্যাপয়েন্ট", "বুক")) or "appointment" in latin.lower():
        intent = "book"
    elif any(word in blob for word in ("কয়টা", "কটা", "ঠিকানা", "কোথায়", "ফি")):
        intent = "faq"
    phone = ""
    match = re.search(r"(?:\+?880)?0?1[3-9]\d{8}", latin)
    if match:
        phone = match.group(0)
        phone_seq = next((turn["seq"] for turn in caller_turns if match.group(0)[-6:] in to_english_digits(turn["text"])), 0)
    else:
        phone_seq = 0
    urgency = "urgent" if any(word in blob for word in ("রক্ত", "শ্বাস", "ফুলে", "জ্বর")) else "none"
    return DraftModel(
        intent=intent,
        phone_raw=phone,
        reason_for_visit="",
        urgency=urgency,
        confidence_name=0.2,
        confidence_phone=0.55 if phone else 0,
        confidence_reason=0.3,
        confidence_datetime=0.3,
        confidence_doctor=0.2,
        source_seq_phone=phone_seq,
    ).model_dump()


async def draft_from_turns(turns: list[dict], doctor_lines: str) -> dict:
    client = _client()
    if client is None:
        return heuristic_draft(turns)
    transcript = "\n".join(f"{turn['seq']}|{turn['speaker']}|{turn['text']}" for turn in turns)
    try:
        parsed = await client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=500,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract only facts spoken in this dental receptionist call. "
                        "Never invent a name, phone, date, or doctor. Use empty strings when unknown. "
                        "Doctors: " + doctor_lines + ". "
                        "intent is book, reschedule, cancel, faq, callback, or other. "
                        "urgency is urgent only for heavy bleeding, swelling with fever, trauma, or breathing trouble; else none or normal. "
                        "confidence values are 0 to 1. source_seq is the transcript seq, or 0."
                    ),
                },
                {"role": "user", "content": transcript or "(empty call)"},
            ],
            response_format=DraftModel,
        )
        draft = parsed.choices[0].message.parsed
        if draft is None:
            return heuristic_draft(turns)
        return draft.model_dump()
    except Exception:
        logger.exception("extraction model failed; using heuristic")
        return heuristic_draft(turns)


async def summarise(transcript: str, facts: str) -> tuple[str, str]:
    client = _client()
    if client is None:
        return "", ""
    try:
        parsed = await client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            temperature=0.2,
            max_tokens=280,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Write a two-sentence call summary for clinic staff. "
                        "summary_bn in colloquial Bangla, summary_en in plain English. "
                        "Only use the facts given. No diagnosis, no medicine names."
                    ),
                },
                {"role": "user", "content": f"Facts:\n{facts}\n\nTranscript:\n{transcript}"},
            ],
            response_format=SummaryModel,
        )
        result = parsed.choices[0].message.parsed
        if result is None:
            return "", ""
        return result.summary_bn.strip(), result.summary_en.strip()
    except Exception:
        logger.exception("summary model failed")
        return "", ""


async def translate_turns(turns: list[dict]) -> dict[int, str]:
    client = _client()
    if client is None or not turns:
        return {}
    packed = "\n".join(f"{turn['seq']}|{turn['text']}" for turn in turns)
    try:
        parsed = await client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=1200,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Translate each dental-call line to natural English. "
                        "Keep names, phone numbers, and clinical English words (scaling, root canal). "
                        "Return every seq."
                    ),
                },
                {"role": "user", "content": packed},
            ],
            response_format=TranslationModel,
        )
        result = parsed.choices[0].message.parsed
        if result is None:
            return {}
        return {item.seq: item.text_en for item in result.turns}
    except Exception:
        logger.exception("translation model failed")
        return {}
