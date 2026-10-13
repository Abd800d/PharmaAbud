"""In-memory sliding-window rate limiter.

Single-instance limiter suitable for one uvicorn process. For multi-node
deployments replace the store with Redis — the interface stays identical.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Tuple

from app.core.config import get_settings
from app.core.errors import RateLimitError

_lock = threading.Lock()
_hits: dict[Tuple[str, str], Deque[float]] = defaultdict(deque)


def check_rate_limit(key: str, route_group: str = "default") -> None:
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return
    limit = (
        settings.rate_limit_auth_per_minute
        if route_group == "auth"
        else settings.rate_limit_per_minute
    )
    now = time.time()
    bucket_key = (key, route_group)
    with _lock:
        q = _hits[bucket_key]
        while q and now - q[0] > 60.0:
            q.popleft()
        if len(q) >= limit:
            raise RateLimitError()
        q.append(now)


def reset_rate_limits() -> None:
    with _lock:
        _hits.clear()
