import pytest

from app.domain.phone import (
    PhoneError,
    grouped_bangla,
    grouped_local,
    normalize_bd_mobile,
    to_bangla_digits,
)


def test_bangla_digits_and_separators() -> None:
    assert normalize_bd_mobile("০১৭১২-৩৪৫-৬৭৮") == "+8801712345678"


def test_english_local_and_e164() -> None:
    assert normalize_bd_mobile("01712345678") == "+8801712345678"
    assert normalize_bd_mobile("+8801712345678") == "+8801712345678"
    assert normalize_bd_mobile("8801712345678") == "+8801712345678"


def test_rejects_short_and_non_mobile_prefix() -> None:
    with pytest.raises(PhoneError):
        normalize_bd_mobile("01712")
    with pytest.raises(PhoneError):
        normalize_bd_mobile("01123456789")


@pytest.mark.parametrize(
    ("raw", "grouped"),
    [
        ("01711111111", "01711-111-111"),
        ("০১৯১২৩৪৫৬৭৮", "01912-345-678"),
    ],
)
def test_groups_as_five_three_three(raw: str, grouped: str) -> None:
    e164 = normalize_bd_mobile(raw)
    assert grouped_local(e164) == grouped
    assert grouped_bangla(e164) == to_bangla_digits(grouped)
