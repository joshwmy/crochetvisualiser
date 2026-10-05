"""Cross-platform stability of ``geometry_fingerprint``.

Windows (MSVC UCRT) and Linux (glibc) libm disagree by one ulp on some
results — e.g. ``math.sin(4 * math.pi / 3)`` is ``-0x1.bb67ae8584ca9p-1`` on
UCRT and ``-0x1.bb67ae8584ca8p-1`` on glibc 2.41. Hashing raw float ``repr``
made the same pattern fingerprint differently per OS, so the fingerprint now
hashes floats quantised to ``FINGERPRINT_FLOAT_DECIMALS`` places. See
docs/canonical-json-audit.md, "Cross-platform float stability".
"""

from __future__ import annotations

import math

import pytest

from crochet_reconstruction.api.service import compile_written_pattern
from crochet_reconstruction.geometry.layout import (
    FINGERPRINT_FLOAT_DECIMALS,
    _quantise_floats,
    compute_geometry_fingerprint,
)
from crochet_reconstruction.geometry.models import GeometryDocument

# Mirrors viewer/src/examples.ts::AMIGURUMI_EXAMPLE.
AMIGURUMI_EXAMPLE = """\
Round 1: 6 sc in magic ring [6]
Round 2: inc in each stitch around [12]
Round 3: (sc, inc) repeat 6 times [18]
Rounds 4-6: sc around [18]
Round 7: (sc, dec) repeat 6 times [12]
Round 8: dec around [6]
"""

# Verified identical on Windows 11 / CPython 3.13.7 and in the Dockerfile.api
# image (python:3.13-slim, glibc 2.41, CPython 3.13.16). A deliberate geometry
# change legitimately moves this value: re-pin it, and re-check it on both OSes.
AMIGURUMI_GEOMETRY_FINGERPRINT = "7242327f8580500064c8ada79a4392cbee0cdac71ea82a3dacec5ebc7f55f809"


def _map_floats(value, fn):
    if isinstance(value, float):
        return fn(value)
    if isinstance(value, dict):
        return {k: _map_floats(v, fn) for k, v in value.items()}
    if isinstance(value, list):
        return [_map_floats(v, fn) for v in value]
    return value


def _float_leaves(value):
    if isinstance(value, float):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _float_leaves(v)
    elif isinstance(value, list):
        for v in value:
            yield from _float_leaves(v)


@pytest.fixture(scope="module")
def amigurumi_geometry() -> GeometryDocument:
    response = compile_written_pattern(AMIGURUMI_EXAMPLE, max_source_length=100_000)
    assert response.success, response.diagnostics
    assert response.geometry is not None
    return response.geometry


def _perturbed(document: GeometryDocument, fn) -> GeometryDocument:
    return GeometryDocument.model_validate(_map_floats(document.model_dump(mode="json"), fn))


def test_amigurumi_geometry_fingerprint_is_pinned_across_platforms(amigurumi_geometry):
    assert amigurumi_geometry.geometry_fingerprint == AMIGURUMI_GEOMETRY_FINGERPRINT


@pytest.mark.parametrize("direction", [math.inf, -math.inf])
def test_one_ulp_libm_noise_does_not_change_fingerprint(amigurumi_geometry, direction):
    noisy = _perturbed(amigurumi_geometry, lambda x: math.nextafter(x, direction))
    assert noisy != amigurumi_geometry
    assert compute_geometry_fingerprint(noisy) == amigurumi_geometry.geometry_fingerprint


def test_observed_ucrt_vs_glibc_sin_values_quantise_identically():
    ucrt = float.fromhex("-0x1.bb67ae8584ca9p-1")
    glibc = float.fromhex("-0x1.bb67ae8584ca8p-1")
    assert ucrt != glibc
    assert _quantise_floats(ucrt) == _quantise_floats(glibc)


def test_negative_zero_hashes_like_zero():
    assert repr(_quantise_floats(-0.0)) == "0.0"
    assert repr(_quantise_floats(-1e-17)) == "0.0"


def test_real_geometry_change_still_changes_fingerprint(amigurumi_geometry):
    shift = 10.0 ** -(FINGERPRINT_FLOAT_DECIMALS - 2)
    moved = amigurumi_geometry.stitches[0].model_copy(
        update={"position": tuple(c + shift for c in amigurumi_geometry.stitches[0].position)}
    )
    changed = amigurumi_geometry.model_copy(
        update={"stitches": [moved, *amigurumi_geometry.stitches[1:]]}
    )
    assert compute_geometry_fingerprint(changed) != amigurumi_geometry.geometry_fingerprint


def test_emitted_geometry_keeps_full_float_precision(amigurumi_geometry):
    # Quantisation applies to the hash input only; the payload the viewer
    # renders is never rounded.
    floats = list(_float_leaves(amigurumi_geometry.model_dump(mode="json")))
    assert any(round(x, FINGERPRINT_FLOAT_DECIMALS) != x for x in floats)
