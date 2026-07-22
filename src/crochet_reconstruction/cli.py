"""Minimal CLI for manual testing of the deterministic pattern engine.

    python -m crochet_reconstruction.cli generate \\
        --input examples/adult_beanie_sc.json \\
        --output build/adult_beanie_sc/

Writes ``pattern.json`` (structured pattern, the source of truth),
``validation_report.json``, and — only if validation has no fatal result —
``pattern.txt`` (human-readable instructions). Exit code is 0 on a fully
valid, rendered pattern; 1 if validation produced fatal results (structured
output is still written); 2 on malformed input; 3 if the requested
measurements/gauge/template combination cannot be sized at all.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from crochet_reconstruction.domain.errors import CrochetReconstructionError
from crochet_reconstruction.domain.pattern import ProjectInput
from crochet_reconstruction.engine.compiler import compile_pattern
from crochet_reconstruction.physical_validation.evaluation_report import generate_evaluation_report
from crochet_reconstruction.physical_validation.review_pack import generate_expert_review_pack
from crochet_reconstruction.physical_validation.trial_matrix import (
    MINIMUM_TRIAL_SET,
    RECOMMENDED_EXTENDED_MINIMUM_SET,
)
from crochet_reconstruction.rendering.text_renderer import render_text


def _generate(input_path: Path, output_dir: Path) -> int:
    try:
        # utf-8-sig transparently strips a BOM if present (common from
        # Windows editors/tools) and behaves identically to utf-8 otherwise.
        raw = json.loads(input_path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        print(f"error: could not read input file {input_path}: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"error: input file {input_path} is not valid JSON: {exc}", file=sys.stderr)
        return 2

    try:
        project_input = ProjectInput.model_validate(raw)
    except PydanticValidationError as exc:
        print("error: input failed validation and was not repaired:", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 2

    try:
        pattern = compile_pattern(project_input)
    except CrochetReconstructionError as exc:
        print(f"error: pattern could not be compiled: {exc}", file=sys.stderr)
        return 3

    output_dir.mkdir(parents=True, exist_ok=True)

    pattern_path = output_dir / "pattern.json"
    pattern_path.write_text(
        json.dumps(pattern.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8"
    )

    assert pattern.validation is not None  # compile_pattern always attaches a report
    validation_path = output_dir / "validation_report.json"
    validation_path.write_text(
        json.dumps(pattern.validation.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(f"status: {pattern.validation.status.value}")
    print(f"fingerprint: {pattern.fingerprint}")
    print(f"wrote {pattern_path}")
    print(f"wrote {validation_path}")

    if pattern.validation.has_fatal:
        print(
            "error: pattern has fatal validation results; instructions were not rendered.",
            file=sys.stderr,
        )
        return 1

    text_path = output_dir / "pattern.txt"
    text_path.write_text(render_text(pattern), encoding="utf-8")
    print(f"wrote {text_path}")
    return 0


def _expert_review_pack(output_dir: Path) -> int:
    rows = generate_expert_review_pack(output_dir)
    print(f"generated {len(rows)} trials under {output_dir}")
    print(f"minimum physical trial set (4): {', '.join(MINIMUM_TRIAL_SET)}")
    print(f"recommended extended set (6): {', '.join(RECOMMENDED_EXTENDED_MINIMUM_SET)}")
    fatal_trials = [row.trial_id for row in rows if row.validation_status != "valid"]
    if fatal_trials:
        print(
            f"warning: {len(fatal_trials)} trial(s) have non-valid software "
            f"validation status: {', '.join(fatal_trials)} — see their "
            f"validation.json before assigning to a physical tester",
            file=sys.stderr,
        )
    print(f"see {output_dir / 'index.md'}")
    return 0


def _evaluate(trials_dir: Path, results_dir: Path, output_dir: Path) -> int:
    if not (trials_dir / "trial-matrix.json").exists():
        print(
            f"error: {trials_dir} does not look like an expert-review pack "
            f"(no trial-matrix.json found)",
            file=sys.stderr,
        )
        return 2
    if not results_dir.is_dir():
        print(f"error: results directory {results_dir} does not exist", file=sys.stderr)
        return 2

    generate_evaluation_report(trials_dir, results_dir, output_dir)
    print(f"wrote evaluation report to {output_dir}")
    print(f"see {output_dir / 'summary.md'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crochet_reconstruction")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generate a pattern from a JSON input file.")
    generate.add_argument(
        "--input", required=True, type=Path, help="Path to a ProjectInput JSON file."
    )
    generate.add_argument(
        "--output", required=True, type=Path, help="Directory to write outputs into."
    )

    review_pack = subparsers.add_parser(
        "expert-review-pack",
        help="Generate the Phase 1.5 physical-validation expert-review pack.",
    )
    review_pack.add_argument(
        "--output",
        type=Path,
        default=Path("build/expert_review"),
        help="Directory to write the review pack into (default: build/expert_review).",
    )

    evaluate = subparsers.add_parser(
        "evaluate", help="Ingest physical trial results and generate an evaluation report."
    )
    evaluate.add_argument(
        "--trials",
        required=True,
        type=Path,
        help="Path to a generated expert-review pack (e.g. build/expert_review/).",
    )
    evaluate.add_argument(
        "--results",
        required=True,
        type=Path,
        help="Directory of submitted PhysicalTrialResult JSON files.",
    )
    evaluate.add_argument(
        "--output",
        type=Path,
        default=Path("build/physical_evaluation"),
        help="Directory to write the evaluation report into (default: build/physical_evaluation).",
    )

    create_admin = subparsers.add_parser(
        "portal-create-admin", help="Create a contributor-portal administrator account."
    )
    create_admin.add_argument("--username", required=True)
    create_admin.add_argument(
        "--password",
        default=None,
        help="If omitted, reads PORTAL_ADMIN_PASSWORD or prompts interactively (never echoed).",
    )

    create_invitation = subparsers.add_parser(
        "portal-create-invitation", help="Create a contributor invitation link."
    )
    create_invitation.add_argument(
        "--label", required=True, help="A note identifying this invitation."
    )
    create_invitation.add_argument("--expiry-days", type=int, default=None)
    create_invitation.add_argument("--max-uses", type=int, default=1)

    export_approved = subparsers.add_parser(
        "portal-export-approved",
        help="Export approved contributor submissions to a dataset directory.",
    )
    export_approved.add_argument("--output", required=True, type=Path)

    backup = subparsers.add_parser(
        "portal-backup",
        help="Create a timestamped backup archive of the portal database and images.",
    )
    backup.add_argument(
        "--output", required=True, type=Path, help="Directory to write the backup archive into."
    )

    return parser


def _portal_create_admin(username: str, password: str | None) -> int:
    # Imported lazily: the deterministic engine and its base install must
    # never require fastapi/sqlalchemy/pillow (see pyproject's `portal`
    # extra). Only these portal-* subcommands touch that code.
    import getpass
    import os
    from datetime import UTC, datetime

    from crochet_reconstruction.portal.config import get_settings
    from crochet_reconstruction.portal.db import create_all_tables, get_session_factory
    from crochet_reconstruction.portal.models import AdminUser
    from crochet_reconstruction.portal.security import hash_password

    get_settings().ensure_data_directories()
    create_all_tables()

    if not password:
        password = os.environ.get("PORTAL_ADMIN_PASSWORD")
    if not password:
        password = getpass.getpass(f"Password for {username}: ")
    if len(password) < 12:
        print("error: password must be at least 12 characters", file=sys.stderr)
        return 2

    from sqlalchemy.exc import IntegrityError

    db = get_session_factory()()
    try:
        admin = AdminUser(
            username=username,
            password_hash=hash_password(password),
            is_active=True,
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(admin)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            print(f"error: an admin user {username!r} already exists", file=sys.stderr)
            return 2
    finally:
        db.close()

    print(f"created admin user {username!r}")
    return 0


def _portal_create_invitation(label: str, expiry_days: int | None, max_uses: int) -> int:
    from crochet_reconstruction.portal.config import get_settings
    from crochet_reconstruction.portal.db import create_all_tables, get_session_factory
    from crochet_reconstruction.portal.services import create_invitation

    settings = get_settings()
    settings.ensure_data_directories()
    create_all_tables()

    db = get_session_factory()()
    try:
        _invitation, token = create_invitation(
            db,
            label=label,
            expiry_days=expiry_days or settings.invitation_default_expiry_days,
            max_uses=max_uses,
        )
    finally:
        db.close()

    print(f"invitation created: {label!r} (max uses: {max_uses})")
    print(f"invitation link: /invite/{token}")
    print(
        "This token is shown only once and is not recoverable if lost — "
        "create a new invitation instead."
    )
    return 0


def _portal_export_approved(output: Path) -> int:
    from crochet_reconstruction.portal.config import get_settings
    from crochet_reconstruction.portal.db import get_session_factory
    from crochet_reconstruction.portal.dependencies import get_storage
    from crochet_reconstruction.portal.services import export_approved_projects

    get_settings().ensure_data_directories()
    db = get_session_factory()()
    try:
        summary = export_approved_projects(db, get_storage(), output)
    finally:
        db.close()

    print(f"exported {summary['project_count']} project(s) to {summary['output_dir']}")
    return 0


def _portal_backup(output: Path) -> int:
    import shutil
    from datetime import datetime

    from crochet_reconstruction.portal.config import get_settings

    settings = get_settings()
    settings.ensure_data_directories()
    output.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    archive_base = output / f"portal_backup_{timestamp}"
    archive_path = shutil.make_archive(
        str(archive_base), "zip", root_dir=settings.data_dir, base_dir="."
    )
    print(f"backup written to {archive_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "generate":
        return _generate(args.input, args.output)
    if args.command == "expert-review-pack":
        return _expert_review_pack(args.output)
    if args.command == "evaluate":
        return _evaluate(args.trials, args.results, args.output)
    if args.command == "portal-create-admin":
        return _portal_create_admin(args.username, args.password)
    if args.command == "portal-create-invitation":
        return _portal_create_invitation(args.label, args.expiry_days, args.max_uses)
    if args.command == "portal-export-approved":
        return _portal_export_approved(args.output)
    if args.command == "portal-backup":
        return _portal_backup(args.output)
    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
