# Canonical JSON / fingerprint audit vs. RFC 8785

## What exists today

Three call sites implement the identical recipe independently (`engine/compiler.py::canonical_json`,
`graph/fingerprint.py::canonical_graph_json`, `geometry/layout.py::_canonical_json`):

```python
json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
```

then SHA-256 over the UTF-8 bytes.

## Is this RFC 8785 (JSON Canonicalization Scheme, JCS)?

**No.** RFC 8785 additionally requires:

1. **Specific number serialization** — every JSON number must be produced by
   the algorithm in RFC 8785 §3.2.2.3 (based on ECMAScript `Number::toString`),
   which normalizes floating-point representation (no `1.0` vs `1`
   ambiguity, no locale/platform variance). Python's `json.dumps` uses
   `repr(float)`/`int.__str__`, which is *usually* compatible for small
   integers but is not guaranteed byte-identical to the ECMAScript
   algorithm for all floats.
2. **Unicode normalization** of string values is not itself mandated by JCS,
   but RFC 8785 mandates UTF-8 output with no escaping beyond what's
   structurally required — `json.dumps`'s default `ensure_ascii=True`
   behavior (escaping non-ASCII as `\uXXXX`) is a **direct deviation**: JCS
   requires raw UTF-8 bytes for non-ASCII characters, not `\u` escapes.
3. **`default=str` is a project-specific escape hatch** (used here so
   `Decimal`/`datetime` values serialize instead of raising) with no RFC
   8785 equivalent — RFC 8785 only defines canonicalization for values that
   are already valid JSON; the pre-conversion step is out of its scope by
   definition, so this specific point isn't a deviation, but it does mean
   compliance depends on what `str(value)` produces for each type.

## Why this remains deterministic for this codebase's actual data, despite not being JCS-compliant

Every value that reaches these three `canonical_json` functions today is one
of: a `StrEnum` member (ASCII-only string), a plain ASCII string
(`stitch_id`, `source_reference`, project titles), a `Decimal` (converted via
`default=str` to a fixed-format decimal string, never scientific notation
for the value ranges this domain uses — centimeters/percentages in the
single/double digits), a Python `int`, or `None`/`bool`. There is no case
in the current schema where:

- a value contains non-ASCII characters (would trigger the `\uXXXX`-escaping
  deviation above, but no current field accepts free-form Unicode text —
  `project.title` is validated ASCII-safe by convention, not by explicit
  regex; **this is a latent gap, not a proven bug** — see "Residual risk"
  below), or
- a float is serialized directly without going through `Decimal` first
  (`geometry/models.py`'s `Vec3`/`Quat` tuples ARE plain Python `float` —
  see residual risk), or
- two distinct in-domain values could canonicalize to the same string under
  Python's `json.dumps` but to different strings under RFC 8785 (the
  reverse — same RFC-8785 string for different `json.dumps` output — is the
  only direction that would actually break fingerprint uniqueness, and no
  such collision is possible for key-sorted, separator-fixed output).

**Conclusion**: the fingerprint remains a valid *stability* check (same
input → same fingerprint, different input → near-certainly different
fingerprint) for everything currently stored in `Pattern`, `StitchGraph`,
and `GeometryDocument`. It is not a portable, cross-language, standards-compliant
canonical form, and must not be advertised as RFC 8785-compliant.

## Cross-platform float stability (geometry fingerprint only)

The same pattern on Windows (CPython 3.13.7, MSVC UCRT libm) and in the
`Dockerfile.api` image (CPython 3.13.16, glibc 2.41) produced an identical
`graph_fingerprint` but a different `geometry_fingerprint`. Diffing the
canonical geometry JSON for the viewer's `AMIGURUMI_EXAMPLE` found 42 of 2597
floats differing, **every one by exactly 1 ulp** (max |Δ| 1.8e-15 cm), all
traced to a single libm disagreement:

| call | UCRT | glibc |
|---|---|---|
| `math.sin(4 * math.pi / 3)` | `-0x1.bb67ae8584ca9p-1` | `-0x1.bb67ae8584ca8p-1` |

That angle is hit once per round of 6/12/18 stitches, and flows into
`position[1]`, `normal[1]`, `tangent[0]`, the adjacent yarn-segment
`control_points`, and (via `math.hypot`) `measurements.max_radius_cm` /
`max_circumference_cm`. Python's own `repr`/`round` are platform-independent
(CPython's bundled dtoa); the drift comes purely from the C library's
transcendental functions, which are not required to be correctly rounded.

**Fix:** `geometry/layout.py::_canonical_json` now hashes every float
quantised with `round(x, FINGERPRINT_FLOAT_DECIMALS) + 0.0`
(`FINGERPRINT_FLOAT_DECIMALS = 9`, i.e. 1e-9 cm; `+ 0.0` folds `-0.0` into
`0.0`). Only the hash input is quantised — the emitted `GeometryDocument`
keeps full float precision, so a client cannot recompute the fingerprint by
hashing the raw payload; it must apply the same quantisation.

What this does and does not guarantee:

- 1-ulp libm noise no longer changes the fingerprint, except when a value sits
  within 1 ulp of a 1e-9 rounding boundary (probability ≈ 1e-7 per differing
  float for magnitudes near 1). Cross-platform equality is therefore
  *expected and tested*, not proven for every possible input.
- Raw `geometry.json` bytes are still **not** cross-platform identical — only
  the fingerprint is. The committed `viewer/public/geometry.json` was
  generated on Windows.
- `pattern_fingerprint` (Decimal-only) and `graph_fingerprint` (no floats)
  were already portable and are unchanged.

Guarded by `tests/geometry/test_fingerprint_portability.py`, which pins the
`AMIGURUMI_EXAMPLE` geometry fingerprint (verified identical on both
platforms above) and checks that nudging every float by ±1 ulp leaves the
fingerprint unchanged. Changing `FINGERPRINT_FLOAT_DECIMALS` or the
quantisation changes every geometry fingerprint.

## Residual risk (documented, not fixed this slice)

`geometry/models.py`'s `Vec3 = tuple[float, float, float]` fields
(`position`, `orientation`, `tangent`, `normal`, `binormal`) are serialized
as raw Python `float` via `model_dump(mode="json")`, which uses `repr`-based
float formatting — this **is** a real (if narrow) RFC 8785 deviation risk:
two floating-point values that differ only in the last bit could
theoretically serialize identically under Python but differently under a
strict ECMAScript number formatter, or vice versa. This does not affect
`geometry_fingerprint`'s *internal* determinism (same Python process,
same `json.dumps`, same output, always) but would matter if a future
non-Python consumer tried to reproduce the same fingerprint from the same
`GeometryDocument` JSON. Documented here rather than fixed, since no such
cross-language fingerprint-reproduction requirement exists yet.

## Test vectors

See `tests/test_canonical_json.py` for executable versions of these.

| Input (Python) | `canonical_json` output | Note |
|---|---|---|
| `{"b": 1, "a": 2}` | `{"a":2,"b":1}` | key order does not affect hash (`d3626ac3...`) |
| `{"z": {"b": 1, "a": 2}, "a": 1}` | `{"a":1,"z":{"a":2,"b":1}}` | key sorting recurses into nested objects |
| `[3, 1, 2]` | `[3,1,2]` | array element order is data, never sorted |
| `{"n": 5}` | `{"n":5}` | plain integers serialize as bare numbers |
| `{"x": Decimal("1.50")}` | `{"x":"1.50"}` | decimal-like values stay quoted strings via `default=str`, never a bare number — `1.5` and `"1.50"` cannot collide |
| `{"s": "café"}` | JSON string escaped to backslash-u-00e9 (non-ASCII never appears as raw UTF-8 bytes) | RFC 8785 deviation above; `"café"` and `"cafe"` still escape to distinct output |
| `{"z": -0}` | `{"z":0}` | Python `int` has no signed zero |
| `{"z": Decimal("-0")}` | `{"z":"-0"}` | `Decimal` *does* preserve the sign of zero in its string form — `Decimal("-0")` and `Decimal("0")` canonicalize differently |
| `{"f": 0.1 + 0.2}` | `{"f":0.30000000000000004}` | raw float uses Python `repr` formatting, not RFC 8785's ECMAScript number algorithm — the residual risk above |
| `{"s": StitchFamily.SC}` | `{"s":"sc"}` | enum serializes as its `.value` |

Key invariant verified by test: **serializing the same logical value twice
in the same process always produces byte-identical output**. The geometry
fingerprint additionally aims for cross-platform stability via float
quantisation (see "Cross-platform float stability" above); the generic
`canonical_json` recipe itself makes no cross-platform promise for raw
floats.
