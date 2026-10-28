"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowDownToLine, ArrowRight, ArrowUp, BookOpen, Check, CheckCheck, ChevronRight, CircleHelp, Copy, ExternalLink, FileText, GitBranch as Github, Layers, LoaderCircle, MessageSquare, Plus, Scale, Search, ShieldCheck, SlidersHorizontal, X } from "lucide-react";

type Source = { id: string; title: string; url: string; publisher: string; source_kind: string; verified_on?: string; text?: string; score?: number; chunk_id: string; word_count?: number };
type Result = { answer: string; evidence: Source[]; retrieved: Source[]; abstained: boolean; latency_ms: number };
type Turn = { question: string; result?: Result; error?: string };
type Status = { sources: Source[]; corpus_sha256: string; mode: string; backend: string };
type Evaluation = { corpus_sha256: string; metrics: Record<string, number>; results: { id: string; question: string; answerable: boolean; abstained: boolean; retrieval_hit_at_1: boolean | null }[] };
const suggestions = [
  { title: "After the warranty", question: "Do consumer guarantee rights end when a manufacturer's warranty expires?", icon: ShieldCheck, detail: "Understand your ongoing rights" },
  { title: "Repairs & refunds", question: "What refund or replacement can a consumer choose for a product with a major problem?", icon: ArrowDownToLine, detail: "Explore remedies for faulty products" },
  { title: "Product quality", question: "What factors help determine acceptable quality and durability of a product?", icon: CheckCheck, detail: "Know what you can reasonably expect" },
];

export default function Home() {
  const [view, setView] = useState<"assistant" | "sources" | "evaluation">("assistant");
  const [status, setStatus] = useState<Status | null>(null);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [loadError, setLoadError] = useState("");
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<Source | null>(null);
  const [copied, setCopied] = useState<number | null>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const modal = useRef<HTMLElement>(null);
  const sourceTrigger = useRef<HTMLElement | null>(null);
  const newest = turns.at(-1)?.result;
  const supported = evaluation?.results.filter((row) => row.answerable) ?? [];
  const unsupported = evaluation?.results.filter((row) => !row.answerable) ?? [];

  useEffect(() => {
    Promise.all([fetch("/api/status"), fetch("/api/evaluation")]).then(async ([s, e]) => {
      if (!s.ok || !e.ok) throw new Error("Could not load the corpus. Refresh to reconnect.");
      setStatus(await s.json()); setEvaluation(await e.json());
    }).catch((error) => setLoadError(error.message));
  }, []);
  useEffect(() => {
    if (!selected) return;
    const trap = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;
      const items = modal.current?.querySelectorAll<HTMLElement>('button, a[href], summary');
      if (!items?.length) return;
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", trap);
    return () => { document.removeEventListener("keydown", trap); sourceTrigger.current?.focus(); };
  }, [selected]);

  function openSource(source: Source) {
    sourceTrigger.current = document.activeElement as HTMLElement;
    setSelected(source);
  }
  useEffect(() => { if (turns.length) end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns]);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "k") { event.preventDefault(); setView("assistant"); input.current?.focus(); }
      if (event.key === "Escape") setSelected(null);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  async function submit(value = question) {
    const text = value.trim();
    if (!text || busy) return;
    setView("assistant"); setBusy(true); setQuestion(""); setTurns((old) => [...old, { question: text }]);
    try {
      const response = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: text }), signal: AbortSignal.timeout(15000) });
      const data = await response.json() as Result & { error?: string };
      if (!response.ok) throw new Error(data.error || "The assistant is unavailable. Please try again.");
      setTurns((old) => [...old.slice(0, -1), { question: text, result: data }]);
    } catch (error) {
      setTurns((old) => [...old.slice(0, -1), { question: text, error: error instanceof Error ? error.message : "Connection failed. Please try again." }]);
    } finally { setBusy(false); }
  }

  async function copy(turn: Turn, index: number) {
    try {
      await navigator.clipboard.writeText(`${turn.question}\n\n${turn.result?.answer}\n\n${turn.result?.evidence.map((source, i) => `[${i + 1}] ${source.title}: ${source.url}`).join("\n")}`);
      setCopied(index); window.setTimeout(() => setCopied(null), 2000);
    } catch { setLoadError("Clipboard access is unavailable. Select the passages to copy them."); }
  }

  function download() {
    const blob = new Blob([JSON.stringify({ exported_at: new Date().toISOString(), corpus_sha256: status?.corpus_sha256, turns }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = "regulatory-research.json"; a.click(); URL.revokeObjectURL(url);
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="Australian Regulatory Assistant home"><span className="brand-mark"><Scale size={22} strokeWidth={1.7}/></span><span>Regulatory<span className="brand-sub">AUSTRALIAN AI ASSISTANT</span></span></a>
      <button className="new-research" disabled={busy} onClick={() => { setTurns([]); setQuestion(""); setView("assistant"); input.current?.focus(); }}><Plus size={16}/> New research <span>↗</span></button>
      <div className="nav-label">WORKSPACE</div>
      <nav aria-label="Main navigation">
        <button className={view === "assistant" ? "nav-item active" : "nav-item"} onClick={() => setView("assistant")}><MessageSquare size={17}/> Assistant <ChevronRight size={14}/></button>
        <button className={view === "sources" ? "nav-item active" : "nav-item"} onClick={() => setView("sources")}><BookOpen size={17}/> Source library <span className="count">{status?.sources.length ?? "–"}</span></button>
        <button className={view === "evaluation" ? "nav-item active" : "nav-item"} onClick={() => setView("evaluation")}><SlidersHorizontal size={17}/> Evaluation</button>
      </nav>
      <div className="sidebar-collection"><div className="nav-label">CURRENT COLLECTION</div><div className="collection-title"><span className="collection-dot"/> Consumer protection</div><p>Australian Competition &<br/>Consumer Commission</p><span className="tiny-pill">ACCC</span><span className="collection-files">3 guidance summaries</span></div>
      <div className="sidebar-bottom"><div className="research-note"><ShieldCheck size={18}/><strong>Evidence comes first.</strong><p>Every passage links back to its source. Always check the original guidance.</p></div><a className="github-link" href="https://github.com/SatyamPalkar/Australian-Regulatory-AI-Assistant" target="_blank" rel="noreferrer"><Github size={16}/> View project <ExternalLink size={13}/></a><div className="profile"><span className="profile-avatar">SP</span><div>Research workspace<small>Personal project</small></div><span className="profile-dot"/></div></div>
    </aside>
    <main className="main-content">
      <header className="topbar"><div className="breadcrumb">Workspace <ChevronRight size={13}/><strong>{view === "assistant" ? "Assistant" : view === "sources" ? "Source library" : "Evaluation"}</strong></div><div className="topbar-right"><span className="demo-badge"><span/> Research demo</span><button className="icon-button" aria-label="About this corpus" onClick={() => setView("sources")}><CircleHelp size={19}/></button></div></header>
      {loadError && <div className="error-banner" role="alert">{loadError}<button aria-label="Dismiss message" onClick={() => setLoadError("")}><X size={16}/></button></div>}
      {view === "assistant" && <div className="assistant-layout"><section className="chat-column">
        {!turns.length ? <div className="welcome"><div className="eyebrow"><span/> AUSTRALIAN CONSUMER GUIDANCE</div><h1>A clearer path through<br/>the <em>fine print.</em></h1><p className="hero-description">Explore regulatory guidance with evidence you can trace.<br className="desktop-break"/> Ask a question. Find relevant passages. Check the source.</p><div className="hero-divider"><span/><Scale size={17}/><span/></div><div className="suggestion-label">A FEW PLACES TO START</div><div className="suggestion-grid">{suggestions.map(({ title, question: text, icon: Icon, detail }) => <button key={title} className="suggestion" disabled={busy} onClick={() => submit(text)}><span className="suggestion-icon"><Icon size={20} strokeWidth={1.6}/></span><strong>{title}</strong><span>{detail}</span><ArrowRight size={16} className="suggestion-arrow"/></button>)}</div><div className="coverage-line"><Check size={14}/><span>Consumer guarantees</span><span className="bullet">·</span><span>Warranties</span><span className="bullet">·</span><span>Repairs & refunds</span></div></div> : <div className="conversation" aria-live="polite">{turns.map((turn, i) => <article className="turn" key={i}><div className="question-row"><span className="user-avatar">You</span><h2>{turn.question}</h2></div><div className="answer-row"><span className="assistant-avatar"><Scale size={17}/></span><div className="answer-body"><div className="answer-heading">Regulatory Assistant <span>{turn.result?.abstained ? "Evidence unavailable" : "Source evidence"}</span></div>{!turn.result && !turn.error && <div className="loading"><LoaderCircle size={16} className="spin"/> Searching the guidance collection…</div>}{turn.error && <div className="request-error" role="alert">{turn.error}<button onClick={() => submit(turn.question)} disabled={busy}>Try again <ArrowRight size={13}/></button></div>}{turn.result && <>{turn.result.abstained ? <div className="abstention"><ShieldCheck size={22}/><h3>This collection doesn’t have enough evidence.</h3><p>Try a question about consumer guarantees, warranties, or remedies. You can also check the original ACCC guidance.</p><button onClick={() => setView("sources")}>Explore the source library <ArrowRight size={14}/></button></div> : <><p className="evidence-intro">These passages may help answer your question. They are project-authored summaries of ACCC guidance.</p>{turn.result.evidence.map((source, n) => <div className="evidence-passage" key={source.chunk_id}><p>{source.text} <button className="citation" aria-label={`View source ${n + 1}: ${source.title}`} onClick={() => openSource(source)}>{n + 1}</button></p><a href={source.url} target="_blank" rel="noreferrer"><FileText size={12}/>{source.title}<ExternalLink size={11}/></a></div>)}<div className="answer-caveat"><CircleHelp size={13}/> Related evidence does not confirm that every part of your question is answered.</div></>}<div className="answer-actions"><button onClick={() => copy(turn, i)} aria-label="Copy answer">{copied === i ? <Check size={14}/> : <Copy size={14}/>} {copied === i ? "Copied" : "Copy"}</button><span>{turn.result.evidence.length} source{turn.result.evidence.length === 1 ? "" : "s"} · {turn.result.latency_ms.toFixed(1)} ms retrieval</span></div></>}</div></div></article>)}<div ref={end}/></div>}
        <div className="composer-area"><form className="composer" onSubmit={(event) => { event.preventDefault(); submit(); }}><label htmlFor="question" className="sr-only">Ask about Australian consumer guidance</label><textarea id="question" ref={input} value={question} maxLength={2000} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask about Australian consumer guidance…" rows={2} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(); } }}/><div className="composer-bottom"><span><Layers size={13}/> ACCC collection <span className="composer-separator">|</span> {question.length > 1800 ? `${question.length}/2000` : "3 sources"}</span><div><span className="keyboard-hint">↵ to ask</span><button type="submit" className="send-button" disabled={!question.trim() || busy} aria-label="Send question">{busy ? <LoaderCircle size={17} className="spin"/> : <ArrowUp size={18}/>}</button></div></div></form><div className="composer-note"><ShieldCheck size={11}/> General guidance, not legal advice. Verify details with the original source.</div></div>
      </section><aside className="context-panel"><div className="context-title"><BookOpen size={16}/><h2>{newest?.evidence.length ? "Retrieved sources" : "Your evidence library"}</h2><span>{newest?.evidence.length || 3}</span></div><p className="context-description">{newest?.evidence.length ? "Open the original guidance to check the full context." : "A focused collection of Australian consumer guidance."}</p><div className="source-list">{(newest?.evidence.length ? newest.evidence : status?.sources ?? []).map((source, i) => <button className="source-card" key={source.id} onClick={() => openSource(source)}><div className="source-card-top"><span className="document-icon"><FileText size={17}/></span><span className="source-publisher">ACCC</span><span className="source-number">0{i + 1}</span></div><h3>{source.title}</h3><p>{source.id === "accc-warranties" ? "Extra promises, extended cover and rights after expiry." : source.id === "accc-remedies" ? "Remedies when a product or service has a problem." : "The basic rights that come with products and services."}</p><div className="source-card-bottom"><span>Guidance summary</span><ArrowRight size={14}/></div></button>)}</div><button className="library-button" onClick={() => setView("sources")}>Explore all sources <ArrowRight size={14}/></button><div className="scope-note"><span className="scope-icon"><Search size={17}/></span><h3>A focused starting point</h3><p>This demo searches three curated summaries. It doesn’t cover all Australian regulations or provide an LLM-generated answer.</p><button onClick={() => setView("evaluation")}>See what we measure <ArrowRight size={13}/></button></div>{turns.some((turn) => turn.result) && <button className="export-button" onClick={download}><ArrowDownToLine size={14}/> Export this research</button>}</aside></div>}
      {view === "sources" && <section className="content-page"><div className="eyebrow"><BookOpen size={15}/> THE EVIDENCE COLLECTION</div><h1>Know your sources.</h1><p className="page-description">Three focused summaries, each linked to the official ACCC guidance.<br/>Open an original page for its complete context and latest updates.</p><div className="collection-banner"><div><ShieldCheck size={22}/><div><strong>Transparent by design</strong><p>Project-authored summaries · verified 28 October 2026 · Australia</p></div></div><span className="tiny-pill">ACCC</span></div><div className="library-grid">{status?.sources.map((source) => <article className="library-card" key={source.id}><FileText size={25} strokeWidth={1.4}/><span className="source-publisher">Australian Competition & Consumer Commission</span><h2>{source.title}</h2><div className="library-meta"><span>Guidance summary</span><span>{source.word_count} words</span></div><a href={source.url} target="_blank" rel="noreferrer">Read original guidance <ExternalLink size={14}/></a></article>)}</div><div className="method-note"><h2>What’s in this collection?</h2><p>The summaries cover consumer guarantees, warranties, and remedies for faulty products. They omit some qualifications and examples. This deployment retrieves evidence using a lexical search baseline; it does not run a language model. Follow the source links before relying on the guidance.</p><p className="hash-label">Corpus fingerprint <code>{status?.corpus_sha256.slice(0, 16) ?? "Loading…"}</code></p></div></section>}
      {view === "evaluation" && <section className="content-page"><div className="eyebrow"><SlidersHorizontal size={15}/> MEASURED, NOT ASSUMED</div><h1>A baseline you can inspect.</h1><p className="page-description">A saved development run over nine questions.<br/>A small smoke check for retrieval, citations, and unsupported questions.</p><div className="metrics-grid"><div className="metric"><span>Supported source ranked first</span><strong>{evaluation ? `${supported.filter((row) => row.retrieval_hit_at_1).length} / ${supported.length}` : "–"}</strong><small>Supported development questions</small></div><div className="metric"><span>Unsupported questions declined</span><strong>{evaluation ? `${unsupported.filter((row) => row.abstained).length} / ${unsupported.length}` : "–"}</strong><small>One known answerability failure</small></div><div className="metric"><span>Reference format checks</span><strong>{evaluation ? `${Math.round(evaluation.metrics.citation_format_pass_rate * 100)}%` : "–"}</strong><small>Syntax checks, not factual accuracy</small></div></div><div className="evaluation-table"><div className="table-heading"><h2>Question-level results</h2><span className="tiny-pill">DEVELOPMENT SET</span></div>{evaluation?.results.map((row) => <div className="evaluation-row" key={row.id}><span className={row.answerable ? "question-type" : "question-type unsupported"}>{row.answerable ? "In scope" : "Unsupported"}</span><p>{row.question}</p><span className={(row.answerable ? row.retrieval_hit_at_1 : row.abstained) ? "result-pass" : "result-fail"}>{row.answerable ? row.retrieval_hit_at_1 ? "Source found" : "Missed" : row.abstained ? "Declined" : "Needs review"}</span></div>)}</div><div className="method-note"><h2>The limits are part of the result.</h2><p>These inspected development questions are not a held-out benchmark. With three source documents, retrieval at three is trivial. The system can return related passages that do not answer a question, as the penalty example shows. Correct citation numbers do not prove factual support. Human review and a frozen test set are required before comparing fine-tuning results.</p><a className="text-link" href="https://github.com/SatyamPalkar/Australian-Regulatory-AI-Assistant/blob/main/reports/dev-baseline.json" target="_blank" rel="noreferrer">Inspect the full report <ExternalLink size={13}/></a></div></section>}
      <footer className="main-footer"><span>Australian Regulatory AI Assistant</span><span>Built for clarity. Grounded in sources.</span></footer>
    </main>
    {selected && <div className="modal-backdrop" onClick={() => setSelected(null)}><section ref={modal} className="source-modal" role="dialog" aria-modal="true" aria-labelledby="source-title" onClick={(event) => event.stopPropagation()}><button className="modal-close icon-button" aria-label="Close source details" onClick={() => setSelected(null)} autoFocus><X size={20}/></button><span className="modal-document"><FileText size={28}/></span><div className="eyebrow">ACCC · GUIDANCE SUMMARY</div><h2 id="source-title">{selected.title}</h2><p>This is a project-authored summary of official guidance. The original page has additional context and may have been updated.</p><dl><div><dt>Publisher</dt><dd>Australian Competition & Consumer Commission</dd></div><div><dt>Jurisdiction</dt><dd>Australia</dd></div><div><dt>Summary verified</dt><dd>28 October 2026</dd></div>{selected.score !== undefined && <div><dt>Retrieval similarity</dt><dd>{selected.score.toFixed(3)} · relevance, not confidence</dd></div>}</dl>{selected.text && <details><summary>Read the retrieved summary</summary><p>{selected.text}</p></details>}<a className="primary-link" href={selected.url} target="_blank" rel="noreferrer">Read original ACCC guidance <ExternalLink size={15}/></a></section></div>}
  </div>;
}
