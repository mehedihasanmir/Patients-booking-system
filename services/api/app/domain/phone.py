from __future__ import annotations

import re

_BANGLA_TO_EN = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_EN_TO_BANGLA = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
_MOBILE = re.compile(r"^01[3-9]\d{8}$")


class PhoneError(ValueError):
    def __init__(self, code: str, say_bn: str) -> None:
        super().__init__(code)
        self.code = code
        self.say_bn = say_bn


def to_bangla_digits(value: str) -> str:
    return value.translate(_EN_TO_BANGLA)


def to_english_digits(value: str) -> str:
    return value.translate(_BANGLA_TO_EN)


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", to_english_digits(value))


def normalize_bd_mobile(raw: str) -> str:
    """Return E.164 +8801XXXXXXXXX or raise PhoneError."""
    digits = digits_only(raw)
    if digits.startswith("880"):
        digits = "0" + digits[3:]
    if len(digits) == 10 and digits.startswith("1"):
        digits = "0" + digits
    if not _MOBILE.fullmatch(digits):
        raise PhoneError(
            "invalid_phone",
            "নম্বরটা পরিষ্কার পাইনি। আরেকবার বলবেন? যেমন শূন্য এক সাত, তারপর বাকি অঙ্ক।",
        )
    return "+880" + digits[1:]


def local_digits(e164: str) -> str:
    normalized = normalize_bd_mobile(e164)
    return "0" + normalized[4:]


def grouped_local(e164: str) -> str:
    local = local_digits(e164)
    return f"{local[:5]}-{local[5:8]}-{local[8:]}"


def grouped_bangla(e164: str) -> str:
    return to_bangla_digits(grouped_local(e164))


def phone_confirmation(e164: str) -> str:
    return f"নম্বরটা {grouped_bangla(e164)} — ঠিক আছে?"
