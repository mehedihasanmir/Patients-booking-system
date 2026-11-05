from __future__ import annotations

import re

_BN = re.compile(r"[\u0980-\u09FF]")
_LATIN = re.compile(r"[A-Za-z]")


def looks_mixed(text: str) -> bool:
    return bool(_BN.search(text) and _LATIN.search(text))


def title_name(value: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        return ""
    if _BN.search(cleaned) and not _LATIN.search(cleaned):
        return cleaned
    return " ".join(part[:1].upper() + part[1:] if part else "" for part in cleaned.split(" "))
