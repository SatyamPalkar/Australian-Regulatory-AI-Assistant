import { policyAnswer } from "../lib/retailer-policy.mjs";
import { ask, status } from "../lib/engine.mjs";
import evaluation from "../lib/evaluation.json" with { type: "json" };
import type { AssistantClient, Evaluation, Result, Status } from "../app/page";

// The Pages build has the same data and retrieval algorithm as the Worker API.
// Queries are handled entirely within the visitor's browser.
export const browserClient: AssistantClient = {
  status: async () => status() as Status,
  evaluation: async () => evaluation as Evaluation,
  ask: async (question, signal, history) => {
    signal.throwIfAborted();
    const start = performance.now();
    const result = await policyAnswer(question, history) ?? ask(question);
    return { ...result, latency_ms: Math.round((performance.now() - start) * 100) / 100 } as Result;
  },
};
