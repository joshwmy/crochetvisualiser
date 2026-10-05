# Deployment

Two independently deployable pieces, matching the architecture: a static
frontend build and a stateless API. Neither needs the other to start — the
viewer loads its bundled `geometry.json` demo with no backend at all (see
`docs/frontend-backend-setup.md`, "The static fixture's role").

This document covers the **visualiser**. The paused contributor portal has its
own, separate deployment guide (`docs/portal-deployment.md`) and its own
`Dockerfile`; do not confuse the two.

## Current state

| Piece | Status | Where |
|---|---|---|
| Frontend | **Deployed** | <https://joshwmy.github.io/crochetvisualiser/> |
| Compile API | **Deployed** | <https://crochet-visualiser-api.onrender.com> (Render free tier, from `render.yaml`) |

The live frontend is built with `VITE_API_BASE_URL` pointing at the Render
service, so "Render in 3D" and the SVG-diagram workflow work end to
end. The free instance sleeps when idle — see the cold-start notes under "After the API is live".

## Frontend: GitHub Pages

Served from the `gh-pages` branch at the repository root. There is no GitHub
Actions workflow: the account's token lacks the `workflow` scope, so the
branch is built locally and pushed.

```bash
cd viewer
MSYS_NO_PATHCONV=1 \
VITE_BASE_PATH=/crochetvisualiser/ \
VITE_API_BASE_URL=https://crochet-visualiser-api.onrender.com \
npm run build
```

`MSYS_NO_PATHCONV=1` is for Git Bash on Windows, which otherwise rewrites
`/crochetvisualiser/` into `C:/Program Files/Git/crochetvisualiser/`. That
once shipped a build whose every asset 404'd; `vite.config.ts` now refuses
any base path that is not `/<something>/`. It is harmless elsewhere.

`VITE_BASE_PATH` matters. A *project* Pages site is served from `/<repo>/`,
not a domain root, so every asset URL must carry that prefix. Two things
depend on it:

- `vite.config.ts`'s `base`, which rewrites the bundled asset URLs.
- `main.ts`'s geometry fixture URL, which reads `import.meta.env.BASE_URL`
  rather than a leading `/`. It is the only absolute asset path in the app;
  the API paths are appended to `getApiBaseUrl()` and are unaffected.

Both default to `/`, so a root-domain host (Netlify, Vercel, a custom domain)
needs no `VITE_BASE_PATH` at all.

Publishing the build:

```bash
# From a scratch directory — never the working tree, so a failed publish
# cannot leave build output committed to the source branch.
cp -r viewer/dist/* .
touch .nojekyll          # Pages otherwise runs Jekyll over the output
git init -b gh-pages && git add -A && git commit -m "Deploy viewer"
git remote add origin https://github.com/joshwmy/crochetvisualiser.git
git push -f origin gh-pages
```

`-f` is correct here: `gh-pages` is a build artefact branch with no history
worth preserving, regenerated wholesale from `dist/` each time.

Verify after a deploy — a 200 on the page alone is not enough, since a wrong
base path serves the HTML fine and then 404s every asset:

```bash
curl -sI https://joshwmy.github.io/crochetvisualiser/ | head -1
curl -sI https://joshwmy.github.io/crochetvisualiser/geometry.json | head -1
curl -s  https://joshwmy.github.io/crochetvisualiser/ | grep -o 'src="[^"]*"'
```

The `src` must start with `/crochetvisualiser/assets/`. Pages serves HTML with
a 10-minute cache, so a browser that loaded the previous deploy can keep
running it for a while — append `?v=<anything>` to check the new one.

## Backend: the compile API

`Dockerfile.api` builds it. Deliberately separate from the repository's
existing `Dockerfile`, which serves the paused portal and pulls in SQLAlchemy,
Alembic, Pillow and a writable data volume — none of which this API has or
wants. It is stateless: no database, no migrations, no file storage, no
secrets, and it never writes a submitted pattern or SVG to disk
(`docs/compile-api.md`).

`render.yaml` is a Render blueprint for it. Deploy via Render's dashboard →
New → Blueprint → select this repository. Any container host works equally
well; Fly and Railway need only the Dockerfile.

### After the API is live

Two changes, both required, in this order:

1. **Backend CORS.** `VISUALIZER_CORS_ORIGINS` must be the frontend's real
   origin — `https://joshwmy.github.io`, with no path and no trailing slash.
   `render.yaml` already sets this. Not `*`: the API has no secrets, but a
   wildcard lets any page on the web drive it, and this list is the only
   access control the service has.
2. **Frontend API URL.** Rebuild and republish with the API's origin baked in:

   ```bash
   cd viewer
   VITE_BASE_PATH=/crochetvisualiser/ \
   VITE_API_BASE_URL=https://crochet-visualiser-api.onrender.com \
   npm run build
   ```

   `VITE_API_BASE_URL` is read at **build** time, not runtime — changing it
   requires a rebuild and a fresh `gh-pages` push, not just an env-var edit.

Then confirm the round trip actually works from the deployed origin, rather
than assuming CORS is right:

```bash
curl -s https://crochet-visualiser-api.onrender.com/healthz
curl -s -X POST https://crochet-visualiser-api.onrender.com/api/visualizer/compile \
  -H 'Content-Type: application/json' \
  -d '{"source":"Round 1: 6 sc in magic ring [6]\n"}' | head -c 200
```

A free-tier Render instance sleeps when idle; the first request after a sleep
can take tens of seconds. The viewer softens this two ways
(`viewer/src/api/client.ts`):

- **Warm-up.** On page load it fires a `no-cors` `GET /healthz` at a remote
  API, so the instance starts booting while the viewer loads rather than on
  the user's first click. Skipped for a `localhost` backend.
- **One retry.** A compile/analyse request that fails at the network level or
  gets a 502/503/504 is retried once after 5 s. Safe because every endpoint is
  stateless and idempotent. A second failure is shown as-is, with a message
  saying an idle server can take up to a minute to wake.

A boot longer than both still surfaces as a network error; trying again a
little later then succeeds.

### Verifying the image locally

Build and run it the way Render will, including an injected `$PORT`, before
deploying. An editable dev install reads straight from `src/`, so a missing
package-data entry only shows up in a real install like this one
(`tests/test_package_data.py` now guards it):

```bash
docker build -f Dockerfile.api -t crochet-visualiser-api:local .
docker run --rm -p 18000:10000 -e PORT=10000 \
  -e VISUALIZER_CORS_ORIGINS=https://joshwmy.github.io \
  crochet-visualiser-api:local
curl -s localhost:18000/healthz
```

Then smoke-test a compile with the `curl -X POST` above (against
`localhost:18000`), or with the viewer's bundled `AMIGURUMI_EXAMPLE` for a
fuller run. Check `success` is `true` — the API reports internal failures as
a 200 with an `INTERNAL_SERVER_FAILURE` diagnostic, so the status code alone
proves nothing.

## What is deliberately not deployed

- **The contributor portal.** Paused, and it handles contributor photographs
  and consent records — see `docs/portal-consent-and-privacy.md` before
  deploying it anywhere. `portal_data/` is git-ignored and has never been
  committed.
- **Any database.** The visualiser has none.
