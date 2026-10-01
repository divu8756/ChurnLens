"""In-memory sliding-window rate limits per client IP (single process; Render runs one).

Behind a proxy, set TRUST_PROXY_HEADERS=true so the first X-Forwarded-For address is used;
otherwise that header is ignored (a client could forge it)."""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.config import get_settings


class RateLimiter:
    def __init__(self, limit: int, window_s: float = 60.0) -> None:
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, now: float | None = None) -> float | None:
        """Record a hit; None if allowed, else seconds until the next slot frees."""
        now = time.monotonic() if now is None else now
        with self._lock:
            self._prune(now)
            hits = self._hits[key]
            if len(hits) >= self.limit:
                return self.window_s - (now - hits[0])
            hits.append(now)
            return None

    def _prune(self, now: float) -> None:
        """Drop expired hits, and IPs with none left, so memory stays bounded."""
        for key in list(self._hits):
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window_s:
                hits.popleft()
            if not hits:
                del self._hits[key]

    def tracked(self) -> int:
        return len(self._hits)


def client_ip(request: Request) -> str:
    if get_settings().TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded.strip():
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce(limiter: RateLimiter, request: Request, what: str) -> None:
    wait = limiter.check(client_ip(request))
    if wait is not None:
        raise HTTPException(429, f"Too many {what} requests; try again in {int(wait) + 1} s.",
                            headers={"Retry-After": str(int(wait) + 1)})
