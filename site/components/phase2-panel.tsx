"use client";
import phase2 from "../lib/phase2.json";

export default function Phase2Panel() {
  return <section className="experiment-panel" aria-label="Conversation and explanation experiment">
    <div className="eyebrow">PHASE TWO / CONVERSATION &amp; EXPLANATIONS</div>
    <h2>More context. A measured experiment.</h2>
    <p>The local AI can use up to three recent conversation turns and retrieves fresh evidence for each answer. Dependent follow-ups quote the strongest fresh provision in the default profile. The browser-only demo handles questions independently.</p>
    <p><strong>The original adapter remains the default.</strong> The new adapter improved explanation structure, but source review caught factual errors. It is available for experimental comparison.</p>
    <div className="experiment-scroll"><table><thead><tr><th>Adapter</th><th>Supported answered</th><th>Three-part cited explanation</th><th>Qualification keyword coverage</th><th>Unsupported declined</th></tr></thead><tbody>{phase2.runs.map(run => <tr key={run.mode}><th><a href={`https://github.com/SatyamPalkar/Australian-Regulatory-AI-Assistant/blob/main/${run.report}`} target="_blank" rel="noreferrer">{run.mode === "v1-explain" ? "Original · explanatory prompt" : "New · explanatory prompt"} ↗</a></th>{["supported_response_rate", "structured_explanation_rate", "qualification_term_coverage", "unsupported_abstention_rate"].map(key => <td key={key}>{Math.round((run.metrics as Record<string, number | null>)[key]! * 100)}%</td>)}</tr>)}</tbody></table></div>
    <p className="experiment-limit">16 synthetic test questions. Structure and keywords are proxies, not factual accuracy. Both adapters received the same explanatory prompt and context settings. Training took {phase2.training.elapsed_seconds.toFixed(1)} s with {phase2.training.peak_mlx_memory_gb.toFixed(2)} GB peak MLX allocation.</p>
  </section>;
}
