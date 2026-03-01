# code-quality-improvements 要件定義書（軽量版）

## 概要

コミット d3a30fe〜0f1df22 間のコードレビュー（Claude Opus 4.6 + OpenAI Codex）で発見された
Critical + High + Medium の計17件の指摘事項に対する改善要件を定義する。

## 関連文書

- **ヒアリング記録**: [interview-record.md](interview-record.md)
- **コンテキストノート**: [note.md](note.md)
- **コードレビュー結果**: [../../reviews/code-review-d3a30fe-to-0f1df22.md](../../reviews/code-review-d3a30fe-to-0f1df22.md)

## 主要機能要件

**【信頼性レベル凡例】**:

- 🔵 **青信号**: コードレビュー結果・ユーザヒアリングを参考にした確実な要件
- 🟡 **黄信号**: コードレビュー結果から妥当な推測による要件
- 🔴 **赤信号**: コードレビュー結果にない推測による要件

### 必須機能（Must Have） - セキュリティ・バグ修正

- REQ-001: `handler.py` の `_get_user_id_from_event` と `shared.py` の `get_user_id_from_context` の JWT dev フォールバックロジックを `shared.py` に統一し、二重実装を解消しなければならない 🔵 *CR-01: 両レビュアー一致*

- REQ-002: JWT dev フォールバック発動時に `logger.warning` で警告ログを出力しなければならない 🔵 *CR-01: 両レビュアー一致 + ヒアリング Q3*

- REQ-003: JWT dev フォールバックの有効化条件を `ENVIRONMENT=dev` 単独ではなく、`AWS_SAM_LOCAL` 環境変数との組み合わせで強化しなければならない 🔵 *CR-01: ヒアリング Q3 で確定*

- REQ-004: `strands_service.py` の `grade_answer` メソッドで `Agent` 初期化時に `GRADING_SYSTEM_PROMPT` を `system_prompt` として設定しなければならない 🔵 *H-06: Claude 指摘（機能バグ）*

- REQ-005: `strands_service.py` の `generate_cards` メソッドで `Agent` 初期化時に適切なシステムプロンプトを `system_prompt` として設定しなければならない 🔵 *H-06: Claude 指摘（機能バグ）*

- REQ-006: `ReviewPage.tsx` のレンダー関数内の `setState` 呼び出し（`setRegradeCardIndex`, `setIsComplete`）を `useEffect` に移動しなければならない 🔵 *M-02: 両レビュアー一致*

### 必須機能（Must Have） - データ整合性

- REQ-007: `card_service.get_due_cards` メソッドで `limit=None` 時に DynamoDB の `LastEvaluatedKey` によるページネーションループを実装し、1MB 上限を超えるカード数でもデータ欠落なく全件取得できなければならない 🔵 *H-01: 両レビュアー一致*

- REQ-008: `card_service.delete_card` 内のレビュー削除処理で `LastEvaluatedKey` によるページネーションループを実装し、全レビューを確実に削除しなければならない 🔵 *M-03: 両レビュアー一致*

- REQ-009: `review_service._get_next_due_date` の `KeyConditionExpression` に `next_review_at > :now` 条件を追加し、将来日のカードのみを取得しなければならない 🔵 *M-06: ヒアリング Q4 で確定*

### 必須機能（Must Have） - コード品質

- REQ-010: `strands_service.py` の 3 メソッド（`generate_cards`, `grade_answer`, `get_learning_advice`）で重複する例外ハンドリングロジックを共通のコンテキストマネージャまたはヘルパーメソッドに抽出しなければならない 🔵 *H-03: Claude 指摘*

- REQ-011: `review_service._record_review` の `except ClientError: pass` を `logger.warning(...)` に変更し、エラーを記録しなければならない。同様に `card_service.delete_card` のレビュー削除の `except Exception: pass` も同等の対応をしなければならない 🔵 *H-05: 両レビュアー一致*

- REQ-012: `handler.py` と `shared.py` の f-string によるロガー呼び出しを Lambda Powertools の構造化ログ形式（`extra={}` パラメータ）に移行しなければならない 🔵 *H-04: Claude 指摘*

- REQ-013: `bedrock.py` の `GeneratedCard` と `GenerationResult` の重複データクラス定義を削除し、`ai_service.py` からの import に統一しなければならない 🔵 *M-05: Claude 指摘*

### Should Have - ロバストネス強化

- REQ-014: `api.ts` の 401 リフレッシュ処理で、再試行フラグを導入して再帰呼び出しを最大 1 回に制限しなければならない 🔵 *M-01: 両レビュアー一致*

- REQ-015: `review_service.py` の `_update_card_review_data` と `undo_review` での `review_history` 更新で DynamoDB の `list_append` を活用するか、`ConditionExpression` による楽観的ロックを実装して、並行リクエスト時のロストアップデートを防止しなければならない 🔵 *H-02: 両レビュアー一致*

- REQ-016: `user_service.link_line` の check-then-update を `ConditionExpression` または `TransactWriteItems` で原子的に更新し、同一 LINE ID の重複紐づけを防止しなければならない 🔵 *M-08: Codex 指摘*

### Should Have - 仕様明文化・型改善

- REQ-017: `undo_review` の実装コメントに「Undo は cards_table の SRS パラメータ（ease_factor, interval, repetitions, next_review_at, review_history）のみ復元し、reviews_table のレコードは削除しない（学習統計の累積を維持する設計意図）」と明文化しなければならない 🔵 *H-08: ヒアリング Q2 で確定*

### 基本的な制約

- REQ-401: 全ての変更はテストカバレッジ 80% 以上を維持しなければならない 🔵 *CLAUDE.md より*

- REQ-402: 既存の API レスポンス形式を変更してはならない（後方互換性維持） 🔵 *既存要件より*

- REQ-403: `handler.py` のスタンドアロン Lambda ハンドラー（`grade_ai_handler`, `advice_handler`）の外部インターフェースは変更してはならない 🔵 *既存実装の互換性より*

## 簡易ユーザーストーリー

### ストーリー1: セキュリティ強化

**私は** インフラ担当者 **として**
**JWT dev フォールバックが安全に管理されることを確認したい**
**そうすることで** 環境変数の誤設定による本番環境での認証バイパスを防止できる

**関連要件**: REQ-001, REQ-002, REQ-003

### ストーリー2: AI 採点品質改善

**私は** 学習者 **として**
**AI 採点・カード生成の品質が向上することを期待する**
**そうすることで** より正確な採点と質の高いフラッシュカードを得られる

**関連要件**: REQ-004, REQ-005

### ストーリー3: データ整合性保証

**私は** ヘビーユーザー **として**
**大量のカード（数百枚以上）を持つ場合でもデータ欠落なく復習できることを期待する**
**そうすることで** 復習漏れや統計の誤表示を心配せずに学習に集中できる

**関連要件**: REQ-007, REQ-008, REQ-009, REQ-015

### ストーリー4: コードベース保守性向上

**私は** 開発者 **として**
**重複コードの削減と適切なログ出力を通じてコードの保守性を向上させたい**
**そうすることで** バグ修正・機能追加がスムーズに行えるようになる

**関連要件**: REQ-010, REQ-011, REQ-012, REQ-013

## 基本的な受け入れ基準

### REQ-001: JWT フォールバック二重実装統合

**Given**: `handler.py` と `shared.py` に同一の JWT dev フォールバックロジックが存在する
**When**: JWT dev フォールバックの実装を変更する
**Then**: `shared.py` の実装のみが残り、`handler.py` はそれを呼び出す形になる

**テストケース**:

- [ ] 正常系: dev 環境で JWT フォールバックが正しく動作する
- [ ] 正常系: 非 dev 環境で JWT フォールバックが無効である
- [ ] 異常系: `AWS_SAM_LOCAL` が未設定の dev 環境ではフォールバックが無効である

### REQ-007: get_due_cards ページネーション

**Given**: ユーザーが DynamoDB 1MB を超える量の復習対象カードを持つ
**When**: `get_due_cards(limit=None)` を呼び出す
**Then**: 全カードが `LastEvaluatedKey` ループで取得され、`total_due_count` が正確な値を返す

**テストケース**:

- [ ] 正常系: ページネーションなし（1ページで全件取得）で正常動作
- [ ] 正常系: ページネーションあり（複数ページ）で全件取得
- [ ] 正常系: `limit` 指定時はページネーションなしで従来通り動作

### REQ-010: 例外ハンドリング共通化

**Given**: `strands_service.py` の 3 メソッドに同一の例外ハンドリングが存在する
**When**: 例外ハンドリングを共通化する
**Then**: 各メソッドの例外ハンドリング動作が変わらず、コード重複が解消される

**テストケース**:

- [ ] 正常系: 各メソッドの例外マッピングが共通化前と同一の結果を返す
- [ ] 異常系: TimeoutError → AITimeoutError のマッピングが正しい
- [ ] 異常系: ConnectionError → AIProviderError のマッピングが正しい
- [ ] 異常系: RateLimitError → AIRateLimitError のマッピングが正しい

## 最小限の非機能要件

- **パフォーマンス**: `get_due_cards` のページネーション追加後も API レスポンスが現状と同等のレイテンシを維持する 🔵

- **セキュリティ**: JWT dev フォールバックが本番環境で絶対に有効化されない保証 🔵

- **保守性**: `strands_service.py` の例外ハンドリング重複解消後、新メソッド追加時に同一ロジックのコピペが不要になる 🔵

- **可観測性**: 構造化ログ移行後、CloudWatch Logs Insights で `card_id`, `user_id` 等のフィールドで検索可能になる 🔵
