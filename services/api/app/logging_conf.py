from __future__ import annotations

import logging
import sys

from app.config import get_settings


def setup_logging() -> None:
    settings = get_settings()
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
