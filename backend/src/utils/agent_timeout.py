"""Timeout helpers for blocking AI SDK calls."""
from __future__ import annotations

import os
import queue
import threading
from collections.abc import Callable
from typing import TypeVar, cast

T = TypeVar("T")

DEFAULT_AGENT_TIMEOUT_SECONDS = 25.0


def resolve_timeout_seconds(
    env_name: str,
    default: float = DEFAULT_AGENT_TIMEOUT_SECONDS,
) -> float:
    """Resolve a positive timeout value from an environment variable."""
    raw = os.getenv(env_name)
    if raw is None:
        return default

    try:
        value = float(raw)
    except ValueError:
        return default

    return value if value > 0 else default


def run_with_timeout(
    fn: Callable[[], T],
    timeout_seconds: float,
    operation_name: str,
) -> T:
    """Run a blocking callable and raise TimeoutError if it takes too long."""
    result_queue: queue.Queue[tuple[bool, T | BaseException]] = queue.Queue(maxsize=1)

    def target() -> None:
        try:
            result_queue.put((True, fn()))
        except BaseException as exc:  # noqa: BLE001 - preserve provider exception type
            result_queue.put((False, exc))

    thread_name = operation_name.lower().replace(" ", "-")[:64]
    thread = threading.Thread(target=target, name=thread_name, daemon=True)
    thread.start()

    try:
        succeeded, value = result_queue.get(timeout=timeout_seconds)
    except queue.Empty as exc:
        raise TimeoutError(
            f"{operation_name} exceeded {timeout_seconds:g} seconds"
        ) from exc

    if succeeded:
        return cast(T, value)

    if isinstance(value, BaseException):
        raise value
    raise RuntimeError(f"{operation_name} failed without an exception")
