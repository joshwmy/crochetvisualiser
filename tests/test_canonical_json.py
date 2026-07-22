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


def test_nested_objects_sort_keys_at_every_level():
    assert _canonical({"z": {"b": 1, "a": 2}, "a": 1}) == '{"a":1,"z":{"a":2,"b":1}}'


def test_arrays_preserve_element_order():
    # sort_keys only sorts object keys; array element order is data, not
    # incidental ordering, and must survive untouched.
    assert _canonical([3, 1, 2]) == "[3,1,2]"


def test_integers_serialize_as_bare_numbers():
    assert _canonical({"n": 5}) == '{"n":5}'


def test_decimal_like_value_stays_a_quoted_string():
    # A Decimal is not a JSON number type here — default=str always quotes
    # it, so "1.50" can never collide with the bare number 1.5.
    assert _canonical({"x": Decimal("1.50")}) == '{"x":"1.50"}'
    assert _canonical({"x": 1.5}) != _canonical({"x": Decimal("1.50")})


def test_unicode_strings_are_backslash_u_escaped():
    # json.dumps defaults to ensure_ascii=True — a direct RFC 8785 deviation
    # (JCS requires raw UTF-8 bytes for non-ASCII), documented in the audit.
    # Distinct inputs must still escape to distinct output.
    assert _canonical({"s": "café ☕"}) == '{"s":"caf\\u00e9 \\u2615"}'
    assert _canonical({"s": "café"}) != _canonical({"s": "cafe"})


def test_negative_zero_int_normalizes_to_zero():
    assert _canonical({"z": -0}) == '{"z":0}'


def test_negative_zero_decimal_keeps_its_sign_via_str():
    # Decimal, unlike int, distinguishes -0 from 0 in its string form — a
    # narrow case where two "logically equal" numeric inputs canonicalize
    # differently depending on which Python numeric type carried them in.
    assert _canonical({"z": Decimal("-0")}) == '{"z":"-0"}'
    assert _canonical({"z": Decimal("-0")}) != _canonical({"z": Decimal("0")})


def test_raw_float_uses_repr_formatting_not_jcs():
    # Residual risk documented in the audit: geometry Vec3/Quat tuples are
    # plain floats serialized via repr-based formatting, not routed through
    # Decimal — this is stable in-process but not proven byte-identical to
    # RFC 8785's ECMAScript-based number algorithm.
    assert _canonical({"f": 0.1 + 0.2}) == '{"f":0.30000000000000004}'
