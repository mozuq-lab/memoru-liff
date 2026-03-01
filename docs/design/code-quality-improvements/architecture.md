# code-quality-improvements アーキテクチャ設計

**作成日**: 2026-03-01
**関連要件定義**: [requirements.md](../../spec/code-quality-improvements/requirements.md)
**ヒアリング記録**: [design-interview.md](design-interview.md)
**既存アーキテクチャ**: [architecture.md](../memoru-liff/architecture.md)

**【信頼性レベル凡例】**:

- 🔵 **青信号**: 要件定義書・コードレビュー結果・ユーザヒアリングから確実な設計
- 🟡 **黄信号**: 要件定義書・コードレビュー結果から妥当な推測による設計
- 🔴 **赤信号**: 要件定義書・コードレビュー結果にない推測による設計

---

## 設計概要 🔵

**信頼性**: 🔵 *コードレビュー結果・要件定義書 REQ-001〜017 より*

既存の memoru-liff アーキテクチャ（サーバーレス + LIFF + Keycloak）は **変更なし**。コードレベルの修正により Critical + High + Medium 計17件の品質問題を解消する。

### 変更方針

- アーキテクチャパターン（サーバーレス）: **変更なし** 🔵
- コンポーネント構成: **変更なし**（新規 Lambda / テーブル追加なし） 🔵
- DynamoDB スキーマ: **変更なし** 🔵
- API エンドポイント: **変更なし**（外部インターフェース互換性維持） 🔵 *REQ-402, REQ-403*
- 対象: 内部実装のリファクタリング・バグ修正・ログ改善のみ 🔵

---

## カテゴリ別設計

### 1. セキュリティ・バグ修正（REQ-001〜006）

#### 1.1 JWT dev フォールバック統合 (REQ-001, 002, 003) 🔵

**信頼性**: 🔵 *CR-01: 両レビュアー一致・ヒアリング Q3 で方針確定*

**問題**: `handler.py` と `shared.py` に同一の JWT dev フォールバックロジックが二重実装

**設計**:

```python
# backend/src/api/shared.py - 統一実装
def get_user_id_from_context(app) -> str:
    """JWT からユーザー ID を取得。dev 環境のみフォールバック許可"""
    try:
        # 通常の JWT 検証
        return app.current_event.request_context.authorizer.jwt_claim["sub"]
    except (AttributeError, KeyError, TypeError):
        # dev フォールバック: ENVIRONMENT=dev AND AWS_SAM_LOCAL が両方設定されている場合のみ
        environment = os.environ.get("ENVIRONMENT", "")
        aws_sam_local = os.environ.get("AWS_SAM_LOCAL", "")

        if environment == "dev" and aws_sam_local == "true":
            logger.warning(
                "JWT dev fallback activated",
                extra={"environment": environment, "aws_sam_local": aws_sam_local}
            )
            # Base64 デコードによるフォールバック
            return _decode_jwt_fallback(app)

        raise UnauthorizedError("Authentication required")
```

```python
# backend/src/api/handler.py - 共通関数を呼び出し
# Before: _get_user_id_from_event() の独自実装
# After: shared.py の get_user_id_from_context() を使用

@app.get("/cards")
def get_cards():
    user_id = get_user_id_from_context(app)  # 統一された関数
    ...
```

**変更対象ファイル**:

| ファイル | 変更内容 |
|---------|---------|
| `backend/src/api/shared.py` | `get_user_id_from_context` に環境変数チェック追加、warning ログ追加 |
| `backend/src/api/handler.py` | `_get_user_id_from_event` 削除、`get_user_id_from_context` に統一 |

---

#### 1.2 Strands Agent system_prompt 設定 (REQ-004, 005) 🔵

**信頼性**: 🔵 *H-06: Claude 指摘（機能バグ）*

**問題**: `grade_answer` と `generate_cards` で `Agent` 初期化時に `system_prompt` が未設定

**設計**:

```python
# backend/src/services/strands_service.py

# grade_answer メソッド
agent = Agent(
    model=self.model,
    system_prompt=GRADING_SYSTEM_PROMPT,  # 追加
    tools=[grade_tool],
)

# generate_cards メソッド
agent = Agent(
    model=self.model,
    system_prompt=CARD_GENERATION_SYSTEM_PROMPT,  # 追加
    tools=[generate_tool],
)
```

**変更対象ファイル**:

| ファイル | 変更内容 |
|---------|---------|
| `backend/src/services/strands_service.py` | `Agent` 初期化に `system_prompt` パラメータ追加（2箇所） |

---

#### 1.3 ReviewPage render 内 setState 修正 (REQ-006) 🔵

**信頼性**: 🔵 *M-02: 両レビュアー一致*

**問題**: レンダー関数内で `setRegradeCardIndex`, `setIsComplete` を直接呼び出し → React 無限レンダリングリスク

**設計**:

```typescript
// frontend/src/pages/ReviewPage.tsx

// Before: render 内で直接 setState
// if (condition) { setRegradeCardIndex(0); }

// After: useEffect に移動
useEffect(() => {
  if (regradeResults.length > 0 && regradeCardIndex === -1) {
    setRegradeCardIndex(0);
  }
}, [regradeResults, regradeCardIndex]);

useEffect(() => {
  if (shouldComplete) {
    setIsComplete(true);
  }
}, [shouldComplete]);
```

**変更対象ファイル**:

| ファイル | 変更内容 |
|---------|---------|
| `frontend/src/pages/ReviewPage.tsx` | render 内の `setState` を `useEffect` に移動 |

---

### 2. データ整合性（REQ-007〜009, REQ-015）

#### 2.1 get_due_cards ページネーション (REQ-007) 🔵

**信頼性**: 🔵 *H-01: 両レビュアー一致*

**問題**: `limit=None` 時に DynamoDB 1MB 上限を超えるデータ取得でデータ欠落

**設計**:

```python
# backend/src/services/card_service.py

def get_due_cards(self, user_id: str, limit: int | None = None, ...) -> dict:
    if limit is not None:
        # limit 指定時: 従来通り単一クエリ（変更なし）
        response = self.cards_table.query(...)
        return {"cards": response["Items"], "total_due_count": response["Count"]}

    # limit=None（全件取得）: ページネーションループ
    all_items = []
    query_params = {
        "KeyConditionExpression": ...,
        "FilterExpression": ...,
    }

    while True:
        response = self.cards_table.query(**query_params)
        all_items.extend(response.get("Items", []))

        if "LastEvaluatedKey" not in response:
            break
        query_params["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    return {"cards": all_items, "total_due_count": len(all_items)}
```

**変更対象ファイル**:

| ファイル | 変更内容 |
|---------|---------|
| `backend/src/services/card_service.py` | `get_due_cards` に `LastEvaluatedKey` ページネーションループ追加 |

---

#### 2.2 delete_card レビュー削除ページネーション (REQ-008) 🔵

**信頼性**: 🔵 *M-03: 両レビュアー一致*

**問題**: カード削除時のレビュー削除で `LastEvaluatedKey` 未対応

**設計**:

```python
# backend/src/services/card_service.py

def _delete_reviews_for_card(self, user_id: str, card_id: str) -> None:
    """カードに関連する全レビューを削除（ページネーション対応）"""
    query_params = {
        "KeyConditionExpression": Key("user_id").eq(user_id),
        "FilterExpression": Attr("card_id").eq(card_id),
        "ProjectionExpression": "user_id, review_id",
    }

    while True:
        response = self.reviews_table.query(**query_params)
        items = response.get("Items", [])

        with self.reviews_table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={"user_id": item["user_id"], "review_id": item["review_id"]})

        if "LastEvaluatedKey" not in response:
            break
        query_params["ExclusiveStartKey"] = response["LastEvaluatedKey"]
```

**変更対象ファイル**:

| ファイル | 変更内容 |
|---------|---------|
| `backend/src/services/card_service.py` | レビュー削除にページネーションループ追加 |

---

#### 2.3 _get_next_due_date 条件追加 (REQ-009) 🔵

**信頼性**: 🔵 *M-06: ヒアリング Q4 で確定*

**問題**: `KeyConditionExpression` に将来日フィルタがなく、過去の期限切れカードも取得される可能性

**設計**:

```python
# backend/src/services/review_service.py

def _get_next_due_date(self, user_id: str) -> str | None:
    response = self.cards_table.query(
        IndexName="user-next-review-index",
        KeyConditionExpression=(
            Key("user_id").eq(user_id)
            & Key("next_review_at").gt(now_iso)  # 追加: 将来日のみ
        ),
        Limit=1,
        ScanIndexForward=True,
    )
    items = response.get("Items", [])
    return items[0]["next_review_at"] if items else None
```

**変更対象ファイル**:

| ファイル | 変更内容 |
|---------|---------|
| `backend/src/services/review_service.py` | `_get_next_due_date` に `next_review_at > :now` 条件追加 |

---

#### 2.4 review_history 並行更新対策 (REQ-015) 🔵

**信頼性**: 🔵 *H-02: 両レビュアー一致・設計ヒアリングで list_append 方式に決定*

**問題**: `_update_card_review_data` と `undo_review` で review_history を読み取り→書き込みの非原子操作

**設計**: DynamoDB の `list_append` を活用して原子的に追記

```python
# backend/src/services/review_service.py

def _update_card_review_data(self, user_id, card_id, review_entry, srs_params):
    self.cards_table.update_item(
        Key={"user_id": user_id, "card_id": card_id},
        UpdateExpression=(
            "SET ease_factor = :ef, #interval = :iv, repetitions = :rep, "
            "next_review_at = :nra, "
            "review_history = list_append("
            "  if_not_exists(review_history, :empty_list), :new_entry"
            ")"
        ),
        ExpressionAttributeNames={"#interval": "interval"},
        ExpressionAttributeValues={
            ":ef": review_entry.ease_factor,
            ":iv": review_entry.interval,
            ":rep": review_entry.repetitions,
            ":nra": review_entry.next_review_at,
            ":new_entry": [review_entry.to_dict()],
            ":empty_list": [],
        },
    )
```

**変更対象ファイル**:

| ファイル | 変更内容 |
|---------|---------|
| `backend/src/services/review_service.py` | `_update_card_review_data` で `list_append` 使用、`undo_review` の review_history 更新も同様 |

---

### 3. コード品質（REQ-010〜013）

#### 3.1 例外ハンドリング共通化 (REQ-010) 🔵

**信頼性**: 🔵 *H-03: Claude 指摘・設計ヒアリングでコンテキストマネージャ方式に決定*

**問題**: `strands_service.py` の 3 メソッドに同一の try-except ブロックが重複

**設計**: コンテキストマネージャで共通化

```python
# backend/src/services/strands_service.py

from contextlib import contextmanager

@contextmanager
def _handle_ai_errors(self, operation: str):
    """AI サービス呼び出しの共通例外ハンドリング"""
    try:
        yield
    except TimeoutError as e:
        logger.warning("AI operation timed out", extra={"operation": operation, "error": str(e)})
        raise AITimeoutError(f"{operation} timed out") from e
    except ConnectionError as e:
        logger.warning("AI provider connection error", extra={"operation": operation, "error": str(e)})
        raise AIProviderError(f"{operation} connection failed") from e
    except Exception as e:
        if "throttl" in str(e).lower() or "rate" in str(e).lower():
            logger.warning("AI rate limit hit", extra={"operation": operation, "error": str(e)})
            raise AIRateLimitError(f"{operation} rate limited") from e
        logger.error("AI operation failed", extra={"operation": operation, "error": str(e)})
        raise AIInternalError(f"{operation} failed") from e

# 使用例
def grade_answer(self, card, user_answer):
    with self._handle_ai_errors("grade_answer"):
        agent = Agent(
            model=self.model,
            system_prompt=GRADING_SYSTEM_PROMPT,
            tools=[grade_tool],
        )
        result = agent(prompt)
        return self._parse_grading_result(result)
```

**変更対象ファイル**:

| ファイル | 変更内容 |
|---------|---------|
| `backend/src/services/strands_service.py` | `_handle_ai_errors` コンテキストマネージャ追加、3メソッドのtry-except置換 |

---

#### 3.2 サイレント例外の解消 (REQ-011) 🔵

**信頼性**: 🔵 *H-05: 両レビュアー一致*

**問題**: `except ClientError: pass` / `except Exception: pass` でエラーが握りつぶされている

**設計**:

```python
# backend/src/services/review_service.py - _record_review
# Before:
except ClientError:
    pass

# After:
except ClientError as e:
    logger.warning(
        "Failed to record review",
        extra={"user_id": user_id, "card_id": card_id, "error": str(e)}
    )

# backend/src/services/card_service.py - delete_card レビュー削除
# Before:
except Exception:
    pass

# After:
except Exception as e:
    logger.warning(
        "Failed to delete reviews for card",
        extra={"user_id": user_id, "card_id": card_id, "error": str(e)}
    )
```

**変更対象ファイル**:

| ファイル | 変更内容 |
|---------|---------|
| `backend/src/services/review_service.py` | `_record_review` の `except: pass` → `logger.warning` |
| `backend/src/services/card_service.py` | レビュー削除の `except: pass` → `logger.warning` |

---

#### 3.3 構造化ログ移行 (REQ-012) 🔵

**信頼性**: 🔵 *H-04: Claude 指摘*

**問題**: f-string でログメッセージを構築 → CloudWatch Logs Insights での検索不可

**設計**:

```python
# Before (f-string パターン):
logger.info(f"Card created: {card_id} for user {user_id}")

# After (構造化ログ):
logger.info("Card created", extra={"card_id": card_id, "user_id": user_id})

# Before:
logger.error(f"Failed to grade: {e}")

# After:
logger.error("Failed to grade", extra={"error": str(e), "card_id": card_id})
```

**変更対象ファイル**:

| ファイル | 変更内容 |
|---------|---------|
| `backend/src/api/handler.py` | f-string ログ → 構造化ログ（`extra={}` パラメータ） |
| `backend/src/api/shared.py` | f-string ログ → 構造化ログ |

---

#### 3.4 重複データクラス削除 (REQ-013) 🔵

**信頼性**: 🔵 *M-05: Claude 指摘*

**問題**: `bedrock.py` に `GeneratedCard` と `GenerationResult` が重複定義

**設計**:

```python
# backend/src/services/bedrock.py

# Before: ローカルに重複定義
@dataclass
class GeneratedCard:
    front: str
    back: str

@dataclass
class GenerationResult:
    cards: list[GeneratedCard]

# After: ai_service.py から import
from backend.src.services.ai_service import GeneratedCard, GenerationResult
```

**変更対象ファイル**:

| ファイル | 変更内容 |
|---------|---------|
| `backend/src/services/bedrock.py` | 重複 `GeneratedCard` / `GenerationResult` 削除、`ai_service` から import |

---

### 4. ロバストネス強化（REQ-014, 016, 017）

#### 4.1 401 リフレッシュ再帰制限 (REQ-014) 🔵

**信頼性**: 🔵 *M-01: 両レビュアー一致*

**問題**: 401 レスポンス時のトークンリフレッシュ + リトライが無限再帰の可能性

**設計**:

```typescript
// frontend/src/services/api.ts

private async request<T>(path: string, options?: RequestInit, _isRetry = false): Promise<T> {
  const response = await fetch(url, { ...options, headers });

  if (response.status === 401 && !_isRetry) {
    await this.authService.refreshToken();
    return this.request<T>(path, options, true);  // _isRetry=true で再帰制限
  }

  // 2回目の 401 はリフレッシュせずエラーを投げる
  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }

  return response.json();
}
```

**変更対象ファイル**:

| ファイル | 変更内容 |
|---------|---------|
| `frontend/src/services/api.ts` | `_isRetry` フラグ追加で再帰を最大1回に制限 |

---

#### 4.2 link_line 原子的更新 (REQ-016) 🔵

**信頼性**: 🔵 *M-08: Codex 指摘・設計ヒアリングで ConditionExpression 方式に決定*

**問題**: check-then-update パターンによる TOCTOU 競合リスク

**設計**:

```python
# backend/src/services/user_service.py

def link_line(self, user_id: str, line_user_id: str) -> User:
    try:
        self.users_table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET line_user_id = :lid",
            ConditionExpression=(
                "attribute_not_exists(line_user_id) OR line_user_id = :lid"
            ),
            ExpressionAttributeValues={":lid": line_user_id},
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ConflictError("LINE account already linked to another user")
        raise

    return self.get_user(user_id)
```

**変更対象ファイル**:

| ファイル | 変更内容 |
|---------|---------|
| `backend/src/services/user_service.py` | `link_line` を `ConditionExpression` による原子的更新に変更 |

---

#### 4.3 undo_review 仕様明文化 (REQ-017) 🔵

**信頼性**: 🔵 *H-08: ヒアリング Q2 で確定*

**設計**:

```python
# backend/src/services/review_service.py

def undo_review(self, user_id: str, card_id: str) -> dict:
    """直前のレビューを取り消し、カードの SRS パラメータを復元する。

    設計意図:
    - Undo は cards_table の SRS パラメータ（ease_factor, interval, repetitions,
      next_review_at, review_history）のみ復元する
    - reviews_table のレコードは削除しない（学習統計の累積を維持する設計意図）
    """
    ...
```

**変更対象ファイル**:

| ファイル | 変更内容 |
|---------|---------|
| `backend/src/services/review_service.py` | `undo_review` にドキュメントコメント追加 |

---

## コンポーネント別修正サマリー

### Backend 修正一覧 🔵

| ファイル | 変更内容 | 対応要件 |
|---------|---------|---------|
| `backend/src/api/handler.py` | JWT フォールバック統一、構造化ログ | REQ-001, 012 |
| `backend/src/api/shared.py` | JWT フォールバック強化、構造化ログ | REQ-001, 002, 003, 012 |
| `backend/src/services/strands_service.py` | system_prompt 追加、例外共通化 | REQ-004, 005, 010 |
| `backend/src/services/bedrock.py` | 重複データクラス削除 | REQ-013 |
| `backend/src/services/card_service.py` | ページネーション追加（2箇所）、ログ追加 | REQ-007, 008, 011 |
| `backend/src/services/review_service.py` | list_append、条件追加、ログ追加、コメント | REQ-009, 011, 015, 017 |
| `backend/src/services/user_service.py` | ConditionExpression 原子的更新 | REQ-016 |

### Frontend 修正一覧 🔵

| ファイル | 変更内容 | 対応要件 |
|---------|---------|---------|
| `frontend/src/pages/ReviewPage.tsx` | render 内 setState → useEffect | REQ-006 |
| `frontend/src/services/api.ts` | 401 リトライ制限 | REQ-014 |

---

## 非機能要件の実現方法

### セキュリティ 🔵

**信頼性**: 🔵 *要件定義書・コードレビュー結果より*

| 項目 | 実現方法 | 対応要件 |
|------|---------|---------|
| JWT dev フォールバック制限 | `ENVIRONMENT=dev` AND `AWS_SAM_LOCAL=true` の二重条件 | REQ-003 |
| フォールバック可視化 | `logger.warning` で発動記録 | REQ-002 |

### データ整合性 🔵

**信頼性**: 🔵 *要件定義書・コードレビュー結果より*

| 項目 | 実現方法 | 対応要件 |
|------|---------|---------|
| 大量カード取得 | `LastEvaluatedKey` ページネーションループ | REQ-007 |
| レビュー全件削除 | `LastEvaluatedKey` ページネーションループ | REQ-008 |
| 並行更新防止 | DynamoDB `list_append` 原子操作 | REQ-015 |
| LINE 重複紐づけ防止 | `ConditionExpression` 原子的更新 | REQ-016 |

### 可観測性 🔵

**信頼性**: 🔵 *要件定義書・コードレビュー結果より*

| 項目 | 実現方法 | 対応要件 |
|------|---------|---------|
| 構造化ログ | Lambda Powertools `extra={}` パラメータ | REQ-012 |
| サイレント例外解消 | `except: pass` → `logger.warning` | REQ-011 |

### 保守性 🔵

**信頼性**: 🔵 *要件定義書・コードレビュー結果より*

| 項目 | 実現方法 | 対応要件 |
|------|---------|---------|
| 例外ハンドリング重複解消 | コンテキストマネージャ `_handle_ai_errors` | REQ-010 |
| データクラス重複解消 | `bedrock.py` → `ai_service.py` import | REQ-013 |
| JWT フォールバック二重実装解消 | `shared.py` に統一 | REQ-001 |

---

## 技術的制約 🔵

**信頼性**: 🔵 *CLAUDE.md・要件定義書 REQ-401〜403 より*

- 全変更でテストカバレッジ 80% 以上を維持（REQ-401）
- 既存 API レスポンス形式は変更不可（REQ-402）
- `grade_ai_handler`, `advice_handler` の外部インターフェース変更不可（REQ-403）
- `get_due_cards` のページネーション追加後も API レスポンスレイテンシは現状同等を維持

---

## 関連文書

- **データフロー**: [dataflow.md](dataflow.md)
- **設計ヒアリング**: [design-interview.md](design-interview.md)
- **要件定義**: [requirements.md](../../spec/code-quality-improvements/requirements.md)
- **既存アーキテクチャ**: [architecture.md](../memoru-liff/architecture.md)
- **既存 DB スキーマ**: [database-schema.md](../memoru-liff/database-schema.md)
- **既存 API 仕様**: [api-endpoints.md](../memoru-liff/api-endpoints.md)

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 21件 | 100% |
| 🟡 黄信号 | 0件 | 0% |
| 🔴 赤信号 | 0件 | 0% |

**品質評価**: ✅ 高品質（全項目が青信号、コードレビュー結果とヒアリングに基づく確実な設計）
