# SVG security

SVG is active content (it can carry scripts, event handlers, and external
references) and this project treats **every** uploaded or pasted SVG as
untrusted input — from an unauthenticated client, with no assumption that
the source is a trusted design tool's export. This document is the threat
model and the concrete controls that implement it.

## Pipeline

```text
Untrusted SVG
→ secure parser (defusedxml)
→ sanitisation and limits (security.py / svg_parser.py)
→ transform normalisation
→ Diagram IR
```

Every stage before "Diagram IR" can reject the document; none of them ever
partially trust it. See `src/crochet_reconstruction/diagram/svg_parser.py`.

## Fail closed, not strip-and-hope

Some SVG sanitisers *strip* disallowed content and continue rendering
whatever remains. This project does not do that: **any** violation (a
disallowed tag, an external reference, an oversized document, an
unparseable transform) fails the **whole** document with a structured
diagnostic. The reasoning: partial sanitisation of attacker-controlled
markup is a well-known source of sanitiser bypasses (a stripped `<script>`
that leaves a dangling attribute value the "safe" remainder later
interprets differently, for instance) — refusing to guess which parts of a
hostile document are "safe enough to keep" is a strictly stronger
guarantee than trying to repair it. A user who wants their chart accepted
fixes the flagged element and re-uploads.

## Hardened parsing

`svg_parser.py` uses [`defusedxml`](https://pypi.org/project/defusedxml/)
(MIT-licensed) instead of Python's standard-library `xml.etree.ElementTree`
directly. `defusedxml.ElementTree.fromstring` is called with
`forbid_dtd=True`, `forbid_entities=True`, `forbid_external=True` —
explicitly, even though these are `defusedxml`'s own defaults, so the
intent is visible at the call site rather than relying on a library default
that could change. This closes the classic XML attack classes:

- **XXE (XML External Entity)** — a `<!ENTITY xxe SYSTEM "file:///etc/passwd">`
  declaration reading local files into the parsed document.
- **Billion-laughs / entity-expansion bombs** — nested entity references
  that expand to gigabytes of memory from a few hundred bytes of source.
- **External DTD fetches** — a `<!DOCTYPE svg SYSTEM "http://...">`
  triggering a server-side HTTP request to an attacker-controlled host
  (SSRF).

`defusedxml` does **not** enforce element-count, nesting-depth,
coordinate-magnitude, or path-complexity limits — those are this project's
own, layered on top (see below).

## Disallowed content (`security.py`)

Rejected outright, whole-document, on first occurrence:

- **Tags**: `script`, `foreignObject`, `iframe`, `object`, `embed`, `link`,
  `style`, `image`, `audio`, `video`, `animate`, `animateColor`,
  `animateMotion`, `animateTransform`, `set`.
  - `image` (raster embedding) and `link` (external stylesheets) are
    rejected as a category, not filtered by URL — this project's supported
    profile is vector-only (see `docs/svg-diagram-ingestion.md`), so there
    is no legitimate use of either in a supported chart.
  - `style`/CSS is rejected wholesale rather than parsed and filtered: CSS
    can carry `url(...)` references and this project does not implement a
    CSS parser to distinguish a safe declaration from an unsafe one.
  - Animation elements (`animate*`, `set`, SMIL) are rejected because this
    project has no reviewed rendering path that would ever execute them —
    the frontend never renders raw SVG at all (see below), so there is no
    "safe" animation to preserve.
- **Attributes**: any attribute name starting with `on` (inline event
  handlers — `onclick`, `onload`, `onerror`, ...).
- **Attribute values** containing `javascript:`, `url(`, or
  `data:text/html` as a substring, in *any* attribute — not just the ones
  conventionally used for URLs, since a browser can be tricked into
  interpreting a URL-like value in an unexpected attribute under some
  parsing quirks.
- **External references**: any `href`/`xlink:href` (on `<use>` or
  elsewhere) that does not start with `#` (a local same-document fragment
  reference). This blocks `<use href="http://evil.example/x.svg#sc">` —
  the attack this project's own `<use>`-resolution feature would otherwise
  make newly relevant, since resolving a remote SVG would mean fetching
  attacker-controlled content server-side (SSRF) or rendering it
  client-side without ever having sanitised it.

## Safety limits (`SafetyLimits`, `security.py`)

Every numeric limit below exists specifically so a malicious or merely
excessive document fails fast with a diagnostic instead of hanging or
exhausting memory — never an unbounded loop, never an uncaught crash.

| Limit | Default | Attack it bounds |
|---|---|---|
| `max_source_bytes` | 2,000,000 | Raw upload size / memory |
| `max_element_count` | 20,000 | Wide-tree DoS (many siblings) |
| `max_nesting_depth` | 64 | Deep-tree DoS (stack/recursion exhaustion) |
| `max_path_commands_per_element` | 2,000 | Pathological single-element parse cost |
| `max_text_node_chars` | 2,000 | Oversized text payloads |
| `max_use_references` | 5,000 | `<use>` reference-count amplification |
| `max_transform_nesting` | 64 | Pathological transform-function chains |
| `max_coordinate_magnitude` | 1,000,000 | Numeric overflow / absurd geometry |
| `max_viewbox_dimension` | 1,000,000 | Absurd canvas size |
| `max_symbol_candidates` | 5,000 | Downstream classification cost |
| `max_inferred_stitches` | 5,000 | Downstream topology/graph cost |
| `max_inferred_edges` | 50,000 | Downstream topology/graph cost |

The last three are enforced later in the pipeline (`extraction.py`,
`topology.py`), not by the parser — they bound the *interpretation* cost,
which the raw element count alone doesn't determine (a single `<use>` can
still expand to be a large content).

### A real bug this caught: unbounded recursion before the limits even ran

`_index_ids` (the first pass over the parsed tree, building an id lookup
table before the main safety-limited walk) was originally written as a
plain recursive function with **no** depth or count bound of its own —
meaning a maliciously deep document could raise Python's own
`RecursionError` (an unhandled crash) before `_walk`'s
`max_nesting_depth`/`max_element_count` checks ever got a chance to reject
it with a structured diagnostic. Fixed by rewriting `_index_ids`
iteratively with an explicit stack and its own generous hard cap. See
`tests/diagram/test_security.py::test_deep_nesting_fails_cleanly_not_recursion_error`
for the regression test, and `svg_parser.py`'s `_index_ids` docstring for
the full explanation. This is exactly the class of bug this document's
"fail closed" principle exists to catch early: a document this hardened
parser can't fully vouch for must never reach the point of crashing the
process, let alone reaching symbol extraction.

## Frontend rendering safety

The user's raw uploaded/pasted SVG text is **never** injected into the DOM,
never parsed by the browser as SVG, and never rendered — at all, in any
mode. `viewer/src/diagram/svg_overlay.ts` builds the 2D preview entirely
from the structured `DiagramDocument` JSON the backend returns (positions,
stitch types, confidence, relationships), using
`document.createElementNS` and `setAttribute`/`textContent` calls one at a
time. There is no `innerHTML` assignment of untrusted content anywhere in
this path, so even a value containing literal `<script>` text (say, from a
`source_element_id` an attacker chose) can only ever end up as inert
text/attribute data — it is structurally impossible for it to be
interpreted as markup. See
`viewer/tests/svg_overlay.test.ts::"never contains a <script> tag..."` for
the regression test asserting this directly against adversarial symbol
data.

This is option 1 of the brief's three documented safe approaches ("Render
only the normalised Diagram IR as your own safe SVG overlay") — options 2
(sanitise-then-render the original) and 3 (isolated non-scriptable
representation) were not needed once option 1 was available, since the
Diagram IR already contains everything the preview needs to be useful, and
avoiding the original markup entirely is a strictly smaller attack surface
than sanitising and then trusting it.

## What is intentionally *not* defended against

- **Legitimate but confusing charts**: a syntactically safe SVG that is
  simply hard for the classifier to interpret is a UX problem (diagnostics,
  corrections), not a security problem — this document is about content
  that could harm the user's browser or this project's server, not about
  chart quality.
- **Denial of service via *volume* of requests** (rate limiting, quotas):
  out of scope for this document; a deployment-level concern, not a
  parsing-level one.
- **Supply-chain attacks on `defusedxml` itself**: mitigated by the
  project's normal dependency-pinning practice (see `pyproject.toml`), not
  by anything specific to this document.
