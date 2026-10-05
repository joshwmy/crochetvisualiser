# Free-text annotations

Location: `viewer/src/annotations/types.ts` (data model),
`viewer/src/annotations/annotations.ts` (creation, editing, marker
construction), `viewer/src/main.ts`'s `wireAnnotations()` (UI wiring),
`#annotation-*` elements in `viewer/index.html`.

Annotations let a reviewer attach a short note to a specific stitch or a
specific region of the model — "this is where the crown starts cupping,"
"self-intersection artefact here" — so an observation about the model is
recorded against the thing it is about, rather than in a separate document
that has to re-describe the location in prose.

## What an annotation is, and is not

An annotation is **the user's own text**. Nothing in this pipeline generates,
infers, suggests, or validates annotation content, and the backend never sees
it: annotations are created, edited, and discarded entirely in the browser.
An annotation is not a correction — it changes no geometry, no stitch graph,
no compiled pattern, and never feeds back into the engine. It is a note *about*
the model, sitting alongside it.

Contrast `docs/diagram-corrections.md`, where a user's `SymbolOverride`
genuinely does change what gets compiled. Annotations deliberately have no such
power.

## Data model (`annotations/types.ts`)

```ts
type AnnotationAnchor =
  | { kind: "stitch"; stitchId: string }
  | { kind: "point"; point: Vec3 };

interface Annotation {
  id: string;
  text: string;
  anchor: AnnotationAnchor;
  createdAtMs: number;
  updatedAtMs: number;
  geometryFingerprint: string | null;
}
```

Same discriminated-union shape as `Measurement`
(`docs/measurement-tools.md`), and the same `geometryFingerprint`
provenance field, for the same reasons.

### Why two anchor kinds

A **stitch anchor** stores a `stitch_id` — an identity, not a coordinate. The
marker is placed by looking that id up in the current document every time, so
the note follows the stitch. `resolveAnchorPosition` returns `null` rather than
a fallback position when the id no longer resolves, so a dangling annotation
disappears instead of silently pointing at the origin.

A **point anchor** stores a raw world position, for a note about a region with
no single owning stitch — a gap, a seam line, an area where yarn tubes
self-intersect. There is no identity to store in that case, so there is nothing
to look up.

## Text handling

`normaliseAnnotationText` collapses whitespace runs (including newlines pasted
from elsewhere) into single spaces, trims, and truncates to
`MAX_ANNOTATION_LENGTH` (280). Empty or whitespace-only text is rejected —
`createStitchAnnotation` / `createPointAnnotation` / `updateAnnotationText` all
return `null` rather than producing an unlabelled marker.

`updateAnnotationText` returns a **new** `Annotation` rather than mutating the
existing one, preserving `id`, `anchor`, and `createdAtMs` while advancing
`updatedAtMs`. An edit that would blank the text out returns `null` instead of
emptying the annotation: removing an annotation is a separate, explicit action.

### Untrusted text

Annotation text is user input that gets rendered back into the DOM, so it is
handled as **text, never as markup**. Every display path assigns to
`textContent`; no annotation text is ever passed to `innerHTML`, inserted into
an HTML string, or used to build a selector, URL, or attribute value.

Normalisation deliberately does **not** strip or escape `<`, `>`, `&`, or
quotes. Escaping at the storage layer would be the wrong place — it would
corrupt legitimate notes like `row < 10` while providing no protection that
`textContent` does not already provide completely. The rule is enforced at the
one place it matters (rendering) rather than by mangling the stored data.

## UI interaction

- **`#annotation-mode-toggle`** enables click-to-anchor. Annotation mode and
  measurement mode are kept mutually exclusive — enabling one disables the
  other — because both would otherwise claim the same click.
  `App.handlePointerDown` also checks annotation mode first, so the behaviour
  stays defined even if both flags were somehow set.
- **`#annotation-kind-select`** chooses `stitch` (default) or `point`
  anchoring, mirroring `#measurement-kind-select`.
- One click sets the pending anchor (a stitch click also updates
  `selectedStitchId`, so the inspector panel follows along). The note is then
  typed into `#annotation-text` and confirmed with `#annotation-save` or the
  Enter key. `#annotation-save` stays disabled until an anchor is pending, so
  the flow cannot produce an anchorless annotation.
- **Edit**: each list entry's "Edit" button loads that annotation's text back
  into the input and sets `editingAnnotationId`; the save button relabels to
  "Save annotation" and updates in place rather than creating a second one.
  "Cancel edit" abandons the edit without changing the stored annotation.
- **`#annotation-remaining`** shows the remaining character count against
  `MAX_ANNOTATION_LENGTH`.

## Rendering

`buildAnnotationMarker` draws a small **wireframe octahedron** at the anchor
position, sized relative to gauge (half a stitch width). The shape — not just
the colour — distinguishes it from the selection marker and from measurement
lines, following the project's existing "never rely on colour alone" overlay
convention.

**The text itself is not drawn in 3D.** Doing so would require a canvas
texture per annotation (with matching disposal), and the labels would compete
with the model for legibility at every camera distance. The side-panel list
carries the text instead — the same split `docs/measurement-tools.md` already
applies to scalar measurements, which appear only as list entries.

Markers respect clipping like the model and the measurement lines: an
annotation on a stitch the clipping plane has cut away disappears with it. The
selection marker remains the one deliberate exception
(`docs/clipping-and-section-views.md`).

A text edit does not rebuild the marker — the marker encodes only the anchor.

### Disposal on recompile

`loadGeometryDocument` clears `annotations`, `pendingAnnotationAnchor`, and
`editingAnnotationId`, and `disposeOverlays` disposes every marker's geometry
and material. An annotation anchored to the previous model's stitch ids or
world positions would be meaningless against a new one, and silently
re-pointing it at whatever stitch now happens to hold the same id would be
worse than dropping it.

## Known limitations

- **No persistence.** Annotations live only in the in-memory viewer store;
  reloading the page or recompiling clears them. Same position as measurements
  — there is no save/load mechanism for viewer session state at all yet, and no
  export path, so annotations cannot currently leave the browser session.
- **No backend representation and no JSON Schema** — frontend-only, like
  `Measurement`. See `docs/schema-artifacts.md`'s "Frontend-only types are not
  included, on purpose".
- **No rich text, no attachments, no threading, no authorship.** One flat
  string per annotation, single-user, no identity recorded — there is no
  multi-user concept anywhere in this viewer.
- **No in-scene text label** — deliberate, see "Rendering" above.
- **No annotation-driven navigation.** The list does not focus the camera on an
  annotation's anchor when clicked; existing stitch selection already covers
  that path for stitch anchors.
- **Point anchors do not survive geometry changes meaningfully** even in
  principle: a stored world position has no relationship to a recompiled model.
  This is why all annotations are cleared on recompile rather than only the
  stitch-anchored ones whose ids fail to resolve.
