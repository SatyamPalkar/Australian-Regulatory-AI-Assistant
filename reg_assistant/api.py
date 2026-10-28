"""Local API and the built React interface served from one origin."""
import json
import threading

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .rag import ROOT, load_pipeline, model_manifest

BASE_PATH = "/Australian-Regulatory-AI-Assistant"


class HistoryTurn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    answer: str = Field(max_length=4000)


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[HistoryTurn] = Field(default_factory=list, max_length=3)


def create_app(pipeline=None, index_path=None, adapter=None, answer_style="concise"):
    app = FastAPI(title="Australian Regulatory RAG", version="0.2.0")
    app.add_middleware(CORSMiddleware, allow_origins=["https://satyampalkar.github.io",
                       "http://127.0.0.1:4174", "http://localhost:4174"],
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
    lock = threading.Lock()
    state = {"pipeline": pipeline}
    corpus = json.loads((ROOT / "site/lib/corpus.json").read_text())

    @app.get("/api/health")
    def health():
        return {"status": "ok", "models_loaded": state["pipeline"] is not None,
                "mode": "rag", "corpus_sha256": corpus["corpus_sha256"]}

    @app.get("/api/status")
    def status():
        return {"mode": "rag", "backend": "hybrid", "sources": corpus["sources"],
                "corpus_sha256": corpus["corpus_sha256"], "collection": corpus["collection"],
                "section_count": len(corpus["sources"]), "chunk_count": len(corpus["chunks"]),
                "law_count": 1, "version_dates": sorted({s["version_date"] for s in corpus["sources"]}),
                "models": model_manifest(), "adapter": bool(adapter), "answer_style": answer_style,
                "conversation": {"max_turns": 3, "max_characters": 6000, "persistent": False}}

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
            if state["pipeline"] is None:
                state["pipeline"] = load_pipeline(index_path, adapter, answer_style=answer_style)
            result = state["pipeline"].ask(body.question, history=history) if history else state["pipeline"].ask(body.question)
            # Raw rejected text belongs in offline reports, not the user answer.
            result.pop("raw_generation", None)
            return result
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
