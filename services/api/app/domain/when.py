from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.domain.phone import to_bangla_digits, to_english_digits

DHAKA = ZoneInfo("Asia/Dhaka")

WEEKDAY_BN: dict[str, int] = {
    "সোমবার": 0,
    "মঙ্গলবার": 1,
    "বুধবার": 2,
    "বৃহস্পতিবার": 3,
    "শুক্রবার": 4,
    "শনিবার": 5,
    "রবিবার": 6,
}
WEEKDAY_EN = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
WEEKDAY_LABEL_BN = ["সোমবার", "মঙ্গলবার", "বুধবার", "বৃহস্পতিবার", "শুক্রবার", "শনিবার", "রবিবার"]
WEEKDAY_LABEL_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

BN_HOUR: dict[str, int] = {
    "এক": 1,
    "দুই": 2,
    "তিন": 3,
    "চার": 4,
    "পাঁচ": 5,
    "পাচ": 5,
    "ছয়": 6,
    "ছয়": 6,
    "সাত": 7,
    "আট": 8,
    "নয়": 9,
    "নয়": 9,
    "দশ": 10,
    "এগারো": 11,
    "বারো": 12,
}

WINDOWS: dict[str, tuple[time, time]] = {
    "morning": (time(10, 0), time(12, 0)),
    "noon": (time(12, 0), time(15, 0)),
    "afternoon": (time(15, 0), time(17, 0)),
    "evening": (time(17, 0), time(20, 0)),
}

DEFAULT_OPENING: dict[str, tuple[time, time] | None] = {
    "saturday": (time(10, 0), time(20, 0)),
    "sunday": (time(10, 0), time(20, 0)),
    "monday": (time(10, 0), time(20, 0)),
    "tuesday": (time(10, 0), time(20, 0)),
    "wednesday": (time(10, 0), time(20, 0)),
    "thursday": (time(10, 0), time(20, 0)),
    "friday": None,
}

_SAY = {
    "past": "এই দিনটা পার হয়ে গেছে। আরেকটা দিন বলবেন?",
    "friday": "শুক্রবার আমাদের ক্লিনিক বন্ধ। শনিবার থেকে বৃহস্পতিবার খোলা, সকাল দশটা থেকে রাত আটটা।",
    "holiday": "ওই দিন ক্লিনিকে ছুটি। অন্য একটা দিন বলবেন?",
    "closed": "ওই দিন ক্লিনিক বন্ধ। অন্য একটা দিন বলবেন?",
    "outside_hours": "আমরা সকাল দশটা থেকে রাত আটটা খোলা। এই সময়ের ভেতরে একটা সময় বলবেন?",
    "unparsed": "দিনটা আরেকবার বলবেন? যেমন আগামী রবিবার সন্ধ্যা।",
}


@dataclass(frozen=True)
class WhenResult:
    ok: bool
    day: date | None = None
    window: str | None = None
    slot_start: datetime | None = None
    error: str | None = None
    say_bn: str | None = None


def _tokens(text: str) -> list[str]:
    cleaned = re.sub(r"[।,?!:;]+", " ", text)
    return [part for part in cleaned.split() if part]


def _next_weekday(today: date, weekday: int, *, include_today: bool) -> date:
    delta = (weekday - today.weekday()) % 7
    if delta == 0 and not include_today:
        delta = 7
    return today + timedelta(days=delta)


def _detect_day(text: str, today: date) -> date | None:
    lowered = text.lower()
    toks = _tokens(lowered)

    if any(tok in {"আজ", "আজকে", "today"} for tok in toks):
        return today
    if any(tok in {"আগামীকাল", "আগামীকালকে", "tomorrow"} or tok in {"কাল", "কালকে"} for tok in toks):
        return today + timedelta(days=1)
    if any(tok.startswith("পরশু") for tok in toks) or "day after tomorrow" in lowered:
        return today + timedelta(days=2)

    iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", lowered)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return None

    include_today = True
    if any(tok == "আগামী" for tok in toks) or re.search(r"\bnext\b", lowered):
        include_today = False
    if re.search(r"\bthis\b", lowered) or any(tok == "এই" for tok in toks):
        include_today = True

    for name, weekday in WEEKDAY_EN.items():
        if re.search(rf"\b{name}\b", lowered):
            return _next_weekday(today, weekday, include_today=include_today)
    for name, weekday in WEEKDAY_BN.items():
        if name in text:
            return _next_weekday(today, weekday, include_today=include_today)
    return None


def _detect_window(text: str) -> str | None:
    lowered = text.lower()
    if any(word in text for word in ("সকাল",)) or re.search(r"\bmorning\b", lowered):
        return "morning"
    if "দুপুর" in text or re.search(r"\bnoon\b", lowered):
        return "noon"
    if "বিকেল" in text or re.search(r"\bafternoon\b", lowered):
        return "afternoon"
    if "সন্ধ্যা" in text or re.search(r"\bevening\b", lowered):
        return "evening"
    return None


def _period_adds_twelve(text: str) -> bool:
    lowered = text.lower()
    if any(word in text for word in ("দুপুর", "বিকেল", "সন্ধ্যা", "রাত")):
        return True
    return bool(re.search(r"\b(pm|p\.m\.|afternoon|evening|night|noon)\b", lowered))


def _detect_clock(text: str) -> time | None:
    probe = to_english_digits(text)
    probe = re.sub(r"\d{4}-\d{2}-\d{2}", " ", probe)
    lowered = probe.lower()
    hour: int | None = None
    minute = 0

    match = re.search(
        r"(?<!\d)(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.|টা)?(?!\d)",
        lowered,
    )
    if match and int(match.group(1)) <= 23:
        hour = int(match.group(1))
        if match.group(2):
            minute = int(match.group(2))
        marker = match.group(3) or ""
        if marker in {"pm", "p.m."} and hour < 12:
            hour += 12
        elif marker in {"am", "a.m."} and hour == 12:
            hour = 0
        elif marker in {"pm", "p.m.", "টা", ""} and hour <= 12 and _period_adds_twelve(text) and hour < 12:
            hour += 12
        elif marker in {"", "টা"} and not _period_adds_twelve(text) and hour <= 8:
            hour += 12
    else:
        for word, value in sorted(BN_HOUR.items(), key=lambda item: -len(item[0])):
            if re.search(rf"{word}\s*টা", text):
                hour = value
                if _period_adds_twelve(text) and hour < 12:
                    hour += 12
                elif not _period_adds_twelve(text) and hour <= 8:
                    hour += 12
                break

    if hour is None:
        return None
    if "সাড়ে" in text or "সাড়ে" in text:
        minute = 30
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)


def opening_for(day: date, opening: dict[str, tuple[time, time] | None]) -> tuple[time, time] | None:
    names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    return opening.get(names[day.weekday()])


def iter_slots(day: date, opening: dict[str, tuple[time, time] | None], duration_min: int = 30):
    span = opening_for(day, opening)
    if span is None:
        return
    start_t, end_t = span
    cursor = datetime.combine(day, start_t, DHAKA)
    close = datetime.combine(day, end_t, DHAKA)
    step = timedelta(minutes=duration_min)
    while cursor + step <= close:
        yield cursor, cursor + step
        cursor += step


def slot_containing(moment: datetime, opening: dict[str, tuple[time, time] | None], duration_min: int = 30):
    local = moment.astimezone(DHAKA)
    for start, end in iter_slots(local.date(), opening, duration_min):
        if start <= local < end or abs((start - local).total_seconds()) < 60:
            return start, end
    return None


def window_of(moment: datetime) -> str:
    local = moment.astimezone(DHAKA).time()
    for name, (start, end) in WINDOWS.items():
        if start <= local < end:
            return name
    return "evening"


def format_slot_bn(moment: datetime) -> str:
    local = moment.astimezone(DHAKA)
    hour = local.hour
    display = hour if hour <= 12 else hour - 12
    if display == 0:
        display = 12
    minute = to_bangla_digits(f"{local.minute:02d}")
    hour_bn = to_bangla_digits(str(display))
    part = {"morning": "সকাল", "noon": "দুপুর", "afternoon": "বিকেল", "evening": "সন্ধ্যা"}[window_of(local)]
    return f"{WEEKDAY_LABEL_BN[local.weekday()]} {part} {hour_bn}:{minute}"


def format_slot_en(moment: datetime) -> str:
    local = moment.astimezone(DHAKA)
    hour = local.hour
    suffix = "am" if hour < 12 else "pm"
    display = hour % 12 or 12
    return f"{WEEKDAY_LABEL_EN[local.weekday()]} {display}:{local.minute:02d} {suffix}"


def parse_when(
    text: str,
    *,
    now: datetime,
    holidays: set[date] | None = None,
    opening: dict[str, tuple[time, time] | None] | None = None,
) -> WhenResult:
    holidays = holidays or set()
    opening = opening or DEFAULT_OPENING
    raw = " ".join((text or "").split())
    if not raw:
        return WhenResult(False, error="unparsed", say_bn=_SAY["unparsed"])

    local_now = now.astimezone(DHAKA)
    today = local_now.date()
    normalized = to_english_digits(raw)

    if "রাত" in raw and _detect_clock(raw) is None and _detect_window(raw) is None:
        return WhenResult(False, error="outside_hours", say_bn=_SAY["outside_hours"])

    day = _detect_day(normalized if normalized != raw else raw, today)
    if day is None:
        day = _detect_day(raw, today)
    if day is None:
        try:
            import dateparser

            parsed = dateparser.parse(
                normalized,
                settings={
                    "TIMEZONE": "Asia/Dhaka",
                    "RETURN_AS_TIMEZONE_AWARE": True,
                    "PREFER_DATES_FROM": "future",
                    "RELATIVE_BASE": local_now.replace(tzinfo=None),
                },
            )
            if parsed is not None and not re.fullmatch(r"[\d\s:+-]+", normalized):
                day = parsed.date()
        except Exception:
            day = None

    window = _detect_window(raw) or _detect_window(normalized)
    clock = _detect_clock(raw)
    if day is None:
        return WhenResult(False, error="unparsed", say_bn=_SAY["unparsed"])
    if day < today:
        return WhenResult(False, day=day, error="past", say_bn=_SAY["past"])

    if day.weekday() == 4 or opening_for(day, opening) is None:
        code = "friday" if day.weekday() == 4 else "closed"
        return WhenResult(False, day=day, error=code, say_bn=_SAY[code])
    if day in holidays:
        return WhenResult(False, day=day, error="holiday", say_bn=_SAY["holiday"])

    slot_start = None
    if clock is not None:
        moment = datetime.combine(day, clock, DHAKA)
        if moment <= local_now:
            return WhenResult(False, day=day, error="past", say_bn=_SAY["past"])
        found = slot_containing(moment, opening)
        if found is None:
            return WhenResult(False, day=day, window=window, error="outside_hours", say_bn=_SAY["outside_hours"])
        slot_start = found[0]
        window = window or window_of(slot_start)
    elif window is None:
        window = None

    return WhenResult(True, day=day, window=window, slot_start=slot_start)


def in_window(moment: datetime, window: str | None) -> bool:
    if window is None:
        return True
    span = WINDOWS.get(window)
    if span is None:
        return True
    local = moment.astimezone(DHAKA).timetz().replace(tzinfo=None)
    return span[0] <= local < span[1]
