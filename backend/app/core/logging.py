"""Structured application logging.

Separates application / security / audit / import / sync / ai log streams.
Sensitive values are never logged.
"""
from __future__ import annotations

import logging
import sys

from app.core.config import get_settings

_CONFIGURED = False

STREAMS = ("app", "security", "audit", "import", "sync", "ai")


def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    settings = get_settings()
    fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt))
    root = logging.getLogger("aph")
    root.setLevel(settings.log_level.upper())
    root.handlers = [handler]
    for stream in STREAMS:
        lg = logging.getLogger(f"aph.{stream}")
        lg.setLevel(settings.log_level.upper())
        lg.propagate = True
    _CONFIGURED = True


def get_logger(stream: str = "app") -> logging.Logger:
    if stream not in STREAMS:
        stream = "app"
    return logging.getLogger(f"aph.{stream}")
