"""RefineCardRequest/Response モデルバリデーションテスト."""

import pytest
from pydantic import ValidationError

from models.generate import RefineCardRequest, RefineCardResponse


class TestRefineCardRequestValidation:
    """RefineCardRequest のバリデーションテスト."""

    def test_both_front_and_back_valid(self):
        """表面・裏面の両方が入力された場合、valid であること."""
        req = RefineCardRequest(front="クロージャとは？", back="変数を覚えてる関数")
        assert req.front == "クロージャとは？"
        assert req.back == "変数を覚えてる関数"

    def test_front_only_valid(self):
        """表面のみ入力で valid であること."""
        req = RefineCardRequest(front="クロージャとは？")
        assert req.front == "クロージャとは？"
        assert req.back == ""

    def test_back_only_valid(self):
        """裏面のみ入力で valid であること."""
        req = RefineCardRequest(back="変数を覚えてる関数")
        assert req.front == ""
        assert req.back == "変数を覚えてる関数"

    def test_both_empty_raises_error(self):
        """表面・裏面の両方が空の場合、バリデーションエラーになること."""
        with pytest.raises(ValidationError, match="At least one of front or back"):
            RefineCardRequest(front="", back="")

    def test_both_whitespace_raises_error(self):
        """表面・裏面の両方が空白のみの場合、バリデーションエラーになること."""
        with pytest.raises(ValidationError, match="At least one of front or back"):
            RefineCardRequest(front="   ", back="  \n  ")

    def test_default_values(self):
        """デフォルト値で表面・裏面なしの場合、バリデーションエラーになること."""
        with pytest.raises(ValidationError, match="At least one of front or back"):
            RefineCardRequest()

    def test_front_max_length_exceeded(self):
        """front が 1000 文字を超える場合、バリデーションエラーになること."""
        with pytest.raises(ValidationError):
            RefineCardRequest(front="あ" * 1001)

    def test_front_at_max_length(self):
        """front がちょうど 1000 文字の場合、valid であること."""
        req = RefineCardRequest(front="あ" * 1000)
        assert len(req.front) == 1000

    def test_back_max_length_exceeded(self):
        """back が 2000 文字を超える場合、バリデーションエラーになること."""
        with pytest.raises(ValidationError):
            RefineCardRequest(back="あ" * 2001)

    def test_back_at_max_length(self):
        """back がちょうど 2000 文字の場合、valid であること."""
        req = RefineCardRequest(back="あ" * 2000)
        assert len(req.back) == 2000

    def test_language_default_ja(self):
        """language のデフォルト値が ja であること."""
        req = RefineCardRequest(front="テスト")
        assert req.language == "ja"

    def test_language_en(self):
        """language に en を指定できること."""
        req = RefineCardRequest(front="test", language="en")
        assert req.language == "en"

    def test_language_invalid(self):
        """language に無効な値を指定するとエラーになること."""
        with pytest.raises(ValidationError):
            RefineCardRequest(front="test", language="fr")


class TestRefineCardResponse:
    """RefineCardResponse のテスト."""

    def test_response_creation(self):
        """レスポンスモデルが正しく作成されること."""
        resp = RefineCardResponse(
            refined_front="改善された表面",
            refined_back="改善された裏面",
            model_used="claude-haiku-4-5-20251001",
            processing_time_ms=1500,
        )
        assert resp.refined_front == "改善された表面"
        assert resp.refined_back == "改善された裏面"
        assert resp.model_used == "claude-haiku-4-5-20251001"
        assert resp.processing_time_ms == 1500
