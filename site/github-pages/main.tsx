import { createRoot } from "react-dom/client";
import { useMemo, useState } from "react";
import Home from "../app/page";
import { browserClient } from "./browser-client";
import { apiClient, validateEndpoint } from "./api-client";
import "../app/globals.css";

const root = document.getElementById("root");
if (!root) throw new Error("The application root is missing");

declare global { interface Window { REGULATORY_API_BASE?: string } }

function Application() {
  const [endpoint, setEndpoint] = useState(window.REGULATORY_API_BASE || "");
  const [input, setInput] = useState("http://127.0.0.1:8000");
  const [error, setError] = useState("");
  const client = useMemo(() => endpoint ? apiClient(endpoint) : browserClient, [endpoint]);
  return <><details className="connection-panel"><summary><span className="status-dot"/>{endpoint ? "AI server connected" : "Browser retrieval demo"}<span> · Change mode</span></summary><div><p>{endpoint ? `Questions are sent to ${endpoint} for hybrid retrieval and configured model generation.` : "This mode searches bundled evidence in your browser. Connect your running local AI server for generated answers."}</p><form onSubmit={event => { event.preventDefault(); try { setEndpoint(validateEndpoint(input)); setError(""); } catch (e) { setError(e instanceof Error ? e.message : "Invalid address"); } }}><label htmlFor="api-endpoint">AI server address</label><input id="api-endpoint" type="url" value={input} onChange={e => setInput(e.target.value)} required/><button type="submit">Connect AI</button><button type="button" onClick={() => { setEndpoint(""); setError(""); }}>Use browser demo</button></form>{error && <p role="alert">{error}</p>}<p>Start locally: <code>python -m reg_assistant.cli serve</code>. Switching modes clears this conversation. A server must permit this website’s origin.</p></div></details><Home key={endpoint} client={client} homeHref={import.meta.env.BASE_URL}/></>;
}

createRoot(root).render(<Application/>);
