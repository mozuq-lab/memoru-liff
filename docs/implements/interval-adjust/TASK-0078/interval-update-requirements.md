# TASK-0078: バックエンド interval更新サポート - TDD用要件定義書

**機能名**: バックエンド interval更新サポート
**タスクID**: TASK-0078
**要件名**: interval-adjust
**作成日**: 2026-02-28

---

## 1. 機能の概要

### 何をする機能か 🔵

**信頼性**: 🔵 *要件定義 REQ-001〜004、設計文書 architecture.md システム概要より*

既存の `PUT /cards/:card_id` API を拡張し、リクエストボディに `interval`（復習間隔・日数）フィールドを受け付けるようにする。interval が指定された場合、`next_review_at` を「現在日時 + interval 日」で自動再計算し、DynamoDB のカードレコードを更新する。

### どのような問題を解決するか 🔵

**信頼性**: 🔵 *ユーザストーリー 1.1, 1.2 より*

SM-2 アルゴリズムによる自動計算では対応できない「覚えが悪いカードをもっと頻繁に復習したい」「すでに覚えたカードの復習間隔を長くしたい」というユーザーの要望に対応する。

### 想定されるユーザー 🔵

**信頼性**: 🔵 *ユーザストーリー As a 学習者 より*

学習者（ログイン済みユーザー）。カード詳細画面からプリセットボタンで復習間隔を調整する。

### システム内での位置づけ 🔵

**信頼性**: 🔵 *設計文書 architecture.md 変更方針セクションより*

バックエンドの以下3ファイルを拡張する。新規エンドポイント・新規テーブルは不要。

1. **`backend/src/models/card.py`** - `UpdateCardRequest` に `interval` フィールド追加
2. **`backend/src/services/card_service.py`** - `update_card` メソッドに `interval` パラメータ追加 + next_review_at 再計算ロジック
3. **`backend/src/api/handler.py`** - ハンドラから `card_service.update_card()` へ `interval` を渡す

- **参照した EARS 要件**: REQ-001, REQ-002, REQ-003, REQ-004, REQ-401
- **参照した設計文書**: `docs/design/interval-adjust/architecture.md` - システム概要、変更方針、バックエンド変更セクション

---

## 2. 入力・出力の仕様

### 入力パラメータ 🔵

**信頼性**: 🔵 *要件定義 REQ-101, REQ-102、設計文書 architecture.md UpdateCardRequest拡張セクションより*

#### `PUT /cards/:card_id` リクエストボディ（拡張後）

| フィールド | 型 | 必須 | 制約 | 説明 |
|-----------|-----|------|------|------|
| `front` | `Optional[str]` | No | `min_length=1, max_length=1000` | カード表面（既存） |
| `back` | `Optional[str]` | No | `min_length=1, max_length=2000` | カード裏面（既存） |
| `deck_id` | `Optional[str]` | No | - | デッキID（既存） |
| `tags` | `Optional[List[str]]` | No | 最大10個、各最大50文字 | タグ（既存） |
| **`interval`** | **`Optional[int]`** | **No** | **`ge=1, le=365`** | **復習間隔（日数）（新規追加）** |

#### Pydantic バリデーション

```python
class UpdateCardRequest(BaseModel):
    front: Optional[str] = Field(None, min_length=1, max_length=1000)
    back: Optional[str] = Field(None, min_length=1, max_length=2000)
    deck_id: Optional[str] = None
    tags: Optional[List[str]] = None
    interval: Optional[int] = Field(None, ge=1, le=365)  # 新規追加
```

#### バリデーションエラー条件 🔵

**信頼性**: 🔵 *要件定義 REQ-101, REQ-102、受け入れ基準 TC-101-01〜TC-102-B01 より*

| 入力値 | 結果 | 理由 |
|--------|------|------|
| `interval=0` | 400 Bad Request | `ge=1` 違反 |
| `interval=-1` | 400 Bad Request | `ge=1` 違反 |
| `interval=366` | 400 Bad Request | `le=365` 違反 |
| `interval=1` | 正常（境界値） | `ge=1` を満たす |
| `interval=365` | 正常（境界値） | `le=365` を満たす |
| `interval=7` | 正常 | 範囲内 |
| `interval=null` / 未指定 | 正常（interval更新なし） | Optional フィールド |

### 出力値 🔵

**信頼性**: 🔵 *既存 CardResponse モデル、設計文書 dataflow.md フロー1 より*

#### 正常レスポンス（200 OK）

`CardResponse` モデル（既存のまま変更なし）:

```json
{
  "card_id": "uuid",
  "user_id": "uuid",
  "front": "問題文",
  "back": "答え",
  "deck_id": "optional-deck-id",
  "tags": [],
  "next_review_at": "2026-03-07T10:00:00+00:00",  // interval指定時に再計算
  "interval": 7,                                    // interval指定時に更新
  "ease_factor": 2.5,                               // 不変
  "repetitions": 3,                                  // 不変
  "created_at": "2026-01-01T00:00:00+00:00",
  "updated_at": "2026-02-28T10:00:00+00:00"         // 自動更新
}
```

#### エラーレスポンス（400 Bad Request）

```json
{
  "error": "Invalid request",
  "details": [...]  // Pydantic バリデーションエラー詳細
}
```

### 入出力の関係性 🔵

**信頼性**: 🔵 *要件定義 REQ-003, REQ-004、設計文書 dataflow.md DynamoDB更新式セクションより*

#### interval 指定時の更新フィールド

| フィールド | 更新 | 更新値 |
|-----------|------|--------|
| `interval` | YES | リクエストで指定された値 |
| `next_review_at` | YES | `datetime.now(timezone.utc) + timedelta(days=interval)` |
| `updated_at` | YES | `datetime.now(timezone.utc)` |
| `ease_factor` | **NO** | 変更しない |
| `repetitions` | **NO** | 変更しない |

#### interval 未指定時

interval 関連フィールドは一切更新しない。front/back 等の他フィールドのみ更新する（既存動作）。

#### interval と他フィールドの同時指定 🔵

**信頼性**: 🔵 *設計文書 architecture.md 技術的制約セクションより*

`interval` と `front`/`back` を同時に指定した場合、全フィールドを 1 つの `UpdateExpression` でまとめて更新する。

### データフロー 🔵

**信頼性**: 🔵 *設計文書 dataflow.md フロー1 より*

```
handler.update_card
  → UpdateCardRequest バリデーション (Pydantic)
  → card_service.update_card(user_id, card_id, ..., interval=N)
    → get_card() でカード存在確認
    → interval 指定時: update_parts に interval, next_review_at を追加
    → DynamoDB update_item (SET #interval=:interval, next_review_at=:nra, updated_at=:ua)
    → 更新後の Card オブジェクトを返却
  → CardResponse JSON を返却
```

- **参照した EARS 要件**: REQ-003, REQ-004, REQ-101, REQ-102, REQ-401, REQ-402
- **参照した設計文書**: `docs/design/interval-adjust/architecture.md` - UpdateCardRequest拡張、CardService.update_card拡張、handler拡張セクション; `docs/design/interval-adjust/dataflow.md` - フロー1, フロー3, DynamoDB更新式セクション

---

## 3. 制約条件

### パフォーマンス要件 🟡

**信頼性**: 🟡 *既存API性能要件からの妥当な推測*

- interval更新APIのレスポンスタイムは500ms以内であること (NFR-001)
- 既存の update_card と同じ DynamoDB 単一 update_item 操作のため、追加のパフォーマンス影響はない

### セキュリティ要件 🔵

**信頼性**: 🔵 *既存の handler.update_card の認証パターンより*

- JWT 認証必須（`get_user_id_from_context()` で user_id を取得）
- カード所有者のみ更新可能（`card_service.get_card(user_id, card_id)` で存在確認 + 所有者チェック）
- Pydantic バリデーションで不正な interval 値を拒否

### 互換性要件 🔵

**信頼性**: 🔵 *要件定義 REQ-401, REQ-402 より*

- 既存の `PUT /cards/:card_id` エンドポイントに interval フィールドを追加する形で実現
- `interval` 未指定時は既存動作と完全に同一（後方互換性）
- `interval` 指定時でも front/back 等の既存フィールドの更新動作は変更しない

### アーキテクチャ制約 🔵

**信頼性**: 🔵 *設計文書 architecture.md、既存実装パターンより*

- 既存の `UpdateExpression` パターン（`update_parts` リストへの追加）に従う
- `interval` は DynamoDB 予約語のため `ExpressionAttributeNames` で `#interval` → `interval` のエスケープが必要
- `ease_factor` は DynamoDB で string 型として保存されている。interval 更新時にこの形式を破壊しない

### データベース制約 🔵

**信頼性**: 🔵 *既存 database-schema.md、Card モデルの to_dynamodb_item/from_dynamodb_item より*

- `next_review_at` は ISO 8601 形式（UTC）で保存。`user_id-due-index` GSI のソートキー
- `ease_factor` は string 型で保存（`str(float)` 形式）
- `interval` は Number 型で保存

### API 制約 🔵

**信頼性**: 🔵 *要件定義 REQ-403、設計文書 architecture.md 変更しないコンポーネントセクションより*

- interval 変更は `review_history` に記録しない（復習操作ではないため）
- SM-2 アルゴリズム（`srs.py`）は変更しない
- review_service は変更しない
- SAM テンプレートは変更しない

- **参照した EARS 要件**: NFR-001, REQ-401, REQ-402, REQ-403
- **参照した設計文書**: `docs/design/interval-adjust/architecture.md` - 技術的制約、変更しないコンポーネントセクション; `docs/design/memoru-liff/database-schema.md` - cards テーブル

---

## 4. 想定される使用例

### 基本的な使用パターン 🔵

**信頼性**: 🔵 *要件定義 REQ-002, REQ-003、ユーザストーリー 1.1, 1.2 より*

#### パターン1: interval のみ更新

```json
// リクエスト
PUT /cards/card-1234
{ "interval": 7 }

// レスポンス
{
  "card_id": "card-1234",
  "interval": 7,
  "next_review_at": "2026-03-07T10:00:00+00:00",
  "ease_factor": 2.5,
  "repetitions": 3,
  ...
}
```

#### パターン2: interval と front/back を同時更新

```json
// リクエスト
PUT /cards/card-1234
{ "front": "新しい問題文", "interval": 14 }

// レスポンス
{
  "card_id": "card-1234",
  "front": "新しい問題文",
  "interval": 14,
  "next_review_at": "2026-03-14T10:00:00+00:00",
  ...
}
```

#### パターン3: interval 未指定（既存動作）

```json
// リクエスト
PUT /cards/card-1234
{ "front": "更新された問題" }

// レスポンス - interval, next_review_at は変更されない
{
  "card_id": "card-1234",
  "front": "更新された問題",
  "interval": 7,             // 変更なし
  "next_review_at": "...",   // 変更なし
  ...
}
```

### エッジケース 🟡

**信頼性**: 🟡 *要件定義 EDGE-103 より（初期状態カードへの操作として妥当な推測）*

#### エッジケース1: 未復習カード（repetitions=0, interval=0）への interval 調整

```json
// リクエスト
PUT /cards/new-card-5678
{ "interval": 7 }

// レスポンス - 未復習カードでも interval 調整可能
{
  "card_id": "new-card-5678",
  "interval": 7,
  "next_review_at": "2026-03-07T10:00:00+00:00",
  "ease_factor": 2.5,
  "repetitions": 0,  // 変更なし
  ...
}
```

#### エッジケース2: 境界値 interval=1（最小値）🔵

**信頼性**: 🔵 *要件定義 EDGE-101 より*

```json
// リクエスト
PUT /cards/card-1234
{ "interval": 1 }

// next_review_at は翌日になる
```

#### エッジケース3: 境界値 interval=365（最大値）🔵

**信頼性**: 🔵 *要件定義 EDGE-102 より*

```json
// リクエスト
PUT /cards/card-1234
{ "interval": 365 }

// next_review_at は365日後になる
```

### エラーケース 🔵

**信頼性**: 🔵 *要件定義 REQ-101, REQ-102、受け入れ基準 TC-101-01〜TC-102-01 より*

#### エラーケース1: バリデーションエラー

```json
// リクエスト
PUT /cards/card-1234
{ "interval": 0 }

// レスポンス: 400 Bad Request
{ "error": "Invalid request", "details": [...] }
```

#### エラーケース2: カード未存在

```json
// リクエスト
PUT /cards/nonexistent-card
{ "interval": 7 }

// レスポンス: 404 Not Found
```

- **参照した EARS 要件**: REQ-002, REQ-003, REQ-101, REQ-102, EDGE-101, EDGE-102, EDGE-103
- **参照した設計文書**: `docs/design/interval-adjust/dataflow.md` - フロー1（正常）, フロー3（バリデーションエラー）

---

## 5. EARS要件・設計文書との対応関係

### 参照したユーザストーリー
- ストーリー 1.1: プリセットボタンで間隔を短縮する 🔵
- ストーリー 1.2: プリセットボタンで間隔を延長する 🔵

### 参照した機能要件
- REQ-001: プリセットボタン表示（TASK-0079 で対応、本タスクでは API 側のみ）
- REQ-002: interval更新API呼び出し 🔵
- REQ-003: next_review_at自動再計算 🔵
- REQ-004: ease_factor/repetitions不変 🔵
- REQ-101: interval < 1 バリデーション 🔵
- REQ-102: interval > 365 バリデーション 🔵
- REQ-401: 既存PUT /cards/:idの拡張 🔵
- REQ-402: interval指定時のみnext_review_at再計算 🟡
- REQ-403: review_historyに記録しない 🟡

### 参照した非機能要件
- NFR-001: レスポンスタイム500ms以内 🟡

### 参照したEdgeケース
- EDGE-101: interval=1（最小値）🔵
- EDGE-102: interval=365（最大値）🔵
- EDGE-103: 未復習カード 🟡

### 参照した受け入れ基準
- TC-003-01: interval=7でnext_review_atが7日後 🔵
- TC-003-02: interval=1でnext_review_atが翌日 🔵
- TC-004-01: ease_factorが変わらない 🔵
- TC-004-02: repetitionsが変わらない 🔵
- TC-101-01: interval=0で400エラー 🔵
- TC-101-02: interval=-1で400エラー 🔵
- TC-102-01: interval=366で400エラー 🔵
- TC-101-B01: interval=1で正常更新 🔵
- TC-102-B01: interval=365で正常更新 🔵

### 参照した設計文書
- **アーキテクチャ**: `docs/design/interval-adjust/architecture.md` - システム概要、変更方針、バックエンド変更、技術的制約、変更しないコンポーネント
- **データフロー**: `docs/design/interval-adjust/dataflow.md` - フロー1（正常）, フロー3（バリデーションエラー）, DynamoDB更新式
- **データベース**: `docs/design/memoru-liff/database-schema.md` - cards テーブル定義
- **API仕様**: `docs/design/memoru-liff/api-endpoints.md` - PUT /cards/:card_id

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 22 | 85% |
| 🟡 黄信号 | 4 | 15% |
| 🔴 赤信号 | 0 | 0% |

**品質評価**: ✅ 高品質

**🟡 黄信号の内訳**:
- NFR-001（パフォーマンス500ms）: 既存API性能要件からの推測。実装に影響なし
- REQ-402（interval指定時のみ再計算）: 既存 update_card の動作パターンからの推測。コードで明確に制御可能
- REQ-403（review_historyに記録しない）: SM-2設計意図からの推測。実装で明確に除外可能
- EDGE-103（未復習カード）: 初期状態カードへの操作。update_card の既存ロジックで自然に対応可能
