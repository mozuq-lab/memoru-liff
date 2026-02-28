# interval-adjust アーキテクチャ設計

**作成日**: 2026-02-28
**関連要件定義**: [requirements.md](../../spec/interval-adjust/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・設計文書・ユーザヒアリングを参考にした確実な設計
- 🟡 **黄信号**: EARS要件定義書・設計文書・ユーザヒアリングから妥当な推測による設計
- 🔴 **赤信号**: EARS要件定義書・設計文書・ユーザヒアリングにない推測による設計

---

## システム概要 🔵

**信頼性**: 🔵 *要件定義書概要・ユーザヒアリングより*

カード詳細画面にプリセットボタン（1日, 3日, 7日, 14日, 30日）を追加し、ユーザーが復習間隔（interval）を手動で調整できるようにする。既存の `PUT /cards/:card_id` APIを拡張し、intervalフィールドを受け付ける。interval変更時にnext_review_atを自動再計算し、ease_factorとrepetitionsは変更しない。

## 変更方針 🔵

**信頼性**: 🔵 *ユーザヒアリング API設計・UI配置より*

- **方針**: 既存コンポーネント・APIの拡張のみ。新規エンドポイント・新規テーブルは不要
- **選択理由**: 機能が小規模で、既存のカード更新APIと詳細画面の拡張で十分に実現可能

## 変更対象コンポーネント

### バックエンド変更 🔵

**信頼性**: 🔵 *既存実装・要件定義より*

#### 1. `backend/src/models/card.py` - UpdateCardRequest拡張

現在の `UpdateCardRequest` に `interval` フィールドを追加する。

```python
class UpdateCardRequest(BaseModel):
    front: Optional[str] = Field(None, min_length=1, max_length=1000)
    back: Optional[str] = Field(None, min_length=1, max_length=2000)
    deck_id: Optional[str] = None
    tags: Optional[List[str]] = None
    interval: Optional[int] = Field(None, ge=1, le=365)  # 追加
```

- Pydantic v2のバリデーションで `ge=1, le=365` を設定 🔵 *REQ-101, REQ-102より*

#### 2. `backend/src/services/card_service.py` - update_card拡張

`update_card` メソッドに interval パラメータを追加し、interval指定時に next_review_at を再計算する。

```python
def update_card(
    self,
    user_id: str,
    card_id: str,
    front: Optional[str] = None,
    back: Optional[str] = None,
    deck_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    interval: Optional[int] = None,  # 追加
) -> Card:
```

interval が指定された場合の処理: 🔵 *REQ-003, REQ-004より*
1. `interval` を更新
2. `next_review_at = now + timedelta(days=interval)` で再計算
3. `ease_factor` と `repetitions` は変更しない
4. `review_history` には記録しない（復習ではないため）

#### 3. `backend/src/api/handler.py` - update_card ハンドラ拡張

`card_service.update_card()` 呼び出しに `interval` パラメータを追加する。

```python
card = card_service.update_card(
    user_id=user_id,
    card_id=card_id,
    front=request.front,
    back=request.back,
    deck_id=request.deck_id,
    tags=request.tags,
    interval=request.interval,  # 追加
)
```

### フロントエンド変更 🔵

**信頼性**: 🔵 *既存実装・要件定義より*

#### 1. `frontend/src/types/card.ts` - UpdateCardRequest拡張

```typescript
export interface UpdateCardRequest {
  front?: string;
  back?: string;
  deck_id?: string;
  tags?: string[];
  interval?: number;  // 追加
}
```

#### 2. `frontend/src/pages/CardDetailPage.tsx` - プリセットボタンUI追加

カード詳細画面のメタ情報セクション（`data-testid="card-meta"`）の下にプリセットボタンを追加する。

**状態管理**: 🟡 *既存のisSaving/successMessageパターンから妥当な推測*
- `isAdjusting: boolean` - API呼び出し中フラグ
- 既存の `error` / `successMessage` state を再利用

**UI構成**:
```
┌─────────────────────────────┐
│ メタ情報                      │
│   次回復習日: 2026-03-07       │
│   復習間隔: 7日                │
├─────────────────────────────┤
│ 復習間隔を調整                 │
│ [1日] [3日] [7日] [14日] [30日] │
└─────────────────────────────┘
```

**イベントフロー**:
1. プリセットボタンタップ → `setIsAdjusting(true)`
2. `cardsApi.updateCard(id, { interval: selectedValue })` 呼び出し
3. 成功時: `setCard(updatedCard)`, `setSuccessMessage('復習間隔を更新しました')`
4. 失敗時: `setError('復習間隔の更新に失敗しました')`
5. `setIsAdjusting(false)`

## 変更しないコンポーネント 🔵

**信頼性**: 🔵 *REQ-004・REQ-403より*

- `backend/src/services/srs.py` - SM-2アルゴリズムは変更不要
- `backend/src/services/review_service.py` - 復習フローは変更不要
- `backend/template.yaml` - SAMテンプレートは変更不要
- `frontend/src/services/api.ts` - 既存の `updateCard` メソッドがそのまま使える
- DynamoDBテーブル構造 - 既存のcardsテーブルのinterval/next_review_atフィールドをそのまま使用

## 技術的制約 🔵

**信頼性**: 🔵 *既存実装・CLAUDE.mdより*

- DynamoDBのease_factorはstring型で保存（float非対応）。interval更新時もこの形式を維持する
- next_review_atはISO 8601形式（UTC）で保存。`user_id-due-index` GSIのソートキーとしても使用される
- プリセットボタンのタップ領域は44px以上を確保（既存UIの共通パターン）

## 関連文書

- **データフロー**: [dataflow.md](dataflow.md)
- **要件定義**: [requirements.md](../../spec/interval-adjust/requirements.md)
- **既存API仕様**: [api-endpoints.md](../memoru-liff/api-endpoints.md)
- **既存DBスキーマ**: [database-schema.md](../memoru-liff/database-schema.md)

## 信頼性レベルサマリー

- 🔵 青信号: 10件 (91%)
- 🟡 黄信号: 1件 (9%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質
