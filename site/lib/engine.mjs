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
  const words = [...new Set(terms(question))];
  const coverage = words.length ? words.filter((word) => Object.hasOwn(corpus.idf, word)).length / words.length : 0;
  const evidence = coverage >= corpus.min_query_coverage ? retrieved.filter((hit) => hit.score >= 0.16) : [];
  return { answer: evidence.length ? "Relevant passages from the local corpus (answerability has not been verified):\n\n" +
      evidence.map((hit, i) => `${hit.text} [${i + 1}]`).join("\n\n") : ABSTENTION,
    abstained: !evidence.length, evidence, retrieved, citation_format_valid: true, mode: "extractive" };
}

export function status() {
  return { status: "ok", mode: "extractive", backend: "tfidf", corpus_sha256: corpus.corpus_sha256,
    sources: corpus.sources,
    collection: corpus.collection,
    section_count: corpus.sources.length,
    chunk_count: corpus.chunks.length,
    law_count: new Set(corpus.sources.map((source) => source.law_id)).size,
    version_dates: [...new Set(corpus.sources.map((source) => source.version_date))],
    limitations: "Selected statutory extracts from a pinned Hugging Face dataset. Version dates describe the source compilation, not a guarantee of current law. Related passages may not answer the question. No language model is running in this deployment." };
}
