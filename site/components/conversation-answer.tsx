import { Copy, Check } from "lucide-react";
import type { Result } from "../app/page";

export default function ConversationAnswer({ result, copied, onCopy, onQuestion, onReset, busy }: {
  result: Result; copied: boolean; onCopy: () => void; onQuestion: (question: string) => void; onReset: () => void; busy: boolean;
}) {
  return <>
    <div className="generated-answer" aria-label="Conversational response">{result.answer.split(/\n\n+/).map((text, i) => <p key={i}>{text}</p>)}</div>
    {!!result.quick_actions?.length && <div className="answer-actions">{result.quick_actions.map(action => <button disabled={busy} key={action.question} onClick={() => onQuestion(action.question)}>{action.label}</button>)}<button disabled={busy} onClick={onReset}>Start new research</button></div>}
    <p className="answer-scope">{result.scope_note}</p>
    <details className="generation-trace"><summary>How this answer was produced</summary>{result.trace?.response_strategy === "runtime_facts" ? <p>The local instruction model selected app information. Model names, load states, source coverage and policy-fetch status were read from the running server and formatted directly; the model did not generate these facts. No statutory or policy search was performed.</p> : <p>The local instruction model interpreted the question and recent conversation before retrieval. This response {result.trace?.response_strategy === "clarify" ? "asks for clarification" : result.trace?.response_strategy === "recovery" ? "offers concrete tasks after an unresolved clarification" : "responds to the conversation"}; no statutory or policy search was performed.</p>}<p>{result.trace?.session_turn ? `Session turn ${result.trace.session_turn} · ` : ""}{result.trace?.controller_ms?.toFixed(0)} ms · No LoRA adapter used for conversation.</p></details>
    <div className="answer-actions"><button onClick={onCopy}>{copied ? <Check size={14}/> : <Copy size={14}/>} {copied ? "Copied" : "Copy answer"}</button><span>Conversation · no retrieved sources</span></div>
  </>;
}
