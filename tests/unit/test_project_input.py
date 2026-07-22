"""Cross-field validation on ProjectInput itself (not delegated to the engine).

Regression coverage for a Phase 1.5 audit finding: requesting a brim
without a brim height used to raise a bare ``ValueError`` deep inside
``engine.brim``, which propagated past the CLI's
``CrochetReconstructionError`` handler as an unhandled traceback. The fix
moves this check to input validation, where it belongs — it is invalid
input, not an unsatisfiable-arithmetic condition.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from crochet_reconstruction.domain.enums import BrimType
from tests.conftest import make_project_input


def test_brim_enabled_without_height_is_rejected_at_input_validation() -> None:
    with pytest.raises(ValidationError, match="brim_height_cm is required"):
        make_project_input(brim_type=BrimType.BLO_IN_ROUND, brim_height_cm=None)


def test_brim_none_without_height_is_allowed() -> None:
    project_input = make_project_input(brim_type=BrimType.NONE, brim_height_cm=None)
    assert project_input.measurements.brim_height_cm is None


def test_brim_enabled_with_height_is_allowed() -> None:
    project_input = make_project_input(brim_type=BrimType.BLO_IN_ROUND)
    assert project_input.measurements.brim_height_cm is not None
