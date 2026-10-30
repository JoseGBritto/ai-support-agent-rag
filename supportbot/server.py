"""Flask API + embeddable widget."""
from __future__ import annotations

import hmac
import re
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

from .agent import SupportAgent
from .config import Settings

STATIC = Path(__file__).parent / "static"
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[a-zA-Z]{2,}$")


class RateLimiter:
    def __init__(self, per_minute: int):
        self.per_minute, self.hits = per_minute, defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        if len(self.hits) > 10_000:  # forget idle visitors so memory stays bounded
            for k in [k for k, w in self.hits.items() if not w or now - w[-1] > 60]:
                del self.hits[k]
        window = self.hits[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self.per_minute:
            return False
        window.append(now)
        return True


def create_app(settings: Settings | None = None, agent: SupportAgent | None = None) -> Flask:
    settings = settings or Settings.from_env()
    agent = agent or SupportAgent(settings)
    limiter = RateLimiter(settings.rate_limit_per_minute)
    app = Flask(__name__, static_folder=None)
    if settings.trusted_proxy_hops:  # behind Railway/Render/Nginx the client IP comes in X-Forwarded-For
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=settings.trusted_proxy_hops, x_proto=settings.trusted_proxy_hops)

    @app.after_request
    def cors(response):
        origin = request.headers.get("Origin")
        if origin and ("*" in settings.allowed_origins or origin in settings.allowed_origins):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    def require_admin():
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        configured = settings.admin_token
        if not configured or configured == "change-me" or not hmac.compare_digest(token, configured):
            return jsonify(error="unauthorized"), 401
        return None

    @app.route("/api/chat", methods=["POST", "OPTIONS"])
    def chat():
        if request.method == "OPTIONS":
            return "", 204
        if not limiter.allow(request.remote_addr or "unknown"):
            return jsonify(error="Too many messages. Please wait a minute."), 429
        body = request.get_json(silent=True) or {}
        question = str(body.get("message", "")).strip()
        if not question:
            return jsonify(error="message is required"), 400
        if len(question) > settings.max_question_chars:
            return jsonify(error=f"message is longer than {settings.max_question_chars} characters"), 400
        conversation_id = str(body.get("conversation_id") or uuid.uuid4())[:64]
        history = body.get("history") if isinstance(body.get("history"), list) else []
        reply = agent.ask(question, conversation_id, history)
        return jsonify(conversation_id=conversation_id, **reply.to_dict())

    @app.route("/api/handoff", methods=["POST", "OPTIONS"])
    def handoff():
        if request.method == "OPTIONS":
            return "", 204
        body = request.get_json(silent=True) or {}
        email = str(body.get("email", "")).strip()
        if not EMAIL_RE.match(email):
            return jsonify(error="a valid email is required"), 400
        if not agent.add_contact(str(body.get("conversation_id", ""))[:64], email):
            return jsonify(error="no pending handoff for this conversation"), 404
        return jsonify(ok=True)

    @app.get("/api/admin/stats")
    def stats():
        return require_admin() or jsonify(agent.store.stats() | {"chunks": len(agent.chunks), "ai_enabled": settings.ai_enabled})

    @app.get("/api/admin/gaps")
    def gaps():
        return require_admin() or jsonify(gaps=agent.store.knowledge_gaps())

    @app.post("/api/admin/reindex")
    def reindex():
        return require_admin() or jsonify(chunks=agent.reindex())

    @app.get("/health")
    def health():
        return jsonify(status="ok", chunks=len(agent.chunks))

    @app.get("/widget.js")
    def widget():
        response = send_from_directory(STATIC, "widget.js", mimetype="application/javascript")
        response.headers["Cache-Control"] = "public, max-age=300"
        return response

    @app.get("/")
    def demo():
        return send_from_directory(STATIC, "demo.html")

    return app
