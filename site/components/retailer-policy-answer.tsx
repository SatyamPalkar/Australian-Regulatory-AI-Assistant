import { ArrowDownToLine, ArrowUpRight, Copy, Check, FileText } from "lucide-react";
import type { Result } from "../app/page";

export default function RetailerPolicyAnswer({ result, copied, onCopy, onExport }: {
  result: Result; copied: boolean; onCopy: () => void; onExport?: () => void;
}) {
  const lookup = result.policy_lookup;
  const fetched = result.evidence[0]?.fetched_at;
  return <>
    <p className="answer-scope">{result.scope_note}</p>
    <div className="generated-answer" aria-label="Retailer policy context">
      {result.answer.split(/\n\n+/).map((paragraph, i) => <p key={i}>{paragraph.split(/(\[\d+\])/).map((part, j) => {
        const citation = part.match(/^\[(\d+)\]$/);
        return citation ? <a className="inline-citation" key={j} href={result.evidence[Number(citation[1]) - 1]?.url} target="_blank" rel="noreferrer">{part}</a> : part;
      })}</p>)}
    </div>
    <div className="evidence-passage"><div className="passage-header"><span><FileText size={13}/> OFFICIAL RETAILER POLICY</span><span>{lookup?.status === "fetched" ? "FETCHED ONLINE" : "LOOKUP NEEDED"}</span></div>
      <p>{fetched ? `Retrieved ${new Date(fetched).toLocaleString("en-AU")}. Conditions may change; check the original before acting.` : lookup?.status === "requires_api" ? "Connect the local API for live policy retrieval. The browser-only demo has no policy snapshot." : "The official policy could not be verified on this request. No policy terms have been inferred."}</p>
      {result.evidence.map((source, i) => <details className="retrieved-text" key={source.id}><summary>Read policy excerpt [{i + 1}]</summary><p>{source.text}</p></details>)}
      <a href={lookup?.url} target="_blank" rel="noreferrer">JB Hi-Fi — Refunds & Warranties guide <ArrowUpRight size={14}/></a>
    </div>
    <details className="generation-trace"><summary>How this answer was produced</summary><p>Official retailer-policy routing · {result.latency_ms.toFixed(0)} ms. {result.evidence.length} excerpts retrieved. {result.trace?.controller_ms !== undefined ? `The ${result.trace?.inference_provider === "groq" ? "Groq-hosted" : "local"} instruction model selected the policy tool; the answer uses source excerpts. ` : "Model generation was not used. "}Statutory reranking was not used. No conversation text was sent to the retailer.</p><p>These excerpts provide context; they do not determine eligibility for your particular purchase.</p></details>
    <div className="answer-actions"><button onClick={onCopy}>{copied ? <Check size={14}/> : <Copy size={14}/>} {copied ? "Copied" : "Copy answer"}</button><span>{result.evidence.length ? "1 official policy" : "Policy not verified"}</span>{onExport && <button onClick={onExport}><ArrowDownToLine size={14}/> Export</button>}</div>
  </>;
}
