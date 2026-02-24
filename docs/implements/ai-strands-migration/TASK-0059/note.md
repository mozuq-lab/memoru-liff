# TASK-0059: 回答採点モデル・プロンプト・AI実装 - Tasknote

## タスク概要

TASK-0059 は回答採点機能の実装フェーズ。Pydantic モデル定義、採点プロンプト完成、及び StrandsAIService/BedrockAIService の grade_answer() メソッド実装を行う。

**実装ファイル**:
1. `backend/src/models/grading.py` - 新規作成
2. `backend/src/services/prompts/grading.py` - 完成
3. `backend/src/services/strands_service.py` - grade_answer() 追加
4. `backend/src/services/bedrock.py` - grade_answer() 追加

**テストファイル**:
- `backend/tests/unit/test_grading_models.py` - Pydantic 検証テスト
- `backend/tests/unit/test_grading_prompts.py` - プロンプト生成テスト
- `backend/tests/unit/test_strands_service.py` - Strands 実装テスト
- `backend/tests/unit/test_bedrock.py` - Bedrock 実装テスト（既存を拡充）

---

## 実装の流れ（TDD）

### Phase 1: TDD Red - テストケース定義

#### 1.1 Pydantic モデルテスト (`test_grading_models.py`)

**テストクラス**: `TestGradeAnswerRequestValidation`
- `test_valid_user_answer()` - 正常系（1-2000文字）
- `test_empty_user_answer()` - 異常系（空文字列）
- `test_whitespace_only_user_answer()` - 異常系（空白のみ）
- `test_user_answer_too_long()` - 異常系（2000文字超）

**テストクラス**: `TestGradeAnswerResponseSerialization`
- `test_response_all_fields()` - 全フィールド出力テスト
- `test_response_json_schema()` - JSON シリアライズテスト

#### 1.2 プロンプト生成テスト (`test_grading_prompts.py`)

**テストクラス**: `TestGradingPrompts`
- `test_get_grading_prompt_ja()` - 日本語プロンプト生成
- `test_get_grading_prompt_en()` - 英語プロンプト生成
- `test_grading_prompt_includes_sm2_definitions()` - SM-2 定義の埋め込み確認
- `test_grading_prompt_includes_card_fields()` - card_front, card_back, user_answer の埋め込み確認
- `test_grading_prompt_language_fallback()` - 不正な言語のフォールバック

#### 1.3 Strands AI サービステスト (`test_strands_service.py`)

**テストクラス**: `TestStrandsGradeAnswer`
- `test_grade_answer_success()` - 正常系（grade=5）
- `test_grade_answer_zero()` - 正常系（grade=0）
- `test_grade_answer_parse_error()` - JSON パースエラー
- `test_grade_answer_timeout()` - タイムアウト
- `test_grade_answer_rate_limit()` - レート制限超過
- `test_grade_answer_language_ja()` - 日本語での採点
- `test_grade_answer_language_en()` - 英語での採点
- `test_parse_grading_result_missing_grade()` - grade フィールド欠落
- `test_parse_grading_result_missing_reasoning()` - reasoning フィールド欠落
- `test_parse_grading_result_invalid_grade()` - grade が数値でない

#### 1.4 Bedrock AI サービステスト (`test_bedrock.py` - 拡充)

**テストクラス**: `TestBedrockGradeAnswer`（既存テストに追加）
- `test_grade_answer_success()` - 正常系（grade=3）
- `test_grade_answer_parse_error()` - JSON パースエラー
- `test_grade_answer_timeout()` - タイムアウト
- `test_grade_answer_bedrock_error()` - Bedrock エラー

---

### Phase 2: TDD Green - 実装

#### 2.1 Pydantic モデル (`backend/src/models/grading.py`)

**ファイル新規作成**:

```python
"""Grading models for answer evaluation.

GradeAnswerRequest: ユーザーの回答入力
GradeAnswerResponse: AI採点結果
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class GradeAnswerRequest(BaseModel):
    """Request model for AI answer grading."""

    user_answer: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User's answer to be graded",
    )

    @field_validator("user_answer")
    @classmethod
    def validate_user_answer(cls, v: str) -> str:
        """Validate user answer is not just whitespace."""
        if not v or len(v.strip()) == 0:
            raise ValueError("user_answer cannot be empty or whitespace only")
        if len(v) > 2000:
            raise ValueError("user_answer must be 2000 characters or less")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "user_answer": "The capital of France is Paris"
            }
        }


class GradeAnswerResponse(BaseModel):
    """Response model for AI answer grading."""

    grade: int = Field(
        ...,
        ge=0,
        le=5,
        description="SM-2 grade (0-5)",
    )
    reasoning: str = Field(
        ...,
        description="Explanation of the grade decision",
    )
    card_front: str = Field(
        ...,
        description="The question side of the card (for reference)",
    )
    card_back: str = Field(
        ...,
        description="The correct answer side of the card (for reference)",
    )
    grading_info: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata about grading (model_used, processing_time_ms, etc.)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "grade": 4,
                "reasoning": "Correct answer with minor hesitation in phrasing",
                "card_front": "What is the capital of France?",
                "card_back": "Paris",
                "grading_info": {
                    "model_used": "bedrock",
                    "processing_time_ms": 1234
                }
            }
        }
```

**実装ポイント**:
- Pydantic v2 を使用（Project で指定）
- `min_length=1, max_length=2000` で自動バリデーション
- `@field_validator` で空白チェック
- `grading_info` は Dict[str, Any] で柔軟性を確保
- `Config.json_schema_extra` でスキーマドキュメント化

#### 2.2 プロンプト完成 (`backend/src/services/prompts/grading.py`)

**既存ファイルの確認と完成**:

現在のファイル構成を確認し、以下が含まれていることを保証:

```python
SM2_GRADE_DEFINITIONS = """SM-2 Grading Scale:
- Grade 5: Perfect response - Complete and accurate answer with no hesitation
- Grade 4: Correct with some hesitation - Correct answer but minor gaps or uncertainty
- Grade 3: Correct with serious difficulty - Correct answer but required significant effort to recall
- Grade 2: Incorrect; correct answer seemed easy - Wrong answer, but correct answer was easy to recall after seeing it
- Grade 1: Incorrect; correct answer remembered - Wrong answer, but had some related knowledge
- Grade 0: Complete blackout - No answer or completely unrelated response"""

GRADING_SYSTEM_PROMPT = """You are an expert flashcard grader using the SM-2 spaced repetition algorithm.

Your task is to evaluate the student's answer against the correct answer and assign an SM-2 grade.

[SM2_GRADE_DEFINITIONS embedded here]

Respond ONLY with a JSON object in this exact format:
{
  "grade": <integer 0-5>,
  "reasoning": "<brief explanation of the grade>",
  "feedback": "<constructive feedback for the student>"
}

Do not include any text outside the JSON object."""

def get_grading_prompt(
    card_front: str,
    card_back: str,
    user_answer: str,
    language: Language = "ja"
) -> str:
    """構築: 回答採点プロンプト"""
    # Language instruction を language 値に応じて選択
    # card_front, card_back, user_answer を埋め込む
    # SM-2 定義を含めた質問を返す
```

**実装ポイント**:
- SM-2 定義は SuperMemo の公式定義に従う（0-5）
- JSON 形式の指示を明確化
- 言語別の指示（ja/en）をサポート

#### 2.3 Strands AI サービス実装 (`backend/src/services/strands_service.py`)

**grade_answer() メソッド追加**:

```python
def grade_answer(
    self,
    card_front: str,
    card_back: str,
    user_answer: str,
    language: Language = "ja",
) -> GradingResult:
    """ユーザーの回答を採点する（Strands Agent 使用）.

    Args:
        card_front: カードの問題文。
        card_back: カードの正解。
        user_answer: ユーザーの回答。
        language: 出力言語。

    Returns:
        GradingResult with grade (0-5), reasoning, and metadata.

    Raises:
        AITimeoutError: Agent がタイムアウトした場合。
        AIRateLimitError: レート制限を超過した場合。
        AIParseError: JSON パースに失敗した場合。
        AIProviderError: プロバイダーエラーが発生した場合。
        AIServiceError: その他の予期しないエラー。
    """
    start_time = time.time()

    try:
        # プロンプト構築
        prompt = get_grading_prompt(
            card_front=card_front,
            card_back=card_back,
            user_answer=user_answer,
            language=language,
        )

        # Strands Agent を作成・実行
        agent = Agent(model=self.model)
        response = agent(prompt)

        # レスポンス解析
        response_text = str(response)
        result = self._parse_grading_result(response_text)

        processing_time_ms = int((time.time() - start_time) * 1000)
        result.processing_time_ms = processing_time_ms
        result.model_used = self.model_used

        return result

    except AIServiceError:
        raise
    except TimeoutError as e:
        raise AITimeoutError(f"Agent timed out: {e}") from e
    except ConnectionError as e:
        raise AIProviderError(f"Provider connection error: {e}") from e
    except Exception as e:
        error_str = str(e)

        if _is_rate_limit_error(e):
            raise AIRateLimitError(f"Rate limit exceeded: {e}") from e

        if "timeout" in error_str.lower() or "timed out" in error_str.lower():
            raise AITimeoutError(f"Agent timed out: {e}") from e

        if "connection" in error_str.lower() or "connect" in type(e).__name__.lower():
            raise AIProviderError(f"Provider connection error: {e}") from e

        raise AIServiceError(f"Unexpected error: {e}") from e


def _parse_grading_result(self, response_text: str) -> GradingResult:
    """Agent レスポンスを GradingResult に変換.

    期待フォーマット:
    {
        "grade": 0-5,
        "reasoning": "...",
        "feedback": "..."
    }
    """
    try:
        # Markdown コードブロックまたはプレーン JSON を抽出
        json_match = re.search(r"```json\s*([\s\S]*?)\s*```", response_text)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response_text.strip()

        data = json.loads(json_str)

        grade = int(data["grade"])
        reasoning = str(data["reasoning"])

        return GradingResult(
            grade=grade,
            reasoning=reasoning,
            model_used=self.model_used,
            processing_time_ms=0,  # 呼び出し側で上書き
        )

    except json.JSONDecodeError as e:
        raise AIParseError(f"Failed to parse grading response: {e}") from e
    except (KeyError, ValueError, TypeError) as e:
        raise AIParseError(f"Invalid grading response format: {e}") from e
```

**実装ポイント**:
- 既存の generate_cards() パターンに合わせる
- JSON 解析は re.search で Markdown コードブロック対応
- エラーハンドリングは TASK-0054 のパターンに従う
- 同期メソッド（async 不使用）

#### 2.4 Bedrock AI サービス実装 (`backend/src/services/bedrock.py`)

**grade_answer() メソッド追加** (既に実装済みを確認):

```python
def grade_answer(
    self,
    card_front: str,
    card_back: str,
    user_answer: str,
    language: Language = "ja",
) -> GradingResult:
    """Grade a user's answer using AI.

    [既存実装から確認]
    """
    start_time = time.time()

    prompt = get_grading_prompt(
        card_front=card_front,
        card_back=card_back,
        user_answer=user_answer,
        language=language,
    )

    response_text = self._invoke_with_retry(prompt)

    data = self._parse_json_response(
        response_text,
        required_fields=["grade", "reasoning"],
        context="grading",
    )

    grade = int(data["grade"])
    reasoning = str(data["reasoning"])

    processing_time_ms = int((time.time() - start_time) * 1000)

    return GradingResult(
        grade=grade,
        reasoning=reasoning,
        model_used=self.model_id,
        processing_time_ms=processing_time_ms,
    )
```

**確認ポイント**:
- 既存実装の _parse_json_response() を活用
- _invoke_with_retry() で リトライ/エラーハンドリングを委譲
- generate_cards() と同じパターンで grade_answer() を実装

---

### Phase 3: TDD Refactor - テストとドキュメント整理

#### 3.1 テストカバレッジ検証

```bash
cd /Volumes/external/dev/memoru-liff/backend
make test  # pytest で全テスト実行
pytest --cov=src tests/unit/test_grading_models.py
pytest --cov=src tests/unit/test_grading_prompts.py
pytest --cov=src tests/unit/test_strands_service.py
pytest --cov=src tests/unit/test_bedrock.py
```

**目標**: テストカバレッジ 80% 以上

#### 3.2 ドキュメント整備

- Pydantic モデルに docstring を追加
- grade_answer() メソッドに Args/Returns/Raises を明記
- SM-2 定義の参照元をコメントに記載

---

## 重要な実装パターン

### パターン 1: Pydantic モデルの検証

```python
@field_validator('user_answer')
@classmethod
def validate_user_answer(cls, v):
    if not v or len(v.strip()) == 0:
        raise ValueError("...")
    if len(v) > 2000:
        raise ValueError("...")
    return v
```

**ポイント**:
- 空白チェック: `v.strip()` で空白のみの判定
- 長さチェック: `len(v) > 2000` の順序

### パターン 2: JSON レスポンス解析

**Bedrock** (`_parse_json_response` 既存実装):
```python
json_match = re.search(r"```json\s*([\s\S]*?)\s*```", response_text)
if json_match:
    json_str = json_match.group(1)
else:
    json_str = response_text.strip()
data = json.loads(json_str)
```

**Strands** (同じパターン):
```python
# 同じ re.search パターンを使用
```

### パターン 3: エラーハンドリング

TASK-0054 の AIServiceError 階層に従う:

```python
- AITimeoutError (HTTP 504)
- AIRateLimitError (HTTP 429)
- AIProviderError (HTTP 503)
- AIParseError (HTTP 500)
- AIInternalError (HTTP 500)
```

### パターン 4: プロンプト管理

- 言語別指示: `LANGUAGE_INSTRUCTION.get(language, DEFAULT_LANGUAGE_INSTRUCTION)`
- SM-2 定義: 定数化して再利用
- 埋め込み: f-string で card_front, card_back, user_answer を埋め込む

---

## テストケース設計

### 境界値テスト

| テスト | 入力値 | 期待結果 |
|--------|--------|----------|
| 最小長 | 1文字 | バリデーション OK |
| 最大長 | 2000文字 | バリデーション OK |
| 超過 | 2001文字 | ValueError |
| 空文字 | "" | ValueError |
| 空白のみ | "   \t\n  " | ValueError |

### グレード境界値テスト

| グレード | テスト名 | 説明 |
|----------|----------|------|
| 0 | test_grade_zero | Complete blackout |
| 1 | test_grade_one | Incorrect but related |
| 3 | test_grade_three | Correct with difficulty |
| 5 | test_grade_five | Perfect response |

### エラーハンドリングテスト

| エラー | テスト名 | 期待例外 |
|--------|----------|----------|
| JSON 解析失敗 | test_parse_error | AIParseError |
| タイムアウト | test_timeout | AITimeoutError |
| レート制限 | test_rate_limit | AIRateLimitError |
| プロバイダーエラー | test_provider_error | AIProviderError |

---

## ファイル構造と依存関係

### 新規ファイル

```
backend/src/models/grading.py
├── GradeAnswerRequest (Pydantic model)
│   └── validation: user_answer (1-2000 char, not whitespace-only)
└── GradeAnswerResponse (Pydantic model)
    ├── grade (0-5)
    ├── reasoning (str)
    ├── card_front (str) - 参考用
    ├── card_back (str) - 参考用
    └── grading_info (Dict[str, Any])
```

### 既存ファイル修正

```
backend/src/services/prompts/grading.py
├── SM2_GRADE_DEFINITIONS (既存確認)
├── GRADING_SYSTEM_PROMPT (既存確認)
└── get_grading_prompt() (既存確認)

backend/src/services/strands_service.py
├── grade_answer() - 【新規追加】
└── _parse_grading_result() - 【新規追加】

backend/src/services/bedrock.py
├── grade_answer() - 【既に実装済み】確認用
└── _parse_json_response() - 既存（再利用）
```

### テストファイル

```
backend/tests/unit/
├── test_grading_models.py - 【新規】
├── test_grading_prompts.py - 【拡充】
├── test_strands_service.py - 【拡充】
└── test_bedrock.py - 【拡充】
```

---

## 注意事項と制約

### 1. 同期メソッド（async 不使用）

- TASK-0059 は **同期メソッド** を実装
- 既存の generate_cards() と同じ非同期パターンなし
- API ハンドラーから直接呼び出し可能

### 2. SM-2 グレード定義

- 参照元: https://www.supermemo.com/ 公式定義
- グレード 0-5 の定義は必ず含める
- 日本語/英語で指示言語を切り替え

### 3. JSON 出力形式の統一

- 必須フィールド: `grade`, `reasoning`
- オプション: `feedback`
- Bedrock/Strands 両方で同じ形式を返す

### 4. エラーハンドリング

- TASK-0054 の AIServiceError 階層に従う
- Bedrock は _invoke_with_retry() で自動リトライ
- Strands は Agent の例外をマップ

### 5. パフォーマンス考慮

- タイムアウト: 30秒（Lambda のグローバルタイムアウト）
- 処理時間計測: time.time() で計測、ミリ秒単位で記録

### 6. ローカル開発での検証

```bash
# ローカル Strands 検証（Ollama）
cd backend
ENVIRONMENT=dev make local-api

# ローカル Bedrock 検証
cd backend
ENVIRONMENT=prod make local-api
```

---

## 実装チェックリスト

### ファイル作成・修正

- [ ] `backend/src/models/grading.py` - 新規作成
- [ ] `backend/src/services/strands_service.py` - grade_answer() 追加
- [ ] `backend/src/services/prompts/grading.py` - 確認（既存）
- [ ] `backend/src/services/bedrock.py` - 確認（既存）

### テストファイル作成

- [ ] `backend/tests/unit/test_grading_models.py` - 新規
- [ ] `backend/tests/unit/test_grading_prompts.py` - 拡充
- [ ] `backend/tests/unit/test_strands_service.py` - 拡充
- [ ] `backend/tests/unit/test_bedrock.py` - 拡充

### テスト実行と検証

- [ ] pytest で全テスト実行
- [ ] カバレッジ 80% 以上確認
- [ ] ローカル環境で動作確認
- [ ] エラーケース検証

### ドキュメント

- [ ] docstring を全メソッドに追加
- [ ] type hints を確認
- [ ] README/CLAUDE.md の更新（必要に応じて）

---

## 参考リソース

### 設計文書
- `docs/design/ai-strands-migration/interfaces.py` - データ型定義
- `docs/design/ai-strands-migration/api-endpoints.md` - グレード定義表
- `docs/spec/ai-strands-migration/requirements.md` - 要件定義

### 既存実装の参照
- `backend/src/services/bedrock.py` - generate_cards() パターン
- `backend/src/services/prompts.py` - プロンプト構築パターン
- `backend/tests/unit/test_bedrock.py` - テストパターン

### 関連タスク
- TASK-0054: AI エラーハンドリング・リトライロジック
- TASK-0057: Strands SDK 統合設定・認証
- TASK-0060: POST /reviews/{card_id}/grade-ai エンドポイント

---

## 完了基準

**実装完了の定義**:

1. [ ] GradeAnswerRequest/Response モデルが定義されている
2. [ ] grading.py プロンプトが SM-2 グレード定義を含んでいる
3. [ ] StrandsAIService.grade_answer() が正常に動作する
4. [ ] BedrockAIService.grade_answer() が正常に動作する（既存確認）
5. [ ] 全テストがパスし、カバレッジ 80% 以上
6. [ ] ローカル環境で e2e テスト成功

**品質指標**:
- テストカバレッジ: 80% 以上
- エラーハンドリング: TASK-0054 パターン準拠
- API 契約: GradeAnswerRequest/Response 準拠
- ドキュメント: docstring と type hints 完備

---

## 次のタスク

**TASK-0060** 実装前提条件:
- grade_answer() メソッドが両 AI サービスで実装完了
- GradeAnswerRequest/Response モデルが確定
- エラーハンドリングが TASK-0054 に準拠

---

**タスク作成日**: 2026-02-24
**タスク期限**: Phase 3 完了前
**推定工数**: 8 時間
**関連者**: Backend Team
