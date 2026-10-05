"""Deterministic fingerprint over a :class:`StitchGraph`.

Same recipe as :func:`crochet_reconstruction.engine.compiler.canonical_json` /
``_fingerprint``: canonical (key-sorted, whitespace-minimal) JSON, SHA-256
over the UTF-8 bytes. Kept as a standalone function (not imported from
``engine.compiler``) because the graph package must not depend on ``engine``
— only on ``domain`` enums, to keep the dependency direction one-way.
"""

from __future__ import annotations

import hashlib
import json

from crochet_reconstruction.graph.models import StitchGraph


def canonical_graph_json(graph: StitchGraph) -> str:
    data = graph.model_dump(mode="json", exclude={"fingerprint"})
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def compute_graph_fingerprint(graph: StitchGraph) -> str:
    digest = hashlib.sha256(canonical_graph_json(graph).encode("utf-8"))
    return digest.hexdigest()
