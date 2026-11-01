"""Render entry point: Groq + explicitly lightweight retrieval, one worker."""
import os
import threading
import time
from urllib.parse import urlsplit

from starlette.responses import JSONResponse


def positive_integer(name, default):
    try:
        value = int(os.environ.get(name, default))
    except ValueError:
        raise ValueError(f"{name} must be a positive integer") from None
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


class RequestBudget:
    """Single-process, bounded-memory limits; no IP addresses or questions logged."""
    def __init__(self, per_minute=8, per_day=40, per_client=3, clock=time.time):
        self.per_minute, self.per_day, self.per_client = per_minute, per_day, per_client
        self.clock, self.lock = clock, threading.Lock()
        self.minute = self.day = None
        self.minute_count = self.day_count = 0
        self.clients = {}

    def allow(self, client):
        now = int(self.clock())
        minute, day = now // 60, now // 86400
        with self.lock:
            if minute != self.minute:
                self.minute, self.minute_count, self.clients = minute, 0, {}
            if day != self.day:
                self.day, self.day_count = day, 0
            if self.day_count >= self.per_day:
                return False, (day + 1) * 86400 - now
            if self.minute_count >= self.per_minute or self.clients.get(client, 0) >= self.per_client:
                return False, (minute + 1) * 60 - now
            self.minute_count += 1
            self.day_count += 1
            self.clients[client] = self.clients.get(client, 0) + 1
            return True, 0


class PublicRequestGuard:
    def __init__(self, app, budget, origins, max_body=16384):
        self.app, self.budget, self.origins, self.max_body = app, budget, set(origins), max_body

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") != "/api/ask" or scope.get("method") != "POST":
            return await self.app(scope, receive, send)
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        origin = headers.get(b"origin", b"").decode("latin-1")
        async def reject(status, detail, extra=None):
            response_headers = dict(extra or {})
            if origin in self.origins:
                response_headers.update({"Access-Control-Allow-Origin": origin, "Vary": "Origin"})
            await JSONResponse({"detail": detail}, status_code=status, headers=response_headers)(scope, receive, send)
        if origin and origin not in self.origins:
            return await reject(403, "This browser origin is not allowed.")
        if headers.get(b"content-type", b"").split(b";", 1)[0].strip().lower() != b"application/json":
            return await reject(415, "Send application/json.")
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_body:
                return await reject(413, "Question request exceeds the demo's size limit.")
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        client = (scope.get("client") or ("unknown", 0))[0]
        allowed, retry = self.budget.allow(client)
        if not allowed:
            return await reject(429, "The public demo's request budget is exhausted. Try again later.",
                                {"Retry-After": str(retry)})
        delivered = False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()
        await self.app(scope, replay, send)


def create_render_app():
    from .api import create_app
    if not os.environ.get("GROQ_API_KEY", "").strip():
        raise RuntimeError("Configure GROQ_API_KEY in Render's environment settings; never commit it.")
    origins = [s.strip() for s in os.environ.get("REGULATORY_ALLOWED_ORIGINS", "https://satyampalkar.github.io").split(",") if s.strip()]
    own_origin = os.environ.get("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    if own_origin and own_origin not in origins:
        origins.append(own_origin)
    for origin in origins:
        parsed = urlsplit(origin)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise ValueError("REGULATORY_ALLOWED_ORIGINS must contain HTTPS origins without paths or credentials")
    if not origins:
        raise ValueError("Set at least one allowed frontend origin")
    budget = RequestBudget(per_minute=positive_integer("REGULATORY_REQUESTS_PER_MINUTE", 8),
                           per_day=positive_integer("REGULATORY_REQUESTS_PER_DAY", 40),
                           per_client=positive_integer("REGULATORY_CLIENT_REQUESTS_PER_MINUTE", 3))
    app = create_app(provider="groq", retrieval_backend="tfidf", allowed_origins=origins)
    app.add_middleware(PublicRequestGuard, budget=budget, origins=origins)
    return app
