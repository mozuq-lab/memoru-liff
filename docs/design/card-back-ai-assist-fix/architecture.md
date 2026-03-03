# カード AI 補足機能 レビュー修正 アーキテクチャ設計

**作成日**: 2026-03-03
**関連要件定義**: [requirements.md](../../spec/card-back-ai-assist-fix/requirements.md)
**元機能設計**: [card-back-ai-assist/architecture.md](../card-back-ai-assist/architecture.md)
**ヒアリング記録**: [design-interview.md](design-interview.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: コードレビュー・既存実装・Codex 検証を参考にした確実な設計
- 🟡 **黄信号**: 既存実装パターンから妥当な推測による設計

---

## 修正概要 🔵

**信頼性**: 🔵 *コードレビュー指摘 #1, #2, #4, #6 より*

コードレビューで指摘された 3件のコード修正と 5件のテスト追加を行う。アーキテクチャの変更はなく、既存のレイヤードアーキテクチャ（Handler → Service → AI Provider）を維持する。

## 修正 1: refine プロンプト ja/en テンプレート分岐 🔵

**信頼性**: 🔵 *レビュー指摘 #1 [High]・既存 `generate.py` パターン・ユーザーヒアリングより*
**関連要件**: REQ-FIX-001, REQ-FIX-002

### 変更対象

```
backend/src/services/prompts/refine.py  # テンプレート分岐追加
```

### 設計方針

`generate.py` と同じ「テンプレート分岐」パターンを採用する。`grading.py`/`advice.py` の「LANGUAGE_INSTRUCTION 付加」パターンではなく、完全に別の英語テンプレートを用意する。

**選択理由**: refine プロンプトは UI テキスト（「問題文」「解答」等）を含むため、LANGUAGE_INSTRUCTION の付加だけでは不十分。英語ユーザーに最適な体験を提供するには、テンプレート全体を英語化する必要がある。

### 変更内容

#### `REFINE_SYSTEM_PROMPT` → 関数化

```python
def get_refine_system_prompt(language: Language = "ja") -> str:
    """言語に応じたリファイン用システムプロンプトを返す."""
    if language == "ja":
        return _REFINE_SYSTEM_PROMPT_JA
    else:
        return _REFINE_SYSTEM_PROMPT_EN
```

🟡 **注意**: 既存の `REFINE_SYSTEM_PROMPT` 定数を関数に変更するため、以下の呼び出し元を修正する必要がある:
- `backend/src/services/bedrock.py:277` — `REFINE_SYSTEM_PROMPT` → `get_refine_system_prompt(language)`
- `backend/src/services/strands_service.py:440` — `REFINE_SYSTEM_PROMPT` → `get_refine_system_prompt(language)`
- `backend/src/services/prompts/__init__.py` — エクスポート変更

**代替案**: `REFINE_SYSTEM_PROMPT` 定数を残しつつ `get_refine_system_prompt()` 関数を追加し、サービス層でのみ関数を使用する。これにより後方互換性を維持できる。🟡

#### `get_refine_user_prompt()` の language 対応

```python
def get_refine_user_prompt(front: str, back: str, language: Language = "ja") -> str:
    has_front = bool(front.strip())
    has_back = bool(back.strip())

    if language == "ja":
        if has_front and has_back:
            return _get_both_prompt_ja(front, back)
        elif has_front:
            return _get_front_only_prompt_ja(front)
        else:
            return _get_back_only_prompt_ja(back)
    else:
        if has_front and has_back:
            return _get_both_prompt_en(front, back)
        elif has_front:
            return _get_front_only_prompt_en(front)
        else:
            return _get_back_only_prompt_en(back)
```

#### 英語テンプレート例 🟡

**信頼性**: 🟡 *既存 `generate.py` の英語テンプレートパターンから妥当な推測*

```python
_REFINE_SYSTEM_PROMPT_EN = """You are a flashcard improvement expert.
Improve the front (question) and back (answer) of the user's flashcard.

[Front (Question) Improvement Guidelines]
- Maintain the user's intent while making the question clear and concise
- Replace vague expressions with more specific ones
- Ensure the learner can immediately understand what is being asked

[Back (Answer) Improvement Guidelines]
- Maintain the user's input content as the foundation
- Supplement missing important information
- Format for optimal learning (bullet points, definition + examples, etc.)
- Keep it concise while maintaining accuracy

Respond ONLY in JSON format:
{"refined_front": "...", "refined_back": "..."}"""
```

### サービス層への影響 🔵

**信頼性**: 🔵 *既存実装の直接確認より*

`refine_card()` メソッドのシグネチャは変更不要（既に `language` パラメータを受け取っている）。内部でプロンプト生成時に `language` を渡すのみ。

```python
# bedrock.py (現状)
user_prompt = get_refine_user_prompt(front=front, back=back, language=language)
prompt = f"{REFINE_SYSTEM_PROMPT}\n\n{user_prompt}"

# bedrock.py (修正後)
user_prompt = get_refine_user_prompt(front=front, back=back, language=language)
system_prompt = get_refine_system_prompt(language=language)
prompt = f"{system_prompt}\n\n{user_prompt}"

# strands_service.py (現状)
agent = Agent(model=self.model, system_prompt=REFINE_SYSTEM_PROMPT)

# strands_service.py (修正後)
system_prompt = get_refine_system_prompt(language=language)
agent = Agent(model=self.model, system_prompt=system_prompt)
```

---

## 修正 2: body=null TypeError 対策 🔵

**信頼性**: 🔵 *レビュー指摘 #2 [High]・Codex Powertools v3.23.0 検証より*
**関連要件**: REQ-FIX-003, REQ-FIX-004

### 変更対象

```
backend/src/api/handlers/ai_handler.py  # refine_card, generate_cards 両ハンドラー
```

### 設計方針

`router.current_event.json_body` が `None`（`body: "null"` → `json.loads("null")` → `None`）を返すケースに対応する。`TypeError` を捕捉するか、事前に `isinstance(body, dict)` チェックを追加する。

### 変更内容

```python
# 修正前（refine_card / generate_cards 共通パターン）
try:
    body = router.current_event.json_body
    request = RefineCardRequest(**body)  # body=None で TypeError
except ValidationError as e:
    ...
except json.JSONDecodeError:
    ...

# 修正後
try:
    body = router.current_event.json_body
    if not isinstance(body, dict):
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Request body must be a JSON object"}),
        )
    request = RefineCardRequest(**body)
except ValidationError as e:
    ...
except json.JSONDecodeError:
    ...
```

### 適用範囲 🔵

同一パターンの修正を以下の 2つのハンドラーに適用:
1. `refine_card()` (L99-100) — 今回追加分
2. `generate_cards()` (L37-38) — 既存の同一問題

---

## 修正 3: CardForm useEffect cleanup 🔵

**信頼性**: 🔵 *レビュー指摘 #4 [Low]・React ベストプラクティスより*
**関連要件**: REQ-FIX-005

### 変更対象

```
frontend/src/components/CardForm.tsx  # useEffect cleanup 追加
```

### 変更内容

```tsx
import { useEffect, useRef, useState } from 'react';
// ... 既存の import

export const CardForm = ({ ... }: CardFormProps) => {
  // ... 既存の state

  // アンマウント時に進行中のリクエストをキャンセル
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  // ... 残りは変更なし
};
```

**影響範囲**: `CardForm` コンポーネントのみ。外部インターフェースへの変更なし。

---

## テスト設計 🔵

**信頼性**: 🔵 *レビュー指摘 #6・既存テストパターンより*
**関連要件**: REQ-TEST-001〜005

### 追加テストファイル

| ファイル | テスト対象 | テスト数目安 |
|---------|----------|------------|
| `backend/tests/unit/test_refine_prompts.py` | language="en" プロンプト | +4 |
| `backend/tests/unit/test_handler_refine.py` | body=null / 配列ボディ | +3 |
| `backend/tests/unit/test_handler_generate.py` | body=null（既存ファイルに追加） | +1 |
| `backend/tests/unit/test_bedrock_refine.py` | BedrockService.refine_card 正常・異常系 | +5（新規） |
| `frontend/src/components/__tests__/CardForm.test.tsx` | アンマウント時キャンセル | +1 |

### テスト詳細

#### test_refine_prompts.py（追加）

```python
class TestRefinePromptEnglish:
    """language="en" の英語プロンプトテスト."""

    def test_en_both_inputs_prompt(self):
        """英語で両方入力のプロンプトが生成されること."""

    def test_en_front_only_prompt(self):
        """英語で表面のみプロンプトが生成されること."""

    def test_en_back_only_prompt(self):
        """英語で裏面のみプロンプトが生成されること."""

    def test_en_system_prompt(self):
        """英語のシステムプロンプトが返されること."""
```

#### test_handler_refine.py（追加）

```python
class TestRefineCardInvalidBody:
    """不正ボディのテスト."""

    def test_null_body_returns_400(self, lambda_context):
        """body が null の場合 400 が返ること."""

    def test_array_body_returns_400(self, lambda_context):
        """body が配列の場合 400 が返ること."""

    def test_string_body_returns_400(self, lambda_context):
        """body が文字列の場合 400 が返ること."""
```

#### test_bedrock_refine.py（新規）🔵

```python
class TestBedrockRefineCardSuccess:
    """BedrockService.refine_card 正常系."""

    def test_refine_both(self):
        """表面・裏面両方の refine が成功すること."""

    def test_refine_front_only(self):
        """表面のみの refine が成功すること."""

class TestBedrockRefineCardParsing:
    """BedrockService.refine_card パース系."""

    def test_markdown_json_response(self):
        """Markdown コードブロック内 JSON がパースされること."""

    def test_missing_field_raises_error(self):
        """必須フィールド欠落で BedrockParseError."""

class TestBedrockRefineCardErrors:
    """BedrockService.refine_card エラー系."""

    def test_timeout_raises_error(self):
        """タイムアウト時に BedrockTimeoutError."""
```

---

## 変更対象ファイル一覧 🔵

**信頼性**: 🔵 *修正設計より*

### バックエンド（変更）
```
backend/src/services/prompts/refine.py     # ja/en テンプレート分岐
backend/src/services/prompts/__init__.py   # エクスポート更新
backend/src/services/bedrock.py            # get_refine_system_prompt 使用
backend/src/services/strands_service.py    # get_refine_system_prompt 使用
backend/src/api/handlers/ai_handler.py     # body isinstance チェック追加
```

### フロントエンド（変更）
```
frontend/src/components/CardForm.tsx       # useEffect cleanup 追加
```

### テスト（変更・新規）
```
backend/tests/unit/test_refine_prompts.py  # language="en" テスト追加
backend/tests/unit/test_handler_refine.py  # body=null テスト追加
backend/tests/unit/test_handler_generate.py # body=null テスト追加（既存ファイル）
backend/tests/unit/test_bedrock_refine.py  # 新規: Bedrock refine テスト
frontend/src/components/__tests__/CardForm.test.tsx  # アンマウントテスト追加
```

---

## 関連文書

- **データフロー**: [dataflow.md](dataflow.md)
- **元機能設計**: [card-back-ai-assist/architecture.md](../card-back-ai-assist/architecture.md)
- **要件定義**: [requirements.md](../../spec/card-back-ai-assist-fix/requirements.md)
- **コードレビュー**: [card-back-ai-assist-review.md](../../review/card-back-ai-assist-review.md)

## 信頼性レベルサマリー

- 🔵 青信号: 12 件 (86%)
- 🟡 黄信号: 2 件 (14%)
- 🔴 赤信号: 0 件 (0%)

**品質評価**: ✅ 高品質
