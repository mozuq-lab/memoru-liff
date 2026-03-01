# TASK-0089: deck_service.py description/color REMOVE - テストケース定義書

**タスクID**: TASK-0089
**機能名**: Sentinel パターンを update_deck に適用（description/color REMOVE 対応）
**要件名**: deck-review-fixes
**作成日**: 2026-03-01

---

## テスト対象

### サービス層: `backend/src/services/deck_service.py`

- `_UNSET` sentinel 定義
- `update_deck` メソッドの Sentinel パターン対応（description/color の null/未送信/値 の3パターン区別）

### ハンドラ層: `backend/src/api/handlers/decks_handler.py`

- JSON body の key 存在チェックによる null/未送信判別ロジック

---

## 1. 正常系テストケース

### TC-001: description が _UNSET（未送信）の場合、既存値が変更されない

- **テスト名**: description 未送信時は変更なし
  - **何をテストするか**: `description` パラメータを渡さない場合（デフォルト `_UNSET`）に既存の description が保持されること
  - **期待される動作**: `update_deck` を description 引数なしで呼び出しても、DynamoDB 上の description は変更されない
- **入力値**: `update_deck(user_id="user-1", deck_id=<既存>, name="新しい名前")` — description は渡さない
  - **入力データの意味**: フロントエンドが description フィールドを送信しないケース（名前のみ変更）
- **期待される結果**: `deck.description == "元の説明"` （既存値が維持される）
  - **期待結果の理由**: `_UNSET` はデフォルト値であり、「変更しない」を意味するため
- **テストの目的**: Sentinel パターンの基本動作確認 — 未送信時は既存値を保持する
  - **確認ポイント**: DynamoDB アイテムに description 属性が残存していること
- 🔵 **青信号**: REQ-105 の裏条件 + card_service.py の参照実装と同一パターン

### TC-002: description=None（明示的 null）の場合、DynamoDB から REMOVE される

- **テスト名**: description を null 送信すると REMOVE される
  - **何をテストするか**: `description=None` を明示的に渡した場合に DynamoDB から description 属性が削除されること
  - **期待される動作**: UpdateExpression に REMOVE description が含まれ、DynamoDB アイテムから属性が消える
- **入力値**: `update_deck(user_id="user-1", deck_id=<既存>, description=None)`
  - **入力データの意味**: ユーザーがデッキの説明を「クリア」する操作
- **期待される結果**: `deck.description is None` かつ DynamoDB アイテムに `description` キーが存在しない
  - **期待結果の理由**: REQ-105: description が null の場合 DynamoDB から REMOVE しなければならない
- **テストの目的**: Sentinel パターンの REMOVE 動作確認
  - **確認ポイント**: DynamoDB get_item で `"description" not in item` を検証
- 🔵 **青信号**: REQ-105 より

### TC-003: description に新しい値を渡した場合、SET される

- **テスト名**: description に値を渡すと SET される
  - **何をテストするか**: `description="新しい説明"` を渡した場合に DynamoDB で description が更新されること
  - **期待される動作**: UpdateExpression に SET description = :description が含まれる
- **入力値**: `update_deck(user_id="user-1", deck_id=<既存>, description="新しい説明")`
  - **入力データの意味**: ユーザーがデッキの説明を新しい内容に更新する操作
- **期待される結果**: `deck.description == "新しい説明"` かつ DynamoDB アイテムの description が "新しい説明"
  - **期待結果の理由**: 値が指定されている場合は SET 操作により更新される
- **テストの目的**: Sentinel パターンの SET 動作確認（従来動作の維持）
  - **確認ポイント**: DynamoDB get_item で `item["description"] == "新しい説明"` を検証
- 🔵 **青信号**: architecture.md セクション2 より

### TC-004: color が _UNSET（未送信）の場合、既存値が変更されない

- **テスト名**: color 未送信時は変更なし
  - **何をテストするか**: `color` パラメータを渡さない場合（デフォルト `_UNSET`）に既存の color が保持されること
  - **期待される動作**: `update_deck` を color 引数なしで呼び出しても、DynamoDB 上の color は変更されない
- **入力値**: `update_deck(user_id="user-1", deck_id=<既存>, name="新しい名前")` — color は渡さない
  - **入力データの意味**: フロントエンドが color フィールドを送信しないケース
- **期待される結果**: `deck.color == "#FF5733"` （既存値が維持される）
  - **期待結果の理由**: `_UNSET` はデフォルト値であり、「変更しない」を意味するため
- **テストの目的**: color フィールドの Sentinel パターン基本動作確認
  - **確認ポイント**: DynamoDB アイテムに color 属性が残存していること
- 🔵 **青信号**: REQ-106 の裏条件 + card_service.py の参照実装と同一パターン

### TC-005: color=None（明示的 null）の場合、DynamoDB から REMOVE される

- **テスト名**: color を null 送信すると REMOVE される
  - **何をテストするか**: `color=None` を明示的に渡した場合に DynamoDB から color 属性が削除されること
  - **期待される動作**: UpdateExpression に REMOVE color が含まれ、DynamoDB アイテムから属性が消える
- **入力値**: `update_deck(user_id="user-1", deck_id=<既存>, color=None)`
  - **入力データの意味**: ユーザーがデッキのカラーを「クリア」する操作
- **期待される結果**: `deck.color is None` かつ DynamoDB アイテムに `color` キーが存在しない
  - **期待結果の理由**: REQ-106: color が null の場合 DynamoDB から REMOVE しなければならない
- **テストの目的**: color フィールドの REMOVE 動作確認
  - **確認ポイント**: DynamoDB get_item で `"color" not in item` を検証
- 🔵 **青信号**: REQ-106 より

### TC-006: color に新しい値を渡した場合、SET される

- **テスト名**: color に値を渡すと SET される
  - **何をテストするか**: `color="#00FF00"` を渡した場合に DynamoDB で color が更新されること
  - **期待される動作**: UpdateExpression に SET color = :color が含まれる
- **入力値**: `update_deck(user_id="user-1", deck_id=<既存>, color="#00FF00")`
  - **入力データの意味**: ユーザーがデッキのカラーを新しい色に更新する操作
- **期待される結果**: `deck.color == "#00FF00"` かつ DynamoDB アイテムの color が "#00FF00"
  - **期待結果の理由**: 値が指定されている場合は SET 操作により更新される
- **テストの目的**: color フィールドの SET 動作確認（従来動作の維持）
  - **確認ポイント**: DynamoDB get_item で `item["color"] == "#00FF00"` を検証
- 🔵 **青信号**: architecture.md セクション2 より

### TC-007: description と color を同時に null にした場合、両方 REMOVE される（EDGE-102）

- **テスト名**: description と color を同時に null で REMOVE
  - **何をテストするか**: 両方のオプショナルフィールドを同時に null にした場合に両方が REMOVE されること
  - **期待される動作**: UpdateExpression に REMOVE description, color が含まれる
- **入力値**: `update_deck(user_id="user-1", deck_id=<既存>, description=None, color=None)`
  - **入力データの意味**: ユーザーがデッキの説明とカラーを同時にクリアする操作
- **期待される結果**: `deck.description is None` かつ `deck.color is None` かつ DynamoDB アイテムに両属性が存在しない
  - **期待結果の理由**: EDGE-102: 両属性を同時に null に設定した場合、両方が正しく REMOVE される
- **テストの目的**: 複数フィールド同時 REMOVE の動作確認
  - **確認ポイント**: DynamoDB get_item で `"description" not in item` かつ `"color" not in item` を検証
- 🔵 **青信号**: EDGE-102 より

### TC-008: SET + REMOVE の混合パターン（name SET + description REMOVE + color SET）

- **テスト名**: SET と REMOVE の混合 UpdateExpression
  - **何をテストするか**: SET と REMOVE を組み合わせた UpdateExpression が正しく構築・実行されること
  - **期待される動作**: `SET #name = :name, color = :color, updated_at = :updated_at REMOVE description` 形式の式が構築される
- **入力値**: `update_deck(user_id="user-1", deck_id=<既存>, name="更新名", description=None, color="#00FF00")`
  - **入力データの意味**: 名前変更 + 説明クリア + カラー変更を1回のリクエストで実行
- **期待される結果**: `deck.name == "更新名"` かつ `deck.description is None` かつ `deck.color == "#00FF00"` かつ DynamoDB 上で description が削除、name と color が更新済み
  - **期待結果の理由**: DynamoDB の SET + REMOVE 組み合わせ式で1回の update_item に統合される
- **テストの目的**: SET + REMOVE 混合 UpdateExpression の正常動作確認
  - **確認ポイント**: 各フィールドの DynamoDB 上の状態を個別に検証
- 🔵 **青信号**: architecture.md セクション2 使用例 4.7 より

### TC-009: 全フィールド _UNSET（変更なし）の場合、既存デッキがそのまま返される

- **テスト名**: 全フィールド未送信時はそのまま返却
  - **何をテストするか**: 全パラメータがデフォルト `_UNSET` の場合にデッキが変更されずに返却されること
  - **期待される動作**: update_parts も remove_parts も空のため、DynamoDB update_item は呼ばれずに既存 deck がそのまま返される
- **入力値**: `update_deck(user_id="user-1", deck_id=<既存>)` — 全パラメータなし
  - **入力データの意味**: フロントエンドが空の JSON body `{}` を送信したケース
- **期待される結果**: 既存のデッキオブジェクトがそのまま返される（全フィールド変更なし）
  - **期待結果の理由**: `_UNSET` は全て「変更なし」なので DynamoDB 操作は不要
- **テストの目的**: 空リクエストの安全な処理確認
  - **確認ポイント**: DynamoDB アイテムが変更されていないこと
- 🟡 **黄信号**: 既存 update_deck の動作から妥当な推測（使用例 4.6）

### TC-010: name は _UNSET（変更なし）と値（SET）のみ対応

- **テスト名**: name は _UNSET で変更なし、値で SET
  - **何をテストするか**: `name=_UNSET` でデフォルトの場合に既存名が維持されること
  - **期待される動作**: name 引数を省略した場合、name は変更されない
- **入力値**: `update_deck(user_id="user-1", deck_id=<既存>, description="新しい説明")` — name は渡さない
  - **入力データの意味**: 説明のみ更新し、名前は変えないケース
- **期待される結果**: `deck.name == "元の名前"` かつ `deck.description == "新しい説明"`
  - **期待結果の理由**: name は必須フィールドのため _UNSET の場合は変更しない
- **テストの目的**: name フィールドの Sentinel パターン動作確認
  - **確認ポイント**: name が DynamoDB 上で変更されていないこと
- 🔵 **青信号**: 要件定義 3.2 name フィールドの制約より

### TC-011: REMOVE 後に再度 SET できること（description）

- **テスト名**: description を REMOVE してから SET できる
  - **何をテストするか**: description を一度 REMOVE した後に、新しい値で SET できること
  - **期待される動作**: REMOVE 後のアイテムに新しい description を SET すると正しく追加される
- **入力値**:
  1. `update_deck(user_id="user-1", deck_id=<既存>, description=None)` — REMOVE
  2. `update_deck(user_id="user-1", deck_id=<既存>, description="復活した説明")` — SET
  - **入力データの意味**: ユーザーが説明をクリアした後、再度設定する操作フロー
- **期待される結果**: 最終的に `deck.description == "復活した説明"` かつ DynamoDB 上にも description が存在
  - **期待結果の理由**: REMOVE は属性削除であり、再度 SET すれば属性が追加される
- **テストの目的**: REMOVE → SET の往復操作が正常に動作すること
  - **確認ポイント**: 中間状態（REMOVE 後）と最終状態（SET 後）の両方を検証
- 🔵 **青信号**: card_service.py test_deck_id_remove_then_set と同一パターン

### TC-012: REMOVE 後に再度 SET できること（color）

- **テスト名**: color を REMOVE してから SET できる
  - **何をテストするか**: color を一度 REMOVE した後に、新しい値で SET できること
  - **期待される動作**: REMOVE 後のアイテムに新しい color を SET すると正しく追加される
- **入力値**:
  1. `update_deck(user_id="user-1", deck_id=<既存>, color=None)` — REMOVE
  2. `update_deck(user_id="user-1", deck_id=<既存>, color="#0000FF")` — SET
  - **入力データの意味**: ユーザーがカラーをクリアした後、再度設定する操作フロー
- **期待される結果**: 最終的に `deck.color == "#0000FF"` かつ DynamoDB 上にも color が存在
  - **期待結果の理由**: REMOVE は属性削除であり、再度 SET すれば属性が追加される
- **テストの目的**: REMOVE → SET の往復操作が正常に動作すること（color）
  - **確認ポイント**: 中間状態（REMOVE 後）と最終状態（SET 後）の両方を検証
- 🔵 **青信号**: card_service.py test_deck_id_remove_then_set と同一パターン

### TC-013: _UNSET sentinel は None とは異なるオブジェクト

- **テスト名**: _UNSET と None の独立性確認
  - **何をテストするか**: `_UNSET` sentinel が `None` とは異なるオブジェクトであること
  - **期待される動作**: `_UNSET is not None` が True
- **入力値**: `_UNSET` sentinel 値
  - **入力データの意味**: Sentinel パターンの基盤となる `_UNSET` 定数の正しさ
- **期待される結果**: `_UNSET is not None` が True、`_UNSET != None` が True
  - **期待結果の理由**: sentinel は `object()` で生成される一意のオブジェクトであり、None とは異なる
- **テストの目的**: Sentinel パターンの基本的な前提条件確認
  - **確認ポイント**: is と == の両方で None と異なることを確認
- 🔵 **青信号**: card_service.py test_sentinel_is_not_none と同一パターン

---

## 2. 異常系テストケース

### TC-014: 存在しないデッキの更新で DeckNotFoundError

- **テスト名**: 存在しないデッキの更新でエラー
  - **エラーケースの概要**: 存在しない deck_id を指定して update_deck を呼んだ場合のエラー処理
  - **エラー処理の重要性**: 不正な deck_id を弾くことでデータ整合性を保護する
- **入力値**: `update_deck(user_id="user-1", deck_id="nonexistent", description=None)`
  - **不正な理由**: 指定された deck_id のデッキが DynamoDB に存在しない
  - **実際の発生シナリオ**: デッキ削除後のキャッシュ不整合や、不正な URL パラメータ
- **期待される結果**: `DeckNotFoundError` が発生
  - **エラーメッセージの内容**: "Deck not found: nonexistent"
  - **システムの安全性**: DynamoDB に不正なアイテムが作成されない
- **テストの目的**: 存在チェック + Sentinel パターンの組み合わせ時のエラーハンドリング確認
  - **品質保証の観点**: Sentinel 引数を渡してもエラー処理が正しく動作すること
- 🔵 **青信号**: 既存テスト test_update_not_found と同一パターン

### TC-015: description=None で REMOVE 対象がもともと存在しない場合

- **テスト名**: 既に description がないデッキに description=None を送信
  - **エラーケースの概要**: description 属性がもともと存在しないデッキに対して REMOVE を実行するケース
  - **エラー処理の重要性**: DynamoDB の REMOVE は存在しない属性に対しても冪等に動作するが、アプリケーション層で問題が起きないことを確認
- **入力値**:
  1. description なしでデッキを作成
  2. `update_deck(user_id="user-1", deck_id=<既存>, description=None)`
  - **不正な理由**: 厳密にはエラーケースではないが、REMOVE 対象が存在しない境界的状況
  - **実際の発生シナリオ**: ユーザーが空のデッキに対してクリア操作を実行
- **期待される結果**: エラーなく正常に完了し、`deck.description is None` が返される
  - **エラーメッセージの内容**: エラーは発生しない
  - **システムの安全性**: DynamoDB の REMOVE は冪等であるため安全
- **テストの目的**: REMOVE の冪等性確認
  - **品質保証の観点**: 属性が存在しなくても REMOVE が安全に動作すること
- 🟡 **黄信号**: DynamoDB REMOVE の冪等性は AWS ドキュメントより妥当な推測

---

## 3. 境界値テストケース

### TC-016: description のみ REMOVE で updated_at は SET される

- **テスト名**: REMOVE のみでも updated_at が更新される
  - **境界値の意味**: update_parts が空で remove_parts のみある場合、updated_at は SET として追加される必要がある
  - **境界値での動作保証**: REMOVE only の UpdateExpression + SET updated_at の組み合わせ
- **入力値**: `update_deck(user_id="user-1", deck_id=<既存>, description=None)` — name/color は渡さない
  - **境界値選択の根拠**: SET 対象が updated_at のみ + REMOVE 対象がある「混合の最小構成」
  - **実際の使用場面**: ユーザーが説明だけをクリアするケース
- **期待される結果**: `deck.updated_at is not None` かつ DynamoDB の updated_at が更新されている
  - **境界での正確性**: updated_at は常に SET される必要がある（変更がある限り）
  - **一貫した動作**: SET のみの場合と同様に updated_at が更新される
- **テストの目的**: REMOVE 時の updated_at 更新確認
  - **堅牢性の確認**: REMOVE のみの UpdateExpression が正しく構築されること
- 🔵 **青信号**: architecture.md セクション2 使用例 4.1, 4.2 より

### TC-017: name が _UNSET で description が SET の場合

- **テスト名**: name 省略 + description SET の組み合わせ
  - **境界値の意味**: name は必須フィールドだが _UNSET で省略可能、description は SET するケース
  - **境界値での動作保証**: name が _UNSET の場合は ExpressionAttributeNames に #name が含まれないこと
- **入力値**: `update_deck(user_id="user-1", deck_id=<既存>, description="新しい説明")`
  - **境界値選択の根拠**: 必須フィールド省略 + オプショナルフィールド SET の組み合わせ
  - **実際の使用場面**: 名前はそのままで説明だけ追加するケース
- **期待される結果**: `deck.name == "元の名前"` かつ `deck.description == "新しい説明"`
  - **境界での正確性**: name は変更されない（_UNSET）、description のみ SET
  - **一貫した動作**: ExpressionAttributeNames に #name が含まれない
- **テストの目的**: 必須フィールド _UNSET + オプショナルフィールド SET の動作確認
  - **堅牢性の確認**: name 省略時にも正しく UpdateExpression が構築されること
- 🔵 **青信号**: 要件定義 3.2 + card_service.py パターンより

### TC-018: 全フィールドを SET する場合（従来動作の互換性確認）

- **テスト名**: name + description + color 全フィールド SET
  - **境界値の意味**: 全フィールドに値を渡す「最大構成」のケース
  - **境界値での動作保証**: 従来の update_deck と同等の動作をすること
- **入力値**: `update_deck(user_id="user-1", deck_id=<既存>, name="新名前", description="新説明", color="#0000FF")`
  - **境界値選択の根拠**: Sentinel 導入前と同じ呼び出しパターンの互換性検証
  - **実際の使用場面**: ユーザーがデッキ情報を全て変更するケース
- **期待される結果**: 全フィールドが更新され、DynamoDB 上にも反映されること
  - **境界での正確性**: SET のみの UpdateExpression で REMOVE は含まれない
  - **一貫した動作**: Sentinel 導入前の既存テストと同等の結果
- **テストの目的**: 後方互換性の確認
  - **堅牢性の確認**: Sentinel 導入が既存の SET 動作に影響を与えないこと
- 🔵 **青信号**: 既存テスト test_update_multiple_fields と同一パターン

---

## 4. 開発言語・フレームワーク

- **プログラミング言語**: Python 3.12
  - **言語選択の理由**: 既存プロジェクトのバックエンド言語であり、Lambda 関数と統一
  - **テストに適した機能**: pytest のパラメータ化テスト、fixture 機構
- **テストフレームワーク**: pytest + moto
  - **フレームワーク選択の理由**: 既存のテストコード（test_card_service_sentinel.py, test_deck_service.py）と同一のフレームワーク
  - **テスト実行環境**: moto による DynamoDB Local モック、`make test` で実行
- 🔵 **青信号**: note.md + 既存テストファイルより

---

## 5. テストケース実装時の日本語コメント指針

各テストケースの実装時には以下の日本語コメントを含める。

### テストケース開始時のコメント

```python
# 【テスト目的】: description=None で DynamoDB から REMOVE されること
# 【テスト内容】: description に None を渡して update_deck を呼び出す
# 【期待される動作】: deck.description is None かつ DynamoDB アイテムから description が消える
# 🔵 信頼性レベル: 青信号 - REQ-105 より
```

### Given（準備フェーズ）のコメント

```python
# 【テストデータ準備】: description 付きのデッキを作成
# 【初期条件設定】: description="テスト用の説明" で create_deck を呼び出し
# 【前提条件確認】: DynamoDB にデッキアイテムが存在し、description 属性を持つ
```

### When（実行フェーズ）のコメント

```python
# 【実際の処理実行】: update_deck に description=None を渡して呼び出す
# 【処理内容】: Sentinel パターンにより description の REMOVE が実行される
```

### Then（検証フェーズ）のコメント

```python
# 【結果検証】: 返却された deck オブジェクトの description が None であること
# 【期待値確認】: DynamoDB get_item で description 属性が存在しないこと
# 【品質保証】: REMOVE 操作が正しく DynamoDB に反映されていること
```

### assert ステートメントのコメント

```python
# 【検証項目】: deck.description が None であること
assert card.description is None
# 【検証項目】: DynamoDB アイテムから description 属性が削除されていること
assert "description" not in item
```

### セットアップ・フィクスチャのコメント

```python
@pytest.fixture
def dynamodb_setup():
    """Set up DynamoDB tables for testing."""
    # 【テスト前準備】: moto で DynamoDB テーブルをモック作成
    # 【環境初期化】: decks テーブルを PAY_PER_REQUEST で作成
```

---

## 6. 要件定義との対応関係

### 参照した機能概要
- **セクション 1.1**: Sentinel パターンを update_deck に適用して null/未送信を区別

### 参照した入力・出力仕様
- **セクション 2.1**: update_deck メソッドの入力パラメータ定義（_UNSET / None / 値 の3パターン）
- **セクション 2.2**: decks_handler.py の JSON body key 存在チェック

### 参照した制約条件
- **セクション 3.1**: DynamoDB UpdateExpression の SET + REMOVE 組み合わせ制約
- **セクション 3.2**: name フィールドの REMOVE 不可制約
- **セクション 3.3**: 互換性制約（既存呼び出し元への影響なし）

### 参照した使用例
- **セクション 4.1-4.7**: description のみクリア、color のみクリア、同時クリア、未送信、値更新、空リクエスト、混合パターン

### 参照した EARS 要件
- **REQ-105**: description が null の場合 DynamoDB から REMOVE
- **REQ-106**: color が null の場合 DynamoDB から REMOVE
- **EDGE-102**: description と color の同時 null → 両方 REMOVE

### 参照した参照実装
- **card_service.py**: `_UNSET = object()` + `update_card(deck_id=_UNSET)` パターン（TASK-0085）
- **test_card_service_sentinel.py**: Sentinel テストパターン（TASK-0085）

---

## テストケースサマリー

| No. | テストケース | 分類 | 信頼性 |
|-----|-------------|------|--------|
| TC-001 | description 未送信時は変更なし | 正常系 | 🔵 |
| TC-002 | description を null 送信すると REMOVE | 正常系 | 🔵 |
| TC-003 | description に値を渡すと SET | 正常系 | 🔵 |
| TC-004 | color 未送信時は変更なし | 正常系 | 🔵 |
| TC-005 | color を null 送信すると REMOVE | 正常系 | 🔵 |
| TC-006 | color に値を渡すと SET | 正常系 | 🔵 |
| TC-007 | description と color を同時に null で REMOVE | 正常系 | 🔵 |
| TC-008 | SET と REMOVE の混合 UpdateExpression | 正常系 | 🔵 |
| TC-009 | 全フィールド未送信時はそのまま返却 | 正常系 | 🟡 |
| TC-010 | name は _UNSET で変更なし | 正常系 | 🔵 |
| TC-011 | description を REMOVE してから SET できる | 正常系 | 🔵 |
| TC-012 | color を REMOVE してから SET できる | 正常系 | 🔵 |
| TC-013 | _UNSET と None の独立性確認 | 正常系 | 🔵 |
| TC-014 | 存在しないデッキの更新でエラー | 異常系 | 🔵 |
| TC-015 | description=None で REMOVE 対象がもともと存在しない | 異常系 | 🟡 |
| TC-016 | REMOVE のみでも updated_at が更新される | 境界値 | 🔵 |
| TC-017 | name 省略 + description SET の組み合わせ | 境界値 | 🔵 |
| TC-018 | 全フィールド SET（互換性確認） | 境界値 | 🔵 |

---

## 信頼性レベルサマリー

- **総項目数**: 18テストケース
- 🔵 **青信号**: 16件 (89%)
- 🟡 **黄信号**: 2件 (11%)
- 🔴 **赤信号**: 0件 (0%)

**品質評価**: ✅ 高品質
