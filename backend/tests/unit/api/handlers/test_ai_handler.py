"""Unit tests for AI handler — focus on browser profile ownership validation.

Regression tests for the IDOR vulnerability where another user's profile_id
could be passed to BrowserService and used to access their authenticated
browser session.
"""

import json
from unittest.mock import MagicMock, patch


class TestGenerateFromUrlProfileOwnership:
    """POST /cards/generate-from-url の profile_id 所有者検証テスト."""

    def test_rejects_unowned_profile_id(self, api_gateway_event, lambda_context):
        """他ユーザーの profile_id を渡したら 404 を返す (IDOR 防止)."""
        event = api_gateway_event(
            method="POST",
            path="/cards/generate-from-url",
            body={
                "url": "https://example.com/page",
                "profile_id": "bp-stolen123",
            },
            user_id="user-victim",
        )

        with patch(
            "api.handlers.ai_handler.BrowserProfileService"
        ) as mock_profile_cls, patch(
            "api.handlers.ai_handler.UrlContentService"
        ) as mock_url_cls, patch(
            "api.handlers.ai_handler.BrowserService"
        ), patch(
            "api.handlers.ai_handler.create_ai_service"
        ), patch(
            "api.handlers.ai_handler.CardService"
        ):
            mock_profile = MagicMock()
            mock_profile.validate_profile.return_value = False
            mock_profile_cls.return_value = mock_profile

            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert "Profile not found" in body["error"]
        # 重要: 不一致時には UrlContentService が呼ばれないこと
        mock_url_cls.assert_not_called()
        mock_profile.validate_profile.assert_called_once_with(
            "user-victim", "bp-stolen123"
        )

    def test_validates_profile_before_fetch(self, api_gateway_event, lambda_context):
        """所有者一致なら検証をパスし、UrlContentService が呼ばれる."""
        event = api_gateway_event(
            method="POST",
            path="/cards/generate-from-url",
            body={
                "url": "https://example.com/page",
                "profile_id": "bp-owned",
            },
            user_id="user-owner",
        )

        with patch(
            "api.handlers.ai_handler.BrowserProfileService"
        ) as mock_profile_cls, patch(
            "api.handlers.ai_handler.UrlContentService"
        ) as mock_url_cls, patch(
            "api.handlers.ai_handler.BrowserService"
        ), patch(
            "api.handlers.ai_handler.create_ai_service"
        ) as mock_ai_create, patch(
            "api.handlers.ai_handler.chunk_content"
        ) as mock_chunk, patch(
            "api.handlers.ai_handler.CardService"
        ) as mock_card_service_cls:
            mock_profile = MagicMock()
            mock_profile.validate_profile.return_value = True
            mock_profile_cls.return_value = mock_profile

            mock_url = MagicMock()
            mock_url.fetch_content.return_value = MagicMock(
                url="https://example.com/page",
                title="t",
                text_content="x" * 200,
                fetch_method="browser",
                fetched_at="2026-05-09T00:00:00+00:00",
            )
            mock_url_cls.return_value = mock_url

            mock_chunk.return_value = [MagicMock(text="x" * 200)]
            mock_card_service_cls.return_value.list_cards.return_value = ([], None)

            mock_ai = MagicMock()
            mock_ai.generate_cards_from_chunks.return_value = MagicMock(
                cards=[
                    MagicMock(front="f", back="b", suggested_tags=[]),
                ],
                model_used="claude",
                processing_time_ms=10,
            )
            mock_ai_create.return_value = mock_ai

            from api.handler import handler

            response = handler(event, lambda_context)

        # validate_profile が user_id と profile_id 両方で呼ばれていること
        mock_profile.validate_profile.assert_called_once_with(
            "user-owner", "bp-owned"
        )
        # UrlContentService.fetch_content が profile_id 付きで呼ばれること
        mock_url.fetch_content.assert_called_once()
        call_kwargs = mock_url.fetch_content.call_args.kwargs
        assert call_kwargs.get("profile_id") == "bp-owned"
        assert response["statusCode"] == 200

    def test_skips_validation_when_no_profile_id(
        self, api_gateway_event, lambda_context
    ):
        """profile_id が無いリクエストでは validate_profile を呼ばない."""
        event = api_gateway_event(
            method="POST",
            path="/cards/generate-from-url",
            body={"url": "https://example.com/page"},
            user_id="user-1",
        )

        with patch(
            "api.handlers.ai_handler.BrowserProfileService"
        ) as mock_profile_cls, patch(
            "api.handlers.ai_handler.UrlContentService"
        ) as mock_url_cls, patch(
            "api.handlers.ai_handler.BrowserService"
        ), patch(
            "api.handlers.ai_handler.create_ai_service"
        ) as mock_ai_create, patch(
            "api.handlers.ai_handler.chunk_content"
        ) as mock_chunk, patch(
            "api.handlers.ai_handler.CardService"
        ) as mock_card_service_cls:
            mock_url = MagicMock()
            mock_url.fetch_content.return_value = MagicMock(
                url="https://example.com/page",
                title="t",
                text_content="x" * 200,
                fetch_method="http",
                fetched_at="2026-05-09T00:00:00+00:00",
            )
            mock_url_cls.return_value = mock_url

            mock_chunk.return_value = [MagicMock(text="x" * 200)]
            mock_card_service_cls.return_value.list_cards.return_value = ([], None)

            mock_ai = MagicMock()
            mock_ai.generate_cards_from_chunks.return_value = MagicMock(
                cards=[
                    MagicMock(front="f", back="b", suggested_tags=[]),
                ],
                model_used="claude",
                processing_time_ms=10,
            )
            mock_ai_create.return_value = mock_ai

            from api.handler import handler

            handler(event, lambda_context)

        mock_profile_cls.assert_not_called()
