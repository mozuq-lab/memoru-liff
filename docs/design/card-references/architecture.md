# card-references アーキテクチャ設計

**作成日**: 2026-03-05
**関連要件定義**: [requirements.md](../../spec/card-references/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・設計文書・ユーザヒアリングを参考にした確実な設計
- 🟡 **黄信号**: EARS要件定義書・設計文書・ユーザヒアリングから妥当な推測による設計

---

## システム概要 🔵

**信頼性**: 🔵 *要件定義書より*

カードモデルに `references` フィールド（最大5件のオブジェクトリスト）を追加する。各参考情報は `type`（url / book / note）と `value`（1-500文字）を持つ。既存の CRUD API を拡張して references を扱い、新規エンドポイントは作成しない。

## 変更方針 🔵

**信頼性**: 🔵 *既存実装パターンより*

- **方針**: 既存モデル・コンポーネント・APIの拡張のみ。新規エンドポイント・新規テーブルは不要
- **選択理由**: `tags` フィールドの追加パターンと同様に、リスト型フィールドの追加で実現可能

## 変更対象コンポーネント

### バックエンド変更 🔵

**信頼性**: 🔵 *既存実装・要件定義より*

#### 1. `backend/src/models/card.py` - Reference モデル追加 + 既存モデル拡張

新規 Pydantic モデル `Reference` を追加し、Card 関連モデルに `references` フィールドを追加する。

```python
from typing import List, Literal, Optional

class Reference(BaseModel):
    """参考情報モデル。"""
    type: Literal["url", "book", "note"]
    value: str = Field(..., min_length=1, max_length=500)

class CreateCardRequest(BaseModel):
    front: str = Field(..., min_length=1, max_length=1000)
    back: str = Field(..., min_length=1, max_length=2000)
    deck_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    references: List[Reference] = Field(default_factory=list)  # 追加

    @field_validator("references")
    @classmethod
    def validate_references(cls, v: List[Reference]) -> List[Reference]:
        if len(v) > 5:
            raise ValueError("Maximum 5 references allowed")
        return v

class UpdateCardRequest(BaseModel):
    # ...既存フィールド...
    references: Optional[List[Reference]] = None  # 追加

    @field_validator("references")
    @classmethod
    def validate_references(cls, v: Optional[List[Reference]]) -> Optional[List[Reference]]:
        if v is None:
            return v
        if len(v) > 5:
            raise ValueError("Maximum 5 references allowed")
        return v

class CardResponse(BaseModel):
    # ...既存フィールド...
    references: List[Reference] = Field(default_factory=list)  # 追加

class Card(BaseModel):
    # ...既存フィールド...
    references: List[Reference] = Field(default_factory=list)  # 追加
```

- バリデーション: `tags` と同様のパターンで `field_validator` を使用 🔵 *REQ-C01, REQ-C02*
- `Reference.value` の min_length=1, max_length=500 は Field レベルで検証 🔵 *REQ-C02*

#### 2. `backend/src/models/card.py` - Card シリアライズ/デシリアライズ拡張

```python
class Card(BaseModel):
    def to_response(self) -> CardResponse:
        return CardResponse(
            # ...既存フィールド...
            references=self.references,  # 追加
        )

    def to_dynamodb_item(self) -> dict:
        item = { ... }  # 既存フィールド
        if self.references:  # 空リストは保存しない（DynamoDBの慣例）
            item["references"] = [ref.model_dump() for ref in self.references]
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "Card":
        return cls(
            # ...既存フィールド...
            references=[
                Reference(**ref) for ref in item.get("references", [])
            ],  # 追加: 後方互換（NFR-001）
        )
```

- `to_dynamodb_item`: references が空の場合は DynamoDB アイテムに含めない（既存の `deck_id` と同パターン） 🟡
- `from_dynamodb_item`: `item.get("references", [])` で後方互換性を確保（既存の `tags` と同パターン） 🔵 *NFR-001*

#### 3. `backend/src/services/card_service.py` - create_card / update_card 拡張

**create_card**:

```python
def create_card(
    self,
    user_id: str,
    front: str,
    back: str,
    deck_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    references: Optional[List[Reference]] = None,  # 追加
) -> Card:
    card = Card(
        # ...既存フィールド...
        references=references or [],  # 追加
    )
```

**update_card**:

```python
def update_card(
    self,
    # ...既存パラメータ...
    references: Optional[List[Reference]] = None,  # 追加
) -> Card:
    # references 更新処理を追加
    if references is not None:
        update_parts.append("#references = :references")
        expression_values[":references"] = [ref.model_dump() for ref in references]
        expression_names["#references"] = "references"
        card.references = references
```

- `references` は DynamoDB の予約語ではないが、一貫性のために ExpressionAttributeNames を使用する 🟡

#### 4. `backend/src/api/handler.py` - ハンドラ拡張

`create_card` と `update_card` ハンドラで `references` パラメータを渡す。

```python
# create_card ハンドラ
card = card_service.create_card(
    # ...既存パラメータ...
    references=request.references,  # 追加
)

# update_card ハンドラ
card = card_service.update_card(
    # ...既存パラメータ...
    references=request.references,  # 追加
)
```

### フロントエンド変更 🔵

**信頼性**: 🔵 *既存実装・要件定義より*

#### 1. `frontend/src/types/card.ts` - Reference 型追加 + 既存型拡張

```typescript
export interface Reference {
  type: "url" | "book" | "note";
  value: string;
}

export interface Card {
  // ...既存フィールド...
  references?: Reference[];  // 追加（後方互換のため optional）
}

export interface CreateCardRequest {
  // ...既存フィールド...
  references?: Reference[];  // 追加
}

export interface UpdateCardRequest {
  // ...既存フィールド...
  references?: Reference[];  // 追加
}
```

#### 2. `frontend/src/components/ReferenceEditor.tsx` - 新規コンポーネント 🔵

参考情報の追加・編集・削除を行うエディタコンポーネント。CardForm 内で使用する。

**Props**:
```typescript
interface ReferenceEditorProps {
  references: Reference[];
  onChange: (references: Reference[]) => void;
  disabled?: boolean;
}
```

**UI構成**:
```
┌──────────────────────────────────────┐
│ 参考情報                              │
│                                      │
│ ┌──────────────────────────────────┐ │
│ │ [URL ▼] [https://example.com  ] [x]│ │
│ └──────────────────────────────────┘ │
│ ┌──────────────────────────────────┐ │
│ │ [書籍 ▼] [入門Python p.42     ] [x]│ │
│ └──────────────────────────────────┘ │
│                                      │
│ [+ 参考情報を追加]  (5件未満の場合表示) │
└──────────────────────────────────────┘
```

**機能**:
- type セレクタ: `<select>` で url / book / note を選択
- value 入力: `<input>` で値を入力（500文字制限）
- 削除ボタン: 各参考情報の右端に削除ボタン
- 追加ボタン: 5件未満の場合のみ表示。デフォルト type は "note" 🟡
- disabled 状態: isSaving / isRefining 時に全入力を無効化

#### 3. `frontend/src/components/ReferenceDisplay.tsx` - 新規コンポーネント 🔵

参考情報を表示するコンポーネント。CardDetailPage と ReviewPage で使用する。

**Props**:
```typescript
interface ReferenceDisplayProps {
  references: Reference[];
}
```

**UI構成**:
```
┌──────────────────────────────────┐
│ 参考情報                          │
│  🔗 https://example.com    (リンク) │
│  📖 入門Python p.42         (テキスト) │
│  📝 授業ノート 第3回         (テキスト) │
└──────────────────────────────────┘
```

**表示ルール**:
- `type="url"`: `<a href={value} target="_blank" rel="noopener noreferrer">` でクリッカブルリンク表示 🔵 *REQ-004*
- `type="book"`: テキスト表示（書籍アイコン付き） 🟡
- `type="note"`: テキスト表示（メモアイコン付き） 🟡
- references が空の場合はコンポーネント自体を非表示 🟡

#### 4. `frontend/src/components/CardForm.tsx` - ReferenceEditor 統合

CardForm に ReferenceEditor を統合する。

**変更点**:
- Props に `initialReferences` を追加
- `onSave` シグネチャを `(front, back, references)` に拡張
- references の state 管理を追加
- hasChanges 判定に references の変更を含める

```typescript
interface CardFormProps {
  initialFront: string;
  initialBack: string;
  initialReferences?: Reference[];  // 追加
  onSave: (front: string, back: string, references: Reference[]) => Promise<void>;  // 拡張
  onCancel: () => void;
  isSaving: boolean;
}
```

#### 5. `frontend/src/pages/CardDetailPage.tsx` - ReferenceDisplay 統合

カード詳細画面の表示モードに ReferenceDisplay を追加する。

**配置**: カード本文（card-detail）セクションの裏面の下、メタ情報（card-meta）の上

```
┌─────────────────────────┐
│ 表面（質問）              │
│ ...                     │
├─────────────────────────┤
│ 裏面（解答）              │
│ ...                     │
├─────────────────────────┤
│ 参考情報                  │  ← 追加
│ ...                     │
└─────────────────────────┘
┌─────────────────────────┐
│ メタ情報                  │
│ ...                     │
└─────────────────────────┘
```

**編集モード**: CardForm に `initialReferences={card.references}` を渡す。`handleSave` を references 対応に拡張する。

#### 6. `frontend/src/pages/ReviewPage.tsx` - ReferenceDisplay 統合

復習画面の裏面表示時に ReferenceDisplay を追加する。

**配置**: 裏面テキストの下に参考情報を表示 🔵 *REQ-005*

## 変更しないコンポーネント 🔵

**信頼性**: 🔵 *既存実装より*

- `backend/src/services/srs.py` — SRS アルゴリズムは変更不要
- `backend/src/services/review_service.py` — 復習フローは変更不要
- `backend/template.yaml` — SAM テンプレートは変更不要
- `frontend/src/services/api.ts` — 既存の `createCard` / `updateCard` / `getCard` メソッドがそのまま使える（リクエスト/レスポンス型が拡張されるだけ）
- DynamoDB テーブル構造 — スキーマレスのため変更不要

## 技術的制約 🔵

**信頼性**: 🔵 *既存実装・DynamoDB 特性より*

- DynamoDB に references はリスト型（L）のマップ型（M）要素として保存される
- 既存カードには references フィールドが存在しない。`from_dynamodb_item()` と `CardResponse` のデフォルト値で後方互換を確保する
- URL の形式バリデーションはフロントエンドのみで実施する（バックエンドは type="url" でも value を文字列として保存） 🟡

## 関連文書

- **要件定義**: [requirements.md](../../spec/card-references/requirements.md)
- **コンテキストノート**: [note.md](../../spec/card-references/note.md)

## 信頼性レベルサマリー

- 🔵 青信号: 16件 (76%)
- 🟡 黄信号: 5件 (24%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質
