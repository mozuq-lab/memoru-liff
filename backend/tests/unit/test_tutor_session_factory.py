"""Unit tests for tutor_session_factory — SessionManager factory function.

Tests factory function create_tutor_session_manager() and
_get_agentcore_client() singleton behavior.
"""

import os
from unittest.mock import MagicMock, patch

import pytest


# Common test data
SESSION_ID = "tutor_test-session-001"
USER_ID = "user-001"
AGENTCORE_MEMORY_ID = "test-memory-id"
TUTOR_SESSIONS_TABLE = "memoru-tutor-sessions-dev"


# ===================================================================
# Helper: reset singleton between tests
# ===================================================================


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the module-level singleton before and after each test."""
    import services.tutor_session_factory as mod

    mod._agentcore_boto_session = None
    yield
    mod._agentcore_boto_session = None


# ===================================================================
# Normal cases
# ===================================================================


class TestCreateTutorSessionManagerAgentcore:
    """TC-001-01: agentcore backend returns AgentCoreMemorySessionManager."""

    @patch(
        "services.tutor_session_factory.AgentCoreMemorySessionManager",
        create=True,
    )
    @patch(
        "services.tutor_session_factory.AgentCoreMemoryConfig",
        create=True,
    )
    @patch(
        "services.tutor_session_factory.boto3",
    )
    def test_agentcore_backend_returns_agentcore_session_manager(
        self, mock_boto3, mock_config_cls, mock_sm_cls
    ):
        mock_boto_session = MagicMock()
        mock_boto3.Session.return_value = mock_boto_session
        mock_config_instance = MagicMock()
        mock_config_cls.return_value = mock_config_instance
        mock_sm_instance = MagicMock()
        mock_sm_cls.return_value = mock_sm_instance

        env = {
            "TUTOR_SESSION_BACKEND": "agentcore",
            "AGENTCORE_MEMORY_ID": AGENTCORE_MEMORY_ID,
        }
        with patch.dict(os.environ, env, clear=False):
            from services.tutor_session_factory import create_tutor_session_manager

            result = create_tutor_session_manager(SESSION_ID, USER_ID)

        mock_config_cls.assert_called_once_with(
            memory_id=AGENTCORE_MEMORY_ID,
            session_id=SESSION_ID,
            actor_id=USER_ID,
        )
        mock_sm_cls.assert_called_once_with(
            mock_config_instance, boto_session=mock_boto_session
        )
        assert result is mock_sm_instance


class TestCreateTutorSessionManagerDynamodb:
    """TC-001-02: dynamodb backend returns DynamoDBSessionManager."""

    @patch(
        "services.tutor_session_factory.DynamoDBSessionManager",
        create=True,
    )
    def test_dynamodb_backend_returns_dynamodb_session_manager(
        self, mock_dynamo_sm_cls
    ):
        mock_dynamo_instance = MagicMock()
        mock_dynamo_sm_cls.return_value = mock_dynamo_instance

        env = {"TUTOR_SESSION_BACKEND": "dynamodb"}
        with patch.dict(os.environ, env, clear=False):
            from services.tutor_session_factory import create_tutor_session_manager

            result = create_tutor_session_manager(SESSION_ID, USER_ID)

        mock_dynamo_sm_cls.assert_called_once_with(
            table_name=TUTOR_SESSIONS_TABLE,
            session_id=SESSION_ID,
            user_id=USER_ID,
            dynamodb_resource=None,
        )
        assert result is mock_dynamo_instance


class TestEnvironmentAutoSelection:
    """TC-103-01 / TC-103-02 / TC-103-03: environment-based auto selection."""

    @patch(
        "services.tutor_session_factory.DynamoDBSessionManager",
        create=True,
    )
    def test_dev_environment_defaults_to_dynamodb(self, mock_dynamo_sm_cls):
        """TC-103-01: ENVIRONMENT=dev without TUTOR_SESSION_BACKEND -> dynamodb."""
        mock_dynamo_instance = MagicMock()
        mock_dynamo_sm_cls.return_value = mock_dynamo_instance

        env = {"ENVIRONMENT": "dev"}
        # Ensure TUTOR_SESSION_BACKEND is not set
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("TUTOR_SESSION_BACKEND", None)
            from services.tutor_session_factory import create_tutor_session_manager

            result = create_tutor_session_manager(SESSION_ID, USER_ID)

        assert result is mock_dynamo_instance

    @patch(
        "services.tutor_session_factory.AgentCoreMemorySessionManager",
        create=True,
    )
    @patch(
        "services.tutor_session_factory.AgentCoreMemoryConfig",
        create=True,
    )
    @patch(
        "services.tutor_session_factory.boto3",
    )
    def test_prod_environment_defaults_to_agentcore(
        self, mock_boto3, mock_config_cls, mock_sm_cls
    ):
        """TC-103-02: ENVIRONMENT=prod without TUTOR_SESSION_BACKEND -> agentcore."""
        mock_sm_instance = MagicMock()
        mock_sm_cls.return_value = mock_sm_instance

        env = {
            "ENVIRONMENT": "prod",
            "AGENTCORE_MEMORY_ID": AGENTCORE_MEMORY_ID,
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("TUTOR_SESSION_BACKEND", None)
            from services.tutor_session_factory import create_tutor_session_manager

            result = create_tutor_session_manager(SESSION_ID, USER_ID)

        assert result is mock_sm_instance

    @patch(
        "services.tutor_session_factory.AgentCoreMemorySessionManager",
        create=True,
    )
    @patch(
        "services.tutor_session_factory.AgentCoreMemoryConfig",
        create=True,
    )
    @patch(
        "services.tutor_session_factory.boto3",
    )
    def test_explicit_backend_overrides_environment(
        self, mock_boto3, mock_config_cls, mock_sm_cls
    ):
        """TC-103-03: TUTOR_SESSION_BACKEND=agentcore overrides ENVIRONMENT=dev."""
        mock_sm_instance = MagicMock()
        mock_sm_cls.return_value = mock_sm_instance

        env = {
            "ENVIRONMENT": "dev",
            "TUTOR_SESSION_BACKEND": "agentcore",
            "AGENTCORE_MEMORY_ID": AGENTCORE_MEMORY_ID,
        }
        with patch.dict(os.environ, env, clear=False):
            from services.tutor_session_factory import create_tutor_session_manager

            result = create_tutor_session_manager(SESSION_ID, USER_ID)

        assert result is mock_sm_instance


# ===================================================================
# Error cases
# ===================================================================


class TestCreateTutorSessionManagerErrors:
    """TC-001-E01 / TC-001-E02: error cases."""

    def test_invalid_backend_raises_value_error(self):
        """TC-001-E01: Unknown backend value raises ValueError."""
        env = {"TUTOR_SESSION_BACKEND": "invalid"}
        with patch.dict(os.environ, env, clear=False):
            from services.tutor_session_factory import create_tutor_session_manager

            with pytest.raises(ValueError, match="Unknown TUTOR_SESSION_BACKEND: invalid"):
                create_tutor_session_manager(SESSION_ID, USER_ID)

    def test_agentcore_without_memory_id_raises_error(self):
        """TC-001-E02: agentcore backend without AGENTCORE_MEMORY_ID raises TutorAIServiceError."""
        from services.tutor_ai_service import TutorAIServiceError

        env = {"TUTOR_SESSION_BACKEND": "agentcore"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("AGENTCORE_MEMORY_ID", None)
            from services.tutor_session_factory import create_tutor_session_manager

            with pytest.raises(
                TutorAIServiceError,
                match="AGENTCORE_MEMORY_ID is required for agentcore backend",
            ):
                create_tutor_session_manager(SESSION_ID, USER_ID)


# ===================================================================
# Singleton
# ===================================================================


class TestGetAgentcoreBotoSessionSingleton:
    """TC-SINGLETON-01: _get_agentcore_boto_session() returns same instance."""

    @patch(
        "services.tutor_session_factory.boto3",
    )
    def test_returns_same_instance_on_multiple_calls(self, mock_boto3):
        """boto3.Session() constructor is called only once; same instance returned."""
        mock_session_instance = MagicMock()
        mock_boto3.Session.return_value = mock_session_instance

        from services.tutor_session_factory import _get_agentcore_boto_session

        first = _get_agentcore_boto_session()
        second = _get_agentcore_boto_session()

        assert first is second
        mock_boto3.Session.assert_called_once()
