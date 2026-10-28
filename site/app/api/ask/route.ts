import { ask } from "@/lib/engine.mjs";

export async function POST(request: Request) {
  const origin = request.headers.get("origin");
  if (origin && origin !== new URL(request.url).origin) return Response.json({ error: "Requests must come from this application." }, { status: 403 });
  if (!request.headers.get("content-type")?.includes("application/json")) return Response.json({ error: "Send an application/json request." }, { status: 415 });
  try {
    const text = await request.text();
    if (text.length > 10000) return Response.json({ error: "Request too large." }, { status: 413 });
    const body = JSON.parse(text);
    if (body === null || typeof body !== "object" || typeof body.question !== "string" || !body.question.trim() || body.question.trim().length > 2000) {
      return Response.json({ error: "Enter a question between 1 and 2,000 characters." }, { status: 400 });
    }
    const start = performance.now();
    return Response.json({ ...ask(body.question.trim()), latency_ms: Math.round((performance.now() - start) * 100) / 100 }, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    if (error instanceof SyntaxError) return Response.json({ error: "Invalid JSON." }, { status: 400 });
    console.error("Retrieval request failed");
    return Response.json({ error: "The assistant could not complete this request. Please try again." }, { status: 500 });
  }
}
