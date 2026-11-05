from __future__ import annotations

PROTECTED_STATUSES = frozenset({"booked", "rescheduled", "cancelled", "follow_up_needed"})


def classify_call(
    *,
    appointment_status: str | None,
    callback_urgency: str | None,
    incomplete: bool,
    caller_turns: int,
    intent: str | None,
    has_phone: bool,
    has_name: bool,
) -> str:
    # Urgent symptoms outrank a slot. The appointment row can still exist.
    if callback_urgency == "urgent":
        return "follow_up_needed"
    if appointment_status == "cancelled":
        return "cancelled"
    if appointment_status == "rescheduled":
        return "rescheduled"
    if appointment_status == "booked":
        return "booked"
    if callback_urgency == "normal":
        return "follow_up_needed"
    if incomplete or caller_turns == 0:
        return "incomplete"
    if has_phone and (intent == "book" or has_name):
        return "follow_up_needed"
    return "enquiry"


def merge_status(current: str, proposed: str) -> str:
    """Do not hide a real booking behind a later pipeline failure or a vague label."""
    if current in PROTECTED_STATUSES and proposed != current:
        return current
    if current == "failed" and proposed in PROTECTED_STATUSES:
        return proposed
    return proposed
