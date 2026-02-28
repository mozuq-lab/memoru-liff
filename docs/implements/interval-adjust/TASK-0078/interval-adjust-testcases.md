# TASK-0078: バックエンド interval更新サポート - TDD用テストケース

**機能名**: interval-adjust (バックエンド interval更新サポート)
**タスクID**: TASK-0078
**要件名**: interval-adjust
**出力ファイル**: `docs/implements/interval-adjust/TASK-0078/interval-adjust-testcases.md`
**作成日**: 2026-02-28

---

## 4. 開発言語・フレームワーク

- **プログラミング言語**: Python 3.12
  - **言語選択の理由**: 既存バックエンドが Python 3.12 で実装されている
  - **テストに適した機能**: Pydantic v2 のバリデーション検証、datetime モック、pytest の fixture/parametrize
- **テストフレームワーク**: pytest + moto
  - **フレームワーク選択の理由**: 既存テスト (`backend/tests/unit/test_card_service.py`) が pytest + moto で実装されている
  - **テスト実行環境**: `cd backend && make test` で実行。`@mock_aws` デコレータで DynamoDB をモック
- 🔵 既存テストスタック (`backend/tests/unit/test_card_service.py`) と同一

---

## テスト対象ファイルと対象レイヤー

| レイヤー | 対象ファイル | テスト内容 |
|---------|-------------|-----------|
| モデル層 | `backend/src/models/card.py` | `UpdateCardRequest` の interval バリデーション |
| サービス層 | `backend/src/services/card_service.py` | `update_card` メソッドの interval 更新ロジック |
| ハンドラ層 | `backend/src/api/handler.py` | `update_card` ハンドラから service への interval 受け渡し |

---

## 1. 正常系テストケース

### TC-N01: interval のみ指定してカード更新が成功する

- **テスト名**: interval のみ指定してカード更新が成功する
  - **何をテストするか**: `card_service.update_card` に `interval=7` を指定した場合に、interval と next_review_at が正しく更新されること
  - **期待される動作**: DynamoDB の update_item が呼ばれ、interval=7, next_review_at=現在日時+7日 が保存される
- **入力値**: `user_id="test-user-id"`, `card_id=<既存カードID>`, `interval=7`
  - **入力データの意味**: プリセットボタン「7日」の典型的な使用を再現
- **期待される結果**: 返却された Card オブジェクトで `interval == 7`, `next_review_at == now + timedelta(days=7)`
  - **期待結果の理由**: REQ-003 に基づき、`next_review_at = 現在日時 + interval日` で再計算される
- **テストの目的**: interval 更新の基本動作確認（REQ-002, REQ-003, TC-003-01）
  - **確認ポイント**: interval 値の保存、next_review_at の再計算、updated_at の自動付与
- 🔵 *要件定義 REQ-003, 受け入れ基準 TC-003-01 より*

### TC-N02: interval 指定時に ease_factor が変更されない

- **テスト名**: interval 指定時に ease_factor が変更されない
  - **何をテストするか**: interval を更新した後、既存の ease_factor が保持されること
  - **期待される動作**: ease_factor は UpdateExpression に含まれず、元の値がそのまま残る
- **入力値**: 事前に `ease_factor=2.8` のカードを作成し、`interval=14` で更新
  - **入力データの意味**: SM-2 で ease_factor が変化したカードへの interval 調整
- **期待される結果**: `ease_factor == 2.8`（変更なし）
  - **期待結果の理由**: REQ-004 に基づき、ease_factor は不変
- **テストの目的**: SRS パラメータの不変性確認（REQ-004, TC-004-01）
  - **確認ポイント**: ease_factor が DynamoDB 上で string 型 (`"2.8"`) のまま維持されること
- 🔵 *要件定義 REQ-004, 受け入れ基準 TC-004-01 より*

### TC-N03: interval 指定時に repetitions が変更されない

- **テスト名**: interval 指定時に repetitions が変更されない
  - **何をテストするか**: interval を更新した後、既存の repetitions が保持されること
  - **期待される動作**: repetitions は UpdateExpression に含まれず、元の値がそのまま残る
- **入力値**: 事前に `repetitions=5` のカードを用意（`update_review_data` で設定）、`interval=30` で更新
  - **入力データの意味**: 復習回数が蓄積されたカードへの interval 調整
- **期待される結果**: `repetitions == 5`（変更なし）
  - **期待結果の理由**: REQ-004 に基づき、repetitions は不変
- **テストの目的**: SRS パラメータの不変性確認（REQ-004, TC-004-02）
  - **確認ポイント**: repetitions が Number 型のまま保持されること
- 🔵 *要件定義 REQ-004, 受け入れ基準 TC-004-02 より*

### TC-N04: interval と front を同時に指定して更新が成功する

- **テスト名**: interval と front を同時に指定して更新が成功する
  - **何をテストするか**: interval と front/back を同時に指定した場合、全フィールドが 1 つの UpdateExpression でまとめて更新されること
  - **期待される動作**: front の更新と interval/next_review_at の更新が同時に反映される
- **入力値**: `front="新しい問題文"`, `interval=14`
  - **入力データの意味**: カード内容と復習間隔を同時に修正するユースケース
- **期待される結果**: `front == "新しい問題文"`, `interval == 14`, `next_review_at == now + 14日`
  - **期待結果の理由**: 設計文書 architecture.md の技術的制約「1つの UpdateExpression でまとめて更新する」に基づく
- **テストの目的**: 同時更新の動作確認
  - **確認ポイント**: 両方のフィールドが正しく反映されること、一方の更新が他方に影響しないこと
- 🔵 *設計文書 architecture.md 技術的制約セクションより*

### TC-N05: interval 未指定時に interval/next_review_at が変更されない

- **テスト名**: interval 未指定時に interval/next_review_at が変更されない
  - **何をテストするか**: interval を指定せずに front のみ更新した場合、interval と next_review_at は元の値のまま保持されること
  - **期待される動作**: interval 関連のフィールドが UpdateExpression に含まれない（既存動作の後方互換性）
- **入力値**: `front="更新された問題文"` のみ（interval 未指定）
  - **入力データの意味**: 既存の front/back 更新フロー（interval 機能追加前と同じ動作）
- **期待される結果**: `interval`（元の値のまま）、`next_review_at`（元の値のまま）
  - **期待結果の理由**: REQ-402 に基づき、interval 未指定時は SRS パラメータを変更しない
- **テストの目的**: 後方互換性の確認（REQ-401, REQ-402）
  - **確認ポイント**: 既存テスト (`test_update_card_front`) と同等の動作が維持されること
- 🔵 *要件定義 REQ-401, REQ-402 より*

### TC-N06: next_review_at が ISO 8601 形式 (UTC) で保存される

- **テスト名**: next_review_at が ISO 8601 形式 (UTC) で保存される
  - **何をテストするか**: interval 更新後の next_review_at が DynamoDB に ISO 8601 形式で保存され、GSI ソートキーとして正しく機能すること
  - **期待される動作**: `next_review_at.isoformat()` 形式で DynamoDB に保存される
- **入力値**: `interval=7`, `datetime.now(timezone.utc)` をモック
  - **入力データの意味**: 固定日時でのテストにより、ISO 8601 形式の正確性を検証
- **期待される結果**: DynamoDB 上の `next_review_at` が `"2026-02-28T10:00:00+00:00"` のような形式
  - **期待結果の理由**: `user_id-due-index` GSI のソートキーとして ISO 8601 形式が必要
- **テストの目的**: データ形式の正確性確認
  - **確認ポイント**: UTC タイムゾーン情報が含まれること、`fromisoformat()` でパース可能であること
- 🟡 *設計文書 architecture.md, note.md の技術的制約から妥当な推測*

### TC-N07: review_history に記録されない

- **テスト名**: interval 更新が review_history に記録されない
  - **何をテストするか**: interval 更新が復習操作ではないため、review_history テーブルにレコードが追加されないこと
  - **期待される動作**: `update_card` メソッド内で review_service は呼び出されない
- **入力値**: `interval=7` で更新後、reviews テーブルを確認
  - **入力データの意味**: interval 調整は復習ではないため記録不要
- **期待される結果**: reviews テーブルにレコードが追加されていない
  - **期待結果の理由**: REQ-403 に基づき、review_history に記録してはならない
- **テストの目的**: review_history 非記録の確認（REQ-403）
  - **確認ポイント**: reviews テーブルの scan で 0 件であること
- 🟡 *要件定義 REQ-403 より（「記録してはならない」の明示的検証）*

---

## 2. 異常系テストケース

### TC-E01: interval=0 でバリデーションエラー（Pydantic モデル層）

- **テスト名**: interval=0 で UpdateCardRequest のバリデーションエラー
  - **エラーケースの概要**: `ge=1` 制約に違反する値 0 が拒否されること
  - **エラー処理の重要性**: 不正な interval 値がサービス層に渡るのを防ぐ入力検証
- **入力値**: `UpdateCardRequest(interval=0)`
  - **不正な理由**: `ge=1` により 1 未満は不正
  - **実際の発生シナリオ**: API に直接 `{ "interval": 0 }` が送信された場合
- **期待される結果**: `pydantic.ValidationError` が発生
  - **エラーメッセージの内容**: `Input should be greater than or equal to 1` に類するメッセージ
  - **システムの安全性**: サービス層に到達する前に拒否される
- **テストの目的**: 下限バリデーションの確認（REQ-101, TC-101-01）
  - **品質保証の観点**: 不正値がDB に保存されることを防ぐ
- 🔵 *要件定義 REQ-101, 受け入れ基準 TC-101-01 より*

### TC-E02: interval=-1 でバリデーションエラー（Pydantic モデル層）

- **テスト名**: interval=-1 で UpdateCardRequest のバリデーションエラー
  - **エラーケースの概要**: 負の値が拒否されること
  - **エラー処理の重要性**: マイナスの復習間隔は論理的に意味がない
- **入力値**: `UpdateCardRequest(interval=-1)`
  - **不正な理由**: `ge=1` により負の値は不正
  - **実際の発生シナリオ**: API に直接 `{ "interval": -1 }` が送信された場合
- **期待される結果**: `pydantic.ValidationError` が発生
  - **エラーメッセージの内容**: `Input should be greater than or equal to 1` に類するメッセージ
  - **システムの安全性**: サービス層に到達する前に拒否される
- **テストの目的**: 負の値のバリデーション確認（REQ-101, TC-101-02）
  - **品質保証の観点**: 論理的に無効な値の排除
- 🔵 *要件定義 REQ-101, 受け入れ基準 TC-101-02 より*

### TC-E03: interval=366 でバリデーションエラー（Pydantic モデル層）

- **テスト名**: interval=366 で UpdateCardRequest のバリデーションエラー
  - **エラーケースの概要**: `le=365` 制約に違反する値 366 が拒否されること
  - **エラー処理の重要性**: 1年を超える復習間隔は非実用的
- **入力値**: `UpdateCardRequest(interval=366)`
  - **不正な理由**: `le=365` により 365 超は不正
  - **実際の発生シナリオ**: API に直接 `{ "interval": 366 }` が送信された場合
- **期待される結果**: `pydantic.ValidationError` が発生
  - **エラーメッセージの内容**: `Input should be less than or equal to 365` に類するメッセージ
  - **システムの安全性**: 極端に長い間隔の設定を防ぐ
- **テストの目的**: 上限バリデーションの確認（REQ-102, TC-102-01）
  - **品質保証の観点**: 非実用的な値の排除
- 🔵 *要件定義 REQ-102, 受け入れ基準 TC-102-01 より*

### TC-E04: interval に文字列を指定してバリデーションエラー（Pydantic モデル層）

- **テスト名**: interval に文字列を指定してバリデーションエラー
  - **エラーケースの概要**: 整数以外の型が拒否されること
  - **エラー処理の重要性**: 型安全性の確保
- **入力値**: `UpdateCardRequest(interval="abc")`
  - **不正な理由**: `Optional[int]` に文字列は不正
  - **実際の発生シナリオ**: 不正な JSON ボディがAPI に送信された場合
- **期待される結果**: `pydantic.ValidationError` が発生
  - **エラーメッセージの内容**: 型変換エラーに関するメッセージ
  - **システムの安全性**: 型の不整合による予期しない動作を防ぐ
- **テストの目的**: 型バリデーションの確認
  - **品質保証の観点**: Pydantic v2 の型検証が interval にも適用されること
- 🟡 *Pydantic v2 の標準動作から妥当な推測*

### TC-E05: interval に小数を指定してバリデーションエラー（Pydantic モデル層）

- **テスト名**: interval に小数を指定してバリデーションエラー
  - **エラーケースの概要**: 浮動小数点数（非整数）が拒否されること
  - **エラー処理の重要性**: interval は日数の整数値として定義
- **入力値**: `UpdateCardRequest(interval=7.5)`
  - **不正な理由**: `Optional[int]` に float は不正（Pydantic v2 strict mode ではないが、v2 デフォルトでは float → int の暗黙変換は可能。ただし `7.5` は切り捨て不可）
  - **実際の発生シナリオ**: API に `{ "interval": 7.5 }` が送信された場合
- **期待される結果**: `pydantic.ValidationError` が発生するか、整数に変換される（Pydantic v2 の動作による）
  - **エラーメッセージの内容**: Pydantic v2 のデフォルトでは `7.5` は int に変換できず ValidationError
  - **システムの安全性**: 小数の復習間隔は意味がない
- **テストの目的**: 小数値の扱い確認
  - **品質保証の観点**: 整数以外の数値型の適切な処理
- 🟡 *Pydantic v2 の int バリデーション動作から妥当な推測*

### TC-E06: 存在しないカードの interval 更新で CardNotFoundError

- **テスト名**: 存在しないカードの interval 更新で CardNotFoundError
  - **エラーケースの概要**: 存在しない card_id に対する interval 更新が適切にエラーとなること
  - **エラー処理の重要性**: 不正なカードIDでの更新を防止
- **入力値**: `user_id="test-user-id"`, `card_id="non-existent-card"`, `interval=7`
  - **不正な理由**: card_id が DynamoDB に存在しない
  - **実際の発生シナリオ**: カード削除後に古い画面から interval 調整を試みた場合
- **期待される結果**: `CardNotFoundError` が発生
  - **エラーメッセージの内容**: `Card not found: non-existent-card`
  - **システムの安全性**: 存在しないカードへの書き込みを防止
- **テストの目的**: カード存在チェックの確認
  - **品質保証の観点**: `get_card()` による事前存在確認が interval 更新時にも機能すること
- 🔵 *既存テスト `test_update_card_not_found` と同パターン*

---

## 3. 境界値テストケース

### TC-B01: interval=1（最小値）で正常に更新できる

- **テスト名**: interval=1（最小値）で正常に更新できる
  - **境界値の意味**: `ge=1` 制約の下限値。最も短い復習間隔
  - **境界値での動作保証**: 下限ぎりぎりの値で正常動作すること
- **入力値**: `interval=1`
  - **境界値選択の根拠**: Pydantic `ge=1` の下限値
  - **実際の使用場面**: 「覚えが悪いカードを翌日に復習したい」ケース
- **期待される結果**: `interval == 1`, `next_review_at == now + timedelta(days=1)`
  - **境界での正確性**: 翌日が正確に計算されること
  - **一貫した動作**: interval=2 と同様のロジックで動作すること
- **テストの目的**: 下限境界値での動作確認（EDGE-101, TC-101-B01）
  - **堅牢性の確認**: 最小値での正常動作
- 🔵 *要件定義 EDGE-101, 受け入れ基準 TC-101-B01 より*

### TC-B02: interval=365（最大値）で正常に更新できる

- **テスト名**: interval=365（最大値）で正常に更新できる
  - **境界値の意味**: `le=365` 制約の上限値。最も長い復習間隔（約1年）
  - **境界値での動作保証**: 上限ぎりぎりの値で正常動作すること
- **入力値**: `interval=365`
  - **境界値選択の根拠**: Pydantic `le=365` の上限値
  - **実際の使用場面**: 「すでに十分覚えたカードの復習を大幅に延長したい」ケース
- **期待される結果**: `interval == 365`, `next_review_at == now + timedelta(days=365)`
  - **境界での正確性**: 365日後が正確に計算されること（うるう年考慮含む）
  - **一貫した動作**: interval=364 と同様のロジックで動作すること
- **テストの目的**: 上限境界値での動作確認（EDGE-102, TC-102-B01）
  - **堅牢性の確認**: 最大値での正常動作
- 🔵 *要件定義 EDGE-102, 受け入れ基準 TC-102-B01 より*

### TC-B03: 未復習カード（repetitions=0, interval=0）に interval 調整ができる

- **テスト名**: 未復習カード（repetitions=0, interval=0）に interval 調整ができる
  - **境界値の意味**: カード作成直後の初期状態。まだ一度も復習されていない
  - **境界値での動作保証**: 初期状態のカードにも interval 調整が可能であること
- **入力値**: 新規カード（`repetitions=0`, `interval=0`）に `interval=7`
  - **境界値選択の根拠**: カード初期状態は interval=0, repetitions=0
  - **実際の使用場面**: 作成直後のカードの復習タイミングを調整したい場合
- **期待される結果**: `interval == 7`, `next_review_at == now + 7日`, `repetitions == 0`（不変）
  - **境界での正確性**: 初期状態から正常に更新されること
  - **一貫した動作**: 既に復習済みのカードと同じロジックで動作すること
- **テストの目的**: 初期状態カードでの動作確認（EDGE-103, TC-EDGE-103-01）
  - **堅牢性の確認**: 復習履歴がないカードでもエラーなく更新できること
- 🟡 *要件定義 EDGE-103（初期状態カードへの操作として妥当な推測）*

### TC-B04: interval=None（未指定）で既存の interval が変更されない

- **テスト名**: interval=None（未指定）で UpdateCardRequest のバリデーションが通る
  - **境界値の意味**: Optional フィールドの未指定パターン
  - **境界値での動作保証**: interval 未指定でも他のフィールド更新が正常に動作すること
- **入力値**: `UpdateCardRequest(front="新しい問題文")` （interval 未指定 = None）
  - **境界値選択の根拠**: Optional[int] の None は「interval 更新なし」を意味する
  - **実際の使用場面**: カード内容のみ編集し、復習間隔は変更しない場合
- **期待される結果**: バリデーション成功、`request.interval is None`
  - **境界での正確性**: None の場合にサービス層で interval 関連の更新がスキップされること
  - **一貫した動作**: 既存の `update_card` と完全に同じ動作
- **テストの目的**: Optional フィールドの未指定時の動作確認（REQ-401, REQ-402）
  - **堅牢性の確認**: interval 機能追加前と同じ動作が維持されること（後方互換性）
- 🔵 *要件定義 REQ-401, REQ-402 より*

---

## 5. テストケース実装時の日本語コメント指針

### テストファイル: `backend/tests/unit/test_card_service.py`（既存ファイルにクラス追加）

テストクラス名: `TestCardServiceUpdateInterval`

```python
# 【テスト目的】: CardService.update_card の interval パラメータ拡張をテスト
# 【テスト内容】: interval 指定時の next_review_at 再計算、ease_factor/repetitions の不変性を検証
# 【期待される動作】: interval 指定時に next_review_at が正しく計算され、SRS パラメータが保持される
# 🔵 要件定義 REQ-002〜004, REQ-401〜403, 受け入れ基準 TC-003-01〜TC-004-02 より

class TestCardServiceUpdateInterval:
    """Tests for CardService.update_card with interval parameter."""
```

#### Given（準備フェーズ）のコメント例

```python
# 【テストデータ準備】: interval 更新テスト用のカードを作成する
# 【初期条件設定】: 復習データ（ease_factor, repetitions, interval）をセットして初期状態を明確化
# 【前提条件確認】: 既存の ease_factor=2.8, repetitions=5 が設定されたカードを用意
```

#### When（実行フェーズ）のコメント例

```python
# 【実際の処理実行】: card_service.update_card に interval=7 を渡して更新を実行
# 【処理内容】: interval + next_review_at の再計算と DynamoDB 更新
# 【実行タイミング】: datetime.now をモックして固定日時で検証
```

#### Then（検証フェーズ）のコメント例

```python
# 【結果検証】: 返却された Card オブジェクトの各フィールドを検証
# 【期待値確認】: interval=7, next_review_at=固定日時+7日, ease_factor=2.8, repetitions=5
# 【品質保証】: SRS パラメータの不変性と next_review_at の正確な再計算を保証

# 【検証項目】: interval が指定した値に更新されていること
# 🔵 REQ-003 より
assert updated.interval == 7  # 【確認内容】: interval が 7 に更新されていることを確認

# 【検証項目】: next_review_at が正しく再計算されていること
# 🔵 REQ-003 より
assert updated.next_review_at == fixed_now + timedelta(days=7)  # 【確認内容】: next_review_at が 7 日後になることを確認

# 【検証項目】: ease_factor が変更されていないこと
# 🔵 REQ-004 より
assert updated.ease_factor == 2.8  # 【確認内容】: ease_factor が元の値のまま保持されることを確認

# 【検証項目】: repetitions が変更されていないこと
# 🔵 REQ-004 より
assert updated.repetitions == 5  # 【確認内容】: repetitions が元の値のまま保持されることを確認
```

### テストファイル: `backend/tests/unit/test_card_model_interval.py`（新規ファイル）

テストクラス名: `TestUpdateCardRequestInterval`

```python
# 【テスト目的】: UpdateCardRequest の interval バリデーションをテスト
# 【テスト内容】: Pydantic v2 の ge=1, le=365 制約が正しく動作することを検証
# 【期待される動作】: 範囲外の値で ValidationError、範囲内の値で正常生成
# 🔵 要件定義 REQ-101, REQ-102, 受け入れ基準 TC-101-01〜TC-102-B01 より

class TestUpdateCardRequestInterval:
    """Tests for UpdateCardRequest interval validation."""
```

#### セットアップ・クリーンアップのコメント例

```python
# 【備考】: UpdateCardRequest はステートレスな Pydantic モデルのため、
#          beforeEach/afterEach のセットアップは不要
```

---

## 6. 要件定義との対応関係

### 参照した機能概要
- **REQ-002**: interval更新API呼び出し → TC-N01
- **REQ-003**: next_review_at自動再計算 → TC-N01, TC-N06, TC-B01, TC-B02
- **REQ-004**: ease_factor/repetitions不変 → TC-N02, TC-N03

### 参照した入力・出力仕様
- **REQ-101**: interval < 1 バリデーション → TC-E01, TC-E02
- **REQ-102**: interval > 365 バリデーション → TC-E03
- **REQ-401**: 既存PUT /cards/:idの拡張 → TC-N04, TC-N05, TC-B04
- **REQ-402**: interval指定時のみnext_review_at再計算 → TC-N05, TC-B04

### 参照した制約条件
- **REQ-403**: review_historyに記録しない → TC-N07

### 参照した使用例
- **TC-003-01**: interval=7でnext_review_atが7日後 → TC-N01
- **TC-003-02**: interval=1でnext_review_atが翌日 → TC-B01
- **TC-004-01**: ease_factorが変わらない → TC-N02
- **TC-004-02**: repetitionsが変わらない → TC-N03
- **TC-101-01**: interval=0で400エラー → TC-E01
- **TC-101-02**: interval=-1で400エラー → TC-E02
- **TC-102-01**: interval=366で400エラー → TC-E03
- **TC-101-B01**: interval=1で正常更新 → TC-B01
- **TC-102-B01**: interval=365で正常更新 → TC-B02
- **EDGE-103**: 未復習カードでinterval調整 → TC-B03

### テストケース ↔ 受け入れ基準マッピング

| テストケース | 受け入れ基準 | 信頼性 |
|-------------|-------------|--------|
| TC-N01 | TC-003-01 | 🔵 |
| TC-N02 | TC-004-01 | 🔵 |
| TC-N03 | TC-004-02 | 🔵 |
| TC-N04 | - (設計文書) | 🔵 |
| TC-N05 | REQ-401, REQ-402 | 🔵 |
| TC-N06 | - (技術制約) | 🟡 |
| TC-N07 | REQ-403 | 🟡 |
| TC-E01 | TC-101-01 | 🔵 |
| TC-E02 | TC-101-02 | 🔵 |
| TC-E03 | TC-102-01 | 🔵 |
| TC-E04 | - (型安全性) | 🟡 |
| TC-E05 | - (型安全性) | 🟡 |
| TC-E06 | - (既存パターン) | 🔵 |
| TC-B01 | TC-101-B01, TC-003-02 | 🔵 |
| TC-B02 | TC-102-B01 | 🔵 |
| TC-B03 | TC-EDGE-103-01 | 🟡 |
| TC-B04 | REQ-401, REQ-402 | 🔵 |

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 12 | 71% |
| 🟡 黄信号 | 5 | 29% |
| 🔴 赤信号 | 0 | 0% |

**🟡 黄信号の内訳**:
- **TC-N06**: ISO 8601 形式の保存確認 - 技術的制約から妥当な推測。`note.md` のデータモデル説明に基づく
- **TC-N07**: review_history 非記録 - REQ-403 から明示的検証として妥当な推測
- **TC-E04**: 文字列入力のバリデーション - Pydantic v2 の標準動作から妥当な推測
- **TC-E05**: 小数入力のバリデーション - Pydantic v2 の int バリデーション動作から妥当な推測
- **TC-B03**: 未復習カードの interval 調整 - EDGE-103 から妥当な推測
