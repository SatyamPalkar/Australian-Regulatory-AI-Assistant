import { status } from "@/lib/engine.mjs";
export function GET() { return Response.json(status(), { headers: { "Cache-Control": "no-store" } }); }
