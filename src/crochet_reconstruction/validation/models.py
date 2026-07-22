"""Mutable report builder used while running the validation rule catalogue.

:class:`~crochet_reconstruction.domain.pattern.ValidationResult` and
``ValidationReport`` are frozen (the *output* of validation must be
immutable), so accumulation during a validation pass happens here instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from crochet_reconstruction.domain.enums import PatternStatus, Severity
from crochet_reconstruction.domain.pattern import ValidationReport, ValidationResult


@dataclass(slots=True)
class ReportBuilder:
    results: list[ValidationResult] = field(default_factory=list)

    def _add(
        self,
        rule_id: str,
        severity: Severity,
        path: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.results.append(
            ValidationResult(
                rule_id=rule_id,
                severity=severity,
                path=path,
                message=message,
                details=details or {},
            )
        )

    def fatal(
        self, rule_id: str, path: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        self._add(rule_id, Severity.FATAL, path, message, details)

    def confirm(
        self, rule_id: str, path: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        self._add(rule_id, Severity.REQUIRES_CONFIRMATION, path, message, details)

    def warning(
        self, rule_id: str, path: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        self._add(rule_id, Severity.WARNING, path, message, details)

    def info(
        self, rule_id: str, path: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        self._add(rule_id, Severity.INFORMATIONAL, path, message, details)

    @property
    def has_fatal(self) -> bool:
        return any(r.severity is Severity.FATAL for r in self.results)

    @property
    def has_requires_confirmation(self) -> bool:
        return any(r.severity is Severity.REQUIRES_CONFIRMATION for r in self.results)

    def build(self, engine_version: str) -> ValidationReport:
        if self.has_fatal:
            status = PatternStatus.INVALID
        elif self.has_requires_confirmation:
            status = PatternStatus.REQUIRES_CONFIRMATION
        else:
            status = PatternStatus.VALID
        return ValidationReport(
            status=status, engine_version=engine_version, results=list(self.results)
        )
