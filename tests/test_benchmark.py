"""Backend pipeline benchmarks: parser -> graph -> geometry -> API.

Deliberately generous ceilings, not tight millisecond assertions (fragile
across shared CI hardware) — see docs/performance-benchmarks.md for the
actual numbers this produces locally, the measurement methodology (warm-up
iterations, median/p95), and why raycast/frontend-build numbers live in
viewer/tests/benchmark.test.ts instead (this file only covers the Python
side of the pipeline).
"""

from __future__ import annotations

import json
import statistics
import time

from fastapi.testclient import TestClient

from crochet_reconstruction.api.app import create_app
from crochet_reconstruction.api.config import ApiSettings
from crochet_reconstruction.geometry.layout import build_geometry
from crochet_reconstruction.graph.builder import build_stitch_graph
from crochet_reconstruction.graph.validation import validate_graph
from crochet_reconstruction.parsing.written import parse_written_pattern
from crochet_reconstruction.parsing.written.semantic import DEFAULT_WRITTEN_PATTERN_GAUGE

SMALL_PATTERN = """\
Round 1: 6 sc in magic ring [6]
Round 2: inc in each stitch around [12]
Round 3: (sc, inc) repeat 6 times [18]
Rounds 4-6: sc around [18]
Round 7: (sc, dec) repeat 6 times [12]
Round 8: dec around [6]
"""


def _make_medium_pattern(round_count: int = 40, stitches_per_round: int = 20) -> str:
    """A synthetic pattern with no increases/decreases after the first round
    — deterministic stitch count = stitches_per_round * round_count, useful
    for generating a specific target size rather than relying on a
    hand-authored fixture's incidental count."""
    lines = [f"Round 1: {stitches_per_round} sc in magic ring [{stitches_per_round}]"]
    for round_number in range(2, round_count + 1):
        lines.append(f"Round {round_number}: sc around [{stitches_per_round}]")
    return "\n".join(lines) + "\n"


MEDIUM_PATTERN = _make_medium_pattern(round_count=40, stitches_per_round=20)  # 800 stitches
LARGE_PATTERN = _make_medium_pattern(
    round_count=100, stitches_per_round=17
)  # 1700 stitches, near the frontend's 1640-stitch reference fixture

WARMUP_ITERATIONS = 2
MEASURED_ITERATIONS = 5


def _timed(fn, iterations: int = MEASURED_ITERATIONS) -> dict[str, float]:
    for _ in range(WARMUP_ITERATIONS):
        fn()
    samples = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    samples.sort()
    p95_index = min(len(samples) - 1, int(len(samples) * 0.95))
    return {
        "median_ms": statistics.median(samples),
        "p95_ms": samples[p95_index],
        "iterations": iterations,
    }


def _report(stage: str, size_label: str, stats: dict[str, float]) -> None:
    print(
        f"[benchmark] {stage} ({size_label}): median={stats['median_ms']:.2f}ms "
        f"p95={stats['p95_ms']:.2f}ms over {stats['iterations']} iterations "
        f"(+{WARMUP_ITERATIONS} warm-up, excluded)"
    )


class TestBackendPipelineBenchmarks:
    """One class per stage so pytest -k can target a single stage; each test
    prints its own numbers rather than asserting a specific value — see the
    module docstring for why."""

    def test_parser_stage(self):
        for label, source in [
            ("small", SMALL_PATTERN),
            ("medium", MEDIUM_PATTERN),
            ("large", LARGE_PATTERN),
        ]:
            stats = _timed(lambda source=source: parse_written_pattern(source))
            _report("parser", label, stats)
            assert stats["p95_ms"] < 2000, f"parser stage p95 exceeded generous ceiling for {label}"

    def test_graph_build_stage(self):
        for label, source in [
            ("small", SMALL_PATTERN),
            ("medium", MEDIUM_PATTERN),
            ("large", LARGE_PATTERN),
        ]:
            components, _ = parse_written_pattern(source)
            assert components is not None

            def build(components=components):
                graph = build_stitch_graph(components)
                validate_graph(graph)

            stats = _timed(build)
            _report("graph build + validate", label, stats)
            assert stats["p95_ms"] < 3000, f"graph stage p95 exceeded generous ceiling for {label}"

    def test_geometry_generation_stage(self):
        for label, source in [
            ("small", SMALL_PATTERN),
            ("medium", MEDIUM_PATTERN),
            ("large", LARGE_PATTERN),
        ]:
            components, _ = parse_written_pattern(source)
            assert components is not None
            graph = build_stitch_graph(components)
            validate_graph(graph)

            stats = _timed(
                lambda components=components, graph=graph: build_geometry(
                    components, DEFAULT_WRITTEN_PATTERN_GAUGE, graph
                )
            )
            _report("geometry generation", label, stats)
            assert stats["p95_ms"] < 5000, (
                f"geometry stage p95 exceeded generous ceiling for {label}"
            )

    def test_full_compile_api_round_trip(self):
        test_client = TestClient(create_app(ApiSettings()))
        for label, source in [
            ("small", SMALL_PATTERN),
            ("medium", MEDIUM_PATTERN),
            ("large", LARGE_PATTERN),
        ]:

            def call(source=source):
                response = test_client.post("/api/visualizer/compile", json={"source": source})
                assert response.status_code == 200
                return response

            stats = _timed(
                call, iterations=3
            )  # real HTTP round trip through TestClient — fewer iterations
            _report("full compile API round trip", label, stats)
            assert stats["p95_ms"] < 8000, (
                f"API round trip p95 exceeded generous ceiling for {label}"
            )

            response = call()
            payload_bytes = len(response.content)
            stitch_count = response.json()["summary"]["stitchCount"]
            print(
                f"[benchmark] payload size ({label}): {payload_bytes / 1024:.1f} KB "
                f"for {stitch_count} stitches "
                f"({payload_bytes / max(stitch_count, 1):.0f} bytes/stitch)"
            )

    def test_reports_exact_stitch_counts_for_each_fixture(self):
        # Not a timing measurement — records what "small"/"medium"/"large"
        # actually mean numerically, so the benchmark numbers above have
        # context without needing to re-read this file's pattern generators.
        for label, source in [
            ("small", SMALL_PATTERN),
            ("medium", MEDIUM_PATTERN),
            ("large", LARGE_PATTERN),
        ]:
            components, _ = parse_written_pattern(source)
            assert components is not None
            graph = build_stitch_graph(components)
            print(f"[benchmark] fixture size ({label}): {len(graph.nodes)} stitches")


def test_serialized_payload_is_reasonably_compact():
    test_client = TestClient(create_app(ApiSettings()))
    response = test_client.post("/api/visualizer/compile", json={"source": LARGE_PATTERN})
    assert response.status_code == 200
    payload = response.json()
    reserialized = json.dumps(payload)
    print(f"[benchmark] large-fixture full response JSON size: {len(reserialized) / 1024:.1f} KB")
    # Generous: this is a sanity ceiling against an accidental O(n^2) blowup
    # in payload size, not a claim about an optimal wire format.
    assert len(reserialized) < 50_000_000
