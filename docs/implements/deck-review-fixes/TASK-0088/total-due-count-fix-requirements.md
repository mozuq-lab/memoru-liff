# TASK-0088: total_due_count 修正 - 要件定義書

**タスクID**: TASK-0088
**要件名**: deck-review-fixes
**機能名**: total_due_count 修正
**作成日**: 2026-03-01

---

## 1. 機能の概要

### 概要 🔵

**信頼性**: 🔵 *レビュー M-1・REQ-005・architecture.md セクション5 より*

- **何をする機能か**: `review_service.py` の `get_due_cards()` メソッドで返される `total_due_count` を、`limit` パラメータに影響されない正確な復習対象カード総数に修正する
- **どのような問題を解決するか**: 現在 `total_due_count` が `limit` で切り詰められた件数を返しているため、フロントエンドが正確な「残り復習カード数」を表示できない問題を修正する
- **想定されるユーザー**: Memoru アプリを使用して暗記カードを復習する学習者
- **システム内での位置づけ**: バックエンド ReviewService 層のバグ修正。`GET /cards/due` API エンドポイントのレスポンスに影響する

### 参照元

- **参照した EARS 要件**: REQ-005
- **参照した設計文書**: architecture.md セクション5 (M-1 total_due_count 修正)

---

## 2. 入力・出力の仕様

### API エンドポイント 🔵

**信頼性**: 🔵 *review_handler.py 実装・architecture.md セクション5 より*

**エンドポイント**: `GET /cards/due`

#### 入力パラメータ

| パラメータ | 型 | デフォルト | 制約 | 説明 |
|-----------|------|-----------|------|------|
| `limit` | int | 20 | 最大 100 | 返却するカード配列の上限数 |
| `deck_id` | str \| null | null | 有効なデッキID | デッキIDによるフィルタ |
| `include_future` | bool | false | - | 未来の復習日のカードを含めるか |

#### 出力（DueCardsResponse）

| フィールド | 型 | 説明 |
|-----------|------|------|
| `due_cards` | List[DueCardInfo] | limit で制限された復習対象カード配列 |
| `total_due_count` | int | **修正対象**: limit に影響されない復習対象カード総数 |
| `next_due_date` | str \| null | 次の復習日（復習対象カードがない場合） |

### DueCardInfo モデル 🔵

**信頼性**: 🔵 *models/review.py 行 68-76 より*

| フィールド | 型 | 説明 |
|-----------|------|------|
| `card_id` | str | カードID |
| `front` | str | カード表面 |
| `back` | str | カード裏面 |
| `deck_id` | str \| null | デッキID |
| `due_date` | str \| null | 復習日 (ISO format) |
| `overdue_days` | int | 復習遅延日数 |

### 入出力の関係性 🔵

**信頼性**: 🔵 *REQ-005・architecture.md セクション5 より*

```
入力: limit=10, deck_id="deck-A"

処理フロー:
1. 全復習対象カードを取得（deck_id フィルタ適用後）
2. total_due_count = len(全復習対象カード)  ← limit 前にカウント
3. due_cards = 全復習対象カード[:limit]      ← limit で制限

出力: due_cards=[10件], total_due_count=[実際の全件数]
```

### 参照元

- **参照した EARS 要件**: REQ-005
- **参照した設計文書**: architecture.md セクション5、models/review.py (DueCardsResponse)

---

## 3. 制約条件

### バグの根本原因分析 🔵

**信頼性**: 🔵 *review_service.py 行 377-446 の実装確認より*

現在の `get_due_cards()` メソッドには **2つのバグ** がある:

#### バグ1: card_service.get_due_cards() に limit が渡されている

```python
# review_service.py 行 398-402（現在の問題コード）
due_cards = self.card_service.get_due_cards(
    user_id=user_id,
    limit=limit,           # ❌ ここで limit が適用される
    before=now if not include_future else None,
)
```

`card_service.get_due_cards()` は DynamoDB Query の `Limit` パラメータとして使用するため、
deck_id フィルタ適用前にカードが `limit` 件に制限される。結果:

- deck_id フィルタ適用後のカード数が実際より少ない可能性がある
- total_due_count も不正確になる

#### バグ2: deck_id フィルタ時の total_due_count が limit 後のリスト長

```python
# review_service.py 行 429-430（現在の問題コード）
if deck_id is not None:
    total_due_count = len(due_card_infos)  # ❌ limit 適用後の件数
```

`due_card_infos` は既に limit で切り詰められた `due_cards` から生成されているため、
`total_due_count` が実際の全復習対象カード数を反映しない。

### パフォーマンス要件 🟡

**信頼性**: 🟡 *NFR-001 から妥当な推測*

- `GET /cards/due?deck_id=xxx` のレスポンスタイムは deck_id フィルタなしの場合と同等であること
- 全カードスキャンは MVP 段階ではリスク許容（最大 2000 件程度）
- 将来改善: GSI カウント または DynamoDB Streams + カウンターテーブル

### セキュリティ要件 🔵

**信頼性**: 🔵 *NFR-101・既存セキュリティ設計より*

- `user_id` は JWT 認証 (`get_user_id_from_context()`) で取得
- DynamoDB Query は `user_id` パーティションキーで制限されるため、他ユーザーのデータにアクセス不可
- `deck_id` フィルタは同一ユーザーのカードのみに適用される

### アーキテクチャ制約 🔵

**信頼性**: 🔵 *architecture.md・既存実装より*

- 修正は `review_service.py` の `get_due_cards()` メソッド内に限定
- `DueCardsResponse` モデル（models/review.py）の構造変更は不要
- `review_handler.py` のレスポンス構造は既存を維持
- `card_service.py` の `get_due_cards()` / `get_due_card_count()` は参照するが、メソッド自体の修正は最小限に留める

### 参照元

- **参照した EARS 要件**: REQ-005, NFR-001, NFR-101
- **参照した設計文書**: architecture.md セクション5、review_service.py 行 377-446

---

## 4. 想定される使用例

### 正常系 🔵

**信頼性**: 🔵 *REQ-005・タスクファイル TASK-0088 より*

#### パターン1: deck_id なし、limit < 全件数

```
入力: limit=10, deck_id=null
全復習対象カード: 20件
期待出力: due_cards=10件, total_due_count=20
```

#### パターン2: deck_id あり、limit > デッキ内カード数

```
入力: limit=10, deck_id="deck-A"
デッキA内復習対象: 5件
期待出力: due_cards=5件, total_due_count=5
```

#### パターン3: deck_id あり、limit < デッキ内カード数

```
入力: limit=10, deck_id="deck-B"
デッキB内復習対象: 15件
期待出力: due_cards=10件, total_due_count=15
```

#### パターン4: deck_id なし、limit >= 全件数

```
入力: limit=20, deck_id=null
全復習対象カード: 15件
期待出力: due_cards=15件, total_due_count=15
```

### 境界値 🟡

**信頼性**: 🟡 *note.md テストケース設計から妥当な推測*

#### パターン5: limit=0

```
入力: limit=0, deck_id=null
全復習対象カード: 10件
期待出力: due_cards=0件（空リスト）, total_due_count=10
```

#### パターン6: 存在しない deck_id

```
入力: limit=10, deck_id="non-existent"
期待出力: due_cards=0件, total_due_count=0
```

#### パターン7: 復習対象カードが0件

```
入力: limit=10, deck_id=null
全復習対象カード: 0件
期待出力: due_cards=0件, total_due_count=0, next_due_date=次回復習日
```

### エラーケース 🟡

**信頼性**: 🟡 *既存実装から妥当な推測*

#### パターン8: DynamoDB エラー

```
条件: DynamoDB 接続エラー
期待動作: CardServiceError が発生し、review_handler.py で 500 エラーとして返される
```

### 参照元

- **参照した EARS 要件**: REQ-005
- **参照した設計文書**: architecture.md セクション5、note.md テストケース設計

---

## 5. EARS 要件・設計文書との対応関係

### 参照したユーザストーリー

- 学習者として、デッキごとの復習対象カード総数を正確に把握したい。それにより、学習計画を効率的に立てることができる

### 参照した機能要件

- **REQ-005**: `GET /cards/due?deck_id=xxx` の `total_due_count` は、`limit` パラメータに影響されず、指定デッキの復習対象カード総数を正確に返さなければならない

### 参照した非機能要件

- **NFR-001**: `GET /cards/due?deck_id=xxx` のレスポンスタイムは、deck_id フィルタなしの場合と同等でなければならない
- **NFR-101**: デッキフィルタは他ユーザーのデッキを参照してはならない

### 参照した Edge ケース

- 該当する明示的な EDGE 要件なし（テストケース設計で境界値を補完）

### 参照した受け入れ基準

- 20件の復習対象カード、limit=10 の場合 `total_due_count=20`, `due_cards=10件`
- deck_id フィルタ付きで正確な件数を返すこと

### 参照した設計文書

- **アーキテクチャ**: architecture.md セクション5 (M-1 total_due_count 修正)
- **データフロー**: dataflow.md フロー5 (復習対象カード取得フロー)
- **型定義**: models/review.py (`DueCardsResponse`, `DueCardInfo`)
- **データベース**: DynamoDB `user_id-due-index` GSI
- **API 仕様**: `GET /cards/due` エンドポイント (review_handler.py 行 27-49)

---

## 6. 修正方針

### review_service.py get_due_cards() メソッド修正 🔵

**信頼性**: 🔵 *architecture.md セクション5 の擬似コードより*

```python
def get_due_cards(self, user_id, limit=20, include_future=False, deck_id=None):
    now = datetime.now(timezone.utc)

    # Step 1: limit なしで全復習対象カードを取得
    all_due_cards = self.card_service.get_due_cards(
        user_id=user_id,
        limit=None,  # ← limit を渡さない（または十分大きい値）
        before=now if not include_future else None,
    )

    # Step 2: deck_id フィルタ適用
    if deck_id is not None:
        all_due_cards = [c for c in all_due_cards if c.deck_id == deck_id]

    # Step 3: total_due_count を limit 前にカウント
    total_due_count = len(all_due_cards)

    # Step 4: limit 適用（返却カードのみ制限）
    limited_cards = all_due_cards[:limit]

    # Step 5: DueCardInfo に変換
    due_card_infos = [...]  # limited_cards から変換

    # Step 6: レスポンス返却
    return DueCardsResponse(
        due_cards=due_card_infos,
        total_due_count=total_due_count,
        next_due_date=...,
    )
```

### card_service.get_due_cards() への影響 🟡

**信頼性**: 🟡 *実装調査から妥当な推測*

`card_service.get_due_cards()` の `limit` パラメータは DynamoDB Query の `Limit` として使用されている（行 513）。limit なしで全件取得するために以下のいずれかが必要:

- **案 A**: `review_service.py` 側で十分大きい limit（例: 2000）を渡す
- **案 B**: `card_service.get_due_cards()` が `limit=None` をサポートするよう修正
- **案 C**: `card_service.get_due_card_count()` を deck_id 対応にして、カウントと返却カードを別々に取得

実装時に最適な案を選択する。

### review_handler.py への影響 🔵

**信頼性**: 🔵 *review_handler.py 実装確認より*

`review_handler.py` は `response.model_dump(mode="json")` で `DueCardsResponse` をそのままシリアライズしているため、handler 側の変更は不要。`total_due_count` フィールドは `DueCardsResponse` モデルに既に含まれている。

---

## 信頼性レベルサマリー

- **総項目数**: 12項目
- 🔵 **青信号**: 9項目 (75%)
- 🟡 **黄信号**: 3項目 (25%)
- 🔴 **赤信号**: 0項目 (0%)

**品質評価**: ✅ 高品質
