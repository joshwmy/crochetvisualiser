"""API tests for POST /api/visualizer/compile and GET /healthz."""

from __future__ import annotations

from fastapi.testclient import TestClient

from crochet_reconstruction.api.app import create_app
from crochet_reconstruction.api.config import ApiSettings

AMIGURUMI_EXAMPLE = """\
Round 1: 6 sc in magic ring [6]
Round 2: inc in each stitch around [12]
Round 3: (sc, inc) repeat 6 times [18]
Rounds 4-6: sc around [18]
Round 7: (sc, dec) repeat 6 times [12]
Round 8: dec around [6]
"""


def client() -> TestClient:
    return TestClient(create_app(ApiSettings()))


def test_health_endpoint():
    response = client().get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_successful_compile_returns_full_payload():
    response = client().post("/api/visualizer/compile", json={"source": AMIGURUMI_EXAMPLE})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["summary"]["stitchCount"] == 108
    assert data["summary"]["componentCount"] == 1
    assert data["summary"]["sectionCount"] == 8
    assert data["summary"]["graphFingerprint"]
    assert data["summary"]["geometryFingerprint"]
    assert len(data["stitchGraph"]["nodes"]) == 108
    assert len(data["geometry"]["stitches"]) == 108
    assert data["pattern"]["components"][0]["kind"] == "piece"


def test_invalid_syntax_returns_structured_diagnostics_not_pattern():
    response = client().post(
        "/api/visualizer/compile", json={"source": "Round 1: 6 xyz in magic ring [6]\n"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["pattern"] is None
    assert data["stitchGraph"] is None
    assert data["geometry"] is None
    assert data["summary"] is None
    assert any(d["code"] == "INVALID_SYNTAX" for d in data["diagnostics"])


def test_unsupported_syntax():
    response = client().post("/api/visualizer/compile", json={"source": "Round 1: 10 ch [10]\n"})
    data = response.json()
    assert data["success"] is False
    assert any(d["code"] == "UNSUPPORTED_SYNTAX" for d in data["diagnostics"])


def test_stitch_count_mismatch():
    response = client().post(
        "/api/visualizer/compile",
        json={"source": "Round 1: 6 sc in magic ring [6]\nRound 2: inc around [999]\n"},
    )
    data = response.json()
    assert data["success"] is False
    assert any(d["code"] == "STITCH_COUNT_MISMATCH" for d in data["diagnostics"])


def test_empty_input():
    response = client().post("/api/visualizer/compile", json={"source": ""})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert any(d["code"] == "EMPTY_INPUT" for d in data["diagnostics"])


def test_input_size_limit_returns_structured_diagnostic_not_500():
    tiny_settings = ApiSettings(max_source_length=50)
    test_client = TestClient(create_app(tiny_settings))
    long_source = "Round 1: 6 sc in magic ring [6]\n" * 10
    response = test_client.post("/api/visualizer/compile", json={"source": long_source})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert any(d["code"] == "INPUT_TOO_LARGE" for d in data["diagnostics"])


def test_invalid_terminology_is_rejected_as_request_validation_error():
    response = client().post(
        "/api/visualizer/compile", json={"source": AMIGURUMI_EXAMPLE, "terminology": "UK"}
    )
    assert response.status_code == 422
    # Must be FastAPI's own structured validation-error envelope, not a raw
    # Python traceback.
    body = response.json()
    assert "detail" in body
    assert "Traceback" not in response.text


def test_malformed_json_is_rejected_cleanly():
    response = client().post(
        "/api/visualizer/compile",
        content=b"{not valid json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert "Traceback" not in response.text


def test_no_traceback_leakage_on_any_response():
    # Sweep a handful of inputs designed to probe edge cases and confirm
    # none ever echoes Python internals back to the client.
    probes = [
        {"source": ""},
        {"source": "Round 1: 6 xyz in magic ring [6]\n"},
        {"source": "Round 1: 6 sc in magic ring [6]\nRound 2: dec around [999]\n"},
        {"source": "a" * 200},
    ]
    for payload in probes:
        response = client().post("/api/visualizer/compile", json=payload)
        assert "Traceback" not in response.text
        assert "site-packages" not in response.text


def test_fingerprints_are_stable_across_repeated_compiles():
    responses = [
        client().post("/api/visualizer/compile", json={"source": AMIGURUMI_EXAMPLE}).json()
        for _ in range(2)
    ]
    first, second = responses
    assert first["summary"]["graphFingerprint"] == second["summary"]["graphFingerprint"]
    assert first["summary"]["geometryFingerprint"] == second["summary"]["geometryFingerprint"]


def test_cors_configuration_reflects_allowed_origin():
    settings = ApiSettings(cors_allow_origins=["http://example-viewer.test"])
    test_client = TestClient(create_app(settings))
    response = test_client.options(
        "/api/visualizer/compile",
        headers={
            "Origin": "http://example-viewer.test",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://example-viewer.test"


def test_cors_rejects_unlisted_origin():
    settings = ApiSettings(cors_allow_origins=["http://example-viewer.test"])
    test_client = TestClient(create_app(settings))
    response = test_client.options(
        "/api/visualizer/compile",
        headers={
            "Origin": "http://not-allowed.test",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers.get("access-control-allow-origin") != "http://not-allowed.test"
