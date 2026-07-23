import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 60
_CLEANUP_INTERVAL = 300

_attempts: dict[str, list[float]] = defaultdict(list)
_last_cleanup = 0.0


def _cleanup() -> None:
    global _last_cleanup
    now = time.monotonic()
    if now - _last_cleanup < _CLEANUP_INTERVAL:
        return
    _last_cleanup = now
    cutoff = now - WINDOW_SECONDS
    stale = [ip for ip, ts in _attempts.items() if not ts or ts[-1] < cutoff]
    for ip in stale:
        del _attempts[ip]


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(request: Request) -> None:
    _cleanup()
    ip = _client_ip(request)
    now = time.monotonic()
    cutoff = now - WINDOW_SECONDS
    timestamps = _attempts[ip]
    _attempts[ip] = [t for t in timestamps if t > cutoff]
    if len(_attempts[ip]) >= MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Try again later.",
        )
    _attempts[ip].append(now)


def reset_rate_limits() -> None:
    _attempts.clear()
