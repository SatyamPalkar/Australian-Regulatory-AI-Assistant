import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { validateEndpoint } from "./github-pages/api-client";

if (process.env.VITE_REGULATORY_API_BASE) {
  try {
    if (!validateEndpoint(process.env.VITE_REGULATORY_API_BASE).startsWith("https://")) throw new Error();
  } catch {
    // A mistyped variable might contain a credential. Never print its value.
    throw new Error("VITE_REGULATORY_API_BASE must be a public HTTPS origin without credentials, paths or query strings");
  }
}

const repository = process.env.GITHUB_REPOSITORY?.split("/")[1] || "Australian-Regulatory-AI-Assistant";
const base = process.env.PAGES_BASE_PATH || `/${repository}/`;
if (!base.startsWith("/") || !base.endsWith("/") || base.includes("..") || base.includes(":")) {
  throw new Error("PAGES_BASE_PATH must be an absolute URL path ending in a slash");
}

export default defineConfig({
  root: fileURLToPath(new URL("./github-pages", import.meta.url)),
  publicDir: fileURLToPath(new URL("./public", import.meta.url)),
  cacheDir: fileURLToPath(new URL("./.sites-runtime/pages-vite", import.meta.url)),
  base,
  plugins: [react()],
  build: {
    outDir: fileURLToPath(new URL("./pages-dist", import.meta.url)),
    emptyOutDir: true,
    target: "es2022",
  },
  preview: { host: "127.0.0.1", port: 4174, strictPort: true },
});
