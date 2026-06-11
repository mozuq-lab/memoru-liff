"""Unit tests for browser profile management service (T039)."""

from unittest.mock import MagicMock, patch


from services.browser_profile_service import (
    BrowserProfileService,
    BrowserProfile,
)


class TestBrowserProfileTableName:
    """Tests for table name resolution (I-8)."""

    @patch("services.browser_profile_service.boto3")
    def test_default_table_name_has_dev_suffix(self, mock_boto3: MagicMock) -> None:
        """Default table name should follow the -dev convention (I-8)."""
        mock_dynamodb = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb

        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("BROWSER_PROFILES_TABLE", None)
            service = BrowserProfileService()

        assert service._table_name == "memoru-browser-profiles-dev"
        mock_dynamodb.Table.assert_called_once_with("memoru-browser-profiles-dev")

    @patch("services.browser_profile_service.boto3")
    def test_env_var_overrides_default(self, mock_boto3: MagicMock) -> None:
        """BROWSER_PROFILES_TABLE env var should override the default."""
        mock_dynamodb = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb

        with patch.dict(
            "os.environ", {"BROWSER_PROFILES_TABLE": "custom-table"}, clear=False
        ):
            service = BrowserProfileService()

        assert service._table_name == "custom-table"

    @patch("services.browser_profile_service.boto3")
    def test_explicit_arg_overrides_env_and_default(
        self, mock_boto3: MagicMock
    ) -> None:
        """Explicit table_name arg should take precedence over env and default."""
        mock_dynamodb = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb

        with patch.dict(
            "os.environ", {"BROWSER_PROFILES_TABLE": "env-table"}, clear=False
        ):
            service = BrowserProfileService(table_name="explicit-table")

        assert service._table_name == "explicit-table"


class TestBrowserProfileService:
    """Tests for BrowserProfileService."""

    @patch("services.browser_profile_service.boto3")
    def test_create_profile(self, mock_boto3: MagicMock) -> None:
        """Create a new browser profile."""
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        service = BrowserProfileService()
        profile = service.create_profile(
            user_id="user-123",
            name="My Profile",
        )

        assert isinstance(profile, BrowserProfile)
        assert profile.user_id == "user-123"
        assert profile.name == "My Profile"
        assert profile.profile_id is not None
        mock_table.put_item.assert_called_once()

    @patch("services.browser_profile_service.boto3")
    def test_list_profiles(self, mock_boto3: MagicMock) -> None:
        """List profiles for a user."""
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "profile_id": "profile-1",
                    "user_id": "user-123",
                    "name": "Profile 1",
                    "created_at": "2026-03-06T10:00:00Z",
                },
                {
                    "profile_id": "profile-2",
                    "user_id": "user-123",
                    "name": "Profile 2",
                    "created_at": "2026-03-06T11:00:00Z",
                },
            ]
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        service = BrowserProfileService()
        profiles = service.list_profiles("user-123")

        assert len(profiles) == 2
        assert profiles[0].name == "Profile 1"
        assert profiles[1].name == "Profile 2"

    @patch("services.browser_profile_service.boto3")
    def test_list_profiles_empty(self, mock_boto3: MagicMock) -> None:
        """Returns empty list when user has no profiles."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        service = BrowserProfileService()
        profiles = service.list_profiles("user-no-profiles")

        assert profiles == []

    @patch("services.browser_profile_service.boto3")
    def test_get_profile(self, mock_boto3: MagicMock) -> None:
        """Get a specific profile by ID."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "profile_id": "profile-1",
                "user_id": "user-123",
                "name": "My Profile",
                "created_at": "2026-03-06T10:00:00Z",
            }
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        service = BrowserProfileService()
        profile = service.get_profile("user-123", "profile-1")

        assert profile is not None
        assert profile.profile_id == "profile-1"

    @patch("services.browser_profile_service.boto3")
    def test_get_profile_not_found(self, mock_boto3: MagicMock) -> None:
        """Returns None when profile not found."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        service = BrowserProfileService()
        profile = service.get_profile("user-123", "nonexistent")

        assert profile is None

    @patch("services.browser_profile_service.boto3")
    def test_get_profile_wrong_user(self, mock_boto3: MagicMock) -> None:
        """Returns None when querying with wrong user_id (composite key prevents cross-user access)."""
        mock_table = MagicMock()
        # With composite key (user_id + profile_id), DynamoDB returns no item for wrong user
        mock_table.get_item.return_value = {}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        service = BrowserProfileService()
        profile = service.get_profile("user-123", "profile-1")

        assert profile is None
        mock_table.get_item.assert_called_once_with(
            Key={"user_id": "user-123", "profile_id": "profile-1"},
        )

    @patch("services.browser_profile_service.boto3")
    def test_delete_profile(self, mock_boto3: MagicMock) -> None:
        """Delete a profile."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "profile_id": "profile-1",
                "user_id": "user-123",
                "name": "To Delete",
                "created_at": "2026-03-06T10:00:00Z",
            }
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        service = BrowserProfileService()
        result = service.delete_profile("user-123", "profile-1")

        assert result is True
        mock_table.delete_item.assert_called_once()

    @patch("services.browser_profile_service.boto3")
    def test_delete_profile_not_found(self, mock_boto3: MagicMock) -> None:
        """Delete returns False when profile not found."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        service = BrowserProfileService()
        result = service.delete_profile("user-123", "nonexistent")

        assert result is False

    @patch("services.browser_profile_service.boto3")
    def test_validate_profile_exists(self, mock_boto3: MagicMock) -> None:
        """Validate returns True for existing profile owned by user."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "profile_id": "profile-1",
                "user_id": "user-123",
                "name": "Valid",
                "created_at": "2026-03-06T10:00:00Z",
            }
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        service = BrowserProfileService()
        assert service.validate_profile("user-123", "profile-1") is True

    @patch("services.browser_profile_service.boto3")
    def test_validate_profile_not_exists(self, mock_boto3: MagicMock) -> None:
        """Validate returns False for nonexistent profile."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        service = BrowserProfileService()
        assert service.validate_profile("user-123", "nonexistent") is False
