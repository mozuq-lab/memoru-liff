# TASK-0089: deck_service.py description/color REMOVE - 要件定義書

**タスクID**: TASK-0089
**機能名**: Sentinel パターンを update_deck に適用（description/color REMOVE 対応）
**要件名**: deck-review-fixes
**作成日**: 2026-03-01

---

## 1. 機能の概要

### 1.1 何をする機能か 🔵

**信頼性**: 🔵 *レビュー M-3・要件定義 REQ-105, REQ-106・architecture.md セクション2 より*

`deck_service.py` の `update_deck` メソッドにおいて、`description` と `color` フィールドの JSON `null` 送信（明示的クリア）と未送信（変更なし）を区別できるようにする。TASK-0085 で `card_service.py` に導入済みの Sentinel パターン（`_UNSET`）を `deck_service.py` にも適用する。

### 1.2 どのような問題を解決するか 🔵

**信頼性**: 🔵 *レビュー M-3 より*

**現状の問題**: `update_deck` メソッドでは `description=None` と `color=None` のデフォルト値を使用しているため、以下の2つのケースを区別できない：

1. **フロントエンドが明示的に `null` を送信** → DynamoDB から属性を REMOVE すべき
2. **フロントエンドがフィールドを送信しない** → 既存の値を変更しない

この結果、ユーザーがデッキの説明やカラーを「クリア」する操作ができない。

### 1.3 想定されるユーザー 🔵

**信頼性**: 🔵 *ユーザストーリーより*

- デッキの説明やカラーを編集・クリアしたいユーザー
- DeckFormModal で差分送信を行うフロントエンド（TASK-0094 の前提）

### 1.4 システム内での位置づけ 🔵

**信頼性**: 🔵 *architecture.md セクション2・ディレクトリ構造より*

- **バックエンドサービス層**: `backend/src/services/deck_service.py` - DynamoDB 操作のビジネスロジック
- **バックエンド API ハンドラ層**: `backend/src/api/handlers/decks_handler.py` - HTTP リクエスト処理
- **依存元**: TASK-0085（Sentinel パターン導入済み）
- **被依存**: TASK-0094（DeckFormModal 差分送信）

**参照した EARS 要件**: REQ-105, REQ-106, EDGE-102
**参照した設計文書**: architecture.md セクション2（DynamoDB REMOVE パターン）

---

## 2. 入力・出力の仕様

### 2.1 deck_service.py update_deck メソッド 🔵

**信頼性**: 🔵 *architecture.md セクション2・card_service.py 参照実装より*

#### 入力パラメータ

| パラメータ | 型 | デフォルト値 | 説明 |
|-----------|---|-------------|------|
| `user_id` | `str` | (必須) | ユーザーID |
| `deck_id` | `str` | (必須) | デッキID |
| `name` | `_UNSET \| str` | `_UNSET` | デッキ名（REMOVE 不可、必須フィールド） |
| `description` | `_UNSET \| None \| str` | `_UNSET` | デッキ説明 |
| `color` | `_UNSET \| None \| str` | `_UNSET` | カラーコード |

#### 値と動作の対応

| 値 | 動作 | DynamoDB 操作 |
|---|------|--------------|
| `_UNSET` (デフォルト) | 変更なし | 何もしない |
| `None` | 明示的クリア | REMOVE |
| `"value"` | 新しい値に更新 | SET |

#### 出力

- 成功時: 更新された `Deck` オブジェクト
- `deck.description` / `deck.color` が `None` にセットされる（REMOVE 時）
- エラー時: `DeckNotFoundError` (デッキが存在しない場合)

### 2.2 decks_handler.py update_deck ハンドラ 🔵

**信頼性**: 🔵 *architecture.md セクション2・cards_handler.py 参照実装より*

#### 入力（HTTP リクエスト）

- `PUT /decks/<deck_id>`
- JSON body の例:
  - `{"name": "新しい名前"}` → name のみ SET、description/color は変更なし
  - `{"description": null}` → description を REMOVE
  - `{"color": null}` → color を REMOVE
  - `{"description": null, "color": null}` → 両方 REMOVE (EDGE-102)
  - `{"name": "名前", "description": "説明", "color": "#FF5733"}` → 全フィールド SET

#### 判定ロジック

- JSON body に key が存在する場合 → その値（`None` または文字列）を `update_deck` に渡す
- JSON body に key が存在しない場合 → `_UNSET` (デフォルト値) のまま渡す
- `name`, `description`, `color` それぞれに対して `"name" in body` / `"description" in body` / `"color" in body` で判定

#### 出力

- 成功時: 200 OK + 更新されたデッキの JSON レスポンス
- エラー時: 404 Not Found（デッキ不存在）、400 Bad Request（バリデーションエラー）

**参照した EARS 要件**: REQ-105, REQ-106
**参照した設計文書**: architecture.md セクション2（DynamoDB REMOVE パターン）、cards_handler.py のパターン

---

## 3. 制約条件

### 3.1 DynamoDB UpdateExpression 制約 🔵

**信頼性**: 🔵 *architecture.md 技術的制約・AWS ドキュメントより*

- UpdateExpression で `SET` と `REMOVE` を組み合わせる場合、`SET ... REMOVE ...` の形式で記述する
- `SET` 部分がない場合（全フィールドが REMOVE の場合）、`REMOVE` のみの UpdateExpression を構築する
- `REMOVE` 部分がない場合（全フィールドが SET の場合）、`SET` のみの UpdateExpression を構築する（従来動作）
- ExpressionAttributeValues は SET 用の値のみ含める（REMOVE には不要）

### 3.2 name フィールドの制約 🔵

**信頼性**: 🔵 *既存モデル定義・データ整合性要件より*

- `name` はデッキの必須フィールドであり、REMOVE 不可
- `name=_UNSET` → 変更なし、`name=値` → SET
- `name=None` は受け付けない（ただし Sentinel パターンでは `_UNSET` がデフォルトのため、通常到達しない）

### 3.3 互換性制約 🔵

**信頼性**: 🔵 *既存 API 契約・card_service.py 参照実装より*

- `_UNSET` sentinel 値は `card_service.py` で既に定義済み。`deck_service.py` にも同じパターンでモジュールレベルに定義する（共有モジュールへの切り出しは将来検討）
- 既存の `update_deck` 呼び出し元（テストコード含む）で引数なしで呼び出しているケースは、`_UNSET` デフォルト値により従来と同じ「変更なし」動作を維持
- `UpdateDeckRequest` Pydantic モデル自体は変更不要（handler で raw body の key 存在チェックにより判別）

### 3.4 Pydantic バリデーション制約 🟡

**信頼性**: 🟡 *既存モデル定義・Pydantic v2 挙動から妥当な推測*

- `UpdateDeckRequest` の `description` / `color` は `Optional[str] = Field(None)` で定義済み
- JSON の `{"description": null}` は Pydantic で `description=None` にパースされる
- JSON の `{}` (description 未送信) も Pydantic で `description=None` になる
- そのため、Pydantic モデルだけでは null と未送信を区別できない → handler で raw body (`router.current_event.json_body`) から `"description" in body` で判別する必要がある

**参照した EARS 要件**: REQ-105, REQ-106
**参照した設計文書**: architecture.md セクション2・技術的制約

---

## 4. 想定される使用例

### 4.1 基本パターン: description のみクリア 🔵

**信頼性**: 🔵 *REQ-105 より*

```
PUT /decks/{deck_id}
Body: {"description": null}

→ deck_service.update_deck(user_id, deck_id, description=None)
→ DynamoDB: REMOVE description, SET updated_at = :updated_at
→ Response: deck.description = null
```

### 4.2 基本パターン: color のみクリア 🔵

**信頼性**: 🔵 *REQ-106 より*

```
PUT /decks/{deck_id}
Body: {"color": null}

→ deck_service.update_deck(user_id, deck_id, color=None)
→ DynamoDB: REMOVE color, SET updated_at = :updated_at
→ Response: deck.color = null
```

### 4.3 エッジケース: description と color を同時にクリア 🔵

**信頼性**: 🔵 *EDGE-102 より*

```
PUT /decks/{deck_id}
Body: {"description": null, "color": null}

→ deck_service.update_deck(user_id, deck_id, description=None, color=None)
→ DynamoDB: REMOVE description, color SET updated_at = :updated_at
→ Response: deck.description = null, deck.color = null
```

### 4.4 基本パターン: フィールド未送信（変更なし） 🔵

**信頼性**: 🔵 *REQ-105, REQ-106 の裏条件より*

```
PUT /decks/{deck_id}
Body: {"name": "新しい名前"}

→ deck_service.update_deck(user_id, deck_id, name="新しい名前")
→ description, color は _UNSET (デフォルト) → 変更なし
→ DynamoDB: SET #name = :name, updated_at = :updated_at
→ Response: deck.description = (既存値), deck.color = (既存値)
```

### 4.5 基本パターン: 値の更新 🔵

**信頼性**: 🔵 *architecture.md セクション2 より*

```
PUT /decks/{deck_id}
Body: {"description": "新しい説明", "color": "#FF5733"}

→ deck_service.update_deck(user_id, deck_id, description="新しい説明", color="#FF5733")
→ DynamoDB: SET description = :description, color = :color, updated_at = :updated_at
→ Response: deck.description = "新しい説明", deck.color = "#FF5733"
```

### 4.6 エッジケース: 空リクエスト（全フィールド未送信） 🟡

**信頼性**: 🟡 *既存 update_deck の動作から妥当な推測*

```
PUT /decks/{deck_id}
Body: {}

→ deck_service.update_deck(user_id, deck_id)
→ 全フィールド _UNSET → update_parts も remove_parts も空
→ 変更なし → 既存の deck をそのまま返却
```

### 4.7 エッジケース: 混合パターン（SET + REMOVE） 🔵

**信頼性**: 🔵 *architecture.md セクション2 より*

```
PUT /decks/{deck_id}
Body: {"name": "更新名", "description": null, "color": "#00FF00"}

→ deck_service.update_deck(user_id, deck_id, name="更新名", description=None, color="#00FF00")
→ DynamoDB: SET #name = :name, color = :color, updated_at = :updated_at REMOVE description
→ Response: deck.name = "更新名", deck.description = null, deck.color = "#00FF00"
```

**参照した EARS 要件**: REQ-105, REQ-106, EDGE-102
**参照した設計文書**: architecture.md セクション2

---

## 5. EARS 要件・設計文書との対応関係

### 参照したユーザストーリー

- デッキの説明やカラーを編集・クリアしたいユーザーのストーリー

### 参照した機能要件

- **REQ-105**: `UpdateDeckRequest` の `description` が `null` の場合、バックエンドはデッキの `description` を DynamoDB から REMOVE しなければならない
- **REQ-106**: `UpdateDeckRequest` の `color` が `null` の場合、バックエンドはデッキの `color` を DynamoDB から REMOVE しなければならない

### 参照した非機能要件

- なし（本タスクはパフォーマンス・セキュリティに影響なし）

### 参照した Edge ケース

- **EDGE-102**: `description` と `color` を同時に `null` に設定したデッキ更新リクエストで、両属性が正しく REMOVE される

### 参照した受け入れ基準

- `update_deck` の `name`, `description`, `color` 引数にデフォルト値 `_UNSET` を適用
- `description=None` → DynamoDB REMOVE、`description=_UNSET` → 変更なし
- `color=None` → DynamoDB REMOVE、`color=_UNSET` → 変更なし
- `description` と `color` を同時に `null` にした場合、両方 REMOVE される
- `decks_handler.py` で JSON の null/未送信を正しく sentinel に変換
- テスト: 各フィールドの null/未送信/値の3パターン

### 参照した設計文書

- **アーキテクチャ**: `docs/design/deck-review-fixes/architecture.md` セクション2（DynamoDB REMOVE パターン）
- **型定義**: `backend/src/models/deck.py` - `UpdateDeckRequest`, `Deck`
- **データベース**: DynamoDB Decks テーブル（`user_id` パーティションキー、`deck_id` ソートキー）
- **API 仕様**: `PUT /decks/<deck_id>` エンドポイント

### 参照した参照実装

- **card_service.py**: `backend/src/services/card_service.py` - `_UNSET` sentinel + `update_card(deck_id=_UNSET)` パターン (TASK-0085)
- **cards_handler.py**: `backend/src/api/handlers/cards_handler.py` - `if "deck_id" in body:` パターン (TASK-0085)

---

## 信頼性レベルサマリー

- **総項目数**: 15項目
- 🔵 **青信号**: 13項目 (87%)
- 🟡 **黄信号**: 2項目 (13%)
- 🔴 **赤信号**: 0項目 (0%)

**品質評価**: ✅ 高品質
