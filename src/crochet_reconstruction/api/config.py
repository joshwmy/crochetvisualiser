"""Environment-driven configuration for the visualizer compile API.

No secrets: this API has no auth, no database, no file storage — the only
configuration surface is CORS and the request-size limit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ApiSettings:
    environment: str = "development"
    cors_allow_origins: list[str] = field(default_factory=lambda: ["http://localhost:5173"])
    max_source_length: int = 50_000
    """Characters. Generous for any hand-typed pattern; well under a size
    that could cause meaningful parsing latency (the parser is O(lines))."""

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


def load_settings() -> ApiSettings:
    environment = os.environ.get("VISUALIZER_ENVIRONMENT", "development")
    origins_raw = os.environ.get("VISUALIZER_CORS_ORIGINS")
    origins = (
        [origin.strip() for origin in origins_raw.split(",") if origin.strip()]
        if origins_raw
        else ["http://localhost:5173"]
    )
    max_length_raw = os.environ.get("VISUALIZER_MAX_SOURCE_LENGTH")
    max_length = int(max_length_raw) if max_length_raw else 50_000
    return ApiSettings(
        environment=environment, cors_allow_origins=origins, max_source_length=max_length
    )
