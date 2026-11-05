from app.domain.outcomes import classify_call, merge_status
from app.domain.text import looks_mixed, title_name


def test_booking_wins() -> None:
    assert (
        classify_call(
            appointment_status="booked",
            callback_urgency=None,
            incomplete=False,
            caller_turns=4,
            intent="book",
            has_phone=True,
            has_name=True,
        )
        == "booked"
    )


def test_urgent_callback_outranks_booking() -> None:
    assert (
        classify_call(
            appointment_status="booked",
            callback_urgency="urgent",
            incomplete=False,
            caller_turns=4,
            intent="callback",
            has_phone=True,
            has_name=True,
        )
        == "follow_up_needed"
    )


def test_partial_booking_needs_follow_up() -> None:
    assert (
        classify_call(
            appointment_status=None,
            callback_urgency=None,
            incomplete=False,
            caller_turns=3,
            intent="book",
            has_phone=True,
            has_name=True,
        )
        == "follow_up_needed"
    )


def test_silence_is_incomplete() -> None:
    assert (
        classify_call(
            appointment_status=None,
            callback_urgency=None,
            incomplete=True,
            caller_turns=0,
            intent=None,
            has_phone=False,
            has_name=False,
        )
        == "incomplete"
    )


def test_merge_keeps_booked_if_pipeline_wants_failed() -> None:
    assert merge_status("booked", "failed") == "booked"
    assert merge_status("in_progress", "enquiry") == "enquiry"


def test_language_mix_and_title() -> None:
    assert looks_mixed("আমার root canal করতে হবে")
    assert not looks_mixed("শুধু বাংলা")
    assert title_name("sabrina akter") == "Sabrina Akter"
