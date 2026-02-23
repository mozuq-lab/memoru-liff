# TASK-0061: 学習データ集計 + アドバイスモデル・プロンプト - Tasknote

## タスク概要

TASK-0061 は ReviewService に `get_review_summary()` メソッドを追加し、DynamoDB の reviews / cards テーブルからユーザーの学習データを集計する。合わせて `models/advice.py` に LearningAdviceResponse Pydantic モデルを作成し、`services/prompts/advice.py` のプロンプトが ReviewSummary を適切に扱えることを検証する。

**実装ファイル**:
1. `backend/src/services/review_service.py` - `get_review_summary()` メソッド + 内部ヘルパー追加
2. `backend/src/models/advice.py` - LearningAdviceResponse Pydantic モデル（新規作成）
3. `backend/src/services/prompts/advice.py` - 既存実装の確認・微修正（必要であれば）

**テストファイル**:
- `backend/tests/unit/test_review_service.py` - `get_review_summary()` テスト追加
- `backend/tests/unit/test_advice_models.py` - LearningAdviceResponse モデルテスト（新規）
- `backend/tests/unit/test_advice_prompts.py` - 既存テスト拡充（必要であれば）

---

## 既存コードの現状分析

### 1. ReviewSummary dataclass は既に存在する

`backend/src/services/ai_service.py` の L47-57 に `ReviewSummary` dataclass が定義済み:

```python
@dataclass
class ReviewSummary:
    """復習履歴の集計結果."""
    total_reviews: int
    average_grade: float
    total_cards: int
    cards_due_today: int
    streak_days: int
    tag_performance: Dict[str, float] = field(default_factory=dict)
    recent_review_dates: List[str] = field(default_factory=list)
```

**重要**: タスクファイル TASK-0061.md では `models/advice.py` に Pydantic 版の `ReviewSummary` を新規作成する指示があるが、`ai_service.py` の dataclass 版が `get_learning_advice()` Protocol やプロンプトモジュールから既に参照されている。Pydantic 版を別途作成すると二重定義になり混乱を招く。

**方針**: `ReviewSummary` は `ai_service.py` の dataclass をそのまま使う。`models/advice.py` には **LearningAdviceResponse のみ** を作成する。

### 2. prompts/advice.py は既に完成している

`backend/src/services/prompts/advice.py` は TASK-0054 で既に本実装済み:
- `ADVICE_SYSTEM_PROMPT` 定数: JSON レスポンス形式を指示するシステムプロンプト
- `get_advice_prompt()` 関数: dict と ReviewSummary dataclass の両方に対応
- `_format_review_summary()` 内部関数: タグ別パフォーマンスの整形
- 言語切替（ja/en）とフォールバック

既存テスト `test_advice_prompts.py` に TC-009 ~ TC-024 の 10 テストケースが存在する。

**方針**: `prompts/advice.py` は大幅な変更不要。テストで ReviewSummary dataclass からの呼び出しが正しく動作することを確認する程度。

### 3. LearningAdvice dataclass も ai_service.py に存在する

`ai_service.py` L61-67 に `LearningAdvice` dataclass があり、AIService Protocol の `get_learning_advice()` の戻り値型として使用されている。

`LearningAdviceResponse` はこれとは異なり、**HTTP API レスポンス用の Pydantic モデル**（study_stats や advice_info メタ情報を含む）。

### 4. ReviewService の DynamoDB アクセスパターン

ReviewService は `dynamodb_resource` (boto3 resource) を直接使用して DynamoDB テーブルにアクセスする。`dynamodb_client` のような抽象レイヤーは存在しない。

- `self.cards_table` (boto3 Table): `user_id` (PK) + `card_id` (SK)、GSI: `user_id-due-index` (PK: `user_id`, SK: `next_review_at`)
- `self.reviews_table` (boto3 Table): `card_id` (PK) + `reviewed_at` (SK)、GSI: `user_id-reviewed_at-index` (PK: `user_id`, SK: `reviewed_at`)

**重要**: タスクファイルのサンプルコードでは `self.dynamodb_client.query_reviews_by_user()` を使用しているが、そのようなメソッドは存在しない。実際の実装では `self.reviews_table.query()` を GSI `user_id-reviewed_at-index` 経由で直接呼び出す必要がある。

### 5. reviews テーブルのレコード構造

`_record_review()` メソッド (L242-258) から、reviews レコードの構造は:

```python
{
    "user_id": str,          # GSI PK
    "reviewed_at": str,      # ISO datetime (GSI SK / テーブル SK)
    "card_id": str,          # テーブル PK
    "grade": int,            # 0-5
    "ease_factor_before": str,
    "ease_factor_after": str,
    "interval_before": int,
    "interval_after": int,
}
```

**注意**: reviews レコードには `tags` フィールドが含まれない。タスクファイルの `_calculate_tag_accuracy()` は `review.get("tags", [])` を使用しているが、これは動作しない。タグ別正答率を計算するには、review の `card_id` からカードの `tags` を逆引きする必要がある。

### 6. cards テーブルの due 判定

cards テーブルの due 判定には `next_review_at` フィールドを使用する（`due_date` ではない）。タスクファイルのサンプルでは `card.get("due_date")` を使っているが、実際は `next_review_at` である。

### 7. 全メソッドは同期

ReviewService の全メソッドは同期（`def`、`async def` ではない）。`get_review_summary()` も同期で実装する。

---

## 実装の流れ（TDD）

### Phase 1: TDD Red - テストケース定義

#### テストファイル 1: `backend/tests/unit/test_review_service.py` (拡充)

テストクラス `TestGetReviewSummary` を追加。moto の `@mock_aws` で DynamoDB をモックし、reviews / cards テーブルにテストデータを投入して `get_review_summary()` の結果を検証する。

**テストカテゴリ**:
- A: 正常系（複数レビュー + カードがある場合）
- B: 空データ（レビューなし / カードなし）
- C: 計算精度（平均グレード、正答率、期限カード数、streak_days）
- D: エラーハンドリング（DynamoDB エラー時のデフォルト値返却）

#### テストファイル 2: `backend/tests/unit/test_advice_models.py` (新規)

LearningAdviceResponse Pydantic モデルのバリデーション・シリアライズテスト。

#### テストファイル 3: `backend/tests/unit/test_advice_prompts.py` (拡充は不要)

既存テストで ReviewSummary dataclass との連携は TC-011 で検証済み。追加は不要。

### Phase 2: TDD Green - 実装

#### 1. `backend/src/models/advice.py` (新規)

LearningAdviceResponse のみを定義する Pydantic モデル:

```python
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

#### 2. `backend/src/services/review_service.py` (拡充)

`get_review_summary()` メソッドと内部ヘルパーを追加:

```python
def get_review_summary(self, user_id: str) -> ReviewSummary:
    """ユーザーの学習データを集計して ReviewSummary を返す。"""
    # 1. reviews テーブルから GSI user_id-reviewed_at-index で全レビューを取得
    # 2. cards テーブルから user_id (PK) で全カードを取得
    # 3. 集計: total_reviews, average_grade, total_cards, cards_due_today
    # 4. タグ別正答率: card_id -> tags のマッピングを使って計算
    # 5. streak_days: 連続学習日数
    # 6. recent_review_dates: 直近の復習日
    # 7. ReviewSummary (ai_service.py の dataclass) を返す
```

### Phase 3: TDD Refactor

- コードの整理、docstring 追加
- テストカバレッジ 80% 以上確認

---

## DynamoDB クエリ設計

### reviews の取得: GSI 経由

```python
response = self.reviews_table.query(
    IndexName="user_id-reviewed_at-index",
    KeyConditionExpression="user_id = :uid",
    ExpressionAttributeValues={":uid": user_id},
)
reviews = response.get("Items", [])
# ページネーション対応が必要な場合は LastEvaluatedKey をチェック
```

### cards の取得: PK クエリ

```python
response = self.cards_table.query(
    KeyConditionExpression="user_id = :uid",
    ExpressionAttributeValues={":uid": user_id},
)
cards = response.get("Items", [])
```

### タグ別正答率の計算手順

reviews レコードには tags が含まれないため:

1. cards をクエリして `{card_id: tags}` のマッピングを構築
2. reviews を走査し、各 review の `card_id` から tags を逆引き
3. tag ごとに grade >= 3 の正答数 / 総レビュー数を計算

```python
card_tags_map = {card["card_id"]: card.get("tags", []) for card in cards}

for review in reviews:
    tags = card_tags_map.get(review["card_id"], [])
    grade = review.get("grade", 0)
    is_correct = grade >= 3
    for tag in tags:
        tag_stats[tag]["total"] += 1
        if is_correct:
            tag_stats[tag]["correct"] += 1
```

### 本日期限カード数

```python
now = datetime.now(timezone.utc)
cards_due_today = sum(
    1 for card in cards
    if card.get("next_review_at") and
       datetime.fromisoformat(card["next_review_at"]) <= now
)
```

### streak_days 計算

最新の学習日から遡って、連続して学習した日数をカウント:

```python
review_dates = set()
for review in reviews:
    reviewed_at = review.get("reviewed_at")
    if reviewed_at:
        date_obj = datetime.fromisoformat(reviewed_at).date()
        review_dates.add(date_obj)

sorted_dates = sorted(review_dates, reverse=True)
today = datetime.now(timezone.utc).date()
streak = 0
for i, d in enumerate(sorted_dates):
    expected = today - timedelta(days=i)
    if d == expected:
        streak += 1
    else:
        break
```

---

## タスクファイルとの乖離点

| 項目 | タスクファイルの記述 | 実際のコードベース | 対応方針 |
|------|-------------------|-------------------|---------|
| ReviewSummary | `models/advice.py` に Pydantic 版を新規作成 | `ai_service.py` に dataclass 版が存在、Protocol と prompts から参照済み | dataclass 版を使用、Pydantic 版は作成しない |
| DynamoDB アクセス | `self.dynamodb_client.query_reviews_by_user()` | そのようなメソッドなし。`self.reviews_table.query()` を直接使用 | 既存パターンに合わせ `self.reviews_table.query()` + GSI を使用 |
| reviews.tags | `review.get("tags", [])` でタグを取得 | reviews レコードに tags フィールドなし | card_id から cards テーブルの tags を逆引き |
| due_date | `card.get("due_date")` | `next_review_at` フィールドを使用 | `next_review_at` で実装 |
| async | `async def get_review_summary()` | 全メソッドが同期 | `def get_review_summary()` (同期) |
| tag_accuracy vs tag_performance | タスクファイルは `tag_accuracy` | ReviewSummary dataclass は `tag_performance` | `tag_performance` に合わせる（dataclass のフィールド名） |
| average_grade の型 | タスクファイルは `Optional[float]` (None 許容) | dataclass は `float`（None 不可） | dataclass に合わせて `float`、データなし時は `0.0` |
| prompts/advice.py | 「完成させる」指示 | 既に TASK-0054 で完成済み | 変更不要、テストで確認のみ |

---

## 依存関係

```
TASK-0054 (プロンプトモジュール) ──┐
                                    ├── TASK-0061 (本タスク) ──> TASK-0062 (GET /advice)
TASK-0057 (Strands SDK 統合) ─────┘
```

---

## テスト戦略

### ReviewService テスト: moto で DynamoDB をモック

既存の `dynamodb_tables` / `review_service` フィクスチャを再利用。ただし:

1. reviews テーブルの PK/SK が**テストファイルでは `user_id` + `reviewed_at`** だが、**template.yaml では `card_id` + `reviewed_at`**（GSI が `user_id-reviewed_at-index`）
2. テスト用テーブル作成時に GSI `user_id-reviewed_at-index` を追加する必要がある
3. 既存の `dynamodb_tables` フィクスチャの reviews テーブルは `user_id` が PK になっているため、GSI ではなく直接クエリで取得可能 -- ただし実際の本番テーブルとスキーマが異なる点に注意

**方針**: テストフィクスチャでは、reviews テーブルを本番スキーマ（PK: `card_id`, SK: `reviewed_at`, GSI: `user_id-reviewed_at-index`）に合わせて修正するか、もしくは既存フィクスチャ（PK: `user_id`, SK: `reviewed_at`）をそのまま使い、実装側でも PK クエリと GSI クエリの両方に対応するかを検討する。

既存テストの `dynamodb_tables` フィクスチャは `user_id` を PK にしているため、既存テスト (TestSubmitReview, TestGetDueCards) との互換性を保つ必要がある。最も安全なアプローチは:

1. 新しいテストクラス `TestGetReviewSummary` 専用のフィクスチャを作成する（本番スキーマに合わせた GSI 付きテーブル）
2. または既存フィクスチャに GSI を追加してリファクタリングする

### LearningAdviceResponse テスト: 単純な Pydantic モデルテスト

Pydantic v2 の `BaseModel` のインスタンス化、`model_dump()`、`model_dump_json()` の動作を確認。

---

## 完了基準

1. [ ] `ReviewService.get_review_summary()` が正しくデータを集計する
2. [ ] `LearningAdviceResponse` モデルが `models/advice.py` に定義されている
3. [ ] 復習履歴 0 件の場合の挙動が定義されている（デフォルト値返却）
4. [ ] タグ別パフォーマンスが cards テーブルの tags から正しく計算される
5. [ ] テストカバレッジ 80% 以上

---

## 参考リソース

### 設計文書
- `docs/design/ai-strands-migration/architecture.md`
- `docs/design/ai-strands-migration/interfaces.py`
- `docs/design/ai-strands-migration/dataflow.md`
- `docs/design/ai-strands-migration/api-endpoints.md`

### 既存実装の参照
- `backend/src/services/review_service.py` - ReviewService 既存実装
- `backend/src/services/ai_service.py` - ReviewSummary dataclass、LearningAdvice dataclass
- `backend/src/services/prompts/advice.py` - 学習アドバイスプロンプト（TASK-0054 で完成済み）
- `backend/src/services/prompts/_types.py` - 共通型定義
- `backend/src/models/review.py` - Review 関連 Pydantic モデル
- `backend/src/models/card.py` - Card Pydantic モデル
- `backend/template.yaml` - DynamoDB テーブル定義（PK/SK/GSI）

### 依存タスク
- TASK-0054: プロンプトモジュールディレクトリ化（advice.py 完成済み）
- TASK-0057: Strands SDK 統合設定

### 後続タスク
- TASK-0062: 学習アドバイス AI 実装 + GET /advice エンドポイント

---

*作成日*: 2026-02-24
*タスク*: TASK-0061 Tasknote Phase
