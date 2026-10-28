"use client";
import experiment from "../lib/experiments.json";

type Run = { mode: string; metrics: Record<string, number | null>; report: string };
const labels: Record<string, string> = { tfidf: "TF-IDF baseline", hybrid: "Hybrid + reranker", "base-rag": "Base model + RAG", "adapter-rag": "LoRA model + RAG" };
const percentage = (n: number | null | undefined) => n == null ? "—" : `${Math.round(n * 100)}%`;

export default function ExperimentPanel() {
  const runs = experiment.runs as Run[];
  if (!runs.length) return null;
  return <section className="experiment-panel" aria-label="Frozen model experiment">
    <div className="eyebrow">FROZEN EXPERIMENT / {runs[0].metrics.questions} QUESTIONS</div>
    <h2>Measure the model, keep the failures.</h2>
    <p>Same questions and corpus across every run. Test source sections are separate from training sections. These synthetic questions have not received independent legal review.</p>
    <div className="experiment-scroll"><table><thead><tr><th>Pipeline</th><th>Source in top 3</th><th>Supported answered</th><th>Unsupported declined</th><th>Median latency</th><th>Peak MLX memory</th></tr></thead><tbody>{runs.map(run => <tr key={run.mode}><th><a href={`https://github.com/SatyamPalkar/Australian-Regulatory-AI-Assistant/blob/main/${run.report}`} target="_blank" rel="noreferrer">{labels[run.mode] ?? run.mode} ↗</a></th><td>{percentage(run.metrics.retrieval_hit_at_3)}</td><td>{percentage(run.metrics.answerable_response_rate)}</td><td>{percentage(run.metrics.unsupported_abstention_rate)}</td><td>{run.metrics.p50_latency_ms == null ? "—" : `${(run.metrics.p50_latency_ms / 1000).toFixed(2)} s`}</td><td>{run.metrics.peak_mlx_memory_gb ? `${run.metrics.peak_mlx_memory_gb.toFixed(2)} GB` : "—"}</td></tr>)}</tbody></table></div>
    <p className="experiment-limit">Source retrieval and response rates do not measure factual correctness. Citation entailment and factual accuracy await human review. MLX memory covers its allocator, not total system memory. First requests include cold loading; measured on one M3 Pro.</p>
  </section>;
}
