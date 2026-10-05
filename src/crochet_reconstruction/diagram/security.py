"""Safety limits and disallowed-content policy for untrusted SVG input.

SVG is active content (brief: "SVG is active content and must be treated as
untrusted input"). Every limit here exists to make a malicious or excessive
document fail fast with a structured diagnostic instead of hanging or
exhausting memory — see ``docs/svg-security.md`` for the threat model each
limit addresses.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyLimits:
    """All bounds are deliberately generous for a "clean vector chart" (the
    only supported profile — see ``docs/svg-diagram-ingestion.md``) while
    still ruling out pathological/adversarial input. Values are not tuned
    against a large real-world corpus (none exists for this project's
    synthetic-only fixture policy); revisit if a legitimate chart is ever
    rejected."""

    max_source_bytes: int = 2_000_000
    max_element_count: int = 20_000
    max_nesting_depth: int = 64
    max_path_commands_per_element: int = 2_000
    max_text_node_chars: int = 2_000
    max_use_references: int = 5_000
    max_transform_nesting: int = 64
    max_coordinate_magnitude: float = 1_000_000.0
    max_viewbox_dimension: float = 1_000_000.0
    max_symbol_candidates: int = 5_000
    max_inferred_stitches: int = 5_000
    max_inferred_edges: int = 50_000


DEFAULT_LIMITS = SafetyLimits()

# Tags rejected outright (element + subtree dropped, document fails with a
# structured diagnostic rather than being silently repaired) — active
# content, external-content loaders, or content this profile has no
# reviewed rendering path for.
DISALLOWED_TAGS = frozenset(
    {
        "script",
        "foreignObject",
        "iframe",
        "object",
        "embed",
        "link",
        "style",
        "image",
        "audio",
        "video",
        "animate",
        "animateColor",
        "animateMotion",
        "animateTransform",
        "set",
    }
)

# Attribute *names* rejected wherever found (any `on*` inline event handler).
DISALLOWED_ATTRIBUTE_PREFIXES = ("on",)

# Attribute values containing any of these substrings are rejected outright
# (javascript: URLs, CSS url(...) references, data: URIs used as an
# executable/remote-content vector).
DISALLOWED_VALUE_SUBSTRINGS = ("javascript:", "url(", "data:text/html")

HREF_ATTRIBUTES = ("href", "{http://www.w3.org/1999/xlink}href", "xlink:href")
"""``<use>``/other href-bearing attributes: only a local fragment reference
(starts with ``#``) is permitted — see ``_check_external_reference``."""
