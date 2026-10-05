"""``POST /api/visualizer/diagram/analyse`` and ``.../compile``: success
paths, structured errors, no traceback leakage, no persistence, stable
fingerprints.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from crochet_reconstruction.api.app import create_app

MAGIC_RING_6SC = """<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" \
viewBox="0 0 400 400">
<g id="ring" data-stitch-type="magic_ring" transform="translate(200,200)"><circle r="8"/></g>
<g data-stitch-type="single_crochet" transform="translate(230,200)"></g>
<g data-stitch-type="single_crochet" transform="translate(215,226.02)"></g>
<g data-stitch-type="single_crochet" transform="translate(185,226.02)"></g>
<g data-stitch-type="single_crochet" transform="translate(170,200)"></g>
<g data-stitch-type="single_crochet" transform="translate(185,173.98)"></g>
<g data-stitch-type="single_crochet" transform="translate(215,173.98)"></g>
</svg>"""


def client():
    return TestClient(create_app())


def test_analyse_success():
    r = client().post("/api/visualizer/diagram/analyse", json={"svgSource": MAGIC_RING_6SC})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["summary"]["symbolCount"] == 7
    assert data["summary"]["readyToCompile"] is True
    # DiagramDocument is a deep domain payload, not the thin API wrapper —
    # it stays snake_case on the wire, matching how StitchGraph/
    # GeometryDocument are also carried un-renamed inside CompileResponse.
    assert data["diagram"]["schema_version"] == "1.0.0"


def test_compile_success_end_to_end():
    c = client()
    analysed = c.post("/api/visualizer/diagram/analyse", json={"svgSource": MAGIC_RING_6SC}).json()
    r = c.post(
        "/api/visualizer/diagram/compile",
        json={"diagram": analysed["diagram"], "corrections": {}},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["sourceKind"] == "svg_diagram"
    assert len(data["stitchGraph"]["nodes"]) == 6
    assert len(data["geometry"]["stitches"]) == 6
    assert data["summary"]["graphFingerprint"] is not None


def test_analyse_invalid_xml_returns_structured_error_not_500():
    r = client().post(
        "/api/visualizer/diagram/analyse", json={"svgSource": "<svg><circle r=5></svg>"}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False
    assert data["diagnostics"][0]["code"] == "INVALID_SVG"


def test_analyse_unsafe_svg_returns_structured_error():
    r = client().post(
        "/api/visualizer/diagram/analyse",
        json={
            "svgSource": '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
            "<script>alert(1)</script></svg>"
        },
    )
    data = r.json()
    assert data["success"] is False
    assert data["diagnostics"][0]["code"] == "UNSAFE_SVG_CONTENT"
    assert data["diagram"] is None


def test_analyse_excessive_source_returns_structured_error():
    huge = "<g>" * 30000
    svg_source = f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">{huge}</svg>'
    r = client().post("/api/visualizer/diagram/analyse", json={"svgSource": svg_source})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False


def test_compile_blocked_by_unresolved_errors():
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">
<g id="ring" data-stitch-type="magic_ring" transform="translate(100,100)"><circle r="5"/></g>
<rect id="mystery" x="115" y="95" width="10" height="10"/>
<g data-stitch-type="single_crochet" transform="translate(115,130)"></g>
<g data-stitch-type="single_crochet" transform="translate(85,130)"></g>
<g data-stitch-type="single_crochet" transform="translate(70,100)"></g>
<g data-stitch-type="single_crochet" transform="translate(85,70)"></g>
<g data-stitch-type="single_crochet" transform="translate(115,70)"></g>
</svg>"""
    c = client()
    analysed = c.post("/api/visualizer/diagram/analyse", json={"svgSource": svg}).json()
    assert analysed["summary"]["readyToCompile"] is False

    r = c.post(
        "/api/visualizer/diagram/compile", json={"diagram": analysed["diagram"], "corrections": {}}
    )
    data = r.json()
    assert data["success"] is False
    assert data["stitchGraph"] is None


def test_compile_with_corrections_succeeds():
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">
<g id="ring" data-stitch-type="magic_ring" transform="translate(100,100)"><circle r="5"/></g>
<rect id="mystery" x="115" y="95" width="10" height="10"/>
<g data-stitch-type="single_crochet" transform="translate(115,130)"></g>
<g data-stitch-type="single_crochet" transform="translate(85,130)"></g>
<g data-stitch-type="single_crochet" transform="translate(70,100)"></g>
<g data-stitch-type="single_crochet" transform="translate(85,70)"></g>
<g data-stitch-type="single_crochet" transform="translate(115,70)"></g>
</svg>"""
    c = client()
    analysed = c.post("/api/visualizer/diagram/analyse", json={"svgSource": svg}).json()
    mystery = next(s for s in analysed["diagram"]["symbols"] if s["source_element_id"] == "mystery")

    r = c.post(
        "/api/visualizer/diagram/compile",
        json={
            "diagram": analysed["diagram"],
            # DiagramCorrectionSet is also a deep domain payload (snake_case).
            "corrections": {
                "symbol_overrides": {mystery["symbol_id"]: {"stitch_type": "single_crochet"}}
            },
        },
    )
    data = r.json()
    assert data["success"] is True
    assert len(data["stitchGraph"]["nodes"]) == 6


def test_compile_fingerprints_are_stable_across_requests():
    c = client()
    analysed = c.post("/api/visualizer/diagram/analyse", json={"svgSource": MAGIC_RING_6SC}).json()
    r1 = c.post(
        "/api/visualizer/diagram/compile", json={"diagram": analysed["diagram"], "corrections": {}}
    ).json()
    r2 = c.post(
        "/api/visualizer/diagram/compile", json={"diagram": analysed["diagram"], "corrections": {}}
    ).json()
    assert r1["summary"]["graphFingerprint"] == r2["summary"]["graphFingerprint"]
    assert r1["summary"]["geometryFingerprint"] == r2["summary"]["geometryFingerprint"]


def test_no_raw_traceback_in_any_response_body():
    r = client().post("/api/visualizer/diagram/analyse", json={"svgSource": "not xml at all"})
    assert "Traceback" not in r.text
    assert "site-packages" not in r.text


def test_diagram_response_never_echoes_raw_svg_source():
    r = client().post("/api/visualizer/diagram/analyse", json={"svgSource": MAGIC_RING_6SC})
    assert "<svg" not in r.text


def test_analyse_endpoint_rejects_missing_body_field():
    r = client().post("/api/visualizer/diagram/analyse", json={})
    assert r.status_code == 422


def test_written_pattern_workflow_still_works_unaffected():
    """The diagram endpoints must not have disturbed the existing
    written-pattern compile route (same app, separate router)."""
    r = client().post(
        "/api/visualizer/compile",
        json={"source": "Round 1: magic ring, 6 sc in ring. (6)\n"},
    )
    assert r.status_code == 200
