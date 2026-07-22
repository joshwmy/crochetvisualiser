"""Canonical-JSON determinism vectors — see docs/canonical-json-audit.md.

These check the one guarantee the project's fingerprints actually need:
identical logical input always serializes to identical bytes in-process.
Not an RFC 8785 compliance test — see the audit doc for why that's not
claimed.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from enum import StrEnum


class _Stitch(StrEnum):
    SC = "sc"


def _canonical(data: object) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def test_key_order_does_not_affect_output():
    assert _canonical({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_key_order_does_not_affect_fingerprint():
    a = hashlib.sha256(_canonical({"b": 1, "a": 2}).encode()).hexdigest()
    b = hashlib.sha256(_canonical({"a": 2, "b": 1}).encode()).hexdigest()
    assert a == b == "d3626ac3" + a[8:]


def test_decimal_serializes_via_str():
    assert _canonical({"x": Decimal("1.50")}) == '{"x":"1.50"}'


def test_enum_serializes_as_its_value():
    assert _canonical({"s": _Stitch.SC}) == '{"s":"sc"}'


def test_repeated_serialization_is_byte_identical():
    data = {"nested": {"z": 1, "a": [3, 2, 1]}, "top": Decimal("2.00")}
    first = _canonical(data)
    second = _canonical(data)
    assert first == second
