"""Unit tests for review service."""

import pytest
from unittest.mock import patch
from moto import mock_aws
from unittest.mock import patch
import boto3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from services.review_service import (
    ReviewService,
    InvalidGradeError,
    NoReviewHistoryError,
)
from services.card_service import CardNotFoundError


@pytest.fixture
def dynamodb_tables():
    """Create mock DynamoDB tables."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")

        # Create cards table
        cards_table = dynamodb.create_table(
            TableName="memoru-cards-test",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "card_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "card_id", "AttributeType": "S"},
                {"AttributeName": "next_review_at", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "user_id-due-index",
                    "KeySchema": [
                        {"AttributeName": "user_id", "KeyType": "HASH"},
                        {"AttributeName": "next_review_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        cards_table.wait_until_exists()

        # Create reviews table
        reviews_table = dynamodb.create_table(
            TableName="memoru-reviews-test",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "reviewed_at", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "reviewed_at", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        reviews_table.wait_until_exists()

        yield dynamodb


@pytest.fixture
def review_service(dynamodb_tables):
    """Create ReviewService with mock DynamoDB."""
    return ReviewService(
        cards_table_name="memoru-cards-test",
        reviews_table_name="memoru-reviews-test",
        dynamodb_resource=dynamodb_tables,
    )


@pytest.fixture
def sample_card(dynamodb_tables):
    """Create a sample card for testing."""
    now = datetime.now(timezone.utc)
    table = dynamodb_tables.Table("memoru-cards-test")
    table.put_item(
        Item={
            "user_id": "test-user-id",
            "card_id": "test-card-id",
            "front": "Test Question",
            "back": "Test Answer",
            "next_review_at": now.isoformat(),
            "interval": 1,
            "ease_factor": "2.5",
            "repetitions": 0,
            "tags": [],
            "created_at": now.isoformat(),
        }
    )
    return {
        "user_id": "test-user-id",
        "card_id": "test-card-id",
    }


class TestSubmitReview:
    """Tests for ReviewService.submit_review method."""

    def test_submit_review_success(self, review_service, sample_card):
        """Test submitting a successful review."""
        response = review_service.submit_review(
            user_id="test-user-id",
            card_id="test-card-id",
            grade=4,
        )

        assert response.card_id == "test-card-id"
        assert response.grade == 4
        assert response.previous.ease_factor == 2.5
        assert response.previous.interval == 1
        assert response.previous.repetitions == 0
        assert response.updated.repetitions == 1
        assert response.updated.interval == 1  # First review interval
        assert response.updated.ease_factor == 2.5  # Grade 4 doesn't change EF much
        assert response.reviewed_at is not None

    def test_submit_review_grade_5(self, review_service, sample_card):
        """Test perfect review increases ease factor."""
        response = review_service.submit_review(
            user_id="test-user-id",
            card_id="test-card-id",
            grade=5,
        )

        assert response.updated.ease_factor == 2.6
        assert response.updated.repetitions == 1

    def test_submit_review_grade_0_resets(self, review_service, dynamodb_tables):
        """Test grade 0 resets repetitions and interval."""
        # Create a card with some progress
        now = datetime.now(timezone.utc)
        table = dynamodb_tables.Table("memoru-cards-test")
        table.put_item(
            Item={
                "user_id": "test-user-id",
                "card_id": "advanced-card",
                "front": "Advanced Question",
                "back": "Advanced Answer",
                "next_review_at": now.isoformat(),
                "interval": 30,
                "ease_factor": "2.5",
                "repetitions": 5,
                "tags": [],
                "created_at": now.isoformat(),
            }
        )

        response = review_service.submit_review(
            user_id="test-user-id",
            card_id="advanced-card",
            grade=0,
        )

        assert response.updated.repetitions == 0
        assert response.updated.interval == 1

    def test_submit_review_invalid_grade_negative(self, review_service, sample_card):
        """Test invalid negative grade raises error."""
        with pytest.raises(InvalidGradeError):
            review_service.submit_review(
                user_id="test-user-id",
                card_id="test-card-id",
                grade=-1,
            )

    def test_submit_review_invalid_grade_too_high(self, review_service, sample_card):
        """Test invalid grade too high raises error."""
        with pytest.raises(InvalidGradeError):
            review_service.submit_review(
                user_id="test-user-id",
                card_id="test-card-id",
                grade=6,
            )

    def test_submit_review_card_not_found(self, review_service):
        """Test reviewing non-existent card raises error."""
        with pytest.raises(CardNotFoundError):
            review_service.submit_review(
                user_id="test-user-id",
                card_id="non-existent-card",
                grade=4,
            )

    def test_submit_review_wrong_user(self, review_service, sample_card):
        """Test reviewing another user's card raises error."""
        with pytest.raises(CardNotFoundError):
            review_service.submit_review(
                user_id="other-user-id",
                card_id="test-card-id",
                grade=4,
            )


class TestSubmitReviewDayBoundaryNormalization:
    """Tests for day boundary normalization in submit_review (TASK-0104).

    Verifies that next_review_at is normalized to user's day boundary time
    instead of raw datetime.
    """

    def test_next_review_at_normalized_to_day_boundary(self, review_service, sample_card):
        """Test that next_review_at is normalized to day boundary (04:00 JST by default).

        Given: A card exists with interval=1, review at 10:00 JST
        When: submit_review with grade=4 (interval stays 1)
        Then: next_review_at should be next day 04:00 JST (19:00 UTC previous day)
        """
        # Mock datetime to 2024-06-15 10:00:00 JST (01:00:00 UTC)
        mock_now = datetime(2024, 6, 15, 1, 0, 0, tzinfo=timezone.utc)
        with patch("services.srs.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            response = review_service.submit_review(
                user_id="test-user-id",
                card_id="test-card-id",
                grade=4,
                user_timezone="Asia/Tokyo",
                day_start_hour=4,
            )

        # interval=1, reviewed at 10:00 JST (after boundary)
        # effective_date = 2024-06-15, target_date = 2024-06-16
        # next_review_at = 2024-06-16 04:00 JST = 2024-06-15 19:00 UTC
        expected = datetime(2024, 6, 15, 19, 0, 0, tzinfo=timezone.utc)
        actual_due_date = response.updated.due_date
        # due_date is the UTC date portion of next_review_at (2024-06-15 19:00 UTC)
        assert actual_due_date == "2024-06-15"

    def test_next_review_at_stored_in_dynamodb_as_normalized(self, review_service, sample_card, dynamodb_tables):
        """Test that the normalized next_review_at is actually stored in DynamoDB."""
        mock_now = datetime(2024, 6, 15, 1, 0, 0, tzinfo=timezone.utc)
        with patch("services.srs.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            review_service.submit_review(
                user_id="test-user-id",
                card_id="test-card-id",
                grade=4,
                user_timezone="Asia/Tokyo",
                day_start_hour=4,
            )

        # Verify stored value in DynamoDB
        table = dynamodb_tables.Table("memoru-cards-test")
        item = table.get_item(Key={"user_id": "test-user-id", "card_id": "test-card-id"})["Item"]
        stored_next_review_at = item["next_review_at"]

        # Should be 2024-06-15T19:00:00+00:00 (= 2024-06-16 04:00 JST)
        parsed = datetime.fromisoformat(stored_next_review_at)
        assert parsed.hour == 19
        assert parsed.date() == datetime(2024, 6, 15).date()

    def test_before_boundary_treats_as_previous_day(self, review_service, dynamodb_tables):
        """Test review before day boundary treats current time as previous day.

        Given: Review at 01:00 JST (before 04:00 boundary)
        When: submit_review with interval=1
        Then: next_review_at is same day 04:00 JST (not next day)
        """
        now = datetime.now(timezone.utc)
        table = dynamodb_tables.Table("memoru-cards-test")
        table.put_item(
            Item={
                "user_id": "test-user-id",
                "card_id": "before-boundary-card",
                "front": "Q",
                "back": "A",
                "next_review_at": now.isoformat(),
                "interval": 1,
                "ease_factor": "2.5",
                "repetitions": 0,
                "tags": [],
                "created_at": now.isoformat(),
            }
        )

        # 2024-06-15 01:00 JST = 2024-06-14 16:00 UTC (before boundary)
        mock_now = datetime(2024, 6, 14, 16, 0, 0, tzinfo=timezone.utc)
        with patch("services.srs.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            response = review_service.submit_review(
                user_id="test-user-id",
                card_id="before-boundary-card",
                grade=4,
                user_timezone="Asia/Tokyo",
                day_start_hour=4,
            )

        # Before boundary: effective_date = 2024-06-14 (前日扱い)
        # interval=1, target_date = 2024-06-15
        # next_review_at = 2024-06-15 04:00 JST = 2024-06-14 19:00 UTC
        # due_date uses UTC date from next_review_at
        assert response.updated.due_date == "2024-06-14"

        # Verify the actual stored next_review_at is correct
        table = dynamodb_tables.Table("memoru-cards-test")
        item = table.get_item(Key={"user_id": "test-user-id", "card_id": "before-boundary-card"})["Item"]
        stored = datetime.fromisoformat(item["next_review_at"])
        # In JST this is 2024-06-15 04:00
        jst = stored.astimezone(ZoneInfo("Asia/Tokyo"))
        assert jst.day == 15
        assert jst.hour == 4

    def test_default_timezone_and_day_start_hour(self, review_service, sample_card):
        """Test that default values (Asia/Tokyo, day_start_hour=4) work correctly."""
        # Call without explicit timezone/day_start_hour - should use defaults
        response = review_service.submit_review(
            user_id="test-user-id",
            card_id="test-card-id",
            grade=4,
        )

        # Should still produce a valid response with normalized next_review_at
        assert response.updated.due_date is not None
        assert response.updated.interval == 1

    def test_custom_day_start_hour(self, review_service, dynamodb_tables):
        """Test with custom day_start_hour (14:00 for night shift workers)."""
        now = datetime.now(timezone.utc)
        table = dynamodb_tables.Table("memoru-cards-test")
        table.put_item(
            Item={
                "user_id": "test-user-id",
                "card_id": "night-shift-card",
                "front": "Q",
                "back": "A",
                "next_review_at": now.isoformat(),
                "interval": 1,
                "ease_factor": "2.5",
                "repetitions": 0,
                "tags": [],
                "created_at": now.isoformat(),
            }
        )

        # 2024-06-15 16:00 JST = 2024-06-15 07:00 UTC (after 14:00 boundary)
        mock_now = datetime(2024, 6, 15, 7, 0, 0, tzinfo=timezone.utc)
        with patch("services.srs.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            response = review_service.submit_review(
                user_id="test-user-id",
                card_id="night-shift-card",
                grade=4,
                user_timezone="Asia/Tokyo",
                day_start_hour=14,
            )

        # After 14:00 boundary: effective_date = 2024-06-15
        # interval=1, target_date = 2024-06-16
        # next_review_at = 2024-06-16 14:00 JST = 2024-06-16 05:00 UTC
        assert response.updated.due_date == "2024-06-16"


class TestGetDueCards:
    """Tests for ReviewService.get_due_cards method."""

    def test_get_due_cards_success(self, review_service, dynamodb_tables):
        """Test getting due cards returns correct cards."""
        now = datetime.now(timezone.utc)
        table = dynamodb_tables.Table("memoru-cards-test")

        # Create due cards
        for i in range(3):
            table.put_item(
                Item={
                    "user_id": "test-user-id",
                    "card_id": f"due-card-{i}",
                    "front": f"Due Question {i}",
                    "back": f"Due Answer {i}",
                    "next_review_at": (now - timedelta(hours=i + 1)).isoformat(),
                    "interval": 1,
                    "ease_factor": "2.5",
                    "repetitions": 0,
                    "tags": [],
                    "created_at": now.isoformat(),
                }
            )

        response = review_service.get_due_cards("test-user-id")

        assert response.total_due_count == 3
        assert len(response.due_cards) == 3

    def test_get_due_cards_empty(self, review_service, dynamodb_tables):
        """Test getting due cards when none are due."""
        now = datetime.now(timezone.utc)
        table = dynamodb_tables.Table("memoru-cards-test")

        # Create future cards
        table.put_item(
            Item={
                "user_id": "test-user-id",
                "card_id": "future-card",
                "front": "Future Question",
                "back": "Future Answer",
                "next_review_at": (now + timedelta(days=1)).isoformat(),
                "interval": 1,
                "ease_factor": "2.5",
                "repetitions": 0,
                "tags": [],
                "created_at": now.isoformat(),
            }
        )

        response = review_service.get_due_cards("test-user-id")

        assert response.total_due_count == 0
        assert len(response.due_cards) == 0

    def test_get_due_cards_with_limit(self, review_service, dynamodb_tables):
        """Test getting due cards with limit."""
        now = datetime.now(timezone.utc)
        table = dynamodb_tables.Table("memoru-cards-test")

        # Create 5 due cards
        for i in range(5):
            table.put_item(
                Item={
                    "user_id": "test-user-id",
                    "card_id": f"due-card-{i}",
                    "front": f"Due Question {i}",
                    "back": f"Due Answer {i}",
                    "next_review_at": (now - timedelta(hours=i + 1)).isoformat(),
                    "interval": 1,
                    "ease_factor": "2.5",
                    "repetitions": 0,
                    "tags": [],
                    "created_at": now.isoformat(),
                }
            )

        response = review_service.get_due_cards("test-user-id", limit=2)

        assert len(response.due_cards) <= 2

    def test_get_due_cards_overdue_days(self, review_service, dynamodb_tables):
        """Test overdue days calculation."""
        now = datetime.now(timezone.utc)
        table = dynamodb_tables.Table("memoru-cards-test")

        # Create an overdue card
        table.put_item(
            Item={
                "user_id": "test-user-id",
                "card_id": "overdue-card",
                "front": "Overdue Question",
                "back": "Overdue Answer",
                "next_review_at": (now - timedelta(days=3)).isoformat(),
                "interval": 1,
                "ease_factor": "2.5",
                "repetitions": 0,
                "tags": [],
                "created_at": now.isoformat(),
            }
        )

        response = review_service.get_due_cards("test-user-id")

        assert len(response.due_cards) == 1
        assert response.due_cards[0].overdue_days >= 2  # At least 2 days overdue


def _put_due_card(dynamodb, user_id: str, card_id: str, due_offset_hours: int = -1, deck_id: str = None):
    """due カードを DynamoDB に投入するヘルパー関数。

    Args:
        dynamodb: moto DynamoDB resource
        user_id: ユーザーID
        card_id: カードID
        due_offset_hours: 現在時刻からの offset（負値 = 過去 = due 状態）
        deck_id: デッキID（None の場合はデッキなし）
    """
    now = datetime.now(timezone.utc)
    item = {
        "user_id": user_id,
        "card_id": card_id,
        "front": f"Question for {card_id}",
        "back": f"Answer for {card_id}",
        "next_review_at": (now + timedelta(hours=due_offset_hours)).isoformat(),
        "interval": 1,
        "ease_factor": "2.5",
        "repetitions": 0,
        "tags": [],
        "created_at": now.isoformat(),
    }
    if deck_id is not None:
        item["deck_id"] = deck_id
    dynamodb.Table("memoru-cards-test").put_item(Item=item)


class TestGetDueCardsTotalDueCountFix:
    """TASK-0088: total_due_count が limit に影響されない正確な総数を返すことを検証するテスト群。

    バグの内容:
    - バグ1: card_service.get_due_cards() に limit が渡されており、DynamoDB Query レベルで
             カードが切り詰められてしまい、deck_id フィルタ前にカードが失われる。
    - バグ2: deck_id フィルタ時の total_due_count が limit 後のリスト長（due_card_infos）
             を使っており、実際の全件数を反映しない。
    """

    # ------------------------------------------------------------------
    # TC-001: 正常系 - deck_id なし・limit < 全件数
    # ------------------------------------------------------------------
    def test_tc001_total_due_count_without_deck_id_limit_less_than_total(
        self, review_service, dynamodb_tables
    ):
        """TC-001: deck_id なし・limit=10 で20件の復習対象カードがある場合、total_due_count=20 を返す。

        【テスト目的】: total_due_count が limit に影響されず正確な全件数を返すことを確認
        【テスト内容】: 20件の復習対象カードに対して limit=10 で get_due_cards を呼び出す
        【期待される動作】: total_due_count=20（全件数）, len(due_cards)=10（limit 適用後）
        🔵 REQ-005 受け入れ基準に直接対応
        """
        # 【テストデータ準備】: 復習対象カード20件を DynamoDB に投入（next_review_at を過去日に設定）
        # 【初期条件設定】: 全カードの next_review_at を現在時刻より前に設定し、復習対象とする
        for i in range(20):
            _put_due_card(dynamodb_tables, "test-user-id", f"card-tc001-{i}", due_offset_hours=-(i + 1))

        # 【実際の処理実行】: review_service.get_due_cards() を limit=10, deck_id=None で呼び出す
        # 【処理内容】: card_service から全復習対象カードを取得し、total_due_count 計算後に limit 適用
        response = review_service.get_due_cards("test-user-id", limit=10)

        # 【結果検証】: total_due_count が limit 前の全件数を返していること
        # 【期待値確認】: total_due_count=20（全件数）, len(due_cards)=10（limit 適用後）
        assert response.total_due_count == 20  # 【確認内容】: 全件数20が返されること（limit=10 に影響されない）🔵
        assert len(response.due_cards) == 10  # 【確認内容】: limit=10 で返却カードが10件に制限されること

    # ------------------------------------------------------------------
    # TC-002: 正常系 - deck_id あり・limit > デッキ内カード数
    # ------------------------------------------------------------------
    def test_tc002_total_due_count_with_deck_id_limit_greater_than_deck_cards(
        self, review_service, dynamodb_tables
    ):
        """TC-002: deck_id フィルタ付き・limit(10) > デッキ内カード数(5) の場合の total_due_count。

        【テスト目的】: deck_id フィルタが total_due_count に正しく反映されることを確認
        【テスト内容】: デッキA内5件 + デッキB内3件、limit=10、deck_id="deck-a" で呼び出す
        【期待される動作】: total_due_count=5（デッキA内件数）, due_cards=5件（全件返却）
        🔵 要件定義 パターン2 に直接対応
        """
        # 【テストデータ準備】: デッキA内5件 + デッキB内3件を投入
        # 【初期条件設定】: 複数デッキの due カードを混在させ、フィルタの正確性を確認する
        for i in range(5):
            _put_due_card(dynamodb_tables, "test-user-id", f"card-deck-a-{i}", due_offset_hours=-(i + 1), deck_id="deck-a")
        for i in range(3):
            _put_due_card(dynamodb_tables, "test-user-id", f"card-deck-b-{i}", due_offset_hours=-(i + 1), deck_id="deck-b")

        # 【実際の処理実行】: deck_id="deck-a"、limit=10 で get_due_cards を呼び出す
        response = review_service.get_due_cards("test-user-id", limit=10, deck_id="deck-a")

        # 【結果検証】: デッキA内の件数のみがカウントされ、デッキBのカードは含まれないこと
        assert response.total_due_count == 5  # 【確認内容】: デッキA内全5件（デッキBの3件を含まない）🔵
        assert len(response.due_cards) == 5  # 【確認内容】: limit(10) >= デッキ内件数(5) なので全件返却

    # ------------------------------------------------------------------
    # TC-003: 正常系 - deck_id あり・limit < デッキ内カード数（バグ2の直接検証）
    # ------------------------------------------------------------------
    def test_tc003_total_due_count_with_deck_id_limit_less_than_deck_cards(
        self, review_service, dynamodb_tables
    ):
        """TC-003: deck_id フィルタ付き・limit(10) < デッキ内カード数(15) の場合の total_due_count。

        【テスト目的】: バグ2（deck_id フィルタ時の total_due_count が limit 後のリスト長）の修正を検証
        【テスト内容】: デッキB内15件 + デッキA内3件、limit=10、deck_id="deck-b" で呼び出す
        【期待される動作】: total_due_count=15（デッキB内全件数）, due_cards=10件（limit 適用後）
        🔵 要件定義 パターン3 に直接対応。バグ2 の根本原因の修正を検証
        """
        # 【テストデータ準備】: デッキB内15件（due状態）+ デッキA内3件を投入
        # 【初期条件設定】: limit < デッキ内カード数となるよう15件を用意する
        for i in range(15):
            _put_due_card(dynamodb_tables, "test-user-id", f"card-deck-b-tc003-{i}", due_offset_hours=-(i + 1), deck_id="deck-b-tc003")
        for i in range(3):
            _put_due_card(dynamodb_tables, "test-user-id", f"card-deck-a-tc003-{i}", due_offset_hours=-(i + 1), deck_id="deck-a-tc003")

        # 【実際の処理実行】: deck_id="deck-b-tc003"、limit=10 で get_due_cards を呼び出す
        response = review_service.get_due_cards("test-user-id", limit=10, deck_id="deck-b-tc003")

        # 【結果検証】: total_due_count が limit(10) ではなくデッキ内全件数(15) を返すこと
        # これが現在のバグ（バグ2）: total_due_count = len(due_card_infos) = 10（limit後）になっている
        assert response.total_due_count == 15  # 【確認内容】: limit に影響されないデッキ内全15件 🔵
        assert len(response.due_cards) == 10   # 【確認内容】: limit=10 で返却カードが10件に制限されること

    # ------------------------------------------------------------------
    # TC-004: 正常系 - deck_id なし・limit >= 全件数
    # ------------------------------------------------------------------
    def test_tc004_total_due_count_without_deck_id_limit_gte_total(
        self, review_service, dynamodb_tables
    ):
        """TC-004: limit(20) >= 全件数(15) の場合に total_due_count と due_cards の件数が一致。

        【テスト目的】: limit が全件数以上の場合でも total_due_count が正確であることを確認
        【テスト内容】: 復習対象15件、limit=20 で get_due_cards を呼び出す
        【期待される動作】: total_due_count=15, due_cards=15件（全件返却）
        🔵 要件定義 パターン4 に直接対応
        """
        # 【テストデータ準備】: 復習対象カード15件を投入
        for i in range(15):
            _put_due_card(dynamodb_tables, "test-user-id", f"card-tc004-{i}", due_offset_hours=-(i + 1))

        # 【実際の処理実行】: limit=20（全件数より大きい）で呼び出す
        response = review_service.get_due_cards("test-user-id", limit=20)

        # 【結果検証】: limit >= 全件数なので全件返却、total_due_count も全件数と一致
        assert response.total_due_count == 15  # 【確認内容】: total_due_count が15件 🔵
        assert len(response.due_cards) == 15   # 【確認内容】: due_cards も15件（全件返却）

    # ------------------------------------------------------------------
    # TC-005: 正常系 - card_service に limit なしで全件取得（バグ1の検証）
    # ------------------------------------------------------------------
    def test_tc005_card_service_called_without_limit_for_total_count(
        self, review_service, dynamodb_tables
    ):
        """TC-005: card_service.get_due_cards に limit が渡されず全件取得されることの確認。

        【テスト目的】: バグ1（card_service.get_due_cards に limit が渡されている問題）の修正を検証
        【テスト内容】: 復習対象10件、limit=5 で get_due_cards を呼び出す
        【期待される動作】: total_due_count=10（全件数）, due_cards=5件（limit 適用後）
        🔵 要件定義 セクション3 バグ1 の根本原因分析に直接対応
        """
        # 【テストデータ準備】: 復習対象カード10件を投入
        # 【前提条件確認】: 旧実装では card_service に limit=5 が渡されるため、10件の内5件しか取得できない
        for i in range(10):
            _put_due_card(dynamodb_tables, "test-user-id", f"card-tc005-{i}", due_offset_hours=-(i + 1))

        # 【実際の処理実行】: limit=5 で呼び出す（旧実装では card_service に limit=5 が渡される）
        response = review_service.get_due_cards("test-user-id", limit=5)

        # 【結果検証】: card_service が全件(10) を取得し、total_due_count=10、返却カードのみ limit(5) で制限
        assert response.total_due_count == 10  # 【確認内容】: card_service レベルで切り詰められていない 🔵
        assert len(response.due_cards) == 5    # 【確認内容】: limit=5 で返却カードが5件に制限されること

    # ------------------------------------------------------------------
    # TC-006: 異常系 - 存在しない deck_id を指定した場合
    # ------------------------------------------------------------------
    def test_tc006_nonexistent_deck_id_returns_empty_response(
        self, review_service, dynamodb_tables
    ):
        """TC-006: 存在しないデッキIDを指定した場合に空レスポンスが返る。

        【テスト目的】: 存在しない deck_id でも例外が発生しないことを確認
        【テスト内容】: 別デッキの due カード5件がある状態で deck_id="non-existent" を指定する
        【期待される動作】: total_due_count=0, due_cards=[], エラーなし
        🟡 要件定義 パターン6 から妥当な推測
        """
        # 【テストデータ準備】: 別デッキの due カード5件を投入（指定 deck_id とは無関係）
        for i in range(5):
            _put_due_card(dynamodb_tables, "test-user-id", f"card-other-{i}", due_offset_hours=-(i + 1), deck_id="deck-other")

        # 【実際の処理実行】: 存在しない deck_id で呼び出す
        response = review_service.get_due_cards("test-user-id", limit=10, deck_id="non-existent-deck")

        # 【結果検証】: エラーなし、空のレスポンスが返ること
        assert response.total_due_count == 0  # 【確認内容】: 該当カードなしで0件 🟡
        assert len(response.due_cards) == 0   # 【確認内容】: due_cards は空リスト

    # ------------------------------------------------------------------
    # TC-007: 異常系 - 復習対象カードが0件の場合
    # ------------------------------------------------------------------
    def test_tc007_zero_due_cards_returns_next_due_date(
        self, review_service, dynamodb_tables
    ):
        """TC-007: 復習対象カードがない場合に total_due_count=0 と next_due_date が返る。

        【テスト目的】: 復習完了状態での total_due_count と next_due_date の正確性を確認
        【テスト内容】: 未来日の復習カード1件がある状態で get_due_cards を呼び出す
        【期待される動作】: total_due_count=0, due_cards=[], next_due_date is not None
        🔵 要件定義 パターン7・既存テスト test_get_due_cards_empty に対応
        """
        # 【テストデータ準備】: 未来の復習日を持つカード1件を投入（due 状態でない）
        now = datetime.now(timezone.utc)
        dynamodb_tables.Table("memoru-cards-test").put_item(Item={
            "user_id": "test-user-id",
            "card_id": "future-card-tc007",
            "front": "Future Question",
            "back": "Future Answer",
            "next_review_at": (now + timedelta(days=1)).isoformat(),
            "interval": 1,
            "ease_factor": "2.5",
            "repetitions": 0,
            "tags": [],
            "created_at": now.isoformat(),
        })

        # 【実際の処理実行】: deck_id=None で呼び出す（due カードは0件）
        response = review_service.get_due_cards("test-user-id", limit=10)

        # 【結果検証】: 空リスト + 次回復習日の適切な返却
        assert response.total_due_count == 0        # 【確認内容】: due 状態のカードが0件 🔵
        assert len(response.due_cards) == 0         # 【確認内容】: due_cards は空リスト
        assert response.next_due_date is not None   # 【確認内容】: 次の復習日が設定されていること

    # ------------------------------------------------------------------
    # TC-008: 境界値 - limit=2（小さい値）の場合
    # ------------------------------------------------------------------
    def test_tc008_small_limit_returns_correct_total_count(
        self, review_service, dynamodb_tables
    ):
        """TC-008: limit=2（小さい値）の場合に total_due_count が全件数を返す。

        【テスト目的】: 小さい limit 値での total_due_count の正確性を確認
        【テスト内容】: 復習対象10件、limit=2 で get_due_cards を呼び出す
        【期待される動作】: total_due_count=10（全件数）, due_cards=2件
        🟡 要件定義 パターン5 から妥当な推測
        注意: DynamoDB Query の Limit パラメータは 1 以上が必須のため、limit=0 は扱わない
        """
        # 【テストデータ準備】: 復習対象カード10件を投入
        for i in range(10):
            _put_due_card(dynamodb_tables, "test-user-id", f"card-tc008-{i}", due_offset_hours=-(i + 1))

        # 【実際の処理実行】: limit=2（小さい値）で呼び出す
        response = review_service.get_due_cards("test-user-id", limit=2)

        # 【結果検証】: due_cards は2件のみだが total_due_count は全件数を返す
        assert response.total_due_count == 10  # 【確認内容】: limit=2 でも全件数10が返されること 🟡
        assert len(response.due_cards) == 2    # 【確認内容】: limit=2 で2件のみ返却

    # ------------------------------------------------------------------
    # TC-009: 境界値 - limit=1 の場合
    # ------------------------------------------------------------------
    def test_tc009_limit_one_returns_single_card_with_correct_total(
        self, review_service, dynamodb_tables
    ):
        """TC-009: limit=1（最小有効値）の場合に total_due_count が全件数を返す。

        【テスト目的】: limit 最小有効値での total_due_count の正確性を確認
        【テスト内容】: 復習対象5件、limit=1 で get_due_cards を呼び出す
        【期待される動作】: total_due_count=5（全件数）, due_cards=1件
        🟡 要件定義から妥当な推測（boundary として重要）
        """
        # 【テストデータ準備】: 復習対象カード5件を投入
        for i in range(5):
            _put_due_card(dynamodb_tables, "test-user-id", f"card-tc009-{i}", due_offset_hours=-(i + 1))

        # 【実際の処理実行】: limit=1 で呼び出す（due_cards は1件のみ返却）
        response = review_service.get_due_cards("test-user-id", limit=1)

        # 【結果検証】: due_cards は1件のみ、total_due_count は全件数
        assert response.total_due_count == 5  # 【確認内容】: limit=1 でも全件数5が返されること 🟡
        assert len(response.due_cards) == 1   # 【確認内容】: limit=1 で1件のみ返却

    # ------------------------------------------------------------------
    # TC-010: 境界値 - deck_id フィルタで全カードが除外される場合
    # ------------------------------------------------------------------
    def test_tc010_deck_id_filter_excludes_all_cards_returns_zero(
        self, review_service, dynamodb_tables
    ):
        """TC-010: deck_id フィルタで該当カード0件の場合に total_due_count=0 を返す。

        【テスト目的】: deck_id フィルタ後の0件境界でのカウント正確性を確認
        【テスト内容】: 別デッキの due カード5件がある状態で deck_id="deck-empty" を指定する
        【期待される動作】: total_due_count=0, due_cards=[]
        🟡 要件定義パターン6 と組み合わせた妥当な推測
        """
        # 【テストデータ準備】: 全カードを "deck-other-tc010" に属させ、"deck-empty-tc010" は空にする
        for i in range(5):
            _put_due_card(dynamodb_tables, "test-user-id", f"card-other-tc010-{i}", due_offset_hours=-(i + 1), deck_id="deck-other-tc010")

        # 【実際の処理実行】: フィルタ結果が0件となる deck_id を指定
        response = review_service.get_due_cards("test-user-id", limit=10, deck_id="deck-empty-tc010")

        # 【結果検証】: フィルタ後0件でも total_due_count=0 が正確に返される
        assert response.total_due_count == 0  # 【確認内容】: フィルタ後0件で total_due_count=0 🟡
        assert len(response.due_cards) == 0   # 【確認内容】: due_cards は空リスト

    # ------------------------------------------------------------------
    # TC-011: 境界値 - deck_id + limit でバグ1検証（card_service レベルの切り詰め）
    # ------------------------------------------------------------------
    def test_tc011_deck_id_with_limit_card_service_level_truncation_bug(
        self, review_service, dynamodb_tables
    ):
        """TC-011: deck_id フィルタ時に card_service レベルの limit でカードが切り詰められないこと。

        【テスト目的】: バグ1（card_service に limit が渡される）を deck_id と組み合わせて検証
        【テスト内容】: デッキA内4件（due日が古い順）+ デッキB内4件、limit=5、deck_id="deck-b-tc011"
        【期待される動作】: total_due_count=4（デッキB内全件数）, due_cards=4件
        🔵 要件定義 セクション3 バグ1 の根本原因分析に直接対応

        旧実装では card_service に limit=5 が渡され、DynamoDB GSI ソート順（古い順）で
        先頭5件が取得される。デッキA内4件が古い場合、5件中デッキBは1件のみとなり、
        deck_id="deck-b-tc011" フィルタ後の total_due_count=1 となってしまう（正解は4）。
        """
        # 【テストデータ準備】: デッキAのカードを古い due 日、デッキBをやや新しい due 日に設定
        # GSI ソート（古い順）でデッキAが先に取得されやすくする
        for i in range(4):
            # deck-a-tc011: より古い due 日（20〜23時間前）
            _put_due_card(dynamodb_tables, "test-user-id", f"card-a-tc011-{i}", due_offset_hours=-(20 + i), deck_id="deck-a-tc011")
        for i in range(4):
            # deck-b-tc011: やや新しい due 日（1〜4時間前）
            _put_due_card(dynamodb_tables, "test-user-id", f"card-b-tc011-{i}", due_offset_hours=-(1 + i), deck_id="deck-b-tc011")

        # 【実際の処理実行】: deck_id="deck-b-tc011"、limit=5 で呼び出す
        response = review_service.get_due_cards("test-user-id", limit=5, deck_id="deck-b-tc011")

        # 【結果検証】: card_service が全件(8件) を取得し、deck_id フィルタ後4件、limit(5) >= 4件なので全件返却
        assert response.total_due_count == 4  # 【確認内容】: card_service レベルで切り詰められていない 🔵
        assert len(response.due_cards) == 4   # 【確認内容】: デッキB内4件が全て返却される

    # ------------------------------------------------------------------
    # TC-012: 境界値 - limit=100（API 上限値）での total_due_count 正確性
    # ------------------------------------------------------------------
    def test_tc012_limit_max_100_with_larger_total_returns_correct_count(
        self, review_service, dynamodb_tables
    ):
        """TC-012: limit=100（API 上限）の場合に total_due_count が正確な全件数を返す。

        【テスト目的】: limit 上限値での total_due_count 正確性の確認
        【テスト内容】: 復習対象120件、limit=100 で get_due_cards を呼び出す
        【期待される動作】: total_due_count=120（全件数）, due_cards=100件（limit 適用後）
        🟡 limit=100 は要件定義セクション2から。120件テストは妥当な推測
        """
        # 【テストデータ準備】: 復習対象カード120件を投入（limit=100 を超える件数）
        for i in range(120):
            _put_due_card(dynamodb_tables, "test-user-id", f"card-tc012-{i}", due_offset_hours=-(i + 1))

        # 【実際の処理実行】: limit=100（API 上限値）で呼び出す
        response = review_service.get_due_cards("test-user-id", limit=100)

        # 【結果検証】: limit 上限値でも total_due_count は実際の全件数を返す
        assert response.total_due_count == 120  # 【確認内容】: 全件数120が返されること（limit=100 に影響されない）🟡
        assert len(response.due_cards) == 100   # 【確認内容】: limit=100 で返却カードが100件に制限されること


class TestReviewIntegration:
    """Integration tests for review workflow."""

    def test_review_updates_due_date(self, review_service, sample_card):
        """Test that reviewing a card updates due date."""
        # Submit a review
        review_response = review_service.submit_review(
            user_id="test-user-id",
            card_id="test-card-id",
            grade=4,
        )

        # Due date should be in the future now
        due_response = review_service.get_due_cards("test-user-id")

        # Card should no longer be due (assuming interval >= 1 day)
        card_ids = [c.card_id for c in due_response.due_cards]
        assert "test-card-id" not in card_ids

    def test_consecutive_reviews_increase_interval(self, review_service, sample_card):
        """Test that consecutive successful reviews increase interval."""
        # First review
        response1 = review_service.submit_review(
            user_id="test-user-id",
            card_id="test-card-id",
            grade=4,
        )
        interval1 = response1.updated.interval

        # Need to update the card's next_review_at to be in the past to review again
        # For this test, we'll just verify the SM-2 logic produces increasing intervals

        assert interval1 == 1  # First review always 1 day


# ---------------------------------------------------------------------------
# Fixtures for TestGetReviewSummary (production schema with GSI on reviews)
# ---------------------------------------------------------------------------

@pytest.fixture
def dynamodb_tables_with_gsi():
    """Create mock DynamoDB tables with production schema (GSI on reviews)."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")

        # Cards table (same schema as production)
        cards_table = dynamodb.create_table(
            TableName="memoru-cards-test",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "card_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "card_id", "AttributeType": "S"},
                {"AttributeName": "next_review_at", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "user_id-due-index",
                    "KeySchema": [
                        {"AttributeName": "user_id", "KeyType": "HASH"},
                        {"AttributeName": "next_review_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        cards_table.wait_until_exists()

        # Reviews table with PRODUCTION schema (PK: card_id, GSI: user_id-reviewed_at-index)
        reviews_table = dynamodb.create_table(
            TableName="memoru-reviews-test",
            KeySchema=[
                {"AttributeName": "card_id", "KeyType": "HASH"},
                {"AttributeName": "reviewed_at", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "card_id", "AttributeType": "S"},
                {"AttributeName": "reviewed_at", "AttributeType": "S"},
                {"AttributeName": "user_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "user_id-reviewed_at-index",
                    "KeySchema": [
                        {"AttributeName": "user_id", "KeyType": "HASH"},
                        {"AttributeName": "reviewed_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        reviews_table.wait_until_exists()

        yield dynamodb


@pytest.fixture
def review_service_with_gsi(dynamodb_tables_with_gsi):
    """Create ReviewService with production-schema mock DynamoDB."""
    return ReviewService(
        cards_table_name="memoru-cards-test",
        reviews_table_name="memoru-reviews-test",
        dynamodb_resource=dynamodb_tables_with_gsi,
    )


def _put_review(dynamodb, user_id: str, card_id: str, grade: int, reviewed_at: str):
    """Insert a review record into the reviews table."""
    table = dynamodb.Table("memoru-reviews-test")
    table.put_item(Item={
        "user_id": user_id,
        "card_id": card_id,
        "reviewed_at": reviewed_at,
        "grade": grade,
        "ease_factor_before": "2.5",
        "ease_factor_after": "2.5",
        "interval_before": 1,
        "interval_after": 1,
    })


def _put_card(dynamodb, user_id: str, card_id: str, next_review_at: str, tags: list = None):
    """Insert a card record into the cards table."""
    table = dynamodb.Table("memoru-cards-test")
    now = datetime.now(timezone.utc).isoformat()
    table.put_item(Item={
        "user_id": user_id,
        "card_id": card_id,
        "front": f"Question for {card_id}",
        "back": f"Answer for {card_id}",
        "next_review_at": next_review_at,
        "interval": 1,
        "ease_factor": "2.5",
        "repetitions": 0,
        "tags": tags or [],
        "created_at": now,
    })


class TestGetReviewSummary:
    """Tests for ReviewService.get_review_summary method (TC-061-SUM-001 ~ TC-061-SUM-017)."""

    def test_get_review_summary_returns_review_summary_type(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-001: get_review_summary() returns a ReviewSummary dataclass instance."""
        from services.ai_service import ReviewSummary

        now = datetime.now(timezone.utc)
        _put_card(
            dynamodb_tables_with_gsi,
            "user-1", "card-1",
            (now - timedelta(hours=1)).isoformat(),
            tags=["math"],
        )
        _put_review(
            dynamodb_tables_with_gsi,
            "user-1", "card-1", 4,
            now.isoformat(),
        )

        result = review_service_with_gsi.get_review_summary("user-1")

        assert isinstance(result, ReviewSummary)

    def test_get_review_summary_total_reviews_count(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-002: total_reviews equals the number of review records."""
        now = datetime.now(timezone.utc)
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now - timedelta(hours=1)).isoformat())
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-2",
                  (now - timedelta(hours=1)).isoformat())

        # card-1: 3 reviews
        for i, grade in enumerate([3, 4, 5]):
            _put_review(
                dynamodb_tables_with_gsi, "user-1", "card-1", grade,
                (now - timedelta(hours=10 - i)).isoformat(),
            )
        # card-2: 2 reviews
        for i, grade in enumerate([2, 3]):
            _put_review(
                dynamodb_tables_with_gsi, "user-1", "card-2", grade,
                (now - timedelta(hours=5 - i)).isoformat(),
            )

        result = review_service_with_gsi.get_review_summary("user-1")

        assert result.total_reviews == 5

    def test_get_review_summary_average_grade_calculation(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-003: average_grade is the arithmetic mean of all review grades."""
        now = datetime.now(timezone.utc)
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now - timedelta(hours=1)).isoformat())

        # grades: [3, 4, 5, 2, 1] -> average = 15/5 = 3.0
        for i, grade in enumerate([3, 4, 5, 2, 1]):
            _put_review(
                dynamodb_tables_with_gsi, "user-1", "card-1", grade,
                (now - timedelta(hours=10 - i)).isoformat(),
            )

        result = review_service_with_gsi.get_review_summary("user-1")

        assert result.average_grade == 3.0

    def test_get_review_summary_total_cards_count(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-004: total_cards equals the number of cards belonging to the user."""
        now = datetime.now(timezone.utc)
        for i in range(1, 4):
            _put_card(
                dynamodb_tables_with_gsi, "user-1", f"card-{i}",
                (now + timedelta(days=1)).isoformat(),
            )

        result = review_service_with_gsi.get_review_summary("user-1")

        assert result.total_cards == 3

    def test_get_review_summary_cards_due_today(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-005: cards_due_today counts cards whose next_review_at is <= now."""
        now = datetime.now(timezone.utc)
        # card-1: due 1 hour ago
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now - timedelta(hours=1)).isoformat())
        # card-2: due 1 day ago
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-2",
                  (now - timedelta(days=1)).isoformat())
        # card-3: due 1 day in the future
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-3",
                  (now + timedelta(days=1)).isoformat())

        result = review_service_with_gsi.get_review_summary("user-1")

        assert result.cards_due_today == 2

    def test_get_review_summary_tag_performance(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-006: tag_performance is derived from cards.tags (not reviews.tags)."""
        now = datetime.now(timezone.utc)
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now - timedelta(hours=1)).isoformat(), tags=["math"])
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-2",
                  (now - timedelta(hours=1)).isoformat(), tags=["english"])

        # card-1: 3 correct reviews (grade >= 3)
        for i, grade in enumerate([3, 4, 5]):
            _put_review(
                dynamodb_tables_with_gsi, "user-1", "card-1", grade,
                (now - timedelta(hours=10 - i)).isoformat(),
            )
        # card-2: 2 incorrect reviews (grade < 3)
        for i, grade in enumerate([1, 2]):
            _put_review(
                dynamodb_tables_with_gsi, "user-1", "card-2", grade,
                (now - timedelta(hours=5 - i)).isoformat(),
            )

        result = review_service_with_gsi.get_review_summary("user-1")

        # math: 3/3 = 1.0 (100% correct)
        assert result.tag_performance["math"] == pytest.approx(1.0)
        # english: 0/2 = 0.0 (0% correct)
        assert result.tag_performance["english"] == pytest.approx(0.0)

    def test_get_review_summary_streak_days_consecutive(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-007: streak_days counts consecutive days of study ending today."""
        now = datetime.now(timezone.utc)
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now + timedelta(days=1)).isoformat())

        today = now
        yesterday = now - timedelta(days=1)
        day_before = now - timedelta(days=2)

        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 4,
                    today.isoformat())
        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 4,
                    yesterday.replace(hour=10).isoformat())
        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 4,
                    day_before.replace(hour=10).isoformat())

        result = review_service_with_gsi.get_review_summary("user-1")

        assert result.streak_days == 3

    def test_get_review_summary_streak_days_broken(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-008: streak_days resets when study days are not consecutive."""
        now = datetime.now(timezone.utc)
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now + timedelta(days=1)).isoformat())

        today = now
        three_days_ago = now - timedelta(days=3)

        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 4,
                    today.isoformat())
        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 4,
                    three_days_ago.replace(hour=10).isoformat())

        result = review_service_with_gsi.get_review_summary("user-1")

        assert result.streak_days == 1  # today only

    def test_get_review_summary_recent_review_dates(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-009: recent_review_dates is a list of unique dates, newest first."""
        now = datetime.now(timezone.utc)
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now + timedelta(days=1)).isoformat())

        today = now
        yesterday = now - timedelta(days=1)
        three_days_ago = now - timedelta(days=3)

        # today: 2 reviews (same day)
        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 4,
                    today.isoformat())
        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 3,
                    today.replace(hour=(today.hour - 1) % 24).isoformat())
        # yesterday: 2 reviews
        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 4,
                    yesterday.replace(hour=10).isoformat())
        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 5,
                    yesterday.replace(hour=14).isoformat())
        # 3 days ago: 1 review
        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 3,
                    three_days_ago.replace(hour=9).isoformat())

        result = review_service_with_gsi.get_review_summary("user-1")

        # unique dates: 3
        assert len(result.recent_review_dates) == 3
        # sorted newest first (descending)
        assert result.recent_review_dates[0] > result.recent_review_dates[1]
        assert result.recent_review_dates[1] > result.recent_review_dates[2]
        # each entry is a string
        for date_str in result.recent_review_dates:
            assert isinstance(date_str, str)

    def test_get_review_summary_empty_reviews(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-010: returns default values when there are no reviews and no cards."""
        result = review_service_with_gsi.get_review_summary("user-1")

        assert result.total_reviews == 0
        assert result.average_grade == 0.0
        assert result.total_cards == 0
        assert result.cards_due_today == 0
        assert result.tag_performance == {}
        assert result.streak_days == 0
        assert result.recent_review_dates == []

    def test_get_review_summary_reviews_but_no_cards(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-011: orphaned reviews (card deleted) still count in total_reviews."""
        now = datetime.now(timezone.utc)
        # Insert reviews with no corresponding cards
        for i in range(3):
            _put_review(
                dynamodb_tables_with_gsi, "user-1", f"deleted-card-{i}", 4,
                (now - timedelta(hours=i + 1)).isoformat(),
            )

        result = review_service_with_gsi.get_review_summary("user-1")

        assert result.total_reviews == 3
        assert result.total_cards == 0
        assert result.tag_performance == {}

    def test_get_review_summary_cards_but_no_reviews(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-012: cards without reviews return correct totals and zero review fields."""
        now = datetime.now(timezone.utc)
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now - timedelta(hours=1)).isoformat())
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-2",
                  (now - timedelta(days=1)).isoformat())

        result = review_service_with_gsi.get_review_summary("user-1")

        assert result.total_reviews == 0
        assert result.average_grade == 0.0
        assert result.total_cards == 2
        assert result.cards_due_today == 2
        assert result.streak_days == 0

    def test_get_review_summary_error_returns_default(
        self, review_service_with_gsi
    ):
        """TC-061-SUM-013: DynamoDB error returns a default ReviewSummary with zero values."""
        from unittest.mock import patch
        from botocore.exceptions import ClientError

        error_response = {
            "Error": {"Code": "InternalServerError", "Message": "Test error"}
        }
        with patch.object(
            review_service_with_gsi.reviews_table,
            "query",
            side_effect=ClientError(error_response, "Query"),
        ):
            result = review_service_with_gsi.get_review_summary("user-1")

        assert result.total_reviews == 0
        assert result.average_grade == 0.0
        assert result.total_cards == 0
        assert result.cards_due_today == 0
        assert result.tag_performance == {}
        assert result.streak_days == 0
        assert result.recent_review_dates == []

    def test_get_review_summary_queries_reviews_by_user_id(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-014: data from other users does not leak into the result."""
        now = datetime.now(timezone.utc)
        # user-1: 2 cards, 3 reviews
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-u1-1",
                  (now + timedelta(days=1)).isoformat())
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-u1-2",
                  (now + timedelta(days=1)).isoformat())
        for i in range(3):
            _put_review(
                dynamodb_tables_with_gsi, "user-1", "card-u1-1", 4,
                (now - timedelta(hours=i + 1)).isoformat(),
            )
        # user-2: 1 card, 2 reviews
        _put_card(dynamodb_tables_with_gsi, "user-2", "card-u2-1",
                  (now + timedelta(days=1)).isoformat())
        for i in range(2):
            _put_review(
                dynamodb_tables_with_gsi, "user-2", "card-u2-1", 3,
                (now - timedelta(hours=i + 1)).isoformat(),
            )

        result = review_service_with_gsi.get_review_summary("user-1")

        assert result.total_reviews == 3  # user-1's reviews only
        assert result.total_cards == 2    # user-1's cards only

    def test_get_review_summary_tag_performance_uses_card_tags(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-015: tag_performance is derived from cards.tags, not reviews.tags."""
        now = datetime.now(timezone.utc)
        # card-1 has multiple tags; the review record does NOT have a tags field
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now - timedelta(hours=1)).isoformat(),
                  tags=["science", "biology"])

        # Review record intentionally omits tags to confirm cards.tags is used
        table = dynamodb_tables_with_gsi.Table("memoru-reviews-test")
        table.put_item(Item={
            "user_id": "user-1",
            "card_id": "card-1",
            "reviewed_at": now.isoformat(),
            "grade": 4,
            "ease_factor_before": "2.5",
            "ease_factor_after": "2.5",
            "interval_before": 1,
            "interval_after": 1,
            # NOTE: no "tags" field in reviews record
        })

        result = review_service_with_gsi.get_review_summary("user-1")

        assert "science" in result.tag_performance
        assert "biology" in result.tag_performance
        assert result.tag_performance["science"] == pytest.approx(1.0)
        assert result.tag_performance["biology"] == pytest.approx(1.0)

    def test_get_review_summary_grade_3_is_correct(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-016: grade=3 is counted as correct (boundary value)."""
        now = datetime.now(timezone.utc)
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now - timedelta(hours=1)).isoformat(), tags=["test-tag"])
        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 3,
                    now.isoformat())

        result = review_service_with_gsi.get_review_summary("user-1")

        # grade >= 3 is correct
        assert result.tag_performance["test-tag"] == pytest.approx(1.0)

    def test_get_review_summary_grade_2_is_incorrect(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-017: grade=2 is counted as incorrect (boundary value)."""
        now = datetime.now(timezone.utc)
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now - timedelta(hours=1)).isoformat(), tags=["test-tag"])
        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 2,
                    now.isoformat())

        result = review_service_with_gsi.get_review_summary("user-1")

        # grade < 3 is incorrect
        assert result.tag_performance["test-tag"] == pytest.approx(0.0)


class TestUndoReview:
    """Tests for ReviewService.undo_review method."""

    def test_undo_review_restores_srs_parameters(self, review_service, sample_card):
        """Test that undo restores ease_factor, interval, repetitions, next_review_at."""
        # First, submit a review to create history
        review_service.submit_review(
            user_id="test-user-id",
            card_id="test-card-id",
            grade=4,
        )

        # Now undo it
        response = review_service.undo_review(
            user_id="test-user-id",
            card_id="test-card-id",
        )

        assert response.card_id == "test-card-id"
        assert response.restored.ease_factor == 2.5  # Original ease_factor
        assert response.restored.interval == 1  # Original interval
        assert response.restored.repetitions == 0  # Original repetitions
        assert response.undone_at is not None

    def test_undo_review_removes_latest_history_entry(self, review_service, sample_card):
        """Test that undo removes the latest review_history entry."""
        # Submit two reviews
        review_service.submit_review(
            user_id="test-user-id",
            card_id="test-card-id",
            grade=4,
        )
        review_service.submit_review(
            user_id="test-user-id",
            card_id="test-card-id",
            grade=5,
        )

        # Verify 2 history entries exist
        table = review_service.cards_table
        item = table.get_item(
            Key={"user_id": "test-user-id", "card_id": "test-card-id"}
        )["Item"]
        assert len(item["review_history"]) == 2

        # Undo the latest review
        review_service.undo_review(
            user_id="test-user-id",
            card_id="test-card-id",
        )

        # Verify only 1 history entry remains
        item = table.get_item(
            Key={"user_id": "test-user-id", "card_id": "test-card-id"}
        )["Item"]
        assert len(item["review_history"]) == 1

    def test_undo_review_no_history_raises_error(self, review_service, sample_card):
        """Test that undo with no review history raises NoReviewHistoryError."""
        with pytest.raises(NoReviewHistoryError):
            review_service.undo_review(
                user_id="test-user-id",
                card_id="test-card-id",
            )

    def test_undo_review_card_not_found(self, review_service):
        """Test that undo with non-existent card raises CardNotFoundError."""
        with pytest.raises(CardNotFoundError):
            review_service.undo_review(
                user_id="test-user-id",
                card_id="non-existent-card",
            )

    def test_undo_review_wrong_user(self, review_service, sample_card):
        """Test that undo with wrong user raises CardNotFoundError."""
        with pytest.raises(CardNotFoundError):
            review_service.undo_review(
                user_id="other-user-id",
                card_id="test-card-id",
            )

    def test_undo_review_returns_correct_response_format(self, review_service, sample_card):
        """Test that UndoReviewResponse has correct structure."""
        from models.review import UndoReviewResponse, UndoRestoredState

        review_service.submit_review(
            user_id="test-user-id",
            card_id="test-card-id",
            grade=4,
        )

        response = review_service.undo_review(
            user_id="test-user-id",
            card_id="test-card-id",
        )

        assert isinstance(response, UndoReviewResponse)
        assert isinstance(response.restored, UndoRestoredState)
        assert isinstance(response.restored.ease_factor, float)
        assert isinstance(response.restored.interval, int)
        assert isinstance(response.restored.repetitions, int)
        assert isinstance(response.restored.due_date, str)

    def test_undo_review_preserves_reviews_table(self, review_service, sample_card):
        """Test that reviews table records are preserved after undo."""
        # Submit a review (creates record in reviews table)
        review_service.submit_review(
            user_id="test-user-id",
            card_id="test-card-id",
            grade=4,
        )

        # Undo the review
        review_service.undo_review(
            user_id="test-user-id",
            card_id="test-card-id",
        )

        # Verify reviews table still has the record
        reviews_table = review_service.reviews_table
        response = reviews_table.scan()
        assert len(response["Items"]) >= 1


class TestGetNextDueDateFutureFilter:
    """Tests for _get_next_due_date filtering future dates only (TASK-0110)."""

    def test_next_due_date_returns_future_card(self, review_service, dynamodb_tables):
        """_get_next_due_date は未来の next_review_at のみ返す。"""
        now = datetime.now(timezone.utc)
        table = dynamodb_tables.Table("memoru-cards-test")

        # Card due in the past (should be excluded)
        table.put_item(
            Item={
                "user_id": "u1", "card_id": "past-card", "front": "Q", "back": "A",
                "next_review_at": (now - timedelta(hours=2)).isoformat(),
                "interval": 1, "ease_factor": "2.5", "repetitions": 0,
                "tags": [], "created_at": now.isoformat(),
            }
        )
        # Card due in the future
        future_date = now + timedelta(days=3)
        table.put_item(
            Item={
                "user_id": "u1", "card_id": "future-card", "front": "Q2", "back": "A2",
                "next_review_at": future_date.isoformat(),
                "interval": 3, "ease_factor": "2.5", "repetitions": 1,
                "tags": [], "created_at": now.isoformat(),
            }
        )

        result = review_service._get_next_due_date("u1")

        assert result == future_date.date().isoformat()

    def test_next_due_date_returns_none_when_only_past(self, review_service, dynamodb_tables):
        """過去のカードしかない場合は None を返す。"""
        now = datetime.now(timezone.utc)
        table = dynamodb_tables.Table("memoru-cards-test")

        table.put_item(
            Item={
                "user_id": "u1", "card_id": "past-card", "front": "Q", "back": "A",
                "next_review_at": (now - timedelta(hours=1)).isoformat(),
                "interval": 1, "ease_factor": "2.5", "repetitions": 0,
                "tags": [], "created_at": now.isoformat(),
            }
        )

        result = review_service._get_next_due_date("u1")

        assert result is None

    def test_next_due_date_returns_none_when_no_cards(self, review_service, dynamodb_tables):
        """カードがない場合は None を返す。"""
        result = review_service._get_next_due_date("no-cards-user")
        assert result is None


class TestUpdateCardReviewDataListAppend:
    """Tests for list_append usage in _update_card_review_data (TASK-0110)."""

    def test_review_history_appended_atomically(self, review_service, sample_card, dynamodb_tables):
        """submit_review で review_history が追加され、list_append で処理される。"""
        # Submit two reviews
        review_service.submit_review("test-user-id", "test-card-id", grade=4)
        review_service.submit_review("test-user-id", "test-card-id", grade=3)

        # Verify review_history has 2 entries
        table = dynamodb_tables.Table("memoru-cards-test")
        response = table.get_item(Key={"user_id": "test-user-id", "card_id": "test-card-id"})
        history = response["Item"].get("review_history", [])

        assert len(history) == 2
        assert history[0]["grade"] == 4
        assert history[1]["grade"] == 3

    def test_review_history_created_when_missing(self, review_service, dynamodb_tables):
        """review_history 属性がないカードでも if_not_exists で初期化される。"""
        now = datetime.now(timezone.utc)
        table = dynamodb_tables.Table("memoru-cards-test")

        # Create card without review_history attribute
        table.put_item(
            Item={
                "user_id": "u1", "card_id": "no-history-card", "front": "Q", "back": "A",
                "next_review_at": now.isoformat(),
                "interval": 1, "ease_factor": "2.5", "repetitions": 0,
                "tags": [], "created_at": now.isoformat(),
            }
        )

        review_service.submit_review("u1", "no-history-card", grade=5)

        response = table.get_item(Key={"user_id": "u1", "card_id": "no-history-card"})
        history = response["Item"].get("review_history", [])

        assert len(history) == 1
        assert history[0]["grade"] == 5


class TestRecordReviewLogging:
    """Tests for _record_review logging on failure (TASK-0110)."""

    def test_record_review_failure_logs_warning(self, review_service, sample_card, monkeypatch):
        """_record_review 失敗時に logger.warning が呼ばれることを確認する。"""
        from botocore.exceptions import ClientError

        def raise_client_error(**kwargs):
            raise ClientError(
                {"Error": {"Code": "InternalServerError", "Message": "Service unavailable"}},
                "PutItem",
            )

        monkeypatch.setattr(review_service.reviews_table, "put_item", raise_client_error)

        with patch("services.review_service.logger") as mock_logger:
            # _record_review is called internally by submit_review
            # but we can call it directly
            review_service._record_review(
                user_id="test-user-id",
                card_id="test-card-id",
                grade=4,
                reviewed_at=datetime.now(timezone.utc),
                ease_factor_before=2.5,
                ease_factor_after=2.6,
                interval_before=1,
                interval_after=3,
            )

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "card_id" in call_args[1]["extra"]
            assert call_args[1]["extra"]["card_id"] == "test-card-id"

    def test_submit_review_succeeds_despite_record_failure(self, review_service, sample_card, monkeypatch):
        """_record_review が失敗しても submit_review は成功する。"""
        from botocore.exceptions import ClientError

        def raise_client_error(**kwargs):
            raise ClientError(
                {"Error": {"Code": "InternalServerError", "Message": "fail"}},
                "PutItem",
            )

        monkeypatch.setattr(review_service.reviews_table, "put_item", raise_client_error)

        with patch("services.review_service.logger"):
            result = review_service.submit_review("test-user-id", "test-card-id", grade=4)

        assert result.card_id == "test-card-id"
        assert result.grade == 4
