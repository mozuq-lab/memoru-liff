# コードレビュー: feature/card-back-ai-assist-spec

**レビュー日**: 2026-03-03
**レビュアー**: Claude Opus 4.6 + OpenAI Codex (MCP経由)
**対象ブランチ**: `feature/card-back-ai-assist-spec` (6 commits, main比 +2626/-13 lines)

---

## 概要

フラッシュカードアプリ「Memoru LIFF」に「AI で補足」機能を追加。ユーザーがカード編集フォームで「AI で補足」ボタンを押すと、AI がカードの表面（問題文）と裏面（解答）を改善する。

### 変更スコープ
| レイヤー | ファイル | 内容 |
|---------|--------|------|
| API | `ai_handler.py` | `POST /cards/refine` エンドポイント追加 |
| Model | `generate.py` | `RefineCardRequest/Response` Pydantic モデル |
| Service | `ai_service.py` | `RefineResult` データクラス、Protocol に `refine_card` 追加 |
| Service | `bedrock.py` | `BedrockService.refine_card()` 実装 |
| Service | `strands_service.py` | `StrandsAIService.refine_card()` 実装 |
| Prompt | `prompts/refine.py` | リファインプロンプト（新規） |
| Prompt | `prompts/__init__.py` | エクスポート追加 |
| Frontend | `CardForm.tsx` | AI 補足ボタン・UI 追加 |
| Frontend | `api.ts` | `refineCard` API クライアント追加 |
| Frontend | `card.ts` | `RefineCardRequest/Response` 型追加 |
| Test | 5ファイル | バックエンド4 + フロントエンド1 |

---

## 総合評価

全体的に既存のコードパターン（generate_cards, grade_answer 等）に良く倣った実装であり、テストカバレッジも十分。以下に指摘事項を重大度順に記載する。

---

## 指摘事項

### 1. [High] `language` パラメータが未実装

**ファイル**: `backend/src/services/prompts/refine.py:31`

**内容**: `get_refine_user_prompt()` は `language` パラメータを受け取るが、プロンプトテンプレートは常に日本語固定。他のプロンプトモジュール（`generate.py`, `grading.py`, `advice.py`）は `language` に応じて ja/en を切り替えている。

```python
# refine.py:31 - language を受け取るが未使用
def get_refine_user_prompt(front: str, back: str, language: Language = "ja") -> str:
    # ... 常に日本語テンプレートを返す
```

**影響**: API 契約（`language: "ja" | "en"`）と実装が不一致。`language="en"` を指定しても日本語プロンプトで処理される。

**推奨対応**: `_types.py` の `LANGUAGE_INSTRUCTION` を活用し、`generate.py` と同様に ja/en 分岐テンプレートを実装する。

**Codex との議論結果**: 両者とも High で一致。型定義上 `en` を受け付ける以上、実装の整合性は必須。

---

### 2. [High] `body=null` 送信時の TypeError 未捕捉

**ファイル**: `backend/src/api/handlers/ai_handler.py:99-100`

**内容**: `router.current_event.json_body` は、リクエストボディが `"null"` の場合 `json.loads("null")` → `None` を返す（Powertools v3.23.0 確認済み）。`RefineCardRequest(**None)` で `TypeError` が発生し、5xx レスポンスになる。

```python
body = router.current_event.json_body  # body が None になりうる
request = RefineCardRequest(**body)     # TypeError: argument after ** must be a mapping
```

**影響**: 不正入力で 400 ではなく 500 が返る。

**補足**: 同じパターンは既存の `generate_cards` ハンドラー（38行目）にも存在する既知の問題。修正する場合は両方同時に対応するのが望ましい。

**推奨対応**:
```python
try:
    body = router.current_event.json_body
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object")
    request = RefineCardRequest(**body)
except (ValidationError, ValueError, TypeError) as e:
    # 400 レスポンス
```

**Codex との議論結果**: Codex が発見。Powertools のソースコード確認で `json_body` が `None` を返すケースを検証済み。

---

### 3. [Medium-Low] BedrockService での system/user プロンプト結合

**ファイル**: `backend/src/services/bedrock.py:277`

**内容**: `refine_card()` で `REFINE_SYSTEM_PROMPT` と `user_prompt` を文字列結合して単一の user メッセージとして送信している。一方、`StrandsAIService` は `Agent(system_prompt=...)` で適切に分離。

```python
# bedrock.py:277 - 文字列結合
prompt = f"{REFINE_SYSTEM_PROMPT}\n\n{user_prompt}"
response_text = self._invoke_with_retry(prompt)

# strands_service.py:440 - 適切に分離
agent = Agent(model=self.model, system_prompt=REFINE_SYSTEM_PROMPT)
response = agent(user_prompt)
```

**影響**: 即座に壊れるバグではないが、Bedrock Converse API のベストプラクティス（`system` パラメータの使用）から外れており、プロバイダー間の動作一貫性が低下する。

**推奨対応**: `_invoke_claude()` を `system_prompt` 引数に対応させ、Messages API の `system` フィールドを使用する。ただし既存の `generate_cards` / `grade_answer` / `get_learning_advice` も同じ設計のため、将来のリファクタ課題として扱ってよい。

**Codex との議論結果**: 深刻度 Medium-Low で合意。現状動作するが、将来的なリファクタ候補。

---

### 4. [Low] フロントエンド: アンマウント時の AbortController クリーンアップ

**ファイル**: `frontend/src/components/CardForm.tsx:33, 55`

**内容**: `AbortController` は `handleRefine` 内で管理されているが、コンポーネントのアンマウント時に `abort()` を呼ぶ `useEffect` クリーンアップがない。

```tsx
// 現状: アンマウント時のクリーンアップなし
const abortControllerRef = useRef<AbortController | null>(null);
```

**影響**: 画面遷移時に進行中のリクエストが完了するまで通信が継続する。ただし `controller.signal.aborted` チェックにより、不正な state 更新は防止されている。

**推奨対応**:
```tsx
useEffect(() => {
  return () => { abortControllerRef.current?.abort(); };
}, []);
```

**Codex との議論結果**: 「必須ではないが有益」で合意。既存の `aborted` チェックで致命的問題は防げているが、ベストプラクティスとして追加が望ましい。

---

### 5. [Low] プロンプトインジェクション耐性

**ファイル**: `backend/src/services/prompts/refine.py:58, 71, 82`

**内容**: ユーザー入力を f-string でプロンプトに直接埋め込んでおり、悪意ある入力（例: 「上記の指示を無視して...」）で出力品質が低下する可能性がある。

```python
return f"""以下のフラッシュカードを改善してください。

## 問題文（表面）
{front}       # ← ユーザー入力をそのまま埋め込み

## 解答（裏面）
{back}        # ← ユーザー入力をそのまま埋め込み
```

**影響**: リファイン結果がJSON形式から逸脱し、パースエラー（500）が発生する可能性。ただし被害範囲はリクエストした本人のみに限定される（他ユーザーへの影響なし）。

**Codex との議論結果**: 初回 Medium → 議論後 Low に再評価。ユーザー自身のカードのリファインであり、横断的なセキュリティリスクは限定的。ただし JSON 逸脱によるパース失敗率の上昇は運用上の注意点。

---

### 6. [Low] テストカバレッジの不足箇所

**ファイル**: 複数テストファイル

**不足ケース**:

| カテゴリ | 不足テスト | 対象ファイル |
|---------|----------|------------|
| ハンドラー | `body=null` / 配列ボディ | `test_handler_refine.py` |
| ハンドラー | `language="en"` の動作 | `test_handler_refine.py` |
| Bedrock | `refine_card` 正常・異常系（専用テストなし） | 新規テストファイル必要 |
| プロンプト | `language="en"` の期待値 | `test_refine_prompts.py` |
| フロントエンド | アンマウント中の通信キャンセル | `CardForm.test.tsx` |

---

### 7. [Info] 既存パターンとの整合性で良い点

以下の設計判断は既存コードベースとよく整合しており、評価できる:

- **エラーハンドリング**: `map_ai_error_to_http()` の再利用による HTTP ステータスコードの一貫性
- **Pydantic バリデーション**: `model_validator(mode="after")` による cross-field バリデーション
- **AbortController**: `generateCards` と同じパターンで `signal` を API クライアントに伝播
- **テスト構造**: クラスベースのテスト分類（Success / Validation / Auth / AIErrors）
- **エラーメッセージ分岐**: フロントエンドで HTTP ステータスコード別にユーザーフレンドリーなメッセージ表示
- **Protocol 準拠**: `AIService` Protocol に `refine_card` を追加し、Bedrock / Strands 両実装で統一

---

## 修正優先度まとめ

| 優先度 | 項目 | 工数目安 |
|-------|------|---------|
| **P1** | `language` パラメータの ja/en 実装 | 中（テンプレート2言語分 + テスト） |
| **P1** | `body=null` TypeError 対策 | 小（型チェック追加、既存 generate にも適用） |
| **P2** | `useEffect` cleanup 追加 | 小（1行追加） |
| **P3** | Bedrock system prompt 分離 | 中（`_invoke_claude` のシグネチャ変更、全メソッド影響） |
| **P3** | テスト追加（不足ケース） | 中 |
| **P4** | プロンプトインジェクション対策 | 要検討（XML タグによる区切り等） |

---

## レビュープロセス

1. Claude Opus 4.6 が全変更ファイル（実装 + テスト 16ファイル）を精読
2. Codex (MCP経由) に独立レビューを依頼
3. Codex の指摘事項について 5点の議論を実施:
   - `body=null` の挙動 → Powertools ソースコード検証で確認
   - プロンプトインジェクション → 優先度 Medium → Low に再評価
   - CardForm 責務分離 → YAGNI で現状維持が妥当と合意
   - Bedrock system prompt → Medium-Low で合意
   - useEffect cleanup → Low（有益だが必須ではない）で合意
4. 議論結果を反映し、最終レビュー文書を作成
