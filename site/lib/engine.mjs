import corpus from "./corpus.json" with { type: "json" };

export const ABSTENTION = "I don't have enough evidence in the indexed documents to answer this question.";
const stop = new Set(corpus.stop_words);
const terms = (text) => (text.toLowerCase().match(/[a-z]+/g) ?? []).filter((word) => !stop.has(word));

export function retrieve(question, k = 3) {
  if (typeof question !== "string" || !question.trim() || question.trim().length > 2000) {
    throw new Error("Enter a question between 1 and 2,000 characters.");
  }
  if (!Number.isInteger(k) || k < 1 || k > 3) throw new Error("Top k must be between 1 and 3.");
  const counts = new Map();
  for (const word of terms(question)) counts.set(word, (counts.get(word) ?? 0) + 1);
  const query = Object.fromEntries([...counts].filter(([word]) => Object.hasOwn(corpus.idf, word))
    .map(([word, count]) => [word, (1 + Math.log(count)) * corpus.idf[word]]));
  const norm = Math.sqrt(Object.values(query).reduce((total, n) => total + n * n, 0)) || 1;
  return corpus.chunks.map((chunk, i) => ({ ...chunk,
    score: Object.entries(query).reduce((total, [word, value]) => total + value / norm * (corpus.vectors[i][word] ?? 0), 0),
  })).sort((a, b) => b.score - a.score).slice(0, k).map((chunk) => ({ ...chunk, score: Number(chunk.score.toFixed(6)) }));
}

export function ask(question) {
  const retrieved = retrieve(question);
  const evidence = retrieved.filter((hit) => hit.score >= 0.16);
  return { answer: evidence.length ? "Relevant passages from the local corpus (answerability has not been verified):\n\n" +
      evidence.map((hit, i) => `${hit.text} [${i + 1}]`).join("\n\n") : ABSTENTION,
    abstained: !evidence.length, evidence, retrieved, citation_format_valid: true, mode: "extractive" };
}

export function status() {
  return { status: "ok", mode: "extractive", backend: "tfidf", corpus_sha256: corpus.corpus_sha256,
    sources: corpus.chunks.map(({ text, ...source }) => ({ ...source, word_count: text.split(/\s+/).length })),
    limitations: "Three project-authored summaries of ACCC guidance. Related passages may not answer your question. No language model or fine-tuned adapter is running in this deployment." };
}
