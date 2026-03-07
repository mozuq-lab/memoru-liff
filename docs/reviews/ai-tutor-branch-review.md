# AI Tutor Feature Branch Review

**Branch:** `claude/add-ai-tutor-feature`
**Base:** `main`
**Date:** 2026-03-07
**Reviewers:** Claude (Opus 4.6), OpenAI Codex

---

## Summary

AI チューター機能の全実装（バックエンド API、フロントエンド UI、DynamoDB テーブル、テスト）を含む大規模な変更（42 files, +5,549 lines）。全体的な設計は妥当だが、セッションライフサイクル管理とフロントエンド状態遷移に重大な問題がいくつかある。

---

## Critical Issues

### C-1: セッション開始失敗時に既存セッションが消失する

**ファイル:** `backend/src/services/tutor_service.py:109-142`
**発見者:** Claude, Codex (一致)

`start_session()` は最初に `_auto_end_active_sessions()` を呼び出し、その後でデッキ存在確認・空デッキ判定・レビュー履歴判定・AI greeting 呼び出しを行う。これにより以下のシナリオで既存のアクティブセッションが不可逆的に終了する:

- `deck_id` の typo → `TutorServiceError` → 500
- 空デッキ → `EmptyDeckError` → 422
- `weak_point` モードでレビュー履歴不足 → `InsufficientReviewDataError` → 422
- Bedrock タイムアウト → `TutorAITimeoutError` → 504

**修正案:** バリデーションと AI greeting をすべて完了してから `_auto_end_active_sessions()` を呼ぶ。もしくはトランザクション的に扱い、失敗時にロールバックする。

### C-2: モード切り替え（handleModeSwitch）が機能しない

**ファイル:** `frontend/src/pages/TutorPage.tsx:79, 56-59`
**発見者:** Codex

`handleModeSwitch()` は `view` を `"mode-select"` にセットするが、`useEffect` (L56-59) が `session` が残っている限り即座に `view` を `"chat"` に戻す。結果として:

- メッセージ上限到達後の「新しいセッションを開始する」ボタンが動かない
- タイムアウト後の再開ができない
- チャットヘッダーの「モード選択に戻る」が効かない

**修正案:** `handleModeSwitch` 時に `session` を `null` にクリアするか、`useEffect` の条件に `resumeChecked` 状態を加えて初回マウント時のみ自動遷移する。

---

## High Issues

### H-1: タイムアウト状態の不整合

**ファイル:** `backend/src/services/tutor_service.py:215, 355, 456`
**発見者:** Claude, Codex (一致)

タイムアウト検出は `send_message()` 内でのみ行われる。`list_sessions()` と `get_session()` は期限切れセッションでも `"active"` を返し続ける。また `_auto_end_active_sessions()` はタイムアウトしたセッションを `"timed_out"` ではなく `"ended"` にマークする。

フロントエンド (`TutorContext.tsx:195`) は独自に `updated_at` を見てタイムアウトを補正しているが、バックエンド状態と一貫しない。

**修正案:** `get_session()` と `list_sessions()` でもタイムアウトチェックを実施し、タイムアウトしたセッションは `"timed_out"` ステータスに更新する。

### H-2: HTTP ステータスコードが API 契約と不一致

**ファイル:** `backend/src/api/handlers/tutor_handler.py:85-117`, `backend/src/services/tutor_service.py:485`
**発見者:** Codex

| シナリオ | 実装 | 契約 (tutor-api.md) |
|---|---|---|
| 存在しないデッキ | 500 (`TutorServiceError`) | 404 |
| メッセージ上限到達 | 409 (`SessionEndedError`) | 429 (独自エラー) |

`_get_deck()` は `TutorServiceError` を発生させるが、ハンドラーはこれを 500 として処理する。`MessageLimitError` は定義されているが使われていない。

**修正案:** デッキ未発見用に `DeckNotFoundError` を追加し 404 を返す。メッセージ上限は `MessageLimitError` を使い、適切な HTTP ステータスを返す。

---

## Medium Issues

### M-1: カード取得のパフォーマンス問題

**ファイル:** `backend/src/services/tutor_service.py:499-507`
**発見者:** Claude, Codex (一致)

`_get_deck_cards()` は `CardsTable` を `user_id` でクエリし、`deck_id` を `FilterExpression` でフィルタする。CardsTable のキースキーマは `user_id/card_id` であるため、ユーザーの全カードをスキャンしてから後段フィルタとなる。ユーザーのカード総数が多いほどコストとレイテンシが増大する。

**修正案:** `deck_id` を含む GSI（既存の `user_id-deck_id-index` 等）を活用してクエリする。

### M-2: IAM ポリシーが TUTOR_MODEL_ID をカバーしていない

**ファイル:** `backend/template.yaml:349-357`
**発見者:** Codex

`TutorModelId` パラメータで独自モデルを設定できるが、IAM ポリシーは `BedrockModelId` のみを許可している。`TutorModelId` を別の inference profile にした場合、`AccessDenied` エラーになる。

**修正案:** IAM ポリシーの `Resource` に `TutorModelId` 用の ARN も追加する。

### M-3: SessionListResponse の `total` フィールド不整合

**ファイル:** `backend/src/api/handlers/tutor_handler.py:192`, `backend/src/models/tutor.py:53`, `frontend/src/types/tutor.ts:44`
**発見者:** Codex

ハンドラーは `SessionListResponse(sessions=..., total=len(sessions))` と `total` を渡しているが、`SessionListResponse` モデルには `total` フィールドが定義されていない。Pydantic v2 のデフォルト設定では未知のフィールドは無視される。OpenAPI 契約では `total` は required。

**修正案:** `SessionListResponse` に `total: int` フィールドを追加するか、ハンドラーから `total` を削除して契約を合わせる。

### M-4: related_cards のバリデーション不足

**ファイル:** `backend/src/services/tutor_ai_service.py:100`, `frontend/src/components/tutor/RelatedCardChip.tsx:13`
**発見者:** Claude, Codex (一致)

AI レスポンスから正規表現で抽出した card ID をそのまま保存・表示する。以下のリスクがある:

- AI がハルシネーションした存在しない ID を返す → フロントが各 ID ごとに `getCard()` API コールを行い、404 エラーが大量発生
- デッキ外のカード ID が混入する可能性
- 過剰な API fan-out（card ID が多数の場合）

**修正案:** `send_message()` 内でデッキのカード ID ホワイトリストと照合し、存在しない ID をフィルタアウトする。フロントエンドでも件数上限を設ける。

### M-5: system_prompt を DynamoDB に保存するサイズ懸念

**ファイル:** `backend/src/services/tutor_service.py:170`
**発見者:** Claude

セッション開始時に `system_prompt` を DynamoDB アイテムに保存している。大規模デッキ（100 枚以上）の場合、`MAX_SYSTEM_PROMPT_CHARS = 150,000` の切り詰めがあるとはいえ、会話履歴（`messages`）と合わせると DynamoDB の 400KB アイテムサイズ制限に近づく可能性がある。

**修正案:** `system_prompt` は保存せず、メッセージ送信時に再生成するか、S3 に保存してキーのみ DynamoDB に持つ。

### M-6: フォーマッター変更による差分ノイズ

**ファイル:** `frontend/src/services/api.ts`, `frontend/src/__tests__/App.test.tsx` 他多数
**発見者:** Claude

既存ファイルのシングルクォートをダブルクォートに一括変換している。機能変更とフォーマット変更が同一コミットに混在し、レビュー難易度が上がっている。

**推奨:** フォーマット変更は独立したコミットに分離する。

---

## Low Issues

### L-1: SessionList の ChatMessage key に index を使用

**ファイル:** `frontend/src/components/tutor/SessionList.tsx:101`

`messages.map((msg, i) => <ChatMessage key={i} message={msg} />)` で `key` にインデックスを使用。履歴表示（読み取り専用）のため実害は小さいが、ベストプラクティスとしてはユニークな ID を使うべき。

### L-2: TutorPage でも同様に key={idx}

**ファイル:** `frontend/src/pages/TutorPage.tsx:152`

チャットビューのメッセージ一覧でも `key={idx}` を使用。メッセージの追加は末尾のみなので動作上の問題は少ないが、optimistic update のロールバック時にリスクがある。

### L-3: LearningMode 型の重複定義

**ファイル:** `backend/src/models/tutor.py:59`, `backend/src/services/prompts/tutor.py:10`

`LearningMode` が 2 箇所で定義されている。一方に統一すべき。

### L-4: SessionList のエラーハンドリングが空

**ファイル:** `frontend/src/components/tutor/SessionList.tsx:73-75`

`listSessions` の catch ブロックで `// ignore` としてエラーを握り潰している。ユーザーにフィードバックがない。

---

## Test Coverage Assessment

### バックエンド

テストは主要パスをカバーしているが、以下が不足:

- `start_session` が失敗した際に既存セッションが壊れないこと（C-1 の検証）
- `list_sessions` / `get_session` でのタイムアウト反映（H-1 の検証）
- デッキ未発見時の適切なエラーレスポンス
- `MessageLimitError` の使用
- 大規模デッキでのコンテキスト切り詰め境界値テスト
- Bedrock API の各種エラーコードに対するハンドリング

### フロントエンド

- `TutorPage` のテストがない（モード切替、履歴表示、上限到達 UI、タイムアウト UI が未検証）
- `SessionList` のテストがない
- `RelatedCardChip` のテストがない
- `TutorContext` のテストは基本パスのみで、エラー回復・タイムアウト・リトライが未検証

---

## Security Assessment

- **XSS:** `ChatMessage` はプレーンテキスト描画（`{message.content}`）であり、`dangerouslySetInnerHTML` は使われていない。問題なし。
- **認証・認可:** セッション取得は `user_id + session_id` の複合キーで引いており、他ユーザーのセッションにアクセスする経路はない。
- **インジェクション:** Pydantic バリデーション + DynamoDB SDK の自動エスケープにより、SQL/NoSQL インジェクションのリスクは低い。
- **Prompt Injection:** ユーザー入力がシステムプロンプトに直接注入されることはない（`messages` 配列内にのみ含まれる）。ただし `RELATED_CARDS` タグの改ざんリスクは M-4 で指摘済み。
- **API URL パスインジェクション:** `sendTutorMessage` で `encodeURIComponent(sessionId)` を使用しており、適切。

---

## Positive Observations

- Pydantic モデルによる型安全な API 設計
- モード別のプロンプトテンプレート設計が明確で拡張しやすい
- オプティミスティック更新 + ロールバックのメッセージ送信 UX
- TTL による自動クリーンアップ
- DynamoDB テーブルの KMS 暗号化と PITR 有効化
- `encodeURIComponent` によるパスパラメータの安全なエンコード
- セッション ID に `tutor_` プレフィックスを付与しており識別しやすい

---

## Recommended Action Items (Priority Order)

1. **[C-1]** `_auto_end_active_sessions()` の呼び出し順序を修正
2. **[C-2]** `handleModeSwitch` の `useEffect` 競合を解消
3. **[H-1]** タイムアウト検出を `get_session` / `list_sessions` にも実装
4. **[H-2]** HTTP ステータスコードを API 契約に合わせる
5. **[M-4]** `related_cards` のホワイトリストバリデーション追加
6. **[M-1]** GSI を使ったカード取得の最適化
7. **[M-2]** IAM ポリシーに `TutorModelId` を追加
8. **[M-3]** `SessionListResponse.total` の整合性修正
9. フロントエンドテスト（TutorPage, SessionList, RelatedCardChip）の追加
