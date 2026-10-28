import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

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
