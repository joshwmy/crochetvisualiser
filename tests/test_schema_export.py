"""Confirms the committed schemas/*.schema.json files match what
schema_export.generate_schema_files() produces right now — the whole point
of committing them is that they never silently drift from the Pydantic
models they describe. See docs/schema-artifacts.md.
"""

from __future__ import annotations

from pathlib import Path

from crochet_reconstruction.api.schema_export import (
    SCHEMAS_DIR,
    generate_schema_files,
    render,
)


def test_committed_schemas_match_generated_output():
    generated = generate_schema_files()
    assert generated, "generate_schema_files() must not be empty"

    for filename, schema in generated.items():
        committed_path = SCHEMAS_DIR / filename
        assert committed_path.exists(), (
            f"{committed_path} is missing — run "
            "`python -m crochet_reconstruction.api.schema_export` and commit the result."
        )
        committed_text = committed_path.read_text(encoding="utf-8")
        expected_text = render(schema)
        assert committed_text == expected_text, (
            f"{filename} is stale relative to its Pydantic model — re-run "
            "`python -m crochet_reconstruction.api.schema_export` and commit the result."
        )


def test_no_extra_committed_schema_files():
    generated_filenames = set(generate_schema_files().keys())
    committed_filenames = {p.name for p in SCHEMAS_DIR.glob("*.schema.json")}
    assert committed_filenames == generated_filenames, (
        "schemas/ contains files generate_schema_files() doesn't know about (or vice versa) — "
        f"committed={committed_filenames} generated={generated_filenames}"
    )


def test_every_schema_has_deterministic_identity_fields():
    for filename, schema in generate_schema_files().items():
        assert schema["$id"].endswith(filename)
        assert schema["$schema"]
        assert schema["version"]


def test_generation_is_reproducible_byte_for_byte():
    first = {name: render(schema) for name, schema in generate_schema_files().items()}
    second = {name: render(schema) for name, schema in generate_schema_files().items()}
    assert first == second


def test_geometry_document_schema_version_matches_model():
    from crochet_reconstruction.geometry.models import GEOMETRY_SCHEMA_VERSION

    schema = generate_schema_files()["geometry_document.schema.json"]
    assert schema["version"] == GEOMETRY_SCHEMA_VERSION


def test_stitch_graph_schema_version_matches_model():
    from crochet_reconstruction.graph.models import GRAPH_SCHEMA_VERSION

    schema = generate_schema_files()["stitch_graph.schema.json"]
    assert schema["version"] == GRAPH_SCHEMA_VERSION


def test_write_schema_files_is_idempotent(tmp_path: Path):
    from crochet_reconstruction.api.schema_export import write_schema_files

    write_schema_files(tmp_path)
    first_pass = {p.name: p.read_text(encoding="utf-8") for p in tmp_path.glob("*.schema.json")}
    write_schema_files(tmp_path)
    second_pass = {p.name: p.read_text(encoding="utf-8") for p in tmp_path.glob("*.schema.json")}
    assert first_pass == second_pass
