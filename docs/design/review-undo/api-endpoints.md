# review-undo API エンドポイント仕様

**作成日**: 2026-02-28
**関連設計**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/review-undo/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・設計文書・既存API仕様を参考にした確実な定義
- 🟡 **黄信号**: EARS要件定義書・設計文書・既存API仕様から妥当な推測による定義
- 🔴 **赤信号**: EARS要件定義書・設計文書・既存API仕様にない推測による定義

---

## 共通仕様 🔵

**信頼性**: 🔵 *既存API仕様より*

既存のAPI仕様に準拠する。

### 認証 🔵

```http
Authorization: Bearer {jwt_token}
```

すべてのエンドポイントは認証必須。Keycloak OIDC JWTトークンによる認証。

### エラーレスポンス共通フォーマット 🔵

```json
{
  "message": "エラーメッセージ"
}
```

---

## 新規エンドポイント

### POST /reviews/{cardId}/undo 🔵

**信頼性**: 🔵 *要件定義REQ-009〜012・設計ヒアリングより*

**関連要件**: REQ-009, REQ-010, REQ-011, REQ-012

**説明**: カードの最新の復習結果を取り消し、SRSパラメータを前回の状態に復元する。

#### パスパラメータ

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| cardId | string | Yes | カードID |

#### リクエストボディ

なし（空ボディ）

#### レスポンス（成功） 🔵

**信頼性**: 🔵 *既存ReviewResponseパターン・要件定義REQ-010より*

**ステータスコード**: 200 OK

```json
{
  "card_id": "card-uuid-here",
  "restored": {
    "ease_factor": 2.5,
    "interval": 6,
    "repetitions": 2,
    "due_date": "2026-03-02"
  },
  "undone_at": "2026-02-28T10:30:00+00:00"
}
```

| フィールド | 型 | 説明 |
|-----------|-----|------|
| card_id | string | カードID |
| restored.ease_factor | number | 復元後のease_factor |
| restored.interval | number | 復元後のinterval（日数） |
| restored.repetitions | number | 復元後のrepetitions |
| restored.due_date | string | 復元後の次回復習日（ISO日付） |
| undone_at | string | undo実行日時（ISO 8601） |

#### エラーレスポンス

##### 400 Bad Request - 取り消し対象なし 🟡

**信頼性**: 🟡 *データ整合性の観点から妥当な推測*

review_historyが空の場合（一度も復習されていないカード）。

```json
{
  "message": "No review history to undo"
}
```

##### 401 Unauthorized 🔵

**信頼性**: 🔵 *既存API認証設計より*

認証トークンが無効または未提供。

```json
{
  "message": "Unauthorized"
}
```

##### 404 Not Found 🔵

**信頼性**: 🔵 *既存API認可設計より*

カードが存在しない、または他ユーザーのカード。

```json
{
  "message": "Card not found"
}
```

##### 500 Internal Server Error 🔵

**信頼性**: 🔵 *既存エラーハンドリングパターンより*

DynamoDB操作エラー等。

```json
{
  "message": "Internal server error"
}
```

---

## 既存エンドポイント（参考） 🔵

**信頼性**: 🔵 *既存API仕様より*

### POST /reviews/{cardId}

既存の採点APIは変更なし。undo後の再採点にも同じエンドポイントを使用する。

**変更点**: なし（ただし、`handleGrade`関数でレスポンスの`ReviewResponse`をセッション結果に保存するようフロントエンドを修正）

### GET /cards/due

既存のdue cards APIも変更なし。

---

## バックエンド実装仕様

### handler.py への追加 🔵

**信頼性**: 🔵 *既存handler.py `submit_review` のパターンより*

```python
@app.post("/reviews/<card_id>/undo")
@tracer.capture_method
def undo_review(card_id: str):
    """Undo the latest review for a card."""
    user_id = get_user_id_from_context()
    review_service = ReviewService(...)
    result = review_service.undo_review(user_id, card_id)
    return result.model_dump(), 200
```

### review_service.py への追加 🔵

**信頼性**: 🔵 *既存submit_review メソッドのパターン・要件定義REQ-010〜012より*

`undo_review(user_id, card_id)` メソッドを追加:

1. `card_service.get_card(user_id, card_id)` でカード取得・所有権確認
2. カードの `review_history` を確認（空なら400エラー）
3. 最新エントリから復元値を取得:
   - `ease_factor_before` → `ease_factor`
   - `interval_before` → `interval`
   - `repetitions_before` → `repetitions`（※新規フィールド）
   - `next_review_at_before` → `next_review_at`（※新規フィールド）
4. DynamoDB UpdateItem でSRSパラメータを復元
5. review_historyから最新エントリを削除
6. UndoReviewResponse を返却

### review.py への追加 🟡

**信頼性**: 🟡 *既存ReviewResponseパターンから妥当な推測*

```python
class UndoRestoredState(BaseModel):
    """Restored state after undo."""
    ease_factor: float
    interval: int
    repetitions: int
    due_date: str

class UndoReviewResponse(BaseModel):
    """Response model for undo review."""
    card_id: str
    restored: UndoRestoredState
    undone_at: datetime
```

### srs.py への追加 🟡

**信頼性**: 🟡 *既存ReviewHistoryEntryから妥当な推測*

`ReviewHistoryEntry` に以下のフィールドを追加:
- `repetitions_before: int`
- `repetitions_after: int`
- `next_review_at_before: str` (ISO 8601)
- `next_review_at_after: str` (ISO 8601)

### template.yaml への追加 🔵

**信頼性**: 🔵 *既存SAMテンプレートのルート定義パターンより*

```yaml
/reviews/{cardId}/undo:
  post:
    x-amazon-apigateway-integration:
      # ... ApiFunction integration (既存パターン)
```

---

## フロントエンド実装仕様

### api.ts への追加 🔵

**信頼性**: 🔵 *既存apiClient・reviewsApiパターンより*

```typescript
// ApiClient クラスに追加
async undoReview(cardId: string): Promise<UndoReviewResponse> {
  return this.request<UndoReviewResponse>(`/reviews/${cardId}/undo`, {
    method: 'POST',
  });
}

// reviewsApi に追加
export const reviewsApi = {
  submitReview: (cardId: string, grade: number) => apiClient.submitReview(cardId, grade),
  undoReview: (cardId: string) => apiClient.undoReview(cardId),
};
```

---

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **データフロー**: [dataflow.md](dataflow.md)
- **型定義**: [interfaces.ts](interfaces.ts)
- **要件定義**: [requirements.md](../../spec/review-undo/requirements.md)

## 信頼性レベルサマリー

- 🔵 青信号: 12件 (80%)
- 🟡 黄信号: 3件 (20%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質
