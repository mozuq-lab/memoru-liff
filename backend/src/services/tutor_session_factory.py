"""SessionManager factory — select backend based on environment variables.

Provides create_tutor_session_manager() factory function and
_get_agentcore_client() singleton for MemoryClient initialization.
"""

from __future__ import annotations

import os
import sys

from aws_lambda_powertools import Logger

logger = Logger()

# Singleton for AgentCore MemoryClient
_agentcore_client = None

# These will be populated by lazy imports or overridden by test patches (create=True).
# Using module-level names so unittest.mock.patch can intercept them.
MemoryClient = None
AgentCoreMemorySessionManager = None
AgentCoreMemoryConfig = None
DynamoDBSessionManager = None


def _ensure_agentcore_imports():
    """Lazy-import AgentCore SDK classes into module namespace."""
    _mod = sys.modules[__name__]
    if _mod.MemoryClient is None:
        from bedrock_agentcore.memory import MemoryClient as _MC

        _mod.MemoryClient = _MC
    if _mod.AgentCoreMemoryConfig is None:
        from bedrock_agentcore.memory.integrations.strands.config import (
            AgentCoreMemoryConfig as _Cfg,
        )

        _mod.AgentCoreMemoryConfig = _Cfg
    if _mod.AgentCoreMemorySessionManager is None:
        from bedrock_agentcore.memory.integrations.strands.session_manager import (
            AgentCoreMemorySessionManager as _SM,
        )

        _mod.AgentCoreMemorySessionManager = _SM


def _ensure_dynamodb_imports():
    """Lazy-import DynamoDBSessionManager into module namespace."""
    _mod = sys.modules[__name__]
    if _mod.DynamoDBSessionManager is None:
        from services.tutor_session_manager import DynamoDBSessionManager as _DSM

        _mod.DynamoDBSessionManager = _DSM


def _get_agentcore_client():
    """Return a singleton MemoryClient instance (lazy initialization)."""
    global _agentcore_client
    if _agentcore_client is None:
        _ensure_agentcore_imports()
        _agentcore_client = MemoryClient()
    return _agentcore_client


def create_tutor_session_manager(
    session_id: str,
    user_id: str,
    backend: str | None = None,
):
    """Create a SessionManager based on backend selection.

    Args:
        session_id: Tutor session ID.
        user_id: User ID (used as actor_id for AgentCore).
        backend: Explicit backend override. None reads from env vars.

    Returns:
        A SessionManager instance (AgentCoreMemorySessionManager or DynamoDBSessionManager).

    Raises:
        ValueError: If backend value is not 'agentcore' or 'dynamodb'.
        TutorAIServiceError: If AGENTCORE_MEMORY_ID is missing for agentcore backend.
    """
    if backend is None:
        backend = os.environ.get("TUTOR_SESSION_BACKEND", "")

    if not backend:
        # Auto-select based on ENVIRONMENT
        environment = os.environ.get("ENVIRONMENT", "prod")
        if environment == "dev":
            backend = "dynamodb"
        else:
            backend = "agentcore"
        logger.info("Auto-selected session backend", backend=backend, environment=environment)

    if backend == "agentcore":
        memory_id = os.environ.get("AGENTCORE_MEMORY_ID", "")
        if not memory_id:
            from services.tutor_ai_service import TutorAIServiceError

            raise TutorAIServiceError(
                "AGENTCORE_MEMORY_ID is required for agentcore backend"
            )

        client = _get_agentcore_client()

        config = AgentCoreMemoryConfig(
            memory_id=memory_id,
            session_id=session_id,
            actor_id=user_id,
        )
        return AgentCoreMemorySessionManager(config, memory_client=client)

    elif backend == "dynamodb":
        _ensure_dynamodb_imports()
        table_name = os.environ.get(
            "TUTOR_SESSIONS_TABLE", "memoru-tutor-sessions-dev"
        )
        return DynamoDBSessionManager(
            table_name=table_name,
            session_id=session_id,
            user_id=user_id,
        )

    else:
        raise ValueError(f"Unknown TUTOR_SESSION_BACKEND: {backend}")
