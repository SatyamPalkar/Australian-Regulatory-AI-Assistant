"""Read-only app facts. Configured, loaded and fetched are distinct states."""
import json
from pathlib import Path


def runtime_snapshot(*, corpus=None, manifest=None, controller=None, pipeline=None,
                     adapter=None, policy_state=None):
    from .rag import ROOT, model_manifest
    from .retailer import POLICY_URL
    manifest = model_manifest() if manifest is None else manifest
    if corpus is None:
        corpus = json.loads((ROOT / "site/lib/corpus.json").read_text())
    generator = getattr(pipeline, "generator", None)
    retriever = getattr(pipeline, "retriever", None)
    selected_adapter = getattr(generator, "adapter", adapter)
    models = {role: {"repository": spec["repository"], "revision": spec["revision"], "loaded": False}
              for role, spec in manifest.items()}
    spec = getattr(controller, "model_spec", None) or manifest["generator"]
    models["controller"] = {"repository": spec["repository"], "revision": spec["revision"], "loaded": getattr(controller, "model", None) is not None,
                            "adapter": False}
    models["generator"]["loaded"] = getattr(generator, "model", None) is not None
    models["embedding"]["loaded"] = getattr(retriever, "encoder", None) is not None
    models["reranker"]["loaded"] = getattr(retriever, "reranker", None) is not None
    adapter_path = Path(selected_adapter) if selected_adapter else None
    if adapter_path and not adapter_path.is_absolute():
        adapter_path = ROOT / adapter_path
    adapter_info = {"selected": bool(selected_adapter),
                    "name": adapter_path.name if adapter_path else None,
                    "weights_present": bool(adapter_path and (adapter_path / "adapters.safetensors").is_file()),
                    "loaded": bool(selected_adapter and models["generator"]["loaded"])}
    dates = sorted({s["version_date"] for s in corpus["sources"] if s.get("version_date")})
    section_count, chunk_count = len(corpus["sources"]), len(corpus["chunks"])
    return {"deployment": "local Python API", "models": models, "answer_adapter": adapter_info,
            "conversation": "Local instruction model; up to three recent turns plus bounded topic state; session expires after one hour; no disk persistence",
            "corpus": {"label": corpus["collection"]["label"], "section_count": section_count,
                       "chunk_count": chunk_count, "version_dates": dates,
                       "scope": corpus["collection"]["scope"],
                       "currency_notice": corpus["collection"]["currency_notice"]},
            "statutory_search": f"{section_count} selected sections in {chunk_count} chunks; snapshot, not guaranteed current law",
            "policy_tools": [{"id": "jb_hifi", "retailer": "JB Hi-Fi", "scope": "returns, refunds and warranties",
                              "available": True, "url": POLICY_URL,
                              "indexed_in_statutory_corpus": any(source.get("url") == POLICY_URL for source in corpus["sources"]),
                              "last_attempt_status": (policy_state or {}).get("last_attempt_status", "not_requested"),
                              "last_successful_fetch": (policy_state or {}).get("last_successful_fetch"),
                              "method": "fetch official public article on request"}],
            "policy_change_comparison": False, "general_web_search": False,
            "github_pages": "The browser-only demo does not run this local LLM controller"}


def render_runtime_facts(facts, group="OVERVIEW"):
    """Render server values, never let generation invent configuration details."""
    paragraphs = []
    if group in {"MODELS", "OVERVIEW"}:
        names = {"controller": "Conversation controller", "generator": "Evidence-answer model",
                 "embedding": "Embeddings", "reranker": "Reranker"}
        for role, label in names.items():
            spec = facts["models"][role]
            paragraphs.append(f"{label}: {spec['repository']} (configured; {'loaded' if spec['loaded'] else 'not loaded yet'}).")
        adapter = facts["answer_adapter"]
        if not adapter["selected"]:
            detail = "No LoRA adapter is selected for evidence answers."
        else:
            state = "loaded" if adapter["loaded"] else "weights available, not loaded yet" if adapter["weights_present"] else "weights missing"
            detail = f"Evidence-answer LoRA adapter: {adapter['name']} ({state})."
        paragraphs.append("The conversation controller uses no LoRA adapter. " + detail)
    if group in {"TOOLS", "DATA", "OVERVIEW"}:
        for tool in facts["policy_tools"]:
            state = "available" if tool["available"] else "unavailable"
            text = f"{tool['retailer']} {tool['scope']} lookup is {state} in this local API."
            text += " Its policy is " + ("included" if tool["indexed_in_statutory_corpus"] else "not included") + " in the statutory index; the policy tool fetches official text on demand."
            if tool["last_successful_fetch"]:
                text += f" Last successful policy fetch in this server session: {tool['last_successful_fetch']}."
            else:
                text += " No successful policy fetch has been recorded in this server session."
            text += f" Most recent lookup attempt: {tool['last_attempt_status']}."
            paragraphs.append(text)
        paragraphs.append("Policy lookup does not establish whether a retailer changed its policy. Historical policy comparison and general web search are not available.")
    if group in {"DATA", "OVERVIEW"}:
        corpus = facts["corpus"]
        paragraphs.append(f"Indexed collection: {corpus['label']}; {corpus['section_count']} sections, {corpus['chunk_count']} retrieval chunks. Compilation dates: {', '.join(corpus['version_dates']) or 'unknown'}. Scope: {corpus['scope']}.")
        paragraphs.append(corpus["currency_notice"])
    return "\n\n".join(paragraphs)
