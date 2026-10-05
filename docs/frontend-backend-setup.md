# Frontend-to-backend setup

## Local development

Two processes, run separately:

```bash
# Terminal 1 — backend
pip install -e ".[dev,api]"
uvicorn crochet_reconstruction.api.app:create_app --factory --reload --port 8000

# Terminal 2 — frontend
cd viewer
npm install
cp .env.example .env   # VITE_API_BASE_URL=http://localhost:8000 (the default anyway)
npm run dev             # http://localhost:5173
```

Open `http://localhost:5173`. The viewer loads the static
`viewer/public/example-geometry.json` fixture on startup: the editor's
bundled example pattern, precompiled, so what you first see matches the text
in the editor and needs no backend. The left panel's pattern editor then
compiles and loads live models.

CORS: the backend's default `VISUALIZER_CORS_ORIGINS` already includes
`http://localhost:5173`, matching Vite's default dev port. If you run Vite
on a different port, set `VISUALIZER_CORS_ORIGINS` to match before starting
the backend.

## Environment variables

| Variable | Side | Default | Purpose |
|---|---|---|---|
| `VITE_API_BASE_URL` | frontend (`viewer/.env`) | `http://localhost:8000` | Base URL the browser calls for `/api/visualizer/compile`. Read at **build** time — changing it needs a rebuild, not just an env edit. |
| `VITE_BASE_PATH` | frontend (build env) | `/` | Public base path. Only needed when the site is served from a subpath, e.g. a project GitHub Pages site — see `docs/deployment.md`. |
| `VISUALIZER_CORS_ORIGINS` | backend | `http://localhost:5173` | Comma-separated allow-list of origins permitted to call the API. |
| `VISUALIZER_MAX_SOURCE_LENGTH` | backend | `50000` | See `docs/compile-api.md`. |
| `VISUALIZER_ENVIRONMENT` | backend | `development` | Informational. |

`viewer/.env.example` documents the frontend variable; there is no
`.env.example` for the backend since it has no secrets — its variables are
plain deployment configuration, documented in `docs/compile-api.md`.

## The static fixture's role

`viewer/public/example-geometry.json` is the compile API's `geometry` output
for `viewer/src/examples.ts`' `AMIGURUMI_EXAMPLE`; regenerate it whenever the
example or the geometry pipeline changes. The larger
`viewer/public/geometry.json` (generated via
`python -m crochet_reconstruction.cli generate-geometry`) is no longer loaded
at startup but remains useful as:

- a **demo** that works with zero backend running (open the page, look at a
  beanie, rotate/clip/animate it — nothing requires the API for this),
- a **regression-test input** (`viewer/tests/benchmark.test.ts` reads it
  directly),
- a **fallback** if the backend is unreachable — the initial page load still
  succeeds and shows a model; only the pattern editor's compile button needs
  the backend.

It is explicitly **not** the only way to use the viewer — the pattern
editor's "Render in 3D" workflow replaces it with a freshly compiled
model without any manual fixture regeneration step, which was this slice's
whole point.

## Production deployment

**See [`docs/deployment.md`](deployment.md)** for the actual deployment —
where the frontend is live, the `Dockerfile.api`/`render.yaml` backend config,
and the CORS/base-path steps. The generic shape is below.

The frontend build and backend are independently deployable static/API
services:

```bash
# Backend (any ASGI host — shown here as a plain uvicorn process; put a
# reverse proxy with TLS in front for real deployment, same as the portal's
# own deployment guidance):
pip install ".[api]"
uvicorn crochet_reconstruction.api.app:create_app --factory --host 0.0.0.0 --port 8000

# Frontend (static build, serve dist/ from any static host/CDN):
cd viewer
VITE_API_BASE_URL=https://your-api-domain.example npm run build
# deploy dist/ — e.g. `npm run preview` to smoke-test the production build locally
```

Set `VISUALIZER_CORS_ORIGINS` on the backend to the frontend's real deployed
origin (not `*`, and not the localhost default) before going live.

## Verifying the setup end-to-end

```bash
curl http://localhost:8000/healthz
# {"status":"ok"}

cd viewer && npx playwright test
# runs e2e/compile-workflow.spec.ts against both a real Vite dev server and
# a real backend instance (Playwright starts both itself — see
# playwright.config.ts's webServer entries)
```
