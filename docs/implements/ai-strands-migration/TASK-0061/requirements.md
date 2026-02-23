# TASK-0061: 学習データ集計 + アドバイスモデル・プロンプト - TDD Requirements

## 概要

本ドキュメントは TASK-0061 の TDD Red フェーズで作成するテストケースの詳細要件を定義する。
対象は ReviewService への `get_review_summary()` メソッド追加、`models/advice.py` への LearningAdviceResponse Pydantic モデル作成、既存 `prompts/advice.py` との連携検証。

**関連要件**: REQ-SM-004（学習アドバイス/データ集計）、REQ-SM-403（Pydantic v2）、REQ-SM-404（テストカバレッジ 80%）

---

## 構造的前提

### ReviewSummary の所在

`ReviewSummary` dataclass は `backend/src/services/ai_service.py` L47-57 に既に定義されている。AIService Protocol の `get_learning_advice()` および `prompts/advice.py` から参照されている。**新たに Pydantic 版を作成しない**。`get_review_summary()` の戻り値はこの dataclass を使用する。

```python
# ai_service.py L47-57
@dataclass
class ReviewSummary:
    total_reviews: int
    average_grade: float          # float (not Optional)
    total_cards: int
    cards_due_today: int
    streak_days: int
    tag_performance: Dict[str, float] = field(default_factory=dict)
    recent_review_dates: List[str] = field(default_factory=list)
```

### DynamoDB テーブルスキーマ

**Reviews テーブル** (template.yaml L148-184):
- PK: `card_id` (S)
- SK: `reviewed_at` (S)
- GSI `user_id-reviewed_at-index`: PK `user_id` (S), SK `reviewed_at` (S), Projection ALL
- レコードフィールド: `user_id`, `reviewed_at`, `card_id`, `grade`, `ease_factor_before`, `ease_factor_after`, `interval_before`, `interval_after`
- **tags フィールドは存在しない**

**Cards テーブル** (template.yaml L107-145):
- PK: `user_id` (S)
- SK: `card_id` (S)
- GSI `user_id-due-index`: PK `user_id` (S), SK `next_review_at` (S), Projection ALL
- レコードフィールド: `user_id`, `card_id`, `front`, `back`, `next_review_at`, `interval`, `ease_factor`, `repetitions`, `tags`, `created_at`, etc.

### ReviewService のアクセスパターン

ReviewService は `self.reviews_table` (boto3 Table) と `self.cards_table` (boto3 Table) を直接使用する。抽象的な `dynamodb_client` は存在しない。reviews を user_id で取得するには GSI `user_id-reviewed_at-index` を使用する。

### 全メソッドは同期

`get_review_summary()` は `def`（`async def` ではない）で実装する。

---

## 1. ReviewService.get_review_summary() - 集計ロジック

### 1.1 設計要件

- **REQ-SUM-001** : `get_review_summary(user_id)` が `ReviewSummary` dataclass (from `ai_service.py`) を返すこと。
  - *根拠*: TASK-0061.md L49「async def get_review_summary(self, user_id: str) -> ReviewSummary」、ai_service.py L48-57 の dataclass 定義
- **REQ-SUM-002** : reviews テーブルの GSI `user_id-reviewed_at-index` を使用してユーザーの全レビューを取得すること。
  - *根拠*: template.yaml L167-175 の GSI 定義、ReviewService の既存アクセスパターン
- **REQ-SUM-003** : cards テーブルを `user_id` (PK) でクエリしてユーザーの全カードを取得すること。
  - *根拠*: template.yaml L114-125 の KeySchema、CardService の既存クエリパターン
- **REQ-SUM-004** : `total_reviews` はレビューレコード数であること。
  - *根拠*: TASK-0061.md L55「DynamoDB の reviews テーブルでユーザーの復習レコード数」
- **REQ-SUM-005** : `average_grade` は全レビューの grade の算術平均であること。復習 0 件時は `0.0` を返す。
  - *根拠*: TASK-0061.md L56、ReviewSummary.average_grade は float 型（Optional ではない）
- **REQ-SUM-006** : `total_cards` はユーザーの全カード数であること。
  - *根拠*: TASK-0061.md L57
- **REQ-SUM-007** : `cards_due_today` は `next_review_at` が現在時刻以前のカード数であること。
  - *根拠*: TASK-0061.md L58「due_date が本日以前のカード数」、cards テーブルのフィールド名は `next_review_at`
- **REQ-SUM-008** : `tag_performance` は tag ごとの正答率（grade >= 3 を正答として計算）であること。reviews レコードには tags がないため、card_id -> cards.tags のマッピングを使用して逆引きすること。
  - *根拠*: TASK-0061.md L59「{tag: (正答数 / 復習数)}」、reviews レコード構造に tags なし (review_service.py L242-258)
- **REQ-SUM-009** : `streak_days` は最新の学習日から遡った連続学習日数であること。
  - *根拠*: TASK-0061.md L60
- **REQ-SUM-010** : `recent_review_dates` は直近の復習日（ユニーク日付、新しい順、ISO 形式文字列）であること。
  - *根拠*: TASK-0061.md L61

### 1.2 テストケース: ReviewService.get_review_summary()

**ファイル**: `backend/tests/unit/test_review_service.py`
**テストクラス**: `TestGetReviewSummary`

#### テストフィクスチャの注意点

既存の `dynamodb_tables` フィクスチャは reviews テーブルの PK を `user_id` として定義しているが、本番の template.yaml では PK が `card_id` で GSI `user_id-reviewed_at-index` が存在する。新しいテストで GSI クエリを使用する場合は、テーブルスキーマを本番に合わせたフィクスチャが必要。

ただし、既存テスト（TestSubmitReview, TestGetDueCards）との互換性を保つため、以下のいずれかの方針を取る:
- **方針 A**: `TestGetReviewSummary` 専用のフィクスチャを作成し、本番スキーマ（PK: card_id, GSI: user_id-reviewed_at-index）を使用
- **方針 B**: 実装側で、テーブルの PK が user_id の場合は直接クエリ、card_id の場合は GSI クエリとする分岐を入れる（非推奨）
- **方針 C**: 既存フィクスチャをそのまま使い、`get_review_summary()` 内で reviews テーブルへのクエリを PK = user_id として実装する。本番では GSI 経由だが、テストでは PK クエリで同等の結果が得られる場合

**推奨**: 方針 A。テスト用の reviews テーブルを本番スキーマに合わせ、GSI 経由クエリの動作を正確に検証する。

| TC ID | テスト名 | 入力 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-061-SUM-001 | `test_get_review_summary_returns_review_summary_type` | user_id="user-1", reviews と cards にデータあり | 戻り値が `ReviewSummary` インスタンス | 🔵 |
| TC-061-SUM-002 | `test_get_review_summary_total_reviews_count` | 5 件のレビューレコードを投入 | `total_reviews == 5` | 🔵 |
| TC-061-SUM-003 | `test_get_review_summary_average_grade_calculation` | grade = [3, 4, 5, 2, 1] のレビュー | `average_grade == 3.0` | 🔵 |
| TC-061-SUM-004 | `test_get_review_summary_total_cards_count` | 3 枚のカードを投入 | `total_cards == 3` | 🔵 |
| TC-061-SUM-005 | `test_get_review_summary_cards_due_today` | 2 枚が期限切れ (next_review_at < now), 1 枚が未来 | `cards_due_today == 2` | 🔵 |
| TC-061-SUM-006 | `test_get_review_summary_tag_performance` | tag="math" のカードに grade 3,4,5、tag="english" のカードに grade 1,2 | `tag_performance["math"]` が高い正答率、`tag_performance["english"]` が低い正答率 | 🟡 |
| TC-061-SUM-007 | `test_get_review_summary_streak_days_consecutive` | 今日、昨日、一昨日にレビュー | `streak_days == 3` | 🟡 |
| TC-061-SUM-008 | `test_get_review_summary_streak_days_broken` | 今日と 3 日前にレビュー（昨日・一昨日なし） | `streak_days == 1` | 🟡 |
| TC-061-SUM-009 | `test_get_review_summary_recent_review_dates` | 複数日にレビュー | `recent_review_dates` がユニーク日付、新しい順、ISO 形式 | 🔵 |
| TC-061-SUM-010 | `test_get_review_summary_empty_reviews` | レビュー 0 件、カード 0 件 | `total_reviews == 0, average_grade == 0.0, total_cards == 0, cards_due_today == 0, tag_performance == {}, streak_days == 0, recent_review_dates == []` | 🔵 |
| TC-061-SUM-011 | `test_get_review_summary_reviews_but_no_cards` | レビューあり（orphaned）、カード 0 件 | `total_reviews > 0, total_cards == 0, tag_performance == {}` | 🔵 |
| TC-061-SUM-012 | `test_get_review_summary_cards_but_no_reviews` | カードあり、レビュー 0 件 | `total_reviews == 0, average_grade == 0.0, total_cards > 0` | 🔵 |
| TC-061-SUM-013 | `test_get_review_summary_error_returns_default` | DynamoDB クエリがエラーを発生 | デフォルト ReviewSummary（全フィールドがゼロ/空） | 🔵 |
| TC-061-SUM-014 | `test_get_review_summary_queries_reviews_by_user_id` | 2 ユーザーのデータ。user-1 でクエリ | user-1 のレビューのみが集計される（user-2 のデータは含まれない） | 🔵 |
| TC-061-SUM-015 | `test_get_review_summary_tag_performance_uses_card_tags` | reviews レコードに tags なし、cards に tags あり | tag_performance が cards の tags から正しく計算される | 🔵 |
| TC-061-SUM-016 | `test_get_review_summary_grade_3_is_correct` | grade=3 のレビュー 1 件 | 当該 tag の正答率に正答としてカウントされる (grade >= 3) | 🔵 |
| TC-061-SUM-017 | `test_get_review_summary_grade_2_is_incorrect` | grade=2 のレビュー 1 件 | 当該 tag の正答率に不正答としてカウントされる | 🔵 |

---

## 2. LearningAdviceResponse Pydantic モデル

### 2.1 設計要件

- **REQ-MODEL-001** : `LearningAdviceResponse` が `pydantic.BaseModel` を継承すること。
  - *根拠*: TASK-0061.md L265-271 のモデル定義
- **REQ-MODEL-002** : `advice_text` (str, required) フィールドを持つこと。
  - *根拠*: TASK-0061.md L267、api-endpoints.md のレスポンス仕様
- **REQ-MODEL-003** : `weak_areas` (List[str], default=[]) フィールドを持つこと。
  - *根拠*: TASK-0061.md L268
- **REQ-MODEL-004** : `recommendations` (List[str], default=[]) フィールドを持つこと。
  - *根拠*: TASK-0061.md L269
- **REQ-MODEL-005** : `study_stats` (Dict[str, Any], required) フィールドを持つこと。
  - *根拠*: TASK-0061.md L270
- **REQ-MODEL-006** : `advice_info` (Dict[str, Any], required) フィールドを持つこと。
  - *根拠*: TASK-0061.md L271
- **REQ-MODEL-007** : `model_dump()` で全フィールドを含む dict が返ること。
  - *根拠*: Pydantic v2 準拠、API レスポンスのシリアライズに必要
- **REQ-MODEL-008** : `model_dump_json()` で JSON 文字列が返ること。
  - *根拠*: Pydantic v2 準拠
- **REQ-MODEL-009** : `advice_text` が空文字列の場合は ValidationError が発生しないこと（タスクファイルに min_length 指定なし）。ただし必須フィールドのため None は不可。
  - *根拠*: TASK-0061.md L267 に `...`（required）指定

### 2.2 テストケース: LearningAdviceResponse

**ファイル**: `backend/tests/unit/test_advice_models.py` (新規)
**テストクラス**: `TestLearningAdviceResponse`

| TC ID | テスト名 | 入力 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-061-MODEL-001 | `test_learning_advice_response_all_fields` | 全フィールド指定 | インスタンス生成成功、全属性が正しい値 | 🔵 |
| TC-061-MODEL-002 | `test_learning_advice_response_default_weak_areas` | weak_areas 省略 | `weak_areas == []` | 🔵 |
| TC-061-MODEL-003 | `test_learning_advice_response_default_recommendations` | recommendations 省略 | `recommendations == []` | 🔵 |
| TC-061-MODEL-004 | `test_learning_advice_response_model_dump` | 全フィールド指定 | `model_dump()` が全フィールドを含む dict を返す | 🔵 |
| TC-061-MODEL-005 | `test_learning_advice_response_model_dump_json` | 全フィールド指定 | `model_dump_json()` が JSON 文字列を返し、`json.loads()` で復元可能 | 🔵 |
| TC-061-MODEL-006 | `test_learning_advice_response_requires_advice_text` | advice_text 省略 | `ValidationError` | 🔵 |
| TC-061-MODEL-007 | `test_learning_advice_response_requires_study_stats` | study_stats 省略 | `ValidationError` | 🔵 |
| TC-061-MODEL-008 | `test_learning_advice_response_requires_advice_info` | advice_info 省略 | `ValidationError` | 🔵 |
| TC-061-MODEL-009 | `test_learning_advice_response_study_stats_typical_values` | `study_stats={"total_reviews": 145, "average_grade": 3.8, "streak_days": 12}` | 正常生成、study_stats に全キーが含まれる | 🔵 |
| TC-061-MODEL-010 | `test_learning_advice_response_advice_info_typical_values` | `advice_info={"model_used": "strands", "processing_time_ms": 2456}` | 正常生成、advice_info に全キーが含まれる | 🔵 |

---

## 3. prompts/advice.py との連携

### 3.1 設計要件

- **REQ-PROMPT-001** : `get_advice_prompt()` が ReviewSummary dataclass (ai_service.py) を受け取り、全フィールドをプロンプト文字列に埋め込めること。
  - *根拠*: prompts/advice.py L86-93 の dataclass 対応コード、TC-011 で既に検証済み
- **REQ-PROMPT-002** : `get_review_summary()` の戻り値を直接 `get_advice_prompt()` に渡せること（型互換性）。
  - *根拠*: `get_review_summary()` -> ReviewSummary -> `get_advice_prompt(review_summary)` の流れ

### 3.2 テストケース: プロンプト連携

既存テスト `test_advice_prompts.py` の TC-011 (TestGetAdvicePromptWithReviewSummary) で ReviewSummary dataclass → get_advice_prompt() の連携は検証済み。追加テストは以下の 2 件のみ:

**ファイル**: `backend/tests/unit/test_advice_prompts.py` (拡充)
**テストクラス**: `TestAdvicePromptWithReviewSummaryFields` (新規クラス)

| TC ID | テスト名 | 入力 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-061-PROMPT-001 | `test_advice_prompt_includes_tag_performance` | ReviewSummary with tag_performance={"math": 4.2, "english": 2.1} | プロンプトに "math" と "english" が含まれる | 🔵 |
| TC-061-PROMPT-002 | `test_advice_prompt_no_reviews_shows_zero` | ReviewSummary with total_reviews=0, average_grade=0.0 | プロンプトに "0" が含まれ、エラーなし | 🔵 |

---

## 4. 内部ヘルパーメソッド

### 4.1 設計要件

- **REQ-HELP-001** : `_calculate_tag_performance()` ヘルパーが card_id -> tags マッピングを使用してタグ別正答率を計算すること。
  - *根拠*: reviews レコードに tags がないため、cards テーブルの tags を逆引きする必要がある
- **REQ-HELP-002** : `_calculate_streak_days()` ヘルパーが最新日から遡って連続学習日数を返すこと。
  - *根拠*: TASK-0061.md L166-201
- **REQ-HELP-003** : `_get_recent_review_dates()` ヘルパーがユニークな日付を新しい順で返すこと。
  - *根拠*: TASK-0061.md L204-224

### 4.2 テストケース: 内部ヘルパー

内部ヘルパーは `get_review_summary()` の統合テスト (TC-061-SUM-*) 経由で間接的にテストする。個別のユニットテストは不要（private メソッドのため）。ただし、streak_days の計算が複雑なため、edge case を TC-061-SUM-007, TC-061-SUM-008 で検証する。

---

## 5. エラーハンドリング

### 5.1 設計要件

- **REQ-ERR-001** : DynamoDB クエリでエラーが発生した場合、例外をキャッチしてデフォルト ReviewSummary を返すこと。
  - *根拠*: TASK-0061.md L118-131「except Exception as e: ... return ReviewSummary(total_reviews=0, ...)」
- **REQ-ERR-002** : エラー時のデフォルト ReviewSummary は `total_reviews=0, average_grade=0.0, total_cards=0, cards_due_today=0, tag_performance={}, streak_days=0, recent_review_dates=[]` であること。
  - *根拠*: TASK-0061.md L123-131、ReviewSummary dataclass のフィールド型に合わせる
- **REQ-ERR-003** : エラー時にログ出力すること。
  - *根拠*: TASK-0061.md L119「logger.error(...)」

### 5.2 テストケース: エラーハンドリング

TC-061-SUM-013 で検証済み（上記テーブル参照）。

---

## テストフィクスチャ設計

### 新規フィクスチャ: `dynamodb_tables_production_schema`

本番の reviews テーブルスキーマ（PK: card_id, SK: reviewed_at, GSI: user_id-reviewed_at-index）を使用するフィクスチャ。

```python
@pytest.fixture
def dynamodb_tables_production_schema():
    """Create mock DynamoDB tables with production schema."""
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

### テストデータヘルパー

```python
def _put_review(dynamodb, user_id: str, card_id: str, grade: int, reviewed_at: str):
    """reviews テーブルにレコードを投入するヘルパー。"""
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
    """cards テーブルにレコードを投入するヘルパー。"""
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

---

## テストファイル構成サマリー

### 新規作成ファイル

| ファイル | テストクラス | TC 数 |
|---------|------------|-------|
| `backend/tests/unit/test_advice_models.py` | `TestLearningAdviceResponse` | 10 |

### 拡充ファイル

| ファイル | テストクラス | TC 数 |
|---------|------------|-------|
| `backend/tests/unit/test_review_service.py` | `TestGetReviewSummary` | 17 |
| `backend/tests/unit/test_advice_prompts.py` | `TestAdvicePromptWithReviewSummaryFields` | 2 |

### 実装ファイル

| ファイル | 変更内容 |
|---------|---------|
| `backend/src/services/review_service.py` | `get_review_summary()` メソッド + 内部ヘルパー追加 |
| `backend/src/models/advice.py` | `LearningAdviceResponse` Pydantic モデル新規作成 |
| `backend/src/services/prompts/advice.py` | 変更なし（既に TASK-0054 で完成済み） |

### テスト合計

| カテゴリ | 件数 |
|---------|------|
| ReviewService.get_review_summary() | 17 |
| LearningAdviceResponse モデル | 10 |
| prompts/advice.py 連携 | 2 |
| **合計** | **29** |

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 26 | 90% |
| 🟡 黄信号 | 3 | 10% |
| 🔴 赤信号 | 0 | 0% |

**品質評価**: 高品質（青信号 90%、赤信号なし）

### 黄信号の項目と理由

| TC ID | 理由 |
|-------|------|
| TC-061-SUM-006 | tag_performance の計算方法（reviews に tags なし、cards から逆引き）はタスクファイルのサンプルコードと異なる。実装時に詳細を決定する必要がある |
| TC-061-SUM-007 | streak_days の計算ロジック詳細（当日未学習の場合の扱い等）は設計文書で明確に定義されていない |
| TC-061-SUM-008 | streak_days のエッジケース（学習日が連続しない場合）の厳密な仕様は TASK-0061.md のサンプルコードに依存 |

### 信頼性根拠

主要なテストケースは以下の確定情報に基づいている:
- `ai_service.py` の ReviewSummary dataclass 定義
- `template.yaml` の DynamoDB テーブルスキーマ（PK/SK/GSI）
- `review_service.py` の `_record_review()` によるレコード構造
- `prompts/advice.py` の既存実装と既存テスト
- TASK-0061.md の集計要件定義

---

## 既存テストへの影響

### `test_review_service.py` の既存テスト

`TestGetReviewSummary` は新しいテストクラスであり、既存の `TestSubmitReview`, `TestGetDueCards`, `TestReviewIntegration` には影響しない。

ただし、`TestGetReviewSummary` が本番スキーマのフィクスチャ (`dynamodb_tables_production_schema`) を使用する場合、既存のフィクスチャ (`dynamodb_tables`) と共存させる必要がある。moto の `mock_aws` コンテキストマネージャーは各テスト関数で独立しているため、衝突はない。

### `test_advice_prompts.py` の既存テスト

TC-061-PROMPT-001, TC-061-PROMPT-002 は新しいテストクラスの追加であり、既存テスト (TC-009 ~ TC-024) には影響しない。

---

## 依存関係

```
TASK-0054 (prompts/advice.py 完成) ──┐
                                      ├── TASK-0061 (本タスク) ──> TASK-0062 (GET /advice)
TASK-0057 (Strands SDK 統合) ────────┘
```

---

*作成日*: 2026-02-24
*タスク*: TASK-0061 TDD Requirements Phase
*信頼性*: 🔵 26件 (90%) / 🟡 3件 (10%) / 🔴 0件 (0%)
