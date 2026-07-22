# crochet-reconstruction — deterministic engine, physical validation, and contributor portal

A framework-independent Python engine that generates and validates
mathematically consistent crochet beanie patterns from typed measurements
and gauge. **No AI, no image analysis, no computer vision** — every stitch
count in a generated pattern comes from explicit, tested arithmetic.

This is Phase 1 of a larger project described in the attached decision
package. Phase 1 proves the deterministic core in isolation, before any
image-to-pattern work begins. See
[`docs/product-boundary.md`](docs/product-boundary.md) for the full scope
statement and disclaimer.

## Pipeline

```
Measurements + gauge + selected template
                  ↓
         Structured pattern model      (domain/)
                  ↓
       Deterministic calculations      (engine/sizing.py, crown.py, body.py, brim.py)
                  ↓
          Pattern compilation          (engine/compiler.py)
                  ↓
          Pattern validation           (validation/)
                  ↓
     Human-readable instructions       (rendering/text_renderer.py)
```

The structured `Pattern` object — not the rendered text — is the source of
truth. A pattern with any fatal validation result is never rendered.

## Supported scope (Phase 1)

- **One category:** adult top-down beanies, worked in continuous (spiral)
  rounds.
- **Two body stitches:** single crochet (`sc`), half-double crochet (`hdc`).
- **One optional brim:** simple, unshaped, back-loop-only in-round brim.
- **US crochet terminology.**
- Solid-colour yarn only.

## Explicitly out of scope (Phase 1)

Image upload/analysis, computer vision, stitch recognition, crochet-vs-knit
classification, multimodal AI, automatic gauge/hook inference, 3D
reconstruction, yarn simulation, authentication, payments, social features,
a polished frontend, a mobile app, PostgreSQL/cloud storage, double
crochet, joined rounds, folded/ribbed brims, colour stripes, garments other
than beanies. Full list and rationale in
[`docs/product-boundary.md`](docs/product-boundary.md).

## Installation

Requires Python 3.12+ (developed and tested on 3.13).

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -e ".[dev]"
```

## CLI usage

```bash
python -m crochet_reconstruction.cli generate \
  --input examples/adult_beanie_hdc.json \
  --output build/adult_beanie_hdc/
```

Writes to the output directory:

- `pattern.json` — the full structured pattern (source of truth).
- `validation_report.json` — every validation result, with severity.
- `pattern.txt` — human-readable US-terminology instructions, **written
  only if validation produced no fatal result.**

Exit codes: `0` fully valid and rendered; `1` fatal validation results
(structured output still written, for inspection); `2` malformed input
JSON; `3` measurements/gauge/template combination cannot be sized at all
(e.g. requested height too short for the implied crown/brim).

See `examples/adult_beanie_hdc.json` for the input shape, or any file under
`tests/golden/inputs/` for further worked examples (small/large
circumference, no-brim, sc vs. hdc).

## Phase 1.5: physical validation

Phase 1's software tests prove the engine is internally consistent — they
do not prove a generated pattern produces a physically usable beanie. Phase
1.5 adds tooling to generate a controlled set of trial patterns, package
them for real crochet testers, and evaluate the results honestly (no
fabricated data, no single "accuracy" score, no automatic engine changes).
See [`docs/physical-validation-protocol.md`](docs/physical-validation-protocol.md)
for the full protocol.

```bash
# Generate the expert-review pack (10 trials stressing range boundaries):
python -m crochet_reconstruction.cli expert-review-pack --output build/expert_review/

# After testers submit PhysicalTrialResult JSON files:
python -m crochet_reconstruction.cli evaluate \
  --trials build/expert_review/ \
  --results physical-results/ \
  --output build/physical_evaluation/
```

See [`docs/measurement-guide.md`](docs/measurement-guide.md) and
[`docs/expert-evaluation-rubric.md`](docs/expert-evaluation-rubric.md) for
what a tester fills in, and
[`docs/decision-gates.md`](docs/decision-gates.md) for how results map to a
continue/narrow/redesign recommendation (always for human review — nothing
here changes engine code automatically).

## Contributor submission portal

A small, server-rendered FastAPI application that lets invited crochet
contributors submit project photographs and metadata from a phone, and
lets an administrator review, approve, link to a physical trial, and
export the approved dataset. Built because the repository had **no**
contributor-data, image-upload, consent, or web-serving capability at all
before this — verified by direct audit, not assumed. See
[`docs/portal-architecture.md`](docs/portal-architecture.md) for the full
design and why the audit led to building rather than reusing.

```bash
pip install -e ".[dev,portal]"
cp .env.example .env   # set PORTAL_SECRET_KEY
alembic upgrade head
python -m crochet_reconstruction.cli portal-create-admin --username admin
python -m crochet_reconstruction.cli portal-create-invitation --label "First tester"
uvicorn crochet_reconstruction.portal.app:create_app --factory --reload
```

The deterministic pattern engine has **zero dependency** on this — FastAPI,
SQLAlchemy, and Pillow are all behind the `portal` extra, not the core
install. See:
[contributor workflow](docs/portal-contributor-workflow.md) ·
[administrator workflow](docs/portal-admin-workflow.md) ·
[consent and privacy](docs/portal-consent-and-privacy.md) ·
[image storage](docs/portal-image-storage.md) ·
[deployment, backup, and production checklist](docs/portal-deployment.md) ·
[dataset export](docs/portal-dataset-export.md) ·
[known limitations](docs/portal-known-limitations.md).

## Test commands

```bash
pytest                              # full suite: engine + physical validation + portal
pytest tests/unit                   # fast unit tests
pytest tests/property               # Hypothesis property-based tests
pytest tests/golden                 # reviewed example inputs/outputs (regression)
pytest tests/mutation_cases         # deliberately invalid patterns must be rejected
pytest tests/physical_validation    # trial matrix, review pack, ingestion, metrics, reporting
pytest tests/portal                 # portal domain/service/image/API tests

ruff check .                    # lint
ruff format --check .           # formatting check
mypy                             # type check (strict)
```

## Architecture summary

```
src/crochet_reconstruction/
├── domain/               # Pydantic models: the typed vocabulary. No calculation logic.
├── templates/             # Whitelists: what a template permits (stitches, ranges, schedules).
├── engine/                # Pure Decimal math + orchestration. No I/O, no Pydantic validation logic beyond models.
├── validation/            # Rule catalogue over an already-compiled Pattern. Severity-ranked.
├── rendering/             # Pattern -> text. Reads structured fields only; no arithmetic.
├── physical_validation/   # Phase 1.5: trial matrix, review-pack generation, result ingestion, metrics, reporting.
├── portal/                # Contributor submission portal (FastAPI, SQLAlchemy, Pillow — behind the `portal` extra).
└── cli.py                # Thin I/O wrapper: JSON in, files out.
```

The domain engine has **zero dependency** on FastAPI, a database, a
frontend framework, cloud services, or an AI provider. A web API can be
added later as a thin wrapper around `engine.compiler.compile_pattern` and
`rendering.text_renderer.render_text` without changing either.

Full formula-by-formula documentation, including every rounding policy,
tie-break rule, and supported-range decision, is in
[`docs/mathematical-assumptions.md`](docs/mathematical-assumptions.md).
Structured-format and versioning details are in
[`docs/pattern-format.md`](docs/pattern-format.md).

## Development status

**Phase 1 (deterministic engine) and Phase 1.5 (physical-validation
tooling) are complete; physical trials themselves have not been run yet.**
The engine's software tests all pass and its tooling can generate a
reviewable trial pack and evaluate submitted results — but until real
crocheters submit real results, the engine's supported ranges, crown
schedule, and tolerances remain **unvalidated against physical reality**.
See [`docs/decision-gates.md`](docs/decision-gates.md).

**Not yet done:** the physical trials themselves, expert sign-off on the
supported numeric ranges and crown increase schedule set, and anything
from the image-analysis phases described in the source decision package
(scaffolding only exists for the first such experiment — see
`experiments/crochet_vs_knitting/`).

See [`docs/product-boundary.md`](docs/product-boundary.md) for review
status detail and known limitations.
