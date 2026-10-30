"""Explicit, server-only Groq inference. Never log credentials or provider bodies."""
import json
import os
from pathlib import Path
import time

from .assistant import LocalController
from .rag import ROOT, prompt_messages


class GroqError(RuntimeError):
    def __init__(self, message, status_code=503):
        super().__init__(message)
        self.status_code = status_code


def configuration():
    return json.loads((ROOT / "configs/groq.json").read_text())


def api_key(env_file=None):
    """Read only this credential; do not execute a shell file or mutate os.environ."""
    value = os.environ.get("GROQ_API_KEY", "").strip()
    if not value:
        path = Path(env_file) if env_file is not None else ROOT / ".env"
        if path.is_file():
            for line in path.read_text().splitlines():
                if line.strip().startswith("GROQ_API_KEY="):
                    value = line.strip().split("=", 1)[1].strip().strip("\"'")
    if not value or any(c.isspace() for c in value):
        raise GroqError("Set GROQ_API_KEY in the server environment or local ignored .env file.")
    return value


class GroqClient:
    provider = "groq"

    def __init__(self, *, key=None, transport=None, request_interval=0):
        import httpx
        self.config = configuration()
        self.model_id = self.config["model"]
        self._key = key if key is not None else api_key()
        self._http = httpx.Client(timeout=self.config["timeout_seconds"], transport=transport,
                                  follow_redirects=False)
        self.request_interval = request_interval
        self._last_request = 0
        self.last_stats = {}
        self.completed_requests = 0

    def close(self):
        self._http.close()

    def complete(self, messages, max_tokens):
        import httpx
        delay = self.request_interval - (time.monotonic() - self._last_request)
        if delay > 0:
            time.sleep(delay)
        self._last_request = time.monotonic()
        payload = {"model": self.model_id, "messages": messages, "temperature": 0,
                   "max_completion_tokens": max_tokens, "stream": False,
                   "reasoning_effort": self.config["reasoning_effort"]}
        started = time.perf_counter()
        try:
            response = self._http.post("https://api.groq.com/openai/v1/chat/completions",
                                       headers={"Authorization": "Bearer " + self._key}, json=payload)
        except httpx.HTTPError:
            raise GroqError("Groq could not be reached. Try again shortly.") from None
        if response.status_code == 429:
            raise GroqError("Groq usage limit reached. Try again later; no local fallback was run.", 429)
        if response.status_code in {401, 403}:
            raise GroqError("Groq authentication or model access failed. Check the server credential.")
        if response.status_code != 200:
            raise GroqError("Groq inference is unavailable. No local fallback was run.")
        try:
            data = response.json()
            choice = data["choices"][0]
            text = choice["message"]["content"]
            if choice.get("finish_reason") != "stop" or not isinstance(text, str) or not text.strip():
                raise ValueError("Incomplete completion")
            if len(text) > 16000 or self._key in text:
                raise ValueError("Invalid completion")
            usage = data.get("usage", {})
            elapsed = time.perf_counter() - started
            self.last_stats = {"prompt_tokens": int(usage.get("prompt_tokens", 0)),
                               "generated_tokens": int(usage.get("completion_tokens", 0)),
                               "tokens_per_second": round(int(usage.get("completion_tokens", 0)) / max(elapsed, .001), 2)}
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise GroqError("Groq returned an incomplete or invalid answer. Try again.") from None
        self.completed_requests += 1
        return text.strip()


class GroqController(LocalController):
    provider = "groq"

    def __init__(self, client=None):
        self.client = client if client is not None else GroqClient()
        super().__init__(model_spec={"repository": self.client.model_id,
                                     "revision": "provider-managed", "provider": "groq"})

    def complete(self, messages):
        return self.client.complete(messages, self.client.config["controller_max_tokens"])


class GroqGenerator:
    provider = "groq"
    adapter = None
    model = None

    def __init__(self, client=None, answer_style="concise"):
        self.client = client if client is not None else GroqClient()
        self.model_id = self.client.model_id
        self.answer_style = answer_style
        self.last_stats = {}

    def __call__(self, question, evidence, history=None):
        from .conversation import explanatory_messages, concise_conversation_messages
        messages = (explanatory_messages(question, evidence, history) if self.answer_style == "explain"
                    else concise_conversation_messages(question, evidence, history) if history
                    else prompt_messages(question, evidence))
        text = self.client.complete(messages, self.client.config["answer_max_tokens"])
        self.last_stats = dict(self.client.last_stats)
        return text
