import { defineConfig } from "vitest/config";

/**
 * Public base path. "/" suits local dev and any host serving the site at a
 * domain root. A *project* GitHub Pages site is served from /<repo>/, so
 * that build sets VITE_BASE_PATH — see docs/deployment.md. Anything that
 * reads an asset by absolute URL must go through import.meta.env.BASE_URL
 * for both cases to work; main.ts's geometry fixture is the only one.
 *
 * Validated because Git Bash on Windows silently rewrites a leading-slash
 * env value into a filesystem path ("/crochetvisualiser/" becomes
 * "C:/Program Files/Git/crochetvisualiser/"), which Vite then accepts and
 * bakes into every asset URL — a build that succeeds and 404s every asset.
 */
function resolveBasePath(): string {
  const base = process.env.VITE_BASE_PATH || "/";
  if (!base.startsWith("/") || !base.endsWith("/") || base.includes(":")) {
    throw new Error(
      `VITE_BASE_PATH must look like "/<repo>/", got ${JSON.stringify(base)}. ` +
        "On Git Bash, prefix the build with MSYS_NO_PATHCONV=1.",
    );
  }
  return base;
}

export default defineConfig({
  root: ".",
  base: resolveBasePath(),
  server: { port: 5173 },
  test: {
    environment: "jsdom",
    globals: true,
    // e2e/ holds Playwright specs (real browser + real backend) — a
    // completely different test runner, not a Vitest suite.
    exclude: ["node_modules/**", "e2e/**"],
  },
});
