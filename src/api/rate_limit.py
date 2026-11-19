"""Rate limit en memoria por IP (ventana deslizante) para /login y /register.

Alcanza porque el backend corre como un único proceso. Detrás de un reverse proxy
(Caddy en la misma máquina), uvicorn toma la IP real de `X-Forwarded-For` si el proxy
está en `forwarded_allow_ips` (por defecto 127.0.0.1).
"""

from __future__ import annotations

import threading
import time
from collections import deque

from fastapi import HTTPException, Request

from src.config import AUTH_RATE_LIMIT, AUTH_RATE_WINDOW_S

_hits: dict[str, deque[float]] = {}
_lock = threading.Lock()


def auth_rate_limit(request: Request) -> None:
    """Dependency de FastAPI: 429 si la IP superó AUTH_RATE_LIMIT intentos en la ventana."""
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    cutoff = now - AUTH_RATE_WINDOW_S
    with _lock:
        if len(_hits) > 10_000:  # poda ocasional de IPs inactivas
            for k in [k for k, q in _hits.items() if not q or q[-1] < cutoff]:
                del _hits[k]
        q = _hits.setdefault(ip, deque())
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= AUTH_RATE_LIMIT:
            retry = int(q[0] - cutoff) + 1
            raise HTTPException(
                status_code=429,
                detail="Demasiados intentos; probá de nuevo en un minuto",
                headers={"Retry-After": str(retry)},
            )
        q.append(now)
