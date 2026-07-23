"""SVG crochet-chart diagram ingestion: secure parsing, Diagram IR,
symbol classification, circular topology inference, corrections, and
conversion into the existing StitchGraph/geometry pipeline.

See ``docs/svg-diagram-ingestion.md`` for the supported SVG profile and
end-to-end architecture.
"""

from __future__ import annotations
