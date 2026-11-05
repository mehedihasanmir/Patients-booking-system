from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.domain.when import DHAKA, format_slot_bn, parse_when

NOW = datetime(2026, 11, 5, 9, 0, tzinfo=ZoneInfo("Asia/Dhaka"))  # Thursday


def test_next_sunday_evening() -> None:
    result = parse_when("আগামী রবিবার সন্ধ্যায়", now=NOW)
    assert result.ok
    assert result.day == date(2026, 11, 8)
    assert result.window == "evening"


def test_english_next_sunday_evening() -> None:
    result = parse_when("next Sunday evening", now=NOW)
    assert result.ok
    assert result.day == date(2026, 11, 8)
    assert result.window == "evening"


def test_day_after_tomorrow_morning() -> None:
    result = parse_when("পরশু সকালে", now=NOW)
    assert result.ok
    assert result.day == date(2026, 11, 7)
    assert result.window == "morning"


def test_tomorrow_is_friday_closed() -> None:
    result = parse_when("আগামীকাল বিকেল ৪টা", now=NOW)
    assert not result.ok
    assert result.error == "friday"
    assert result.say_bn


def test_exact_evening_slot_snaps_to_grid() -> None:
    result = parse_when("আগামী রবিবার সন্ধ্যা ৫টা", now=NOW)
    assert result.ok
    assert result.slot_start is not None
    local = result.slot_start.astimezone(DHAKA)
    assert local.hour == 17 and local.minute == 0
    assert "সন্ধ্যা" in format_slot_bn(result.slot_start)


def test_past_date_rejected() -> None:
    result = parse_when("2026-11-01 সকাল ১০টা", now=NOW)
    assert not result.ok
    assert result.error == "past"


def test_holiday_rejected() -> None:
    result = parse_when("2026-12-16 সকাল ১১টা", now=NOW, holidays={date(2026, 12, 16)})
    assert not result.ok
    assert result.error == "holiday"


def test_night_without_clock_is_outside_hours() -> None:
    result = parse_when("আগামী শনিবার রাতে", now=NOW)
    assert not result.ok
    assert result.error == "outside_hours"


def test_seven_pm_bangla_is_inside_hours() -> None:
    result = parse_when("আগামী শনিবার রাত ৭টা", now=NOW)
    assert result.ok
    assert result.slot_start is not None
    assert result.slot_start.astimezone(DHAKA).hour == 19


def test_unparsed() -> None:
    result = parse_when("কখনো একদিন", now=NOW)
    assert not result.ok
    assert result.error == "unparsed"
