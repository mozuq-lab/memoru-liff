# TASK-0088: total_due_count 修正 - テストケース定義書

**タスクID**: TASK-0088
**要件名**: deck-review-fixes
**機能名**: total_due_count 修正
**作成日**: 2026-03-01

---

## 1. 正常系テストケース

### TC-001: deck_id なし・limit < 全件数で total_due_count が全件数を返す

- **テスト名**: deck_id なし・limit 未満の全件数で total_due_count が正確な総数を返す
  - **何をテストするか**: `get_due_cards(limit=10)` 呼び出し時に、復習対象カードが20件ある場合、`total_due_count` が limit に影響されず20を返すこと
  - **期待される動作**: limit 適用前に全復習対象カード数をカウントし、`total_due_count` に設定する
- **入力値**: `user_id="test-user-id"`, `limit=10`, `deck_id=None`, 復習対象カード20件を DynamoDB に投入
  - **入力データの意味**: REQ-005 の受け入れ基準「20件の復習対象カード、limit=10 → total_due_count=20」を直接検証する
- **期待される結果**: `response.total_due_count == 20`, `len(response.due_cards) == 10`
  - **期待結果の理由**: `total_due_count` は limit に影響されない全復習対象カード総数であるべき（REQ-005）
- **テストの目的**: TASK-0088 の核心的なバグ修正を検証する
  - **確認ポイント**: `total_due_count` と `len(due_cards)` が異なる値を持てること
- 🔵 **青信号**: REQ-005 の受け入れ基準・TASK-0088 完了条件に直接対応

---

### TC-002: deck_id あり・limit > デッキ内カード数で total_due_count がデッキ内件数を返す

- **テスト名**: deck_id フィルタ付き・limit がデッキ内カード数以上の場合の total_due_count
  - **何をテストするか**: `get_due_cards(limit=10, deck_id="deck-A")` で、デッキA内の復習対象が5件の場合、`total_due_count=5` を返すこと
  - **期待される動作**: deck_id フィルタ適用後の全件数を `total_due_count` に設定し、limit 未満なので全件返却
- **入力値**: `user_id="test-user-id"`, `limit=10`, `deck_id="deck-A"`, デッキA内5件 + デッキB内3件を投入
  - **入力データの意味**: deck_id フィルタが正しく適用され、他デッキのカードを含まないことを確認する
- **期待される結果**: `response.total_due_count == 5`, `len(response.due_cards) == 5`
  - **期待結果の理由**: deck_id フィルタ後の全件数が total_due_count に反映され、limit より少ないため全件返却
- **テストの目的**: deck_id フィルタが total_due_count に正しく反映されることを確認
  - **確認ポイント**: 他デッキ（deck-B）のカードがカウントに含まれないこと
- 🔵 **青信号**: 要件定義 パターン2 に直接対応

---

### TC-003: deck_id あり・limit < デッキ内カード数で total_due_count がデッキ内全件数を返す

- **テスト名**: deck_id フィルタ付き・limit 未満のデッキ内カード数で total_due_count が正確な総数を返す
  - **何をテストするか**: `get_due_cards(limit=10, deck_id="deck-B")` で、デッキB内の復習対象が15件の場合、`total_due_count=15`, `due_cards=10件` を返すこと
  - **期待される動作**: deck_id フィルタ適用後の全件数を `total_due_count` に設定し、limit で返却カードのみ制限
- **入力値**: `user_id="test-user-id"`, `limit=10`, `deck_id="deck-B"`, デッキB内15件 + デッキA内3件を投入
  - **入力データの意味**: deck_id フィルタと limit の両方が正しく動作する最も重要なケース
- **期待される結果**: `response.total_due_count == 15`, `len(response.due_cards) == 10`
  - **期待結果の理由**: total_due_count はフィルタ後の全件数(15)、due_cards は limit(10)で制限される
- **テストの目的**: deck_id + limit の組み合わせでバグが発生していた箇所の修正を検証する
  - **確認ポイント**: total_due_count が limit(10)ではなくデッキ内全件数(15)を返すこと（現在のバグの直接検証）
- 🔵 **青信号**: 要件定義 パターン3 に直接対応。バグの根本原因（バグ2）の修正を検証

---

### TC-004: deck_id なし・limit >= 全件数で total_due_count が全件数と一致

- **テスト名**: limit が全件数以上の場合に total_due_count と due_cards の件数が一致
  - **何をテストするか**: `get_due_cards(limit=20)` で復習対象15件の場合、`total_due_count=15`, `due_cards=15件` を返すこと
  - **期待される動作**: limit 以下の件数なので全件返却され、total_due_count も同値
- **入力値**: `user_id="test-user-id"`, `limit=20`, `deck_id=None`, 復習対象カード15件を投入
  - **入力データの意味**: limit が十分大きい場合の正常動作を確認（従来動作との互換性）
- **期待される結果**: `response.total_due_count == 15`, `len(response.due_cards) == 15`
  - **期待結果の理由**: limit >= 全件数のため全件返却、total_due_count も全件数と一致
- **テストの目的**: limit が全件数以上の場合でも total_due_count が正確であることを確認
  - **確認ポイント**: 既存動作（deck_id なし）が壊れていないこと
- 🔵 **青信号**: 要件定義 パターン4 に直接対応

---

### TC-005: deck_id なし・limit < 全件数で card_service.get_due_cards に limit なしで全件取得

- **テスト名**: card_service.get_due_cards に limit が渡されず全件取得されることの確認
  - **何をテストするか**: `review_service.get_due_cards(limit=5)` 呼び出し時に、`card_service.get_due_cards()` が limit=5 ではなく全件取得するよう呼び出されること
  - **期待される動作**: card_service への呼び出しで limit 制限なし（または十分大きい値）が渡される
- **入力値**: `user_id="test-user-id"`, `limit=5`, `deck_id=None`, 復習対象カード10件を投入
  - **入力データの意味**: バグ1（card_service に limit が渡される問題）の修正を検証
- **期待される結果**: `response.total_due_count == 10`, `len(response.due_cards) == 5`
  - **期待結果の理由**: card_service が全件(10)を返し、total_due_count=10、返却カードのみ limit(5)で制限
- **テストの目的**: バグ1の修正を確認する。card_service への limit 伝播が解消されていること
  - **確認ポイント**: total_due_count が10であること（card_service レベルで5件に切り詰められていないこと）
- 🔵 **青信号**: 要件定義 セクション3 バグ1 の根本原因分析に直接対応

---

## 2. 異常系テストケース

### TC-006: 存在しない deck_id を指定した場合

- **テスト名**: 存在しないデッキIDを指定した場合に空レスポンスが返る
  - **エラーケースの概要**: `deck_id="non-existent"` を指定した場合、該当カードがなくても正常レスポンスを返す
  - **エラー処理の重要性**: フロントエンドがデッキ選択で不正な deck_id を送った場合でもクラッシュしない
- **入力値**: `user_id="test-user-id"`, `limit=10`, `deck_id="non-existent"`, 復習対象カード5件（別デッキ）を投入
  - **不正な理由**: データベースに存在しないデッキIDだが、アプリケーション層のフィルタリングで処理される
  - **実際の発生シナリオ**: デッキ削除後にキャッシュされた deck_id でリクエストされた場合
- **期待される結果**: `response.total_due_count == 0`, `len(response.due_cards) == 0`, エラーなし
  - **エラーメッセージの内容**: エラーは発生しない。空のレスポンスが返る
  - **システムの安全性**: 正常なレスポンスが返り、フロントエンドが安全に処理できる
- **テストの目的**: 存在しない deck_id でも例外が発生しないことを確認
  - **品質保証の観点**: deck_id フィルタの堅牢性を保証
- 🟡 **黄信号**: 要件定義 パターン6 から妥当な推測（エラーにならないことの確認）

---

### TC-007: 復習対象カードが0件の場合

- **テスト名**: 復習対象カードがない場合に total_due_count=0 と next_due_date が返る
  - **エラーケースの概要**: 復習対象カードがゼロの場合の正常動作確認
  - **エラー処理の重要性**: 学習完了状態でフロントエンドが「次の復習日」を表示するために必要
- **入力値**: `user_id="test-user-id"`, `limit=10`, `deck_id=None`, 未来日の復習カード1件を投入
  - **不正な理由**: 不正ではなく、復習完了時の正常状態
  - **実際の発生シナリオ**: ユーザーがすべてのカードの復習を完了した場合
- **期待される結果**: `response.total_due_count == 0`, `len(response.due_cards) == 0`, `response.next_due_date is not None`
  - **エラーメッセージの内容**: エラーではない。next_due_date に次回復習日が設定される
  - **システムの安全性**: 空リスト + 次回復習日の適切な返却
- **テストの目的**: 復習完了状態での total_due_count と next_due_date の正確性を確認
  - **品質保証の観点**: フロントエンドの「次の復習は X 日後」表示の正確性を保証
- 🔵 **青信号**: 要件定義 パターン7・既存テスト test_get_due_cards_empty に対応

---

## 3. 境界値テストケース

### TC-008: limit=0 の場合に total_due_count が正確な全件数を返す

- **テスト名**: limit=0 の場合にカード0件だが total_due_count は全件数を返す
  - **境界値の意味**: limit の最小値。カードは返さないが、カウントは正確であるべき
  - **境界値での動作保証**: limit=0 でも total_due_count の計算が正常に動作すること
- **入力値**: `user_id="test-user-id"`, `limit=0`, `deck_id=None`, 復習対象カード10件を投入
  - **境界値選択の根拠**: limit の下限値。`all_due_cards[:0]` は空リストだが、total_due_count は10であるべき
  - **実際の使用場面**: フロントエンドがカード件数のみ取得したい場合（プリフェッチ不要時）
- **期待される結果**: `response.total_due_count == 10`, `len(response.due_cards) == 0`
  - **境界での正確性**: total_due_count は limit=0 でも全件数(10)を返す
  - **一貫した動作**: limit=0 と limit>0 で total_due_count の計算ロジックが同一であること
- **テストの目的**: limit の下限境界値での total_due_count の正確性を確認
  - **堅牢性の確認**: limit=0 がスライス `[:0]` で正常処理されること
- 🟡 **黄信号**: 要件定義 パターン5 から妥当な推測

---

### TC-009: limit=1 の場合に total_due_count が正確な全件数を返す

- **テスト名**: limit=1（最小有効値）の場合に total_due_count が全件数を返す
  - **境界値の意味**: 1件だけ返却する最小有効 limit 値
  - **境界値での動作保証**: 最小件数返却時でも total_due_count が正確であること
- **入力値**: `user_id="test-user-id"`, `limit=1`, `deck_id=None`, 復習対象カード5件を投入
  - **境界値選択の根拠**: limit=0 の次の値。1件のカードを返しつつ total_due_count=5 であるべき
  - **実際の使用場面**: 1件ずつカードを表示するUIの場合
- **期待される結果**: `response.total_due_count == 5`, `len(response.due_cards) == 1`
  - **境界での正確性**: due_cards は1件のみ、total_due_count は全件数
  - **一貫した動作**: limit=1 でも total_due_count が正確であること
- **テストの目的**: limit 最小有効値での動作確認
  - **堅牢性の確認**: limit=1 とそれ以上で一貫した total_due_count 計算
- 🟡 **黄信号**: 要件定義から妥当な推測（明示的なパターンはないが boundary として重要）

---

### TC-010: deck_id フィルタで全カードが除外される場合

- **テスト名**: deck_id フィルタで該当カード0件の場合に total_due_count=0 を返す
  - **境界値の意味**: deck_id フィルタ後のカード数が0件となる境界
  - **境界値での動作保証**: フィルタ結果が空でもエラーにならないこと
- **入力値**: `user_id="test-user-id"`, `limit=10`, `deck_id="deck-empty"`, 全カードが `deck_id="deck-other"` で5件投入
  - **境界値選択の根拠**: deck_id フィルタ後の件数が0件となるケース
  - **実際の使用場面**: ユーザーが復習対象カードのないデッキを選択した場合
- **期待される結果**: `response.total_due_count == 0`, `len(response.due_cards) == 0`
  - **境界での正確性**: フィルタ後0件でも total_due_count=0 が正確に返される
  - **一貫した動作**: カードが存在するがフィルタで除外される場合と、カード自体が0件の場合で同じ動作
- **テストの目的**: deck_id フィルタ後の0件境界でのカウント正確性を確認
  - **堅牢性の確認**: フィルタ結果が空リストの場合の処理
- 🟡 **黄信号**: 要件定義パターン6 と組み合わせた妥当な推測

---

### TC-011: deck_id あり・limit < 全件数（card_service の limit バグ検証）

- **テスト名**: deck_id フィルタ時に card_service レベルの limit でカードが切り詰められないことを確認
  - **境界値の意味**: card_service に limit が渡されると deck_id フィルタ前にカードが切り詰められるバグの検証
  - **境界値での動作保証**: 全カード取得後に deck_id フィルタ → limit 適用の順序が正しいこと
- **入力値**: `user_id="test-user-id"`, `limit=5`, `deck_id="deck-B"`, デッキA内4件（due日が古い）+ デッキB内4件（due日が新しい）を投入
  - **境界値選択の根拠**: 旧実装では card_service に limit=5 が渡され、GSI ソート順で先頭5件（デッキA4件 + デッキB1件）が取得される。deck_id="deck-B" フィルタ後1件となり、本来の4件と大きく乖離する
  - **実際の使用場面**: 複数デッキに跨がるカードがある場合の一般的なケース
- **期待される結果**: `response.total_due_count == 4`, `len(response.due_cards) == 4`
  - **境界での正確性**: card_service が全件(8件)を取得し、deck_id フィルタ後4件、limit(5) >= 4件なので全件返却
  - **一貫した動作**: card_service への limit 非伝播により、deck_id フィルタ後の正確なカウントが得られること
- **テストの目的**: バグ1（card_service に limit が渡される）の修正を deck_id と組み合わせて検証
  - **堅牢性の確認**: card_service レベルの limit 切り詰めが発生しないこと
- 🔵 **青信号**: 要件定義 セクション3 バグ1 の根本原因分析に直接対応

---

### TC-012: 大量カード（limit=100 の上限値）での total_due_count 正確性

- **テスト名**: limit=100（API 上限）の場合に total_due_count が正確な全件数を返す
  - **境界値の意味**: API パラメータの上限値（limit max=100）
  - **境界値での動作保証**: 上限値でも total_due_count が正確に計算されること
- **入力値**: `user_id="test-user-id"`, `limit=100`, `deck_id=None`, 復習対象カード150件を投入（テスト実行時間に注意）
  - **境界値選択の根拠**: limit の API 上限値。全件(150) > limit(100) で total_due_count=150 であるべき
  - **実際の使用場面**: ユーザーが大量のカードを持っている場合
- **期待される結果**: `response.total_due_count == 150`, `len(response.due_cards) == 100`
  - **境界での正確性**: limit 上限値でも total_due_count は実際の全件数を返す
  - **一貫した動作**: limit の大小に関わらず total_due_count の計算が一貫していること
- **テストの目的**: limit 上限値での total_due_count 正確性とパフォーマンスの確認
  - **堅牢性の確認**: 大量カード時のスライス処理が正常に動作すること
- 🟡 **黄信号**: limit=100 は要件定義セクション2から。150件テストは妥当な推測

---

## 4. 開発言語・フレームワーク

- **プログラミング言語**: Python 3.12
  - **言語選択の理由**: 既存プロジェクトの言語。バックエンドは Python で統一されている
  - **テストに適した機能**: `datetime` / `timedelta` による日時操作、リスト内包表記
- **テストフレームワーク**: pytest + moto + boto3
  - **フレームワーク選択の理由**: 既存テスト (`backend/tests/unit/test_review_service.py`) と同一のフレームワーク・パターンを使用
  - **テスト実行環境**: `cd backend && pytest tests/unit/test_review_service.py -v`
  - **モック戦略**: `moto` の `mock_aws` で DynamoDB をインメモリモック。実際の AWS リソース不要
- 🔵 **青信号**: 既存テストファイルの実装パターンから確認済み

---

## 5. テストケース実装時の日本語コメント指針

各テストケースの実装時には以下のパターンで日本語コメントを含めること。

### テストケース開始時のコメント

```python
# 【テスト目的】: total_due_count が limit に影響されず正確な全件数を返すことを確認
# 【テスト内容】: 20件の復習対象カードに対して limit=10 で get_due_cards を呼び出す
# 【期待される動作】: total_due_count=20, len(due_cards)=10
# 🔵 REQ-005 受け入れ基準に直接対応
```

### Given（準備フェーズ）のコメント

```python
# 【テストデータ準備】: 復習対象カード20件を DynamoDB に投入（next_review_at を過去日に設定）
# 【初期条件設定】: 全カードの next_review_at を現在時刻より前に設定し、復習対象とする
# 【前提条件確認】: user_id="test-user-id" のカードのみ投入
```

### When（実行フェーズ）のコメント

```python
# 【実際の処理実行】: review_service.get_due_cards() を limit=10, deck_id=None で呼び出す
# 【処理内容】: card_service から全復習対象カードを取得し、total_due_count 計算後に limit 適用
```

### Then（検証フェーズ）のコメント

```python
# 【結果検証】: total_due_count が limit 前の全件数を返していること
# 【期待値確認】: total_due_count=20（全件数）, len(due_cards)=10（limit 適用後）
# 【品質保証】: REQ-005 の受け入れ基準を満たしていること
```

### 各 assert ステートメントのコメント

```python
# 【検証項目】: total_due_count が limit に影響されない全復習対象カード数であること
assert response.total_due_count == 20  # 【確認内容】: 全件数20が返されること（limit=10 に影響されない）
# 【検証項目】: 返却カード数が limit で制限されていること
assert len(response.due_cards) == 10  # 【確認内容】: limit=10 で返却カードが10件に制限されること
```

### セットアップ・クリーンアップのコメント

```python
@pytest.fixture
def dynamodb_tables():
    # 【テスト前準備】: moto で DynamoDB テーブルをインメモリ作成
    # 【環境初期化】: cards テーブルと reviews テーブルを user_id-due-index GSI 付きで作成
    with mock_aws():
        # ...
        yield dynamodb
    # 【テスト後処理】: mock_aws コンテキスト終了で自動クリーンアップ
```

---

## 6. 要件定義との対応関係

### 参照した機能概要

- 要件定義 セクション1「機能の概要」: `review_service.py` の `get_due_cards()` メソッドで返される `total_due_count` を limit パラメータに影響されない正確な総数に修正

### 参照した入力・出力仕様

- 要件定義 セクション2「入力・出力の仕様」: `GET /cards/due` の入力パラメータ（limit, deck_id, include_future）と出力（DueCardsResponse）の定義
- 要件定義 セクション2「入出力の関係性」: `total_due_count = len(全復習対象カード)` を limit 前にカウントするフロー

### 参照した制約条件

- 要件定義 セクション3「バグの根本原因分析」:
  - **バグ1**: `card_service.get_due_cards()` に limit が渡されている → TC-005, TC-011 で検証
  - **バグ2**: deck_id フィルタ時の total_due_count が limit 後のリスト長 → TC-003 で検証
- 要件定義 セクション3「アーキテクチャ制約」: 修正は `review_service.py` 内に限定

### 参照した使用例

- 要件定義 セクション4「想定される使用例」: パターン1〜8 を TC-001〜TC-012 にマッピング
  - パターン1 → TC-001
  - パターン2 → TC-002
  - パターン3 → TC-003
  - パターン4 → TC-004
  - パターン5 → TC-008
  - パターン6 → TC-006, TC-010
  - パターン7 → TC-007
  - パターン8 → (本タスクスコープ外: DynamoDB エラーハンドリングは既存テストで対応済み)

---

## テストケースサマリー

| ID | 分類 | テスト名 | 信頼性 |
|----|------|---------|--------|
| TC-001 | 正常系 | deck_id なし・limit < 全件数 | 🔵 |
| TC-002 | 正常系 | deck_id あり・limit > デッキ内カード数 | 🔵 |
| TC-003 | 正常系 | deck_id あり・limit < デッキ内カード数 | 🔵 |
| TC-004 | 正常系 | deck_id なし・limit >= 全件数 | 🔵 |
| TC-005 | 正常系 | card_service に limit なしで全件取得 | 🔵 |
| TC-006 | 異常系 | 存在しない deck_id | 🟡 |
| TC-007 | 異常系 | 復習対象カード0件 | 🔵 |
| TC-008 | 境界値 | limit=0 | 🟡 |
| TC-009 | 境界値 | limit=1 | 🟡 |
| TC-010 | 境界値 | deck_id フィルタで全カード除外 | 🟡 |
| TC-011 | 境界値 | deck_id + limit でバグ1検証 | 🔵 |
| TC-012 | 境界値 | limit=100 上限値 | 🟡 |

---

## 信頼性レベルサマリー

- **総項目数**: 12テストケース
- 🔵 **青信号**: 7項目 (58%) - 要件定義・既存実装から直接導出
- 🟡 **黄信号**: 5項目 (42%) - 要件定義から妥当な推測
- 🔴 **赤信号**: 0項目 (0%)

**品質評価**: ✅ 高品質
