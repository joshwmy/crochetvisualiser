"""Contributor submission portal.

A small, server-rendered FastAPI application that lets invited crochet
contributors submit project photographs and metadata, and lets an
administrator review and approve them into the experiment dataset.

This package is strictly additive: it imports from
`crochet_reconstruction.physical_validation` (to validate trial links
against the live trial matrix) but nothing in `domain/`, `engine/`,
`validation/`, `rendering/`, or `physical_validation/` depends on this
package or is changed by it. The deterministic pattern engine has no
dependency on FastAPI, SQLAlchemy, or Pillow — those are declared as the
optional `portal` extra in pyproject.toml, not core dependencies.
"""
