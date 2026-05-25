"""Per-IP rate limiting.

We can't always rely on Chainlit's HTTP layer giving us direct access to a slowapi
Limiter binding cleanly, so we implement a small in-memory sliding-window counter
keyed by hashed IP. This caps cost in the typical 'leaked link gets scraped' case;
the global ceiling provides a second floor.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import threading
import time
from collections import defaultdict, deque

PER_IP_MIN = int(os.environ.get("RATE_LIMIT_PER_MIN", "10"))
PER_IP_HOUR = int(os.environ.get("RATE_LIMIT_PER_HOUR", "60"))
PER_IP_DAY = int(os.environ.get("RATE_LIMIT_PER_DAY", "200"))
GLOBAL_DAILY = int(os.environ.get("RATE_LIMIT_GLOBAL_DAILY", "1000"))

_SALT = os.environ.get("RATE_LIMIT_SALT", "change-me").encode("utf-8")

_lock = threading.Lock()
_per_ip: dict[str, deque[float]] = defaultdict(deque)
_global: deque[float] = deque()


def hash_ip(ip: str) -> str:
    return hmac.new(_SALT, ip.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def _purge_older_than(q: deque[float], cutoff: float) -> None:
    while q and q[0] < cutoff:
        q.popleft()


def check_and_consume(ip: str) -> tuple[bool, str | None]:
    """Returns (allowed, reason_if_blocked)."""
    now = time.time()
    h = hash_ip(ip)
    with _lock:
        q = _per_ip[h]
        _purge_older_than(q, now - 86400)
        _purge_older_than(_global, now - 86400)
        count_day = len(q)
        count_hour = sum(1 for t in q if t > now - 3600)
        count_min = sum(1 for t in q if t > now - 60)
        if len(_global) >= GLOBAL_DAILY:
            return False, "Daily global limit reached. Please try again tomorrow."
        if count_day >= PER_IP_DAY:
            return False, "Daily per-user limit reached. Please try again tomorrow."
        if count_hour >= PER_IP_HOUR:
            return False, "Hourly per-user limit reached. Please try again in an hour."
        if count_min >= PER_IP_MIN:
            return False, "Rate limit: 10 messages per minute. Please slow down."
        q.append(now)
        _global.append(now)
    return True, None
