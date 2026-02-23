"""Unit tests for LearningAdviceResponse Pydantic model (TC-061-MODEL-001 ~ TC-061-MODEL-010)."""

import json
import pytest
from pydantic import ValidationError
from models.advice import LearningAdviceResponse


class TestLearningAdviceResponse:
    """Tests for LearningAdviceResponse Pydantic model."""

    def test_learning_advice_response_all_fields(self):
        """TC-061-MODEL-001: instance is created successfully when all fields are supplied."""
        response = LearningAdviceResponse(
            advice_text="数学の復習を増やしましょう。",
            weak_areas=["math", "grammar"],
            recommendations=["毎日5枚の数学カードを復習する", "文法ルールを暗記する"],
            study_stats={"total_reviews": 145, "average_grade": 3.8, "streak_days": 12},
            advice_info={"model_used": "strands", "processing_time_ms": 2456},
        )

        assert response.advice_text == "数学の復習を増やしましょう。"
        assert response.weak_areas == ["math", "grammar"]
        assert response.recommendations == ["毎日5枚の数学カードを復習する", "文法ルールを暗記する"]
        assert response.study_stats == {
            "total_reviews": 145,
            "average_grade": 3.8,
            "streak_days": 12,
        }
        assert response.advice_info == {
            "model_used": "strands",
            "processing_time_ms": 2456,
        }

    def test_learning_advice_response_default_weak_areas(self):
        """TC-061-MODEL-002: weak_areas defaults to [] when omitted."""
        response = LearningAdviceResponse(
            advice_text="Good progress!",
            study_stats={"total_reviews": 100},
            advice_info={"model_used": "strands"},
        )

        assert response.weak_areas == []

    def test_learning_advice_response_default_recommendations(self):
        """TC-061-MODEL-003: recommendations defaults to [] when omitted."""
        response = LearningAdviceResponse(
            advice_text="Keep studying!",
            study_stats={"total_reviews": 50},
            advice_info={"model_used": "strands"},
        )

        assert response.recommendations == []

    def test_learning_advice_response_model_dump(self):
        """TC-061-MODEL-004: model_dump() returns a dict containing all fields."""
        response = LearningAdviceResponse(
            advice_text="Study more.",
            weak_areas=["vocab"],
            recommendations=["Review daily"],
            study_stats={"total_reviews": 50},
            advice_info={"model_used": "strands"},
        )
        dumped = response.model_dump()

        assert isinstance(dumped, dict)
        assert "advice_text" in dumped
        assert "weak_areas" in dumped
        assert "recommendations" in dumped
        assert "study_stats" in dumped
        assert "advice_info" in dumped
        assert dumped["advice_text"] == "Study more."
        assert dumped["weak_areas"] == ["vocab"]

    def test_learning_advice_response_model_dump_json(self):
        """TC-061-MODEL-005: model_dump_json() returns a valid JSON string."""
        response = LearningAdviceResponse(
            advice_text="Keep going!",
            weak_areas=["reading"],
            recommendations=["Read 10 pages daily"],
            study_stats={"total_reviews": 200, "average_grade": 4.1},
            advice_info={"model_used": "strands", "processing_time_ms": 1500},
        )
        json_str = response.model_dump_json()

        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["advice_text"] == "Keep going!"
        assert parsed["study_stats"]["total_reviews"] == 200

    def test_learning_advice_response_requires_advice_text(self):
        """TC-061-MODEL-006: omitting advice_text raises ValidationError."""
        with pytest.raises(ValidationError):
            LearningAdviceResponse(
                # advice_text omitted
                study_stats={"total_reviews": 10},
                advice_info={"model_used": "strands"},
            )

    def test_learning_advice_response_requires_study_stats(self):
        """TC-061-MODEL-007: omitting study_stats raises ValidationError."""
        with pytest.raises(ValidationError):
            LearningAdviceResponse(
                advice_text="Some advice",
                # study_stats omitted
                advice_info={"model_used": "strands"},
            )

    def test_learning_advice_response_requires_advice_info(self):
        """TC-061-MODEL-008: omitting advice_info raises ValidationError."""
        with pytest.raises(ValidationError):
            LearningAdviceResponse(
                advice_text="Some advice",
                study_stats={"total_reviews": 10},
                # advice_info omitted
            )

    def test_learning_advice_response_study_stats_typical_values(self):
        """TC-061-MODEL-009: study_stats accepts all typical ReviewSummary fields."""
        response = LearningAdviceResponse(
            advice_text="Great progress!",
            study_stats={
                "total_reviews": 145,
                "average_grade": 3.8,
                "streak_days": 12,
                "total_cards": 32,
                "cards_due_today": 5,
            },
            advice_info={"model_used": "strands"},
        )

        assert response.study_stats["total_reviews"] == 145
        assert response.study_stats["average_grade"] == 3.8
        assert response.study_stats["streak_days"] == 12
        assert response.study_stats["total_cards"] == 32
        assert response.study_stats["cards_due_today"] == 5

    def test_learning_advice_response_advice_info_typical_values(self):
        """TC-061-MODEL-010: advice_info accepts typical metadata fields."""
        response = LearningAdviceResponse(
            advice_text="Keep studying!",
            study_stats={"total_reviews": 100},
            advice_info={
                "model_used": "strands",
                "processing_time_ms": 2456,
            },
        )

        assert response.advice_info["model_used"] == "strands"
        assert response.advice_info["processing_time_ms"] == 2456
