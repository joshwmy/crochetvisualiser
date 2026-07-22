import { defineConfig } from "vitest/config";

export default defineConfig({
  root: ".",
  server: { port: 5173 },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
