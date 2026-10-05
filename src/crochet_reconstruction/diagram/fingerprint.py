"""Deterministic fingerprint over a :class:`DiagramDocument`.

Same recipe as :func:`crochet_reconstruction.graph.fingerprint.compute_graph_fingerprint`
— canonical (key-sorted, whitespace-minimal) JSON, SHA-256 over the UTF-8
bytes — kept as a standalone function for the same reason: this package
must not import from ``graph`` for something this small, and the two
fingerprints are never compared to each other.
"""

from __future__ import annotations

import hashlib
import json

from crochet_reconstruction.diagram.ir import DiagramDocument


def canonical_diagram_json(document: DiagramDocument) -> str:
    data = document.model_dump(mode="json", exclude={"fingerprint"})
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def compute_diagram_fingerprint(document: DiagramDocument) -> str:
    digest = hashlib.sha256(canonical_diagram_json(document).encode("utf-8"))
    return digest.hexdigest()
