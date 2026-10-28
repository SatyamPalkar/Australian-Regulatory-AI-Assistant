"use client";

import { useEffect, useRef, useState } from "react";
import Phase2Panel from "../components/phase2-panel";
import ExperimentPanel from "../components/experiment-panel";
import { ArrowDownToLine, ArrowRight, ArrowUpRight, AudioLines, BookOpen, Check, ChevronDown, CircleHelp, Copy, ExternalLink, FileText, Fingerprint, GitBranch, Layers, LoaderCircle, MessageSquare, Plus, Scale, Search, ShieldCheck, SlidersHorizontal, X } from "lucide-react";

type Source = { id: string; title: string; url: string; publisher: string; jurisdiction: string; source_kind: string; version_date: string; dataset: string; dataset_revision: string; dataset_file_url: string; section_number: string; section_heading: string; license: string; license_url: string; current_source_url: string; compilation_id: string; text?: string; score?: number; chunk_id?: string; word_count?: number; evidence_span?: string };
export type Result = { answer: string; evidence: Source[]; retrieved: Source[]; abstained: boolean; latency_ms: number; mode?: string; scope_note?: string | null; trace?: { retrieval_ms: number; retrieval_query?: string; history_turns_used?: number; history_used_for_retrieval?: boolean; answer_style?: string; response_strategy?: string; generator?: string; reranker?: string; adapter?: boolean; generated_tokens?: number; tokens_per_second?: number; peak_mlx_memory_gb?: number } };
export type ConversationTurn = { question: string; answer: string };
type Turn = { question: string; result?: Result; error?: string };
export type Status = { sources: Source[]; corpus_sha256: string; mode: string; backend: string; section_count: number; chunk_count: number; law_count: number; answer_style?: string; version_dates: string[]; collection: { label: string; scope: string; currency_notice: string; dataset: string; revision: string; license: string; license_url: string } };
export type Evaluation = { corpus_sha256: string; metrics: Record<string, number>; results: { id: string; question: string; answerable: boolean; abstained: boolean; retrieval_hit_at_1: boolean | null }[] };
export type AssistantClient = { status: () => Promise<Status>; evaluation: () => Promise<Evaluation>; ask: (question: string, signal: AbortSignal, history?: ConversationTurn[]) => Promise<Result> };

async function requestJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  const data = await response.json() as T & { error?: string };
  if (!response.ok) throw new Error(data.error || "Could not load the assistant. Please try again.");
  return data;
}

const httpClient: AssistantClient = {
  status: () => requestJSON<Status>("/api/status"),
  evaluation: () => requestJSON<Evaluation>("/api/evaluation"),
  ask: (question, signal, history) => requestJSON<Result>("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, ...(history?.length ? { history } : {}) }), signal }),
};
const suggestions = [
  { title: "Consumer guarantees", question: "Under section 54, what factors determine whether goods are of acceptable quality?", icon: ShieldCheck, detail: "What quality should I expect from goods?", color: "lime" },
  { title: "Repairs & refunds", question: "What are the consequences of rejecting goods, including a refund or replacement?", icon: ArrowDownToLine, detail: "What happens when I reject faulty goods?", color: "lavender" },
  { title: "Misleading conduct", question: "What does section 18 say about misleading or deceptive conduct?", icon: Scale, detail: "What does the law say about misleading conduct?", color: "peach" },
];

function formatDate(value?: string) {
  return value ? new Date(`${value}T00:00:00Z`).toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }) : "Loading…";
}

export default function Home({ client = httpClient, homeHref = "/" }: { client?: AssistantClient; homeHref?: string } = {}) {
  const [view, setView] = useState<"assistant" | "sources" | "evaluation">("assistant");
  const [status, setStatus] = useState<Status | null>(null);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [loadError, setLoadError] = useState("");
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<Source | null>(null);
  const [copied, setCopied] = useState<number | null>(null);
  const [sourceQuery, setSourceQuery] = useState("");
  const input = useRef<HTMLTextAreaElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const modal = useRef<HTMLElement>(null);
  const sourceTrigger = useRef<HTMLElement | null>(null);
  const newest = turns.at(-1)?.result;
  const supported = evaluation?.results.filter((row) => row.answerable) ?? [];
  const unsupported = evaluation?.results.filter((row) => !row.answerable) ?? [];
  const sourceCount = status?.section_count ?? 0;
  const versionDate = formatDate(status?.version_dates[0]);
  const previewSources = newest?.evidence.length
    ? [...new Map(newest.evidence.map((source) => [source.id, source])).values()]
    : ["acl-s54", "acl-s263", "acl-s18"].map((id) => status?.sources.find((source) => source.id === id)).filter((source): source is Source => Boolean(source));
  const librarySources = status?.sources.filter((source) => `${source.section_number} ${source.section_heading}`.toLowerCase().includes(sourceQuery.toLowerCase())) ?? [];

  useEffect(() => {
    Promise.all([client.status(), client.evaluation()]).then(([s, e]) => {
      setStatus(s); setEvaluation(e);
    }).catch((error) => setLoadError(error.message));
  }, [client]);
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
  useEffect(() => { if (turns.length) end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns]);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "k") { event.preventDefault(); setView("assistant"); requestAnimationFrame(() => input.current?.focus()); }
      if (event.key === "Escape") setSelected(null);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  function reset() {
    if (busy) return;
    setTurns([]); setQuestion(""); setView("assistant");
    requestAnimationFrame(() => input.current?.focus());
  }
  function openSource(source: Source) { sourceTrigger.current = document.activeElement as HTMLElement; setSelected(source); }

  async function submit(value = question) {
    const text = value.trim();
    if (!text || busy) return;
    setView("assistant"); setBusy(true); setQuestion(""); setTurns((old) => [...old, { question: text }]);
    try {
      const history = status?.mode === "rag" ? turns.filter(turn => turn.result).slice(-3).map(turn => ({ question: turn.question, answer: turn.result!.answer.slice(0, 4000) })) : [];
      const data = await client.ask(text, AbortSignal.timeout(status?.mode === "rag" ? 180000 : 15000), history);
      setTurns((old) => [...old.slice(0, -1), { question: text, result: data }]);
    } catch (error) {
      setTurns((old) => [...old.slice(0, -1), { question: text, error: error instanceof Error ? error.message : "Connection failed. Please try again." }]);
    } finally { setBusy(false); }
  }
  async function copy(turn: Turn, index: number) {
    try {
      await navigator.clipboard.writeText(`${turn.question}\n\n${turn.result?.answer}\n\n${turn.result?.scope_note ? turn.result.scope_note + "\n\n" : ""}${turn.result?.evidence.map((source, i) => `[${i + 1}] ${source.title}: ${source.url}`).join("\n")}`);
      setCopied(index); window.setTimeout(() => setCopied(null), 2000);
    } catch { setLoadError("Clipboard access is unavailable. Select the passages to copy them."); }
  }
  function download() {
    const blob = new Blob([JSON.stringify({ exported_at: new Date().toISOString(), corpus_sha256: status?.corpus_sha256, turns }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = "regulatory-research.json"; a.click(); URL.revokeObjectURL(url);
  }

  const composer = <div className={`composer-area ${turns.length ? "in-conversation" : ""}`}>
    <form className="composer" onSubmit={(event) => { event.preventDefault(); submit(); }}>
      <label htmlFor="question" className="sr-only">Ask about Australian consumer guidance</label>
      <textarea id="question" ref={input} value={question} maxLength={2000} onChange={(event) => setQuestion(event.target.value)} placeholder="What would you like to understand?" rows={2} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); submit(); } }}/>
      <div className="composer-bottom"><button type="button" className="corpus-selector" onClick={() => setView("sources")}><Layers size={14}/><span>Consumer law</span><ChevronDown size={12}/></button><span className="composer-mode"><span/> {status?.mode === "rag" ? "Local AI · Hybrid RAG" : "Evidence search"}</span><div className="composer-controls"><span className="keyboard-hint">{question.length > 1800 ? `${question.length}/2000` : "Enter ↵"}</span><button type="submit" className="send-button" disabled={!question.trim() || busy} aria-label="Send question">{busy ? <LoaderCircle size={19} className="spin"/> : <ArrowUpRight size={22}/>}</button></div></div>
    </form><div className="composer-note"><ShieldCheck size={12}/> Grounded in sources. General guidance, not legal advice.</div>
  </div>;

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href={homeHref} aria-label="Australian Regulatory Assistant home"><span className="brand-mark"><AudioLines size={25} strokeWidth={1.6}/></span><span>regulatory<span className="brand-period">.</span></span></a>
      <div className="workspace-switch"><span className="workspace-avatar">R</span><div>Research workspace<small>PERSONAL PROJECT</small></div><span className="workspace-badge">AU</span></div>
      <button className="new-research" disabled={busy} onClick={reset}><Plus size={17}/> New research <span>⌘ K</span></button>
      <div className="nav-label">EXPLORE</div><nav aria-label="Main navigation">
        <button className={view === "assistant" ? "nav-item active" : "nav-item"} onClick={() => setView("assistant")}><MessageSquare size={17}/> Assistant <span className="active-indicator"/></button>
        <button className={view === "sources" ? "nav-item active" : "nav-item"} onClick={() => setView("sources")}><BookOpen size={17}/> Source library <span className="count">{sourceCount || "–"}</span></button>
        <button className={view === "evaluation" ? "nav-item active" : "nav-item"} onClick={() => setView("evaluation")}><SlidersHorizontal size={17}/> Evaluation <ArrowUpRight size={14}/></button>
      </nav>
      <div className="session-section"><div className="nav-label">THIS SESSION <span>{turns.length.toString().padStart(2, "0")}</span></div>{turns.length ? <div className="session-list">{turns.slice(-5).map((turn, index) => <button key={index} onClick={() => { setView("assistant"); requestAnimationFrame(() => document.getElementById(`turn-${Math.max(0, turns.length - 5) + index}`)?.scrollIntoView({ behavior: "smooth" })); }}><MessageSquare size={12}/><span>{turn.question}</span></button>)}</div> : <div className="session-empty"><span className="session-line"/><p>A fresh perspective<br/>starts with a question.</p></div>}</div>
      <div className="sidebar-bottom"><div className="collection-status"><div className="collection-status-heading"><span className="status-dot"/><span>{status ? "Collection connected" : "Connecting collection"}</span><span className="signal-bars"><i/><i/><i/><i/></span></div><p>Australian Consumer Law · Commonwealth</p><div className="collection-foot"><span>{sourceCount || "…"} statutory sections</span><button onClick={() => setView("sources")} aria-label="Open collection details"><ArrowUpRight size={15}/></button></div></div><a className="github-link" href="https://github.com/SatyamPalkar/Australian-Regulatory-AI-Assistant" target="_blank" rel="noreferrer"><GitBranch size={15}/> Behind the project <ArrowUpRight size={14}/></a><div className="profile"><span className="profile-avatar">SP</span><div>Personal workspace<small>Australian Regulatory Assistant</small></div><span className="profile-plan">DEMO</span></div></div>
    </aside>

    <main className="main-content"><header className="topbar"><div className="breadcrumb"><span className="project-icon"><Fingerprint size={16}/></span> Your workspace <span className="breadcrumb-slash">/</span><strong>{view === "assistant" ? "Assistant" : view === "sources" ? "Source library" : "Evaluation"}</strong></div><div className="topbar-right"><span className="demo-badge"><span/> RESEARCH MODE</span><button className="mobile-new icon-button" onClick={reset} disabled={busy} aria-label="New research"><Plus size={18}/></button><button className="icon-button" aria-label="About this corpus" onClick={() => setView("sources")}><CircleHelp size={18}/></button></div></header>
      {loadError && <div className="error-banner" role="alert">{loadError}<button aria-label="Dismiss message" onClick={() => setLoadError("")}><X size={16}/></button></div>}

      {view === "assistant" && <div className={`chat-stage ${turns.length ? "has-conversation" : ""}`}>
        {!turns.length && <div className="welcome"><div className="hero-copy"><div className="eyebrow"><span className="mini-spark">✳</span> LESS GUESSWORK. MORE CLARITY.</div><h1>Complex rules.<br/><span>Clearer thinking.</span></h1><p>Real consumer-law text for Sydney and NSW research.<br/>Ask freely. Follow the evidence.</p><div className="hero-tags"><span><ShieldCheck size={12}/> Source grounded</span><span><BookOpen size={12}/> Versioned legislation</span></div></div><div className="orb-scene" aria-hidden="true"><div className="orb-grid"/><div className="orb-ring ring-one"/><div className="orb-ring ring-two"/><div className="orb-ring ring-three"/><div className="orb-core"><AudioLines size={51} strokeWidth={1.15}/></div><span className="orb-satellite satellite-one"/><span className="orb-satellite satellite-two"/><span className="orb-coordinate">33.8688° S / 151.2093° E</span><span className="orb-label">CONNECTED TO CONTEXT</span></div></div>}

        {!!turns.length && <section className="conversation" aria-label="Research conversation" aria-live="polite">{turns.map((turn, i) => <article className="turn" id={`turn-${i}`} key={i}><div className="question-row"><span className="user-avatar">SP</span><div><span className="message-label">YOU <span>/{String(i + 1).padStart(2, "0")}</span></span><h2>{turn.question}</h2></div></div><div className="answer-row"><span className="assistant-avatar"><AudioLines size={21}/></span><div className="answer-body"><div className="answer-heading">Regulatory <span className="answer-status"><span/>{turn.result?.abstained ? "Evidence unavailable" : turn.result?.mode === "source-quotes" ? "Source wording · fresh evidence" : (turn.result?.mode === "rag" || turn.result?.mode === "source-quotes") ? "AI answer · cited evidence" : "Evidence search"}</span></div>{!turn.result && !turn.error && <div className="loading"><span className="typing-dots"><i/><i/><i/></span> Connecting your question to the guidance…</div>}{turn.error && <div className="request-error" role="alert"><p>{turn.error}</p><button onClick={() => submit(turn.question)} disabled={busy}>Try again <ArrowRight size={13}/></button></div>}{turn.result && <>{turn.result.abstained ? <div className="abstention"><span className="abstention-icon"><Search size={23}/></span><h3>There isn’t enough support for an answer.</h3><p>I couldn’t produce an adequately cited answer from this snapshot. Explore the original statutory text, or ask a more specific question about consumer guarantees and remedies.</p><button onClick={() => setView("sources")}>Explore the source library <ArrowUpRight size={15}/></button></div> : <>{turn.result.scope_note && <p className="answer-scope">{turn.result.scope_note}</p>}{(turn.result?.mode === "rag" || turn.result?.mode === "source-quotes") && <div className="generated-answer" aria-label="Generated answer">{turn.result.answer.split(/\n\n+/).filter(Boolean).map((paragraph, j) => <p key={j}>{paragraph.split(/(\[\d+\])/).map((part, c) => { const match = part.match(/^\[(\d+)\]$/); const source = match ? turn.result?.evidence[Number(match[1]) - 1] : undefined; return source ? <button className="inline-citation" key={c} onClick={() => openSource(source)} aria-label={`Open cited source ${match?.[1]}`}>{part}</button> : part; })}</p>)}</div>}<p className="evidence-intro">Relevant statutory extracts from the Australian Consumer Law. Check the full provision and later amendments before relying on it.</p>{turn.result.evidence.map((source, n) => <div className="evidence-passage" key={source.chunk_id}><div className="passage-header"><span><FileText size={13}/> STATUTORY TEXT</span><button className="citation" aria-label={`View source ${n + 1}: ${source.title}`} onClick={() => openSource(source)}>SOURCE {n + 1} <ArrowUpRight size={12}/></button></div>{(turn.result?.mode === "rag" || turn.result?.mode === "source-quotes") ? <details className="retrieved-text"><summary>{source.evidence_span === "full_section" ? "Read complete statutory section" : "Read retrieved passage"} · {source.text?.split(/\s+/).length} words</summary><p>{source.text}</p></details> : <p>{source.text}</p>}<a href={source.url} target="_blank" rel="noreferrer">{source.title}<ExternalLink size={12}/></a></div>)}<div className="answer-caveat"><CircleHelp size={13}/><span>Related evidence may not answer every part of your question. Check the original for full context.</span></div></>}{turn.result.trace && <details className="generation-trace"><summary>How this answer was produced</summary>{turn.result.trace.response_strategy === "source_quotes" && <p>Verbatim source quotation; model generation skipped for this follow-up.</p>}{Boolean(turn.result.trace.history_turns_used) && <p>Conversation context: {turn.result.trace.history_turns_used} recent turns · fresh source evidence retrieved for this answer</p>}{turn.result.trace.retrieval_query && turn.result.trace.retrieval_query !== turn.question && <p>Search interpretation: {turn.result.trace.retrieval_query}</p>}<p>Retrieval: {turn.result.trace.retrieval_ms.toFixed(0)} ms · Reranker: {turn.result.trace.reranker}</p><p>Generator: {turn.result.trace.generator ?? "None"}{turn.result.trace.adapter ? " · LoRA adapter" : ""}</p>{Boolean(turn.result.trace.generated_tokens) && <p>{turn.result.trace.generated_tokens} output tokens · {turn.result.trace.tokens_per_second?.toFixed(1)} tokens/s · {turn.result.trace.peak_mlx_memory_gb?.toFixed(2)} GB peak MLX allocation</p>}<p>Citations passed structural checks. Factual support has not been independently verified.</p></details>}<div className="answer-actions"><button onClick={() => copy(turn, i)} aria-label="Copy answer">{copied === i ? <Check size={14}/> : <Copy size={14}/>} {copied === i ? "Copied" : (turn.result?.mode === "rag" || turn.result?.mode === "source-quotes") ? "Copy answer" : "Copy evidence"}</button><span>{turn.result.evidence.length} source{turn.result.evidence.length === 1 ? "" : "s"}<i/>{turn.result.latency_ms >= 1000 ? `${(turn.result.latency_ms / 1000).toFixed(1)} s` : `${turn.result.latency_ms.toFixed(1)} ms`} {(turn.result?.mode === "rag" || turn.result?.mode === "source-quotes") ? "total" : "retrieval"}</span>{i === turns.length - 1 && <button onClick={download} aria-label="Export research"><ArrowDownToLine size={14}/> Export</button>}</div></>}</div></div></article>)}<div ref={end}/></section>}

        {status?.answer_style === "explain" && <p className="answer-scope" role="status">Experimental explanatory mode: source review found factual errors. Check each claim against the cited provision.</p>}
        {composer}

        {!turns.length && <section className="quick-starts" aria-label="Suggested questions"><div className="section-kicker"><span>FOLLOW YOUR CURIOSITY</span><span>TRY A QUESTION <ArrowDownToLine size={10}/></span></div><div className="suggestion-grid">{suggestions.map(({ title, question: text, icon: Icon, detail, color }) => <button key={title} className={`suggestion ${color}`} disabled={busy} onClick={() => submit(text)}><span className="suggestion-icon"><Icon size={18} strokeWidth={1.6}/></span><span className="suggestion-title">{title}</span><strong>{detail}</strong><ArrowUpRight size={16} className="suggestion-arrow"/></button>)}</div></section>}

        <section className="evidence-shelf" aria-label="Evidence sources"><div className="shelf-heading"><div><span className="shelf-dot"/><h2>{newest?.evidence.length ? "Connected evidence" : "Good answers start with good sources."}</h2></div><button onClick={() => setView("sources")}>Source library <ArrowUpRight size={13}/></button></div><div className="source-list">{previewSources.map((source) => <button className="source-card" key={source.id} onClick={() => openSource(source)}><span className="document-icon"><FileText size={17}/></span><div><span className="source-publisher">ACL <span> / s {source.section_number}</span></span><h3>{source.section_heading}</h3></div><ArrowUpRight size={14}/></button>)}</div><p className="currency-note"><CircleHelp size={12}/>{status?.collection.currency_notice}</p><p className="scope-note">Selected national consumer-law provisions · {sourceCount || "…"} sections · compilation {versionDate}. Check the original law for updates.</p></section>
      </div>}

      {view === "sources" && <section className="content-page"><div className="eyebrow"><BookOpen size={14}/> THE SOURCE OF CLARITY</div><h1>The evidence.<br/><span>Nothing behind the curtain.</span></h1><p className="page-description">{sourceCount || "…"} actual statutory sections, imported from Hugging Face.<br/>National consumer law for research in Sydney and NSW.</p><div className="collection-banner"><div><span className="collection-banner-icon"><ShieldCheck size={22}/></span><div><strong>Australian Consumer Law · Schedule 2</strong><p>Source compilation {versionDate} · {status?.chunk_count ?? "…"} retrieval chunks</p></div></div><span className="tiny-pill">COMMONWEALTH / AU</span></div><p className="currency-note"><CircleHelp size={14}/>{status?.collection.currency_notice}</p><label className="library-search"><Search size={16}/><input type="search" aria-label="Search statutory sections" placeholder="Search by section number or subject…" value={sourceQuery} onChange={(event) => setSourceQuery(event.target.value)}/><span>{librarySources.length} sections</span></label><div className="library-grid">{librarySources.map((source) => <article className="library-card" key={source.id}><div className="library-card-top"><FileText size={23}/><span>s {source.section_number}</span></div><span className="source-publisher">STATUTORY EXTRACT · ACL</span><h2>{source.section_heading}</h2><div className="library-meta"><span>Section {source.section_number}</span><span>{source.word_count} words</span></div><a href={source.url} target="_blank" rel="noreferrer">Read statutory source <ArrowUpRight size={16}/></a></article>)}</div><div className="method-note"><Fingerprint size={21}/><div><h2>Traceable by design.</h2><p>Imported from cchew/lex-au at a pinned dataset revision. Copyright Commonwealth of Australia; dataset conversion by cchew, licensed CC BY 4.0. This project selects sections, removes XML markup and normalises whitespace. Coverage is selected Commonwealth law, including consumer guarantees, misleading conduct, unfair terms and remedies. State-only statutes and practical NSW complaint guidance are outside this collection.</p><a className="text-link" href="https://huggingface.co/datasets/cchew/lex-au" target="_blank" rel="noreferrer">View the Hugging Face dataset <ArrowUpRight size={14}/></a><a className="text-link" href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">CC BY 4.0 attribution licence <ArrowUpRight size={14}/></a><p className="hash-label">CORPUS FINGERPRINT <code>{status?.corpus_sha256.slice(0, 16) ?? "Loading…"}</code></p></div></div></section>}

      {view === "evaluation" && <section className="content-page"><Phase2Panel/><ExperimentPanel/><div className="eyebrow"><SlidersHorizontal size={14}/> LOOK UNDER THE HOOD</div><h1>Evidence for<br/><span>the evidence.</span></h1><p className="page-description">A saved development run over {evaluation?.metrics.questions ?? "…"} questions on the active corpus.<br/>The successes, the gaps, and everything we still need to learn.</p><div className="metrics-grid"><div className="metric"><span>SOURCE RANKED FIRST</span><strong>{evaluation ? `${supported.filter((row) => row.retrieval_hit_at_1).length}` : "–"}<small> / {supported.length || "…"}</small></strong><p>Supported development questions</p><div className="metric-bar"><i style={{ width: evaluation ? `${evaluation.metrics.retrieval_hit_at_1 * 100}%` : "0" }}/></div></div><div className="metric lavender"><span>UNSUPPORTED DECLINED</span><strong>{evaluation ? `${unsupported.filter((row) => row.abstained).length}` : "–"}<small> / {unsupported.length || "…"}</small></strong><p>One known answerability failure</p><div className="metric-bar"><i style={{ width: evaluation ? `${evaluation.metrics.unsupported_abstention_rate * 100}%` : "0" }}/></div></div><div className="metric peach"><span>REFERENCE FORMAT CHECKS</span><strong>{evaluation ? Math.round(evaluation.metrics.citation_format_pass_rate * 100) : "–"}<small>%</small></strong><p>Syntax checks, not factual accuracy</p><div className="metric-bar"><i style={{ width: evaluation ? `${evaluation.metrics.citation_format_pass_rate * 100}%` : "0" }}/></div></div></div><div className="evaluation-table"><div className="table-heading"><h2>Question by question</h2><span className="tiny-pill">DEVELOPMENT SET / {evaluation?.metrics.questions ?? "…"}</span></div>{evaluation?.results.map((row) => <div className="evaluation-row" key={row.id}><span className={row.answerable ? "question-type" : "question-type unsupported"}>{row.answerable ? "In scope" : "Unsupported"}</span><p>{row.question}</p><span className={(row.answerable ? row.retrieval_hit_at_1 : row.abstained) ? "result-pass" : "result-fail"}>{row.answerable ? row.retrieval_hit_at_1 ? "Source found" : "Missed" : row.abstained ? "Declined" : "Needs review"}</span></div>)}</div><div className="method-note"><CircleHelp size={21}/><div><h2>The limits belong in the picture.</h2><p>These inspected development questions are not a held-out benchmark. The corpus contains multiple chunks per statutory section. Related passages may not answer a question, as the unsupported development examples show. Correct citation numbers do not prove factual support. Human review and a frozen test set are required before comparing fine-tuning results.</p><a className="text-link" href="https://github.com/SatyamPalkar/Australian-Regulatory-AI-Assistant/blob/main/reports/consumer-law-baseline.json" target="_blank" rel="noreferrer">Inspect the full report <ArrowUpRight size={14}/></a></div></div></section>}

      <footer className="main-footer"><span><span/> AUSTRALIAN REGULATORY ASSISTANT</span><span>Stay curious. Check your sources. <span className="footer-star">✳</span></span></footer>
    </main>
    {selected && <div className="modal-backdrop" onClick={() => setSelected(null)}><section ref={modal} className="source-modal" role="dialog" aria-modal="true" aria-labelledby="source-title" onClick={(event) => event.stopPropagation()}><button className="modal-close icon-button" aria-label="Close source details" onClick={() => setSelected(null)} autoFocus><X size={20}/></button><span className="modal-document"><FileText size={28}/></span><div className="eyebrow">STATUTORY EXTRACT / AUSTRALIAN CONSUMER LAW</div><h2 id="source-title">{selected.title}</h2><p>A statutory extract imported from a pinned Hugging Face dataset. Source compilation: {formatDate(selected.version_date)}. This is a dataset conversion; use the official register to check full context and later amendments.</p><dl><div><dt>Publisher</dt><dd>{selected.publisher}</dd></div><div><dt>Jurisdiction</dt><dd>{selected.jurisdiction}</dd></div><div><dt>Source version</dt><dd>{formatDate(selected.version_date)}</dd></div><div><dt>Compilation</dt><dd>{selected.compilation_id}</dd></div><div><dt>Dataset</dt><dd><a href={selected.dataset_file_url} target="_blank" rel="noreferrer">{selected.dataset} ↗</a></dd></div><div><dt>Dataset revision</dt><dd className="revision-value">{selected.dataset_revision}</dd></div><div><dt>Licence</dt><dd><a href={selected.license_url} target="_blank" rel="noreferrer">{selected.license} ↗</a></dd></div>{selected.score !== undefined && <div><dt>Retrieval similarity</dt><dd>{selected.score.toFixed(3)} · relevance, not confidence</dd></div>}</dl>{selected.text && <details><summary>Read the retrieved statutory passage</summary><p>{selected.text}</p></details>}<a className="primary-link" href={selected.url} target="_blank" rel="noreferrer">Read statutory source <ArrowUpRight size={16}/></a><a className="text-link" href={selected.current_source_url} target="_blank" rel="noreferrer">Check the latest official version <ArrowUpRight size={14}/></a></section></div>}
  </div>;
}
