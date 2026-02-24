"""GradeAnswerRequest / GradeAnswerResponse Pydantic モデルテスト.

TASK-0059: 回答採点モデル・プロンプト・AI実装 - TDD Red フェーズ

カテゴリ:
- TestGradeAnswerRequestValidation: user_answer フィールドのバリデーション (TC-MOD-001 ~ TC-MOD-009)
- TestGradeAnswerResponseSerialization: GradeAnswerResponse のシリアライゼーション (TC-MOD-010 ~ TC-MOD-017)

注意: backend/src/models/grading.py は未作成のため、インポートエラーでテストが失敗する。
これは TDD Red フェーズの意図した挙動である。
"""

import pytest
from pydantic import ValidationError

from models.grading import GradeAnswerRequest, GradeAnswerResponse


# ---------------------------------------------------------------------------
# Category 1: GradeAnswerRequest バリデーションテスト (TC-MOD-001 ~ TC-MOD-009)
# ---------------------------------------------------------------------------


class TestGradeAnswerRequestValidation:
    """GradeAnswerRequest バリデーションテスト."""

    def test_valid_user_answer_minimum(self):
        """TC-MOD-001: 最小長 (1文字) でバリデーション OK."""
        req = GradeAnswerRequest(user_answer="a")
        assert req.user_answer == "a"

    def test_valid_user_answer_maximum(self):
        """TC-MOD-002: 最大長 (2000文字) でバリデーション OK."""
        req = GradeAnswerRequest(user_answer="a" * 2000)
        assert len(req.user_answer) == 2000

    def test_valid_user_answer_japanese(self):
        """TC-MOD-003: 日本語テキストでバリデーション OK."""
        req = GradeAnswerRequest(user_answer="東京です")
        assert req.user_answer == "東京です"

    def test_valid_user_answer_with_leading_trailing_spaces(self):
        """TC-MOD-004: 前後に空白があっても内容があれば OK."""
        req = GradeAnswerRequest(user_answer=" hello ")
        assert req.user_answer == " hello "

    def test_empty_user_answer(self):
        """TC-MOD-005: 空文字列で ValidationError."""
        with pytest.raises(ValidationError):
            GradeAnswerRequest(user_answer="")

    def test_whitespace_only_user_answer_spaces(self):
        """TC-MOD-006: 空白のみで ValidationError."""
        with pytest.raises(ValidationError):
            GradeAnswerRequest(user_answer="   ")

    def test_whitespace_only_user_answer_mixed(self):
        """TC-MOD-007: タブ/改行混在の空白のみで ValidationError."""
        with pytest.raises(ValidationError):
            GradeAnswerRequest(user_answer="  \t\n  ")

    def test_user_answer_too_long(self):
        """TC-MOD-008: 2001 文字で ValidationError."""
        with pytest.raises(ValidationError):
            GradeAnswerRequest(user_answer="a" * 2001)

    def test_user_answer_missing(self):
        """TC-MOD-009: フィールド未指定で ValidationError."""
        with pytest.raises(ValidationError):
            GradeAnswerRequest()


# ---------------------------------------------------------------------------
# Category 2: GradeAnswerResponse シリアライゼーションテスト (TC-MOD-010 ~ TC-MOD-017)
# ---------------------------------------------------------------------------


class TestGradeAnswerResponseSerialization:
    """GradeAnswerResponse シリアライゼーションテスト."""

    def _make_response(self, **overrides):
        """テスト用レスポンスインスタンスを作成するヘルパー."""
        defaults = {
            "grade": 4,
            "reasoning": "Correct with minor hesitation",
            "card_front": "日本の首都は？",
            "card_back": "東京",
            "grading_info": {"model_used": "strands", "processing_time_ms": 1234},
        }
        defaults.update(overrides)
        return GradeAnswerResponse(**defaults)

    def test_response_all_fields(self):
        """TC-MOD-010: 全フィールド指定でインスタンス生成."""
        resp = self._make_response()
        assert resp.grade == 4
        assert resp.reasoning == "Correct with minor hesitation"
        assert resp.card_front == "日本の首都は？"
        assert resp.card_back == "東京"
        assert resp.grading_info == {"model_used": "strands", "processing_time_ms": 1234}

    def test_response_json_serialization(self):
        """TC-MOD-011: model_dump() で全フィールドが含まれる."""
        resp = self._make_response()
        data = resp.model_dump()
        assert "grade" in data
        assert "reasoning" in data
        assert "card_front" in data
        assert "card_back" in data
        assert "grading_info" in data

    def test_response_grade_boundary_zero(self):
        """TC-MOD-012: grade=0 でバリデーション OK."""
        resp = self._make_response(grade=0)
        assert resp.grade == 0

    def test_response_grade_boundary_five(self):
        """TC-MOD-013: grade=5 でバリデーション OK."""
        resp = self._make_response(grade=5)
        assert resp.grade == 5

    def test_response_grade_below_range(self):
        """TC-MOD-014: grade=-1 で ValidationError."""
        with pytest.raises(ValidationError):
            self._make_response(grade=-1)

    def test_response_grade_above_range(self):
        """TC-MOD-015: grade=6 で ValidationError."""
        with pytest.raises(ValidationError):
            self._make_response(grade=6)

    def test_response_grading_info_default_empty(self):
        """TC-MOD-016: grading_info 未指定で空辞書."""
        resp = GradeAnswerResponse(
            grade=3,
            reasoning="OK",
            card_front="Q",
            card_back="A",
        )
        assert resp.grading_info == {}

    def test_response_grading_info_with_metadata(self):
        """TC-MOD-017: メタ情報が正しく保持される."""
        info = {"model_used": "strands_bedrock", "processing_time_ms": 567}
        resp = self._make_response(grading_info=info)
        assert resp.grading_info["model_used"] == "strands_bedrock"
        assert resp.grading_info["processing_time_ms"] == 567
