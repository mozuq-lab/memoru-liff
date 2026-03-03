# カード AI 補足機能 レビュー修正 要件定義書（軽量版）

## 概要

`feature/card-back-ai-assist-spec` ブランチのコードレビュー（Claude Opus 4.6 + Codex）で発見された指摘事項を修正する。P1（High）2件 + P2（Low）1件 + テスト不足の修正を対象とする。P3（Bedrock system prompt 分離）はスコープ外。

## 関連文書

- **コードレビュー**: [📋 card-back-ai-assist-review.md](../../review/card-back-ai-assist-review.md)
- **ヒアリング記録**: [💬 interview-record.md](interview-record.md)
- **元要件定義書**: [📝 card-back-ai-assist/requirements.md](../card-back-ai-assist/requirements.md)
- **コンテキストノート**: [📝 card-back-ai-assist/note.md](../card-back-ai-assist/note.md)

## 主要機能要件

**【信頼性レベル凡例】**:
- 🔵 **青信号**: コードレビュー・既存実装・Codex 検証を参考にした確実な要件
- 🟡 **黄信号**: コードレビューの推奨対応から妥当な推測による要件
- 🔴 **赤信号**: コードレビューにない推測による要件

### 必須修正（Must Have）

- REQ-FIX-001: `get_refine_user_prompt()` は `language` パラメータに応じて日本語/英語のプロンプトテンプレートを切り替えなければならない 🔵 *レビュー指摘#1 [High]、既存 `generate.py` の ja/en 分岐パターンに準拠*
- REQ-FIX-002: `REFINE_SYSTEM_PROMPT` は `language` パラメータに応じて日本語/英語のシステムプロンプトを切り替えるか、または `LANGUAGE_INSTRUCTION` を付加しなければならない 🟡 *既存 `grading.py`/`advice.py` が `LANGUAGE_INSTRUCTION` を使用する実装パターンから妥当な推測*
- REQ-FIX-003: `POST /cards/refine` ハンドラーは、リクエストボディが JSON オブジェクト（dict）でない場合（`null`、配列、数値等）に 400 エラーを返さなければならない 🔵 *レビュー指摘#2 [High]、Codex 検証で Powertools v3.23.0 の `json_body` が `None` を返すケースを確認済み*
- REQ-FIX-004: `POST /cards/generate` ハンドラーも同様に、リクエストボディが JSON オブジェクトでない場合に 400 エラーを返さなければならない 🔵 *レビュー指摘#2 補足、同一パターンの既知問題として同時修正*
- REQ-FIX-005: `CardForm` コンポーネントは、アンマウント時に進行中の AI 補足リクエストをキャンセル（`AbortController.abort()`）しなければならない 🔵 *レビュー指摘#4 [Low]、React ベストプラクティスとして Codex と合意済み*

### テスト追加要件（Must Have）

- REQ-TEST-001: `refine` プロンプトの `language="en"` テストケースを追加しなければならない 🔵 *REQ-FIX-001 の修正に対応するテスト*
- REQ-TEST-002: `POST /cards/refine` ハンドラーの `body=null` / 配列ボディテストケースを追加しなければならない 🔵 *REQ-FIX-003 の修正に対応するテスト*
- REQ-TEST-003: `POST /cards/generate` ハンドラーの `body=null` テストケースを追加しなければならない 🔵 *REQ-FIX-004 の修正に対応するテスト*
- REQ-TEST-004: `BedrockService.refine_card()` の正常系・異常系テストを追加しなければならない 🔵 *レビュー指摘#6、既存 `test_strands_refine.py` と対称的なテストカバレッジ*
- REQ-TEST-005: `CardForm` のアンマウント時通信キャンセルテストを追加しなければならない 🟡 *REQ-FIX-005 の修正に対応するテスト、React Testing Library のアンマウント検証パターンから妥当な推測*

### スコープ外

- **P3: Bedrock system prompt 分離**: `_invoke_claude()` の `system_prompt` 引数対応は、既存メソッド全体への影響が大きいため今回のスコープ外とする
- **P4: プロンプトインジェクション対策**: ユーザー自身のデータのリファインであり横断的リスクが限定的なため今回のスコープ外とする

### 基本的な制約

- REQ-FIX-401: 修正は `feature/card-back-ai-assist-spec` ブランチ上で行い、既存テストを壊さないこと 🔵 *開発ルールより*
- REQ-FIX-402: 英語プロンプトの実装は、既存の `generate.py`（テンプレート分岐）および `_types.py`（`LANGUAGE_INSTRUCTION`）のパターンに従うこと 🔵 *既存コードベースの一貫性維持*
- REQ-FIX-403: `body` 型チェックは `refine` と `generate` の両ハンドラーに共通パターンで適用すること 🔵 *レビュー指摘#2 補足*

## 簡易ユーザーストーリー

### ストーリー 1: 英語カードの AI 補足

**私は** 英語学習者 **として**
**`language="en"` を指定して AI 補足を実行した際、英語のプロンプトで処理されるようにしたい**
**そうすることで** 英語のカードに対して適切な英語での補足が得られる

**関連要件**: REQ-FIX-001, REQ-FIX-002

### ストーリー 2: 不正リクエストの堅牢なハンドリング

**私は** システム運用者 **として**
**不正なリクエストボディ（null、配列等）が送信された場合に 400 エラーが返されるようにしたい**
**そうすることで** 5xx エラーの発生を防ぎ、API の堅牢性を維持できる

**関連要件**: REQ-FIX-003, REQ-FIX-004

## 基本的な受け入れ基準

### REQ-FIX-001: language パラメータ対応

**Given**: `get_refine_user_prompt(front="closure", back="a function that remembers variables", language="en")` が呼ばれた
**When**: プロンプトが生成される
**Then**: 英語のプロンプトテンプレートが返される（"Improve the following flashcard" 等の英語テキスト）

**テストケース**:
- [ ] 正常系: `language="ja"` で日本語プロンプトが生成される
- [ ] 正常系: `language="en"` で英語プロンプトが生成される
- [ ] 正常系: `language="en"` + front_only で英語の front-only プロンプト
- [ ] 正常系: `language="en"` + back_only で英語の back-only プロンプト

### REQ-FIX-003: body=null 対策

**Given**: `POST /cards/refine` に `body: "null"` が送信された
**When**: ハンドラーがリクエストを処理する
**Then**: 400 エラー（`{"error": "Invalid request"}` 等）が返される

**テストケース**:
- [ ] 異常系: `body=null` → 400
- [ ] 異常系: `body=[1,2,3]`（配列）→ 400
- [ ] 異常系: `body="string"` → 400
- [ ] 正常系: `body={"front": "...", "back": "..."}` → 200（既存テストで確認済み）

### REQ-FIX-005: useEffect cleanup

**Given**: CardForm で AI 補足リクエストが進行中
**When**: コンポーネントがアンマウントされる
**Then**: 進行中のリクエストがキャンセルされる

**テストケース**:
- [ ] 正常系: アンマウント時に AbortController.abort() が呼ばれる

## 最小限の非機能要件

- **後方互換性**: `language="ja"`（デフォルト値）での動作は既存実装と同一であること 🔵 *既存テストの継続パスで保証*
- **テストカバレッジ**: 追加テストにより、レビュー指摘の不足テスト 5カテゴリすべてをカバーすること 🔵 *レビュー指摘#6 対応*

## 信頼性レベルサマリー

- **総項目数**: 15 項目（要件 10 + 制約 3 + 非機能 2）
- 🔵 **青信号**: 13 項目 (87%)
- 🟡 **黄信号**: 2 項目 (13%)
- 🔴 **赤信号**: 0 項目 (0%)

**品質評価**: ✅ 高品質 — コードレビュー結果と Codex 検証に基づく確実な要件が大半
