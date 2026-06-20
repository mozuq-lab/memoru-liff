"""Unit tests for AI handler — focus on the disabled browser-profile path.

While the AgentCore Browser integration is disabled, the handler must reject
profile_id requests with 501 Not Implemented (rather than a generic 500 from
inside BrowserService) and must NOT touch BrowserProfileService / BrowserService
in that path. Re-enable these tests in the IDOR-validation form when the
browser integration is restored.
"""

import json
from unittest.mock import MagicMock, patch


class TestGenerateFromUrlProfileIdDisabled:
    """POST /cards/generate-from-url の profile_id は 501 で即拒否される。"""

    def test_profile_id_returns_501(self, api_gateway_event, lambda_context):
        """profile_id を渡すと 501 Not Implemented が返り、ブラウザ系サービスは
        一切呼ばれない (壊れた経路に入らないこと)。"""
        event = api_gateway_event(
            method="POST",
            path="/cards/generate-from-url",
            body={
                "url": "https://example.com/page",
                "profile_id": "bp-anything",
            },
            user_id="user-1",
        )

        with patch("api.handlers.ai_handler.UrlContentService") as mock_url_cls, patch(
            "api.handlers.ai_handler.BrowserService"
        ) as mock_browser_cls, patch(
            "api.handlers.ai_handler.create_ai_service"
        ) as mock_ai_create, patch(
            "api.handlers.ai_handler.CardService"
        ):
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 501
        body = json.loads(response["body"])
        assert body["code"] == "browser_unavailable"
        assert "対応していません" in body["error"]

        # 壊れた経路に入っていないこと
        mock_url_cls.assert_not_called()
        mock_browser_cls.assert_not_called()
        mock_ai_create.assert_not_called()

    def test_no_profile_id_proceeds_normally(
        self, api_gateway_event, lambda_context
    ):
        """profile_id 無しのリクエストは通常フローで動く (HTTP fetch 経路)。"""
        event = api_gateway_event(
            method="POST",
            path="/cards/generate-from-url",
            body={"url": "https://example.com/page"},
            user_id="user-1",
        )

        with patch(
            "api.handlers.ai_handler.UrlContentService"
        ) as mock_url_cls, patch(
            "api.handlers.ai_handler.BrowserService"
        ), patch(
            "services.url_generation_service.create_ai_service"
        ) as mock_ai_create, patch(
            "services.url_generation_service.chunk_content"
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
            mock_card_service_cls.return_value.find_cards_by_reference_url.return_value = []

            mock_ai = MagicMock()
            mock_ai.generate_cards_from_chunks.return_value = MagicMock(
                cards=[MagicMock(front="f", back="b", suggested_tags=[])],
                model_used="claude",
                processing_time_ms=10,
            )
            mock_ai_create.return_value = mock_ai

            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        # profile_id を無視した上で UrlContentService が呼ばれている
        mock_url.fetch_content.assert_called_once()
        call_kwargs = mock_url.fetch_content.call_args.kwargs
        assert call_kwargs.get("profile_id") is None


class TestGenerateFromUrlDuplicateWarning:
    """C-5: duplicate detection uses paginated find_cards_by_reference_url."""

    def test_duplicate_url_sets_warning(self, api_gateway_event, lambda_context):
        """A card matching the URL (even beyond page 1) yields a warning."""
        event = api_gateway_event(
            method="POST",
            path="/cards/generate-from-url",
            body={"url": "https://example.com/dup"},
            user_id="user-1",
        )

        with patch(
            "api.handlers.ai_handler.UrlContentService"
        ) as mock_url_cls, patch(
            "api.handlers.ai_handler.BrowserService"
        ), patch(
            "services.url_generation_service.create_ai_service"
        ) as mock_ai_create, patch(
            "services.url_generation_service.chunk_content"
        ) as mock_chunk, patch(
            "api.handlers.ai_handler.CardService"
        ) as mock_card_service_cls:
            mock_url = MagicMock()
            mock_url.fetch_content.return_value = MagicMock(
                url="https://example.com/dup",
                title="t",
                text_content="x" * 200,
                fetch_method="http",
                fetched_at="2026-05-09T00:00:00+00:00",
            )
            mock_url_cls.return_value = mock_url
            mock_chunk.return_value = [MagicMock(text="x" * 200)]

            # The paginated lookup finds a pre-existing card for this URL.
            mock_card_service_cls.return_value.find_cards_by_reference_url.return_value = [
                MagicMock()
            ]

            mock_ai = MagicMock()
            mock_ai.generate_cards_from_chunks.return_value = MagicMock(
                cards=[MagicMock(front="f", back="b", suggested_tags=[])],
                model_used="claude",
                processing_time_ms=10,
            )
            mock_ai_create.return_value = mock_ai

            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body.get("warning")
        # list_cards must NOT be used for the duplicate check anymore.
        mock_card_service_cls.return_value.list_cards.assert_not_called()
        mock_card_service_cls.return_value.find_cards_by_reference_url.assert_called_once_with(
            "user-1", "https://example.com/dup"
        )
