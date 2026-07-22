import { defineConfig } from "vitest/config";

export default defineConfig({
  root: ".",
  server: { port: 5173 },
  test: {
    environment: "jsdom",
    globals: true,
    // e2e/ holds Playwright specs (real browser + real backend) — a
    // completely different test runner, not a Vitest suite.
    exclude: ["node_modules/**", "e2e/**"],
  },
});
