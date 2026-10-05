import { defineConfig } from "vitest/config";

export default defineConfig({
  root: ".",
  // Public base path. "/" suits local dev and any host serving the site at a
  // domain root. A *project* GitHub Pages site is served from /<repo>/, so
  // that build sets VITE_BASE_PATH — see docs/deployment.md. Anything that
  // reads an asset by absolute URL must go through import.meta.env.BASE_URL
  // for both cases to work; main.ts's geometry fixture is the only one.
  base: process.env.VITE_BASE_PATH || "/",
  server: { port: 5173 },
  test: {
    environment: "jsdom",
    globals: true,
    // e2e/ holds Playwright specs (real browser + real backend) — a
    // completely different test runner, not a Vitest suite.
    exclude: ["node_modules/**", "e2e/**"],
  },
});
