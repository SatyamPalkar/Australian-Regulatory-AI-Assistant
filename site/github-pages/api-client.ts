import type { AssistantClient, Result, Status, Evaluation } from "../app/page";

export function validateEndpoint(value: string): string {
  const url = new URL(value.trim());
  const loopback = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  if ((url.protocol !== "https:" && !(url.protocol === "http:" && loopback)) || url.username || url.password || url.search || url.hash || url.pathname !== "/") {
    throw new Error("Use an HTTPS origin or a local address such as http://127.0.0.1:8000");
  }
  return url.origin;
}

export function apiClient(endpoint: string): AssistantClient {
  const origin = validateEndpoint(endpoint);
  async function request<T>(path: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${origin}${path}`, options);
    const data = await response.json() as { detail?: unknown };
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "The local AI request failed. Check that the server and models are ready.");
    return data as T;
  }
  return {
    status: () => request<Status>("/api/status"),
    evaluation: () => request<Evaluation>("/api/evaluation"),
    ask: (question, signal, history, conversationId) => request<Result>("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, ...(history?.length ? { history } : {}), ...(conversationId ? { conversation_id: conversationId } : {}) }), signal }),
  };
}
