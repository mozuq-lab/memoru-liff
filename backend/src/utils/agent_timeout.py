"""Timeout configuration helpers for AI provider clients."""
from __future__ import annotations

import math
import os
from collections.abc import Sequence

AGENT_TIMEOUT_ENV = "AI_AGENT_TIMEOUT_SECONDS"
TUTOR_AGENT_TIMEOUT_ENV = "TUTOR_AI_AGENT_TIMEOUT_SECONDS"

DEFAULT_AGENT_TIMEOUT_SECONDS = 30.0
DEFAULT_TUTOR_AGENT_TIMEOUT_SECONDS = 60.0
MAX_AGENT_TIMEOUT_SECONDS = 300.0


def resolve_timeout_seconds(
    env_names: str | Sequence[str],
    default: float = DEFAULT_AGENT_TIMEOUT_SECONDS,
    max_seconds: float = MAX_AGENT_TIMEOUT_SECONDS,
) -> float:
    """Resolve a finite positive timeout value from environment variables."""
    names = (env_names,) if isinstance(env_names, str) else tuple(env_names)

    for env_name in names:
        raw = os.getenv(env_name)
        if raw is None:
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        if math.isfinite(value) and value > 0:
            return min(value, max_seconds)

    if not math.isfinite(default) or default <= 0:
        raise ValueError("default timeout must be a finite positive number")
    return min(default, max_seconds)
