/// <reference types="vitest/config" />
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { parse } from "smol-toml";
import { defineConfig } from "vite";

/** Headers for `/*` from ../netlify.toml, so `vite preview` (and the browser tests) run
 * under exactly the Content-Security-Policy and security headers of production. */
export function netlifyHeaders(): Record<string, string> {
  const toml = parse(readFileSync(fileURLToPath(new URL("../netlify.toml", import.meta.url)), "utf8")) as {
    headers?: { for: string; values: Record<string, string> }[];
  };
  return toml.headers?.find((h) => h.for === "/*")?.values ?? {};
}

export default defineConfig({
  plugins: [react()],
  worker: { format: "es" },
  build: { target: "es2022", sourcemap: true, chunkSizeWarningLimit: 900 },
  preview: { headers: netlifyHeaders() },
  test: {
    include: ["tests/**/*.test.ts"],
    environment: "node",
    testTimeout: 30_000,
  },
});
