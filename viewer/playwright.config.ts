import { defineConfig } from "@playwright/test";

// Windows path to the repo's venv python, invoked directly (not through
// `python`/`python3` on PATH) since this repo's global Python has an
// unrelated site-packages conflict — see docs/scientific-viewer-spec.md.
// Backslashes are required here: cmd.exe's command-name resolution (this
// runs via `cmd /c`) does not reliably treat a forward-slash path starting
// with `../` as a relative executable — it was read as the literal command
// name "..", which of course doesn't exist.
const VENV_PYTHON = "..\\.venv\\Scripts\\python.exe";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  // `fullyParallel: false` only serialises tests *within* one spec file —
  // with three spec files (compile-workflow, lifecycle-stress, visual-
  // regression, completion-audit addition), Playwright otherwise picks a
  // worker count from the machine's logical core count and runs files
  // concurrently. All three files share one dev server and one backend
  // process (`webServer` below, not per-worker-isolated) — concurrent
  // workers hammering that single backend with real compiles caused real
  // `page.waitForResponse` timeouts and a `#measurement-list` count race,
  // observed directly while adding the second and third spec files, not
  // hypothetical. `workers: 1` restores the serial execution this suite
  // has always implicitly relied on.
  workers: 1,
  retries: 0,
  // Generous: this single test does three real network round-trips through
  // a real backend, each followed by a real Three.js scene rebuild — not a
  // mocked unit test. 30s was observed to be too tight even for a passing
  // run; 90s itself was later observed to be too tight once the scientific-
  // viewer test grew path-inspection-mode coverage (more canvas-click
  // probing, more real state assertions) — bumped to 150s rather than
  // trimming coverage to fit an arbitrary budget.
  timeout: 150_000,
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "npm run dev -- --port 5173",
      url: "http://localhost:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      // No `cwd` override: the editable install already makes
      // `crochet_reconstruction` importable from this venv regardless of
      // working directory, so the default cwd (this config file's
      // directory) is fine, and keeps VENV_PYTHON's relative path correct.
      command: `${VENV_PYTHON} -m uvicorn crochet_reconstruction.api.app:create_app --factory --port 8000`,
      url: "http://localhost:8000/healthz",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
});
