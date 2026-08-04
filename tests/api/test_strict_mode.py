"""``options.strict`` across both compile paths, plus the shared policy itself.

The behaviour that matters most here is the *default*: `strict` defaults to
false and must reproduce the pre-strict behaviour exactly, so enabling strict
mode is opt-in and no existing caller changes behaviour by upgrading.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from crochet_reconstruction.api.app import create_app
from crochet_reconstruction.api.config import ApiSettings
from crochet_reconstruction.api.schemas import CompileOptions
from crochet_reconstruction.api.strict_mode import (
    strict_block_message,
    strict_blocking_diagnostics,
)
from crochet_reconstruction.diagram.diagnostics import DiagramDiagnostic, DiagramDiagnosticCode
from crochet_reconstruction.parsing.written.diagnostics import Diagnostic, DiagnosticCode

AMIGURUMI_EXAMPLE = """\
Round 1: 6 sc in magic ring [6]
Round 2: inc in each stitch around [12]
Round 3: (sc, inc) repeat 6 times [18]
"""


def client() -> TestClient:
    return TestClient(create_app(ApiSettings()))


def _compile(source: str, **options: bool) -> dict:
    payload: dict[str, object] = {"source": source}
    if options:
        payload["options"] = options
    return client().post("/api/visualizer/compile", json=payload).json()


class TestSharedPolicy:
    def test_warnings_block(self):
        warning = DiagramDiagnostic(
            severity="warning",
            code=DiagramDiagnosticCode.NON_ADJACENT_DECREASE_PARENTS,
            message="non-contiguous decrease",
        )
        assert strict_blocking_diagnostics([warning]) == [warning]

    def test_assumption_applied_blocks_despite_being_info_severity(self):
        assumption = Diagnostic(
            severity="info",
            code=DiagnosticCode.ASSUMPTION_APPLIED,
            message="default gauge used",
        )
        assert strict_blocking_diagnostics([assumption]) == [assumption]

    def test_other_info_diagnostics_do_not_block(self):
        info = DiagramDiagnostic(
            severity="info",
            code=DiagramDiagnosticCode.MISSING_CENTRE,
            message="centre estimated",
        )
        assert strict_blocking_diagnostics([info]) == []

    def test_errors_are_not_this_policys_business(self):
        """Errors already block in both modes; strict must not double-count."""
        error = Diagnostic(severity="error", code=DiagnosticCode.INVALID_SYNTAX, message="bad line")
        assert strict_blocking_diagnostics([error]) == []

    def test_original_order_is_preserved(self):
        first = Diagnostic(severity="info", code=DiagnosticCode.ASSUMPTION_APPLIED, message="one")
        second = Diagnostic(
            severity="warning", code=DiagnosticCode.STITCH_COUNT_MISMATCH, message="two"
        )
        assert strict_blocking_diagnostics([first, second]) == [first, second]

    def test_empty_when_nothing_objectionable(self):
        assert strict_blocking_diagnostics([]) == []

    def test_message_names_the_distinct_codes_without_repeating_messages(self):
        blocking = [
            Diagnostic(severity="info", code=DiagnosticCode.ASSUMPTION_APPLIED, message="a"),
            Diagnostic(severity="info", code=DiagnosticCode.ASSUMPTION_APPLIED, message="b"),
        ]
        message = strict_block_message(blocking)
        assert "ASSUMPTION_APPLIED" in message
        assert message.count("ASSUMPTION_APPLIED") == 1
        assert "2 diagnostic(s)" in message
        assert "strict = false" in message


class TestWrittenCompilePath:
    def test_strict_defaults_to_false(self):
        assert CompileOptions().strict is False

    def test_default_request_compiles_exactly_as_before(self):
        data = _compile(AMIGURUMI_EXAMPLE)
        assert data["success"] is True
        assert data["summary"]["stitchCount"] == 36

    def test_explicit_non_strict_matches_the_default(self):
        assert (
            _compile(AMIGURUMI_EXAMPLE)["summary"]
            == _compile(AMIGURUMI_EXAMPLE, strict=False)["summary"]
        )

    def test_strict_blocks_a_compile_that_relied_on_the_default_gauge(self):
        data = _compile(AMIGURUMI_EXAMPLE, strict=True)
        assert data["success"] is False
        assert any(d["code"] == "STRICT_MODE_BLOCKED" for d in data["diagnostics"])

    def test_strict_failure_keeps_the_offending_diagnostics_alongside_the_block(self):
        """The client must be able to see *what* strict objected to."""
        data = _compile(AMIGURUMI_EXAMPLE, strict=True)
        assert any(d["code"] == "ASSUMPTION_APPLIED" for d in data["diagnostics"])

    def test_strict_failure_uses_the_standard_failure_shape(self):
        data = _compile(AMIGURUMI_EXAMPLE, strict=True)
        assert data["pattern"] is None
        assert data["stitchGraph"] is None
        assert data["geometry"] is None
        assert data["summary"] is None

    def test_strict_does_not_mask_a_genuine_error_with_a_strictness_complaint(self):
        data = _compile("Round 1: 6 xyz in magic ring [6]\n", strict=True)
        assert data["success"] is False
        assert any(d["code"] == "INVALID_SYNTAX" for d in data["diagnostics"])
        assert not any(d["code"] == "STRICT_MODE_BLOCKED" for d in data["diagnostics"])

    def test_strict_response_leaks_no_traceback(self):
        response = client().post(
            "/api/visualizer/compile",
            json={"source": AMIGURUMI_EXAMPLE, "options": {"strict": True}},
        )
        assert "Traceback" not in response.text
        assert "site-packages" not in response.text


class TestDiagramAnalyse:
    """`disconnected_chart.svg` deterministically emits an AMBIGUOUS_CENTRE
    warning while still analysing to `readyToCompile: true` — exactly the case
    strict analysis is meant to catch."""

    @pytest.fixture
    def warning_svg(self) -> str:
        from tests.diagram.conftest import load_fixture

        return load_fixture("disconnected_chart.svg")

    def _analyse(self, svg: str, **options: object) -> dict:
        payload: dict[str, object] = {"svgSource": svg}
        if options:
            payload["options"] = options
        return client().post("/api/visualizer/diagram/analyse", json=payload).json()

    def test_lenient_analysis_reports_ready_despite_the_warning(self, warning_svg):
        data = self._analyse(warning_svg)
        assert any(d["code"] == "AMBIGUOUS_CENTRE" for d in data["diagnostics"])
        assert data["summary"]["readyToCompile"] is True

    def test_strict_analysis_withholds_readiness(self, warning_svg):
        assert self._analyse(warning_svg, strict=True)["summary"]["readyToCompile"] is False

    def test_strict_analysis_still_returns_the_document(self, warning_svg):
        """Strict tightens the readiness verdict; it never refuses to report
        the chart, or the user would have nothing to correct in 2D review."""
        data = self._analyse(warning_svg, strict=True)
        assert data["success"] is True
        assert data["diagram"] is not None
        assert data["summary"]["symbolCount"] > 0


class TestDiagramCompile:
    """`invalid_decrease.svg` compiles successfully while emitting a
    NON_ADJACENT_DECREASE_PARENTS warning — deliberately a warning, not an
    error (docs/known-limitations.md), so strict is the only thing that blocks
    it."""

    @pytest.fixture
    def compiled_warning_diagram(self) -> dict:
        from tests.diagram.conftest import load_fixture

        svg = load_fixture("invalid_decrease.svg")
        analysed = client().post("/api/visualizer/diagram/analyse", json={"svgSource": svg}).json()
        return analysed["diagram"]

    def _compile(self, diagram: dict, **options: object) -> dict:
        payload: dict[str, object] = {"diagram": diagram, "corrections": {}}
        if options:
            payload["options"] = options
        return client().post("/api/visualizer/diagram/compile", json=payload).json()

    def test_lenient_compile_succeeds_with_the_warning_attached(self, compiled_warning_diagram):
        data = self._compile(compiled_warning_diagram)
        assert data["success"] is True
        assert any(d["code"] == "NON_ADJACENT_DECREASE_PARENTS" for d in data["diagnostics"])

    def test_strict_compile_blocks_on_the_same_warning(self, compiled_warning_diagram):
        data = self._compile(compiled_warning_diagram, strict=True)
        assert data["success"] is False
        assert any(d["code"] == "STRICT_MODE_BLOCKED" for d in data["diagnostics"])
        assert data["stitchGraph"] is None
        assert data["geometry"] is None
        assert data["summary"] is None

    def test_strict_compile_still_returns_the_corrected_document(self, compiled_warning_diagram):
        """The user must be able to see what strict objected to and fix it."""
        data = self._compile(compiled_warning_diagram, strict=True)
        assert data["diagram"] is not None
        assert any(d["code"] == "NON_ADJACENT_DECREASE_PARENTS" for d in data["diagnostics"])

    def test_default_compile_matches_explicit_non_strict(self, compiled_warning_diagram):
        default = self._compile(compiled_warning_diagram)
        explicit = self._compile(compiled_warning_diagram, strict=False)
        assert default["summary"] == explicit["summary"]
