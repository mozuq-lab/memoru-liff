# TASK-0088: total_due_count 修正 - Refactor フェーズ記録

**作成日**: 2026-03-01
**タスクID**: TASK-0088
**フェーズ**: Refactor（品質改善）

---

## リファクタリング概要

Greenフェーズで実装したバグ修正コードの品質を改善した。
機能的な変更は一切行わず、コメントの整理・充実と docstring の品質向上のみを実施した。

---

## 改善内容

### 改善1: `review_service.py` - `get_due_cards()` コメント整理と docstring 向上

**ファイル**: `backend/src/services/review_service.py`

**改善ポイント**:
- 古い `get_due_card_count()` に関するコメント（旧実装の痕跡）を削除 🔵
- docstring に `total_due_count` の動作（limit 非依存）を明記 🔵
- `deck_id` パラメータの説明に `total_due_count` への影響を追加 🔵
- Returns セクションに各フィールドの意味を詳述 🔵
- インラインコメントを「何をするか」から「なぜそうするか」の説明に改善 🔵

**信頼性**: 🔵 青信号 - REQ-005 および architecture.md セクション5 に直接対応

**変更箇所**（主な差分）:

```python
# Before: 古いコメントが残存、docstring が簡素
def get_due_cards(self, ...):
    """Get cards due for review.

    Args:
        limit: Maximum number of cards to return.  # 不十分な説明
    ...
    """
    # 【バグ1修正】: ...（実装完了後も "バグ修正" コメントが残存）
    all_due_cards = self.card_service.get_due_cards(limit=None, ...)

    # deck_id なしの場合は card_service.get_due_card_count() を使っていたが、
    # 修正後は全件取得後に len() で計算するため...（旧実装への言及）

# After: 設計意図が明確、docstring が充実
def get_due_cards(self, ...):
    """Get cards due for review.

    【設計方針】: 全復習対象カードを取得してから limit を適用する。...

    Args:
        limit: Maximum number of cards to return in due_cards.
               total_due_count はこの値に影響されず、フィルタ後の全件数を返す。
        deck_id: Optional filter by deck ID.
                 指定した場合、total_due_count はそのデッキ内の復習対象カード総数を返す。

    Returns:
        DueCardsResponse with due cards and metadata.
        - due_cards: limit で制限されたカードリスト
        - total_due_count: deck_id フィルタ後・limit 適用前の全件数（REQ-005）
        - next_due_date: due_cards が空の場合に次の復習予定日を返す
    """
    # 【全件取得】: limit を渡さず全復習対象カードを取得する（設計意図を説明）
    all_due_cards = self.card_service.get_due_cards(limit=None, ...)

    # 【total_due_count 計算】: limit 適用前に全件数を記録する（REQ-005）
    total_due_count = len(all_due_cards)
```

---

### 改善2: `card_service.py` - `get_due_cards()` docstring 品質向上

**ファイル**: `backend/src/services/card_service.py`

**改善ポイント**:
- docstring に `limit=None` の設計意図（呼び出し元の deck_id フィルタ対応）を追記 🔵
- `limit` パラメータの説明を充実（None を渡すタイミングの指針を追加） 🔵
- Returns に「oldest due first（昇順）」の情報を追記 🔵
- インラインコメントに昇順取得の理由を補足 🔵

**信頼性**: 🔵 青信号 - Greenフェーズの実装意図を文書化

---

### 改善3: `card_service.py` - `get_due_card_count()` 用途を明記

**ファイル**: `backend/src/services/card_service.py`

**改善ポイント**:
- docstring に notification_service での使用目的を明記 🔵
- `get_due_cards(limit=None)` との使い分け（シンプルカウント vs 全件取得）を説明 🔵

**確認事項**:
- `get_due_card_count()` は `notification_service.py` で引き続き使用されている
- `review_service.py` からは使用されなくなった（全件取得後 len() で代替）
- メソッド本体は保持（削除は notification_service への影響があるため対象外）

---

## セキュリティレビュー結果

| 項目 | 結果 | 詳細 |
|------|------|------|
| user_id 検証 | ✅ 問題なし | DynamoDB Query の KeyCondition に user_id を使用。他ユーザーのデータアクセス不可 |
| deck_id フィルタ | ✅ 問題なし | user_id スコープ内でアプリケーション層フィルタ。他ユーザーの deck_id 指定でも空結果 |
| limit の型安全性 | ✅ 問題なし | `limit: int = 20` で型ヒントあり。limit=0 でも `[:0]` で安全に空リストを返す |
| 入力値検証 | ✅ 問題なし | limit の上限検証は review_handler.py で実施（min(int, 100)） |

---

## パフォーマンスレビュー結果

| 項目 | 評価 | 詳細 |
|------|------|------|
| 全件取得の影響 | ⚠️ MVP 許容 | limit=None で最大2000件を取得。計算量 O(n)、メモリ使用は許容範囲内 |
| DynamoDB クエリ効率 | ✅ 適切 | GSI (user_id-due-index) を使用。テーブルスキャンなし |
| deck_id フィルタ | ✅ 現状適切 | アプリケーション層でのフィルタ。DynamoDB FilterExpression よりコスト低 |
| 将来改善候補 | 🟡 TODO | deck_id × due 複合 GSI またはカウンターテーブルによる最適化が可能 |

---

## テスト実行結果

### TASK-0088 専用テスト（TestGetDueCardsTotalDueCountFix）

```
tests/unit/test_review_service.py::TestGetDueCardsTotalDueCountFix - 12/12 PASSED
```

### 全 review_service テスト

```
tests/unit/test_review_service.py - 49/49 PASSED（3.44s）
```

### 関連テスト（card_service）

```
tests/unit/test_card_service.py - 30/30 PASSED
```

**合計**: 79 テスト全通過

---

## コード品質評価

| 評価項目 | 結果 | 備考 |
|---------|------|------|
| テスト成功状況 | ✅ | 49/49 全通過（review_service）、79/79（review + card 合計） |
| セキュリティ | ✅ | 重大な脆弱性なし |
| パフォーマンス | ✅ | MVP 段階で許容範囲内（将来改善候補あり） |
| コードコメント品質 | ✅ | 設計意図・なぜそうするかを明記 |
| docstring 品質 | ✅ | 各パラメータ・戻り値の詳細説明を追加 |
| ファイルサイズ | ⚠️ | review_service.py: 614行（500行超）。クラス分割は TASK-0088 の範囲外 |
| 機能的変更 | ✅ | なし（コメント・docstring のみ） |
| 旧実装コメントの削除 | ✅ | "バグ修正" コメント → 設計意図説明に更新 |

---

## 最終コード（変更箇所のみ）

### `review_service.py` - `get_due_cards()` メソッド

```python
def get_due_cards(
    self,
    user_id: str,
    limit: int = 20,
    include_future: bool = False,
    deck_id: Optional[str] = None,
) -> DueCardsResponse:
    """Get cards due for review.

    【設計方針】: 全復習対象カードを取得してから limit を適用する。
    これにより total_due_count が limit に影響されず正確な総数を返すことができる。
    deck_id フィルタはアプリケーション層で適用し、DynamoDB クエリは全件取得する。
    🔵 REQ-005: total_due_count は limit パラメータに影響されない正確な総数を返す

    Args:
        user_id: The user's ID.
        limit: Maximum number of cards to return in due_cards.
               total_due_count はこの値に影響されず、フィルタ後の全件数を返す。
        include_future: Include cards with future due dates.
        deck_id: Optional filter by deck ID.
                 指定した場合、total_due_count はそのデッキ内の復習対象カード総数を返す。

    Returns:
        DueCardsResponse with due cards and metadata.
        - due_cards: limit で制限されたカードリスト
        - total_due_count: deck_id フィルタ後・limit 適用前の全件数（REQ-005）
        - next_due_date: due_cards が空の場合に次の復習予定日を返す
    """
    now = datetime.now(timezone.utc)

    # 【全件取得】: limit を渡さず全復習対象カードを取得する
    all_due_cards = self.card_service.get_due_cards(
        user_id=user_id,
        limit=None,  # 【全件取得】: DynamoDB Query レベルの切り詰めを防ぎ、正確な総数を計算する 🔵
        before=now if not include_future else None,
    )

    # 【deck_id フィルタ】: deck_id が指定された場合はアプリケーション層でフィルタを適用 🔵
    if deck_id is not None:
        all_due_cards = [c for c in all_due_cards if c.deck_id == deck_id]

    # 【total_due_count 計算】: limit 適用前に全件数を記録する（REQ-005）🔵
    total_due_count = len(all_due_cards)

    # 【limit 適用】: 返却カードのみ limit で制限する（total_due_count には影響しない）🔵
    limited_cards = all_due_cards[:limit]

    # 【レスポンス形式変換】: Card モデルから DueCardInfo に変換する
    due_card_infos: List[DueCardInfo] = []
    for card in limited_cards:
        overdue_days = 0
        if card.next_review_at:
            delta = now - card.next_review_at
            overdue_days = max(0, delta.days)

        due_card_infos.append(
            DueCardInfo(
                card_id=card.card_id,
                front=card.front,
                back=card.back,
                deck_id=card.deck_id,
                due_date=card.next_review_at.date().isoformat() if card.next_review_at else None,
                overdue_days=overdue_days,
            )
        )

    next_due_date = None
    if not due_card_infos:
        next_due_date = self._get_next_due_date(user_id)

    return DueCardsResponse(
        due_cards=due_card_infos,
        total_due_count=total_due_count,
        next_due_date=next_due_date,
    )
```

### `card_service.py` - `get_due_cards()` メソッド

```python
def get_due_cards(
    self,
    user_id: str,
    limit: Optional[int] = None,
    before: Optional[datetime] = None,
) -> List[Card]:
    """Get cards due for review.

    【設計方針】: limit=None の場合は DynamoDB に Limit を渡さず全件取得する。
    呼び出し元（review_service）が deck_id フィルタ後に limit を適用するため、
    このメソッドは limit なしで全件返すことで正確な total_due_count を計算できる。 🔵

    Args:
        user_id: The user's ID.
        limit: Maximum number of cards to return. None を指定した場合は全件取得する（デフォルト）。
               deck_id フィルタを上位層で行う場合は None を渡すこと。
        before: Get cards due before this time (defaults to now).

    Returns:
        List of cards due for review, oldest due first.
    """
```
