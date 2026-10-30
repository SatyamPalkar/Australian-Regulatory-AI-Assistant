"""Local API and the built React interface served from one origin."""
import json
import threading
import time
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .rag import ROOT, load_pipeline, model_manifest
from .retailer import answer_policy
from .assistant import LocalController, conversation_result, capabilities
from .session import SessionStore

BASE_PATH = "/Australian-Regulatory-AI-Assistant"


class HistoryTurn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    answer: str = Field(max_length=4000)


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[HistoryTurn] = Field(default_factory=list, max_length=3)
    conversation_id: Optional[UUID] = None


def create_app(pipeline=None, index_path=None, adapter=None, answer_style="concise", policy_fetcher=None, controller=None):
    app = FastAPI(title="Australian Regulatory RAG", version="0.2.0")
    app.add_middleware(CORSMiddleware, allow_origins=["https://satyampalkar.github.io",
                       "http://127.0.0.1:4174", "http://localhost:4174"],
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
    lock = threading.Lock()
    state = {"pipeline": pipeline, "policy_state": {}}
    sessions = SessionStore()
    controller = controller if controller is not None else LocalController()
    corpus = json.loads((ROOT / "site/lib/corpus.json").read_text())

    def runtime_facts():
        return capabilities(corpus=corpus, manifest=model_manifest(), controller=controller,
                            pipeline=state["pipeline"], adapter=adapter, policy_state=state["policy_state"])

    if isinstance(controller, LocalController):
        controller.runtime_facts = runtime_facts

    @app.get("/api/health")
    def health():
        return {"status": "ok", "models_loaded": state["pipeline"] is not None,
                "controller_loaded": getattr(controller, "model", None) is not None,
                "mode": "rag", "corpus_sha256": corpus["corpus_sha256"]}

    @app.get("/api/status")
    def status():
        return {"mode": "rag", "backend": "hybrid", "sources": corpus["sources"],
                "corpus_sha256": corpus["corpus_sha256"], "collection": corpus["collection"],
                "section_count": len(corpus["sources"]), "chunk_count": len(corpus["chunks"]),
                "law_count": 1, "version_dates": sorted({s["version_date"] for s in corpus["sources"]}),
                "models": model_manifest(), "adapter": bool(adapter), "answer_style": answer_style,
                "assistant": runtime_facts(),
                "retailer_policy": {"retailers": ["JB Hi-Fi"], "lookup": "official public content", "sends_question": False},
                "conversation": {"max_turns": 3, "max_characters": 6000, "persistent": False,
                                 "topic_state": "server session", "session_ttl_seconds": sessions.ttl, "max_sessions": sessions.limit}}

    @app.get("/api/evaluation")
    def evaluation():
        return json.loads((ROOT / "site/lib/evaluation.json").read_text())

    @app.get("/api/experiments")
    def experiments():
        path = ROOT / "site/lib/experiments.json"
        return json.loads(path.read_text()) if path.exists() else {"runs": []}

    @app.post("/api/ask")
    def ask(body: Question):
        if not body.question.strip():
            raise HTTPException(422, "Enter a nonempty question")
        from .conversation import bounded_history
        try:
            history = bounded_history([turn.model_dump() for turn in body.history])
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        # One model request at a time bounds memory and avoids concurrent MLX access.
        if not lock.acquire(blocking=False):
            raise HTTPException(429, "The local model is answering another question. Try again shortly.")
        try:
            started = time.perf_counter()
            try:
                conversation_id, topic_state = sessions.get(str(body.conversation_id) if body.conversation_id else None)
            except KeyError as exc:
                raise HTTPException(409, str(exc.args[0])) from exc
            decision = controller.plan(body.question, history, state=topic_state)

            def finish(result):
                topic_state.advance(body.question, decision)
                result["conversation_id"] = conversation_id
                result["conversation_state"] = topic_state.context()
                result.setdefault("trace", {}).update(session_turn=topic_state.turns,
                                                      active_retailer=topic_state.retailer,
                                                      pending_clarification=topic_state.pending_clarification)
                return result

            controller_ms = (time.perf_counter() - started) * 1000
            if decision["action"] in {"chat", "clarify", "recovery"}:
                return finish(conversation_result(decision, controller_ms, history))
            if decision["action"] == "policy":
                result = answer_policy(body.question, history, fetcher=policy_fetcher, routed=True)
                state["policy_state"]["last_attempt_status"] = result["policy_lookup"]["status"]
                if result["policy_lookup"]["status"] == "fetched" and result["evidence"]:
                    state["policy_state"]["last_successful_fetch"] = result["evidence"][0]["fetched_at"]
                result["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
                result["trace"].update(controller_ms=round(controller_ms, 2), controller_action="policy")
                return finish(result)
            if state["pipeline"] is None:
                state["pipeline"] = load_pipeline(index_path, adapter, answer_style=answer_style)
            options = {"history": history} if history else {}
            if decision.get("search_question"):
                options["search_question"] = decision["search_question"]
            result = state["pipeline"].ask(body.question, **options)
            # Raw rejected text belongs in offline reports, not the user answer.
            result.pop("raw_generation", None)
            result["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
            result.setdefault("trace", {}).update(controller_ms=round(controller_ms, 2), controller_action="statutory")
            return finish(result)
        except (RuntimeError, OSError, ValueError) as exc:
            raise HTTPException(503, str(exc)) from exc
        finally:
            lock.release()

    @app.get(f"{BASE_PATH}/runtime-config.js")
    def runtime():
        return Response("window.REGULATORY_API_BASE = window.location.origin;", media_type="text/javascript",
                        headers={"Cache-Control": "no-store"})

    @app.get("/")
    def home():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(f"{BASE_PATH}/")

    static = ROOT / "site/pages-dist"
    if static.exists():
        app.mount(BASE_PATH, StaticFiles(directory=static, html=True), name="ui")
    return app
