# TASK-0061: 学習データ集計 + アドバイスモデル・プロンプト - Testcases

## 概要

本ドキュメントは TASK-0061 の TDD Red フェーズで実装するテストケースの詳細仕様を定義する。
3 つのテストファイル（拡充 2 件 + 新規 1 件）に合計 29 テストケースを配置する。

**テストファイル構成**:

| ファイル | テストクラス | TC 数 | 種別 |
|---------|------------|-------|------|
| `backend/tests/unit/test_review_service.py` | `TestGetReviewSummary` | 17 | 拡充 |
| `backend/tests/unit/test_advice_models.py` | `TestLearningAdviceResponse` | 10 | 新規 |
| `backend/tests/unit/test_advice_prompts.py` | `TestAdvicePromptWithReviewSummaryFields` | 2 | 拡充 |

---

## 重要な前提: タスクファイルとの乖離点

テストケースは **実際のコードベースの現状** に基づいて設計する。タスクファイル (TASK-0061.md) のサンプルコードとは以下の点で異なる:

| 項目 | タスクファイルの記述 | 実際のコードベース | テストでの対応 |
|------|-------------------|-------------------|--------------|
| ReviewSummary | `models/advice.py` に Pydantic 版を新規作成 | `ai_service.py` L47-57 に dataclass 版が存在 | dataclass 版を使用。Pydantic 版は作成しない |
| DynamoDB アクセス | `self.dynamodb_client.query_reviews_by_user()` | `self.reviews_table.query()` を直接使用 | `reviews_table.query()` + GSI をモック |
| reviews.tags | `review.get("tags", [])` でタグ取得 | reviews レコードに tags フィールドなし | card_id から cards テーブルの tags を逆引き |
| due_date | `card.get("due_date")` | `next_review_at` フィールド | `next_review_at` で判定 |
| async | `async def get_review_summary()` | 全メソッド同期 | `def get_review_summary()` (同期) |
| tag_accuracy vs tag_performance | `tag_accuracy` | ReviewSummary dataclass は `tag_performance` | `tag_performance` を使用 |
| average_grade の型 | `Optional[float]` (None 許容) | dataclass は `float` | `float` 型、データなし時は `0.0` |

---

## 1. テストファイル 1: `backend/tests/unit/test_review_service.py`

### 追加テストクラス: `TestGetReviewSummary`

ReviewService に追加する `get_review_summary(user_id)` メソッドのテスト。
戻り値は `ai_service.py` の `ReviewSummary` dataclass。

### フィクスチャ設計

既存の `dynamodb_tables` フィクスチャは reviews テーブルの PK を `user_id` として定義しているが、本番の template.yaml では PK が `card_id` で GSI `user_id-reviewed_at-index` が存在する。`TestGetReviewSummary` では本番スキーマに合わせた専用フィクスチャを使用する。

#### 新規フィクスチャ: `dynamodb_tables_with_gsi`

```python
@pytest.fixture
def dynamodb_tables_with_gsi():
    """Create mock DynamoDB tables with production schema (GSI on reviews)."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")

        # Cards table (same as existing)
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

        # Reviews table with PRODUCTION schema (PK: card_id, GSI: user_id)
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
```

#### 新規フィクスチャ: `review_service_with_gsi`

```python
@pytest.fixture
def review_service_with_gsi(dynamodb_tables_with_gsi):
    """Create ReviewService with production-schema mock DynamoDB."""
    return ReviewService(
        cards_table_name="memoru-cards-test",
        reviews_table_name="memoru-reviews-test",
        dynamodb_resource=dynamodb_tables_with_gsi,
    )
```

#### テストデータヘルパー関数

```python
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
```

### テストケース一覧

---

#### TC-061-SUM-001: `test_get_review_summary_returns_review_summary_type`

**目的**: `get_review_summary()` が `ReviewSummary` dataclass インスタンスを返すことを確認する。

**入力データ**:
- cards テーブルに 1 枚のカード (user_id="user-1", card_id="card-1", next_review_at=過去, tags=["math"])
- reviews テーブルに 1 件のレビュー (user_id="user-1", card_id="card-1", grade=4, reviewed_at=今日)

**実行**:
```python
result = review_service_with_gsi.get_review_summary("user-1")
```

**期待結果**:
- `isinstance(result, ReviewSummary)` が `True`
- `ReviewSummary` は `services.ai_service` からインポートしたもの

**import**:
```python
from services.ai_service import ReviewSummary
```

**信頼性**: 🔵 -- ReviewSummary dataclass は ai_service.py L47-57 に確定定義あり

---

#### TC-061-SUM-002: `test_get_review_summary_total_reviews_count`

**目的**: `total_reviews` がレビューレコード数と一致することを確認する。

**入力データ**:
- cards テーブルに 2 枚のカード (card-1, card-2)
- reviews テーブルに 5 件のレビュー:
  - card-1: 3 件 (grade=3, 4, 5、各異なる reviewed_at)
  - card-2: 2 件 (grade=2, 3、各異なる reviewed_at)

**実行**:
```python
result = review_service_with_gsi.get_review_summary("user-1")
```

**期待結果**:
```python
assert result.total_reviews == 5
```

**信頼性**: 🔵 -- REQ-SUM-004、タスクファイル L55

---

#### TC-061-SUM-003: `test_get_review_summary_average_grade_calculation`

**目的**: `average_grade` が全レビューの grade の算術平均であることを確認する。

**入力データ**:
- cards テーブルに 1 枚のカード (card-1)
- reviews テーブルに 5 件のレビュー: grade = [3, 4, 5, 2, 1]
  - 平均 = (3 + 4 + 5 + 2 + 1) / 5 = 3.0
  - 各レビューは異なる reviewed_at を持つ（同一 card_id でも SK が異なれば別レコード）

**実行**:
```python
result = review_service_with_gsi.get_review_summary("user-1")
```

**期待結果**:
```python
assert result.average_grade == 3.0
```

**信頼性**: 🔵 -- REQ-SUM-005、dataclass の average_grade は float 型

---

#### TC-061-SUM-004: `test_get_review_summary_total_cards_count`

**目的**: `total_cards` がユーザーの全カード数と一致することを確認する。

**入力データ**:
- cards テーブルに 3 枚のカード (card-1, card-2, card-3、全て user_id="user-1")
- reviews テーブルにはレビューなしでも可

**実行**:
```python
result = review_service_with_gsi.get_review_summary("user-1")
```

**期待結果**:
```python
assert result.total_cards == 3
```

**信頼性**: 🔵 -- REQ-SUM-006

---

#### TC-061-SUM-005: `test_get_review_summary_cards_due_today`

**目的**: `cards_due_today` が `next_review_at` が現在時刻以前のカード数であることを確認する。

**入力データ**:
- cards テーブルに 3 枚のカード:
  - card-1: next_review_at = 1 時間前 (期限切れ)
  - card-2: next_review_at = 1 日前 (期限切れ)
  - card-3: next_review_at = 1 日後 (未来)

**実行**:
```python
result = review_service_with_gsi.get_review_summary("user-1")
```

**期待結果**:
```python
assert result.cards_due_today == 2
```

**注意**: `next_review_at` フィールド名を使用（タスクファイルの `due_date` ではない）。`datetime.fromisoformat()` で比較可能な ISO 形式文字列であること。

**信頼性**: 🔵 -- REQ-SUM-007、template.yaml の cards テーブルフィールド名 `next_review_at`

---

#### TC-061-SUM-006: `test_get_review_summary_tag_performance`

**目的**: `tag_performance` が cards テーブルの tags から逆引きされ、正答率 (grade >= 3) が正しく計算されることを確認する。

**入力データ**:
- cards テーブル:
  - card-1: tags=["math"] (user_id="user-1")
  - card-2: tags=["english"] (user_id="user-1")
- reviews テーブル:
  - card-1 に対するレビュー: grade=3, grade=4, grade=5 (3 件すべて正答)
  - card-2 に対するレビュー: grade=1, grade=2 (2 件すべて不正答)

**実行**:
```python
result = review_service_with_gsi.get_review_summary("user-1")
```

**期待結果**:
```python
# math: 3/3 = 1.0 (100% 正答率)
assert result.tag_performance["math"] == pytest.approx(1.0)
# english: 0/2 = 0.0 (0% 正答率)
assert result.tag_performance["english"] == pytest.approx(0.0)
```

**重要**: reviews レコードには tags フィールドが存在しない。実装では card_id から cards テーブルの tags を逆引きする必要がある。タスクファイルの `_calculate_tag_accuracy()` のサンプルコードは `review.get("tags", [])` を使用しているが、これは動作しない。

**信頼性**: 🟡 -- reviews に tags がない点がタスクファイルと乖離。逆引きロジックの詳細は実装時に確定

---

#### TC-061-SUM-007: `test_get_review_summary_streak_days_consecutive`

**目的**: 連続学習日数が正しくカウントされることを確認する（連続 3 日のケース）。

**入力データ**:
- cards テーブルに 1 枚のカード
- reviews テーブルに 3 件のレビュー:
  - 今日 (datetime.now(timezone.utc)) の reviewed_at
  - 昨日の reviewed_at
  - 一昨日の reviewed_at

**実行**:
```python
result = review_service_with_gsi.get_review_summary("user-1")
```

**期待結果**:
```python
assert result.streak_days == 3
```

**注意**: streak_days のカウント基準は「最新の学習日から遡って、連続して学習した日数」。今日を含めてカウントする。

**信頼性**: 🟡 -- streak_days の詳細仕様（当日未学習の扱い等）は設計文書で明確に定義されていない

---

#### TC-061-SUM-008: `test_get_review_summary_streak_days_broken`

**目的**: 学習日が連続しない場合、streak が途切れることを確認する。

**入力データ**:
- cards テーブルに 1 枚のカード
- reviews テーブルに 2 件のレビュー:
  - 今日の reviewed_at
  - 3 日前の reviewed_at (昨日・一昨日はなし)

**実行**:
```python
result = review_service_with_gsi.get_review_summary("user-1")
```

**期待結果**:
```python
assert result.streak_days == 1  # 今日のみ
```

**信頼性**: 🟡 -- streak_days のエッジケース仕様は TASK-0061.md のサンプルコードに依存

---

#### TC-061-SUM-009: `test_get_review_summary_recent_review_dates`

**目的**: `recent_review_dates` がユニーク日付、新しい順、ISO 形式文字列のリストであることを確認する。

**入力データ**:
- cards テーブルに 1 枚のカード
- reviews テーブルに 5 件のレビュー（3 つの異なる日付に分布):
  - 今日: 2 件 (同じ日に複数回学習)
  - 昨日: 2 件
  - 3 日前: 1 件

**実行**:
```python
result = review_service_with_gsi.get_review_summary("user-1")
```

**期待結果**:
```python
# ユニーク日付で 3 つ
assert len(result.recent_review_dates) == 3
# 新しい順（降順）
assert result.recent_review_dates[0] > result.recent_review_dates[1]
assert result.recent_review_dates[1] > result.recent_review_dates[2]
# ISO 形式文字列
for date_str in result.recent_review_dates:
    assert isinstance(date_str, str)
```

**信頼性**: 🔵 -- REQ-SUM-010

---

#### TC-061-SUM-010: `test_get_review_summary_empty_reviews`

**目的**: レビュー 0 件・カード 0 件の場合にデフォルト値が返ることを確認する。

**入力データ**:
- cards テーブルにデータなし
- reviews テーブルにデータなし

**実行**:
```python
result = review_service_with_gsi.get_review_summary("user-1")
```

**期待結果**:
```python
assert result.total_reviews == 0
assert result.average_grade == 0.0  # float、None ではない
assert result.total_cards == 0
assert result.cards_due_today == 0
assert result.tag_performance == {}
assert result.streak_days == 0
assert result.recent_review_dates == []
```

**信頼性**: 🔵 -- REQ-SUM-005 (average_grade は float、データなし時 0.0)、REQ-ERR-002

---

#### TC-061-SUM-011: `test_get_review_summary_reviews_but_no_cards`

**目的**: レビューはあるがカードが削除済み（orphaned reviews）の場合の挙動を確認する。

**入力データ**:
- cards テーブルにデータなし
- reviews テーブルに 3 件のレビュー (card_id="deleted-card-1" 等)

**実行**:
```python
result = review_service_with_gsi.get_review_summary("user-1")
```

**期待結果**:
```python
assert result.total_reviews == 3  # orphaned でもカウントする
assert result.total_cards == 0
assert result.tag_performance == {}  # カードがないため tags 逆引き不可
```

**信頼性**: 🔵 -- カード削除後もレビューレコードは残存するケースの堅牢性

---

#### TC-061-SUM-012: `test_get_review_summary_cards_but_no_reviews`

**目的**: カードはあるがレビュー 0 件の場合の挙動を確認する。

**入力データ**:
- cards テーブルに 2 枚のカード (next_review_at=過去)
- reviews テーブルにデータなし

**実行**:
```python
result = review_service_with_gsi.get_review_summary("user-1")
```

**期待結果**:
```python
assert result.total_reviews == 0
assert result.average_grade == 0.0
assert result.total_cards == 2
assert result.cards_due_today == 2  # 両方期限切れ
assert result.streak_days == 0
```

**信頼性**: 🔵 -- 新規ユーザーがカードを作成したが未学習のケース

---

#### TC-061-SUM-013: `test_get_review_summary_error_returns_default`

**目的**: DynamoDB クエリでエラーが発生した場合、デフォルト ReviewSummary が返ることを確認する。

**入力データ / モック**:
- `review_service_with_gsi` の `reviews_table.query` を `unittest.mock.patch.object` で `ClientError` を raise するようモック
- または `reviews_table.query` に side_effect を設定

**実装例**:
```python
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

def test_get_review_summary_error_returns_default(self, review_service_with_gsi):
    error_response = {"Error": {"Code": "InternalServerError", "Message": "Test error"}}
    with patch.object(
        review_service_with_gsi.reviews_table, "query",
        side_effect=ClientError(error_response, "Query")
    ):
        result = review_service_with_gsi.get_review_summary("user-1")

    assert result.total_reviews == 0
    assert result.average_grade == 0.0
    assert result.total_cards == 0
    assert result.cards_due_today == 0
    assert result.tag_performance == {}
    assert result.streak_days == 0
    assert result.recent_review_dates == []
```

**期待結果**: 全フィールドがゼロ/空のデフォルト ReviewSummary

**信頼性**: 🔵 -- REQ-ERR-001, REQ-ERR-002

---

#### TC-061-SUM-014: `test_get_review_summary_queries_reviews_by_user_id`

**目的**: 他ユーザーのデータが混入しないことを確認する（ユーザー分離）。

**入力データ**:
- user-1: cards 2 枚、reviews 3 件
- user-2: cards 1 枚、reviews 2 件

**実行**:
```python
result = review_service_with_gsi.get_review_summary("user-1")
```

**期待結果**:
```python
assert result.total_reviews == 3  # user-1 のレビューのみ
assert result.total_cards == 2    # user-1 のカードのみ
```

**信頼性**: 🔵 -- GSI user_id-reviewed_at-index の PK=user_id でフィルタされることの検証

---

#### TC-061-SUM-015: `test_get_review_summary_tag_performance_uses_card_tags`

**目的**: tag_performance が reviews レコードの tags ではなく cards テーブルの tags から計算されることを明示的に確認する。

**入力データ**:
- cards テーブル:
  - card-1: tags=["science", "biology"] (複数タグ)
- reviews テーブル:
  - card-1 に対するレビュー: grade=4 (1 件)
  - reviews レコードに tags フィールドはない（put_item で tags を含めない）

**実行**:
```python
result = review_service_with_gsi.get_review_summary("user-1")
```

**期待結果**:
```python
# 両方のタグに正答としてカウント (grade=4 >= 3)
assert "science" in result.tag_performance
assert "biology" in result.tag_performance
assert result.tag_performance["science"] == pytest.approx(1.0)
assert result.tag_performance["biology"] == pytest.approx(1.0)
```

**信頼性**: 🔵 -- reviews レコード構造 (review_service.py L242-258) に tags なし、cards.tags から逆引きが必要

---

#### TC-061-SUM-016: `test_get_review_summary_grade_3_is_correct`

**目的**: grade=3 が正答としてカウントされることを確認する（境界値テスト）。

**入力データ**:
- cards テーブル: card-1 (tags=["test-tag"])
- reviews テーブル: card-1 に対して grade=3 のレビュー 1 件

**実行**:
```python
result = review_service_with_gsi.get_review_summary("user-1")
```

**期待結果**:
```python
# grade >= 3 は正答
assert result.tag_performance["test-tag"] == pytest.approx(1.0)
```

**信頼性**: 🔵 -- REQ-SUM-008 "grade >= 3 を正答として計算"

---

#### TC-061-SUM-017: `test_get_review_summary_grade_2_is_incorrect`

**目的**: grade=2 が不正答としてカウントされることを確認する（境界値テスト）。

**入力データ**:
- cards テーブル: card-1 (tags=["test-tag"])
- reviews テーブル: card-1 に対して grade=2 のレビュー 1 件

**実行**:
```python
result = review_service_with_gsi.get_review_summary("user-1")
```

**期待結果**:
```python
# grade < 3 は不正答
assert result.tag_performance["test-tag"] == pytest.approx(0.0)
```

**信頼性**: 🔵 -- REQ-SUM-008 の境界値

---

### テストケースサマリー: test_review_service.py

| TC ID | テスト名 | カテゴリ | 信頼性 |
|-------|---------|---------|--------|
| TC-061-SUM-001 | `test_get_review_summary_returns_review_summary_type` | 型検証 | 🔵 |
| TC-061-SUM-002 | `test_get_review_summary_total_reviews_count` | 集計 | 🔵 |
| TC-061-SUM-003 | `test_get_review_summary_average_grade_calculation` | 集計 | 🔵 |
| TC-061-SUM-004 | `test_get_review_summary_total_cards_count` | 集計 | 🔵 |
| TC-061-SUM-005 | `test_get_review_summary_cards_due_today` | 集計 | 🔵 |
| TC-061-SUM-006 | `test_get_review_summary_tag_performance` | 集計 | 🟡 |
| TC-061-SUM-007 | `test_get_review_summary_streak_days_consecutive` | streak | 🟡 |
| TC-061-SUM-008 | `test_get_review_summary_streak_days_broken` | streak | 🟡 |
| TC-061-SUM-009 | `test_get_review_summary_recent_review_dates` | 集計 | 🔵 |
| TC-061-SUM-010 | `test_get_review_summary_empty_reviews` | 空データ | 🔵 |
| TC-061-SUM-011 | `test_get_review_summary_reviews_but_no_cards` | 空データ | 🔵 |
| TC-061-SUM-012 | `test_get_review_summary_cards_but_no_reviews` | 空データ | 🔵 |
| TC-061-SUM-013 | `test_get_review_summary_error_returns_default` | エラー | 🔵 |
| TC-061-SUM-014 | `test_get_review_summary_queries_reviews_by_user_id` | 分離 | 🔵 |
| TC-061-SUM-015 | `test_get_review_summary_tag_performance_uses_card_tags` | tags逆引き | 🔵 |
| TC-061-SUM-016 | `test_get_review_summary_grade_3_is_correct` | 境界値 | 🔵 |
| TC-061-SUM-017 | `test_get_review_summary_grade_2_is_incorrect` | 境界値 | 🔵 |

---

## 2. テストファイル 2: `backend/tests/unit/test_advice_models.py` (新規)

### テストクラス: `TestLearningAdviceResponse`

`models/advice.py` に新規作成する `LearningAdviceResponse` Pydantic モデルのテスト。

**注意**: タスクファイルでは `ReviewSummary` Pydantic モデルも `models/advice.py` に作成する指示があるが、`ai_service.py` に dataclass 版が既に存在するため、`LearningAdviceResponse` のみを作成する。テストもこのモデルのみを対象とする。

### import

```python
import json
import pytest
from pydantic import ValidationError
from models.advice import LearningAdviceResponse
```

### テストケース一覧

---

#### TC-061-MODEL-001: `test_learning_advice_response_all_fields`

**目的**: 全フィールドを指定して正常にインスタンスが生成されることを確認する。

**入力**:
```python
response = LearningAdviceResponse(
    advice_text="数学の復習を増やしましょう。",
    weak_areas=["math", "grammar"],
    recommendations=["毎日5枚の数学カードを復習する", "文法ルールを暗記する"],
    study_stats={"total_reviews": 145, "average_grade": 3.8, "streak_days": 12},
    advice_info={"model_used": "strands", "processing_time_ms": 2456},
)
```

**期待結果**:
```python
assert response.advice_text == "数学の復習を増やしましょう。"
assert response.weak_areas == ["math", "grammar"]
assert response.recommendations == ["毎日5枚の数学カードを復習する", "文法ルールを暗記する"]
assert response.study_stats == {"total_reviews": 145, "average_grade": 3.8, "streak_days": 12}
assert response.advice_info == {"model_used": "strands", "processing_time_ms": 2456}
```

**信頼性**: 🔵 -- TASK-0061.md L265-271 のモデル定義

---

#### TC-061-MODEL-002: `test_learning_advice_response_default_weak_areas`

**目的**: `weak_areas` を省略した場合にデフォルト `[]` が適用されることを確認する。

**入力**:
```python
response = LearningAdviceResponse(
    advice_text="Good progress!",
    # weak_areas 省略
    study_stats={"total_reviews": 100},
    advice_info={"model_used": "strands"},
)
```

**期待結果**:
```python
assert response.weak_areas == []
```

**信頼性**: 🔵 -- REQ-MODEL-003

---

#### TC-061-MODEL-003: `test_learning_advice_response_default_recommendations`

**目的**: `recommendations` を省略した場合にデフォルト `[]` が適用されることを確認する。

**入力**:
```python
response = LearningAdviceResponse(
    advice_text="Keep studying!",
    # recommendations 省略
    study_stats={"total_reviews": 50},
    advice_info={"model_used": "strands"},
)
```

**期待結果**:
```python
assert response.recommendations == []
```

**信頼性**: 🔵 -- REQ-MODEL-004

---

#### TC-061-MODEL-004: `test_learning_advice_response_model_dump`

**目的**: `model_dump()` が全フィールドを含む dict を返すことを確認する。

**入力**:
```python
response = LearningAdviceResponse(
    advice_text="Study more.",
    weak_areas=["vocab"],
    recommendations=["Review daily"],
    study_stats={"total_reviews": 50},
    advice_info={"model_used": "strands"},
)
dumped = response.model_dump()
```

**期待結果**:
```python
assert isinstance(dumped, dict)
assert "advice_text" in dumped
assert "weak_areas" in dumped
assert "recommendations" in dumped
assert "study_stats" in dumped
assert "advice_info" in dumped
assert dumped["advice_text"] == "Study more."
assert dumped["weak_areas"] == ["vocab"]
```

**信頼性**: 🔵 -- REQ-MODEL-007

---

#### TC-061-MODEL-005: `test_learning_advice_response_model_dump_json`

**目的**: `model_dump_json()` が有効な JSON 文字列を返し、`json.loads()` で復元可能であることを確認する。

**入力**:
```python
response = LearningAdviceResponse(
    advice_text="Keep going!",
    weak_areas=["reading"],
    recommendations=["Read 10 pages daily"],
    study_stats={"total_reviews": 200, "average_grade": 4.1},
    advice_info={"model_used": "strands", "processing_time_ms": 1500},
)
json_str = response.model_dump_json()
```

**期待結果**:
```python
assert isinstance(json_str, str)
parsed = json.loads(json_str)
assert parsed["advice_text"] == "Keep going!"
assert parsed["study_stats"]["total_reviews"] == 200
```

**信頼性**: 🔵 -- REQ-MODEL-008

---

#### TC-061-MODEL-006: `test_learning_advice_response_requires_advice_text`

**目的**: `advice_text` が必須フィールドであり、省略時に `ValidationError` が発生することを確認する。

**入力**:
```python
with pytest.raises(ValidationError):
    LearningAdviceResponse(
        # advice_text 省略
        study_stats={"total_reviews": 10},
        advice_info={"model_used": "strands"},
    )
```

**期待結果**: `ValidationError` が raise される

**信頼性**: 🔵 -- REQ-MODEL-002 (required フィールド)

---

#### TC-061-MODEL-007: `test_learning_advice_response_requires_study_stats`

**目的**: `study_stats` が必須フィールドであり、省略時に `ValidationError` が発生することを確認する。

**入力**:
```python
with pytest.raises(ValidationError):
    LearningAdviceResponse(
        advice_text="Some advice",
        # study_stats 省略
        advice_info={"model_used": "strands"},
    )
```

**期待結果**: `ValidationError` が raise される

**信頼性**: 🔵 -- REQ-MODEL-005 (required フィールド)

---

#### TC-061-MODEL-008: `test_learning_advice_response_requires_advice_info`

**目的**: `advice_info` が必須フィールドであり、省略時に `ValidationError` が発生することを確認する。

**入力**:
```python
with pytest.raises(ValidationError):
    LearningAdviceResponse(
        advice_text="Some advice",
        study_stats={"total_reviews": 10},
        # advice_info 省略
    )
```

**期待結果**: `ValidationError` が raise される

**信頼性**: 🔵 -- REQ-MODEL-006 (required フィールド)

---

#### TC-061-MODEL-009: `test_learning_advice_response_study_stats_typical_values`

**目的**: `study_stats` に典型的な学習統計値を含めた場合に正常に動作することを確認する。

**入力**:
```python
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
```

**期待結果**:
```python
assert response.study_stats["total_reviews"] == 145
assert response.study_stats["average_grade"] == 3.8
assert response.study_stats["streak_days"] == 12
assert response.study_stats["total_cards"] == 32
assert response.study_stats["cards_due_today"] == 5
```

**信頼性**: 🔵 -- ReviewSummary の全フィールドを study_stats に含められること

---

#### TC-061-MODEL-010: `test_learning_advice_response_advice_info_typical_values`

**目的**: `advice_info` に典型的なメタ情報を含めた場合に正常に動作することを確認する。

**入力**:
```python
response = LearningAdviceResponse(
    advice_text="Keep studying!",
    study_stats={"total_reviews": 100},
    advice_info={
        "model_used": "strands",
        "processing_time_ms": 2456,
    },
)
```

**期待結果**:
```python
assert response.advice_info["model_used"] == "strands"
assert response.advice_info["processing_time_ms"] == 2456
```

**信頼性**: 🔵 -- TASK-0061.md L271 のメタ情報仕様

---

### テストケースサマリー: test_advice_models.py

| TC ID | テスト名 | カテゴリ | 信頼性 |
|-------|---------|---------|--------|
| TC-061-MODEL-001 | `test_learning_advice_response_all_fields` | 正常系 | 🔵 |
| TC-061-MODEL-002 | `test_learning_advice_response_default_weak_areas` | デフォルト | 🔵 |
| TC-061-MODEL-003 | `test_learning_advice_response_default_recommendations` | デフォルト | 🔵 |
| TC-061-MODEL-004 | `test_learning_advice_response_model_dump` | シリアライズ | 🔵 |
| TC-061-MODEL-005 | `test_learning_advice_response_model_dump_json` | シリアライズ | 🔵 |
| TC-061-MODEL-006 | `test_learning_advice_response_requires_advice_text` | バリデーション | 🔵 |
| TC-061-MODEL-007 | `test_learning_advice_response_requires_study_stats` | バリデーション | 🔵 |
| TC-061-MODEL-008 | `test_learning_advice_response_requires_advice_info` | バリデーション | 🔵 |
| TC-061-MODEL-009 | `test_learning_advice_response_study_stats_typical_values` | 正常系 | 🔵 |
| TC-061-MODEL-010 | `test_learning_advice_response_advice_info_typical_values` | 正常系 | 🔵 |

---

## 3. テストファイル 3: `backend/tests/unit/test_advice_prompts.py`

### 追加テストクラス: `TestAdvicePromptWithReviewSummaryFields`

既存テスト (TC-009 ~ TC-024) は `prompts/advice.py` の基本機能を検証済み。TC-011 で ReviewSummary dataclass の基本的な連携は確認されている。追加テストは ReviewSummary の特定フィールド（tag_performance, ゼロ値統計）のプロンプト埋め込みに焦点を当てる。

### import

```python
from services.ai_service import ReviewSummary
from services.prompts.advice import get_advice_prompt
```

### テストケース一覧

---

#### TC-061-PROMPT-001: `test_advice_prompt_includes_tag_performance`

**目的**: ReviewSummary の `tag_performance` フィールドの値がプロンプトに含まれることを確認する。

**入力**:
```python
summary = ReviewSummary(
    total_reviews=50,
    average_grade=3.5,
    total_cards=20,
    cards_due_today=5,
    streak_days=3,
    tag_performance={"math": 4.2, "english": 2.1},
    recent_review_dates=["2026-02-24"],
)
prompt = get_advice_prompt(summary, language="ja")
```

**期待結果**:
```python
assert "math" in prompt
assert "english" in prompt
assert "4.2" in prompt
assert "2.1" in prompt
```

**根拠**: 既存の `prompts/advice.py` L102-107 で tag_performance を `_format_review_summary()` 内部関数で整形している。`{tag}: {score:.1f}` の形式でプロンプトに含まれるはず。

**信頼性**: 🔵 -- prompts/advice.py L103-104 の `tag_perf_str` 生成ロジックから確定

---

#### TC-061-PROMPT-002: `test_advice_prompt_no_reviews_shows_zero`

**目的**: total_reviews=0, average_grade=0.0 の ReviewSummary でエラーなくプロンプトが生成され、"0" が含まれることを確認する。

**入力**:
```python
summary = ReviewSummary(
    total_reviews=0,
    average_grade=0.0,
    total_cards=0,
    cards_due_today=0,
    streak_days=0,
    tag_performance={},
    recent_review_dates=[],
)
prompt = get_advice_prompt(summary, language="ja")
```

**期待結果**:
```python
assert isinstance(prompt, str)
assert len(prompt) > 0
# average_grade=0.0 が "0.0" としてフォーマットされること
assert "0.0" in prompt
```

**根拠**: prompts/advice.py L116 で `{average_grade:.1f}` としてフォーマットされるため、`0.0` が含まれるはず。空の tag_performance は L107 で `"(no tag data available)"` に置換される。

**信頼性**: 🔵 -- prompts/advice.py の既存実装から確定

---

### テストケースサマリー: test_advice_prompts.py

| TC ID | テスト名 | カテゴリ | 信頼性 |
|-------|---------|---------|--------|
| TC-061-PROMPT-001 | `test_advice_prompt_includes_tag_performance` | フィールド埋め込み | 🔵 |
| TC-061-PROMPT-002 | `test_advice_prompt_no_reviews_shows_zero` | ゼロ値 | 🔵 |

---

## 全体サマリー

### テスト合計

| カテゴリ | 件数 |
|---------|------|
| ReviewService.get_review_summary() | 17 |
| LearningAdviceResponse モデル | 10 |
| prompts/advice.py 連携 | 2 |
| **合計** | **29** |

### 信頼性レベル

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 26 | 90% |
| 🟡 黄信号 | 3 | 10% |
| 🔴 赤信号 | 0 | 0% |

**品質評価**: 高品質（青信号 90%、赤信号なし）

### 黄信号の項目と理由

| TC ID | 理由 | 対処方針 |
|-------|------|---------|
| TC-061-SUM-006 | tag_performance の計算方法（reviews に tags なし、cards から逆引き）はタスクファイルのサンプルと異なる | 実装時に逆引きロジックを確定し、テストもそれに合わせて調整 |
| TC-061-SUM-007 | streak_days の計算ロジック詳細（当日未学習の場合の扱い等）は設計文書で明確に定義されていない | TASK-0061.md のサンプルコード準拠。今日の日付から遡ってカウント |
| TC-061-SUM-008 | streak_days のエッジケース（学習日が連続しない場合）の厳密な仕様 | TC-061-SUM-007 と同じアルゴリズムを前提とする |

### 既存テストへの影響

- **test_review_service.py**: `TestGetReviewSummary` は新規テストクラスの追加。既存の `TestSubmitReview`, `TestGetDueCards`, `TestReviewIntegration` は `dynamodb_tables` フィクスチャを使用し続ける。新テストクラスは `dynamodb_tables_with_gsi` フィクスチャを使用するため衝突なし。
- **test_advice_prompts.py**: `TestAdvicePromptWithReviewSummaryFields` は新規テストクラスの追加。既存テスト (TC-009 ~ TC-024) には影響なし。
- **test_advice_models.py**: 完全新規ファイルのため既存テストへの影響なし。

---

## 実装ファイルのスタブ定義

TDD Red フェーズで「テストが失敗する」状態にするため、以下の最小スタブが必要:

### 1. `backend/src/services/review_service.py` に追加するスタブ

```python
def get_review_summary(self, user_id: str):
    """Get review summary for a user. (stub - to be implemented)"""
    raise NotImplementedError("get_review_summary is not yet implemented")
```

### 2. `backend/src/models/advice.py` に作成するスタブ

```python
"""Advice models for Memoru LIFF application."""

from pydantic import BaseModel, Field
from typing import Any, Dict, List


class LearningAdviceResponse(BaseModel):
    """学習アドバイス API レスポンスモデル."""

    advice_text: str = Field(..., description="AI 生成の学習アドバイス")
    weak_areas: List[str] = Field(default_factory=list, description="弱点分野")
    recommendations: List[str] = Field(default_factory=list, description="推奨学習アクション")
    study_stats: Dict[str, Any] = Field(..., description="学習統計サマリー")
    advice_info: Dict[str, Any] = Field(..., description="メタ情報")
```

**注意**: LearningAdviceResponse は Red フェーズでもテストが通る完全な定義を持つ（Pydantic モデルの定義自体がバリデーションの実装であるため、スタブではなく完成形とする）。ReviewService.get_review_summary() のスタブのみが `NotImplementedError` を raise する。

---

## 依存関係

```
TASK-0054 (prompts/advice.py 完成) ──┐
                                      ├── TASK-0061 (本タスク) ──> TASK-0062 (GET /advice)
TASK-0057 (Strands SDK 統合) ────────┘
```

---

*作成日*: 2026-02-24
*タスク*: TASK-0061 TDD Testcases Phase
*信頼性*: 🔵 26件 (90%) / 🟡 3件 (10%) / 🔴 0件 (0%)
