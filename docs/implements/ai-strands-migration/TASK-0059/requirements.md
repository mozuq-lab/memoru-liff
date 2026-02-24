# TASK-0059: 回答採点モデル・プロンプト・AI実装 - TDD Requirements

## 概要

本ドキュメントは TASK-0059 の TDD Red フェーズで作成するテストケースの詳細要件を定義する。
対象は回答採点機能の Pydantic モデル、採点プロンプト完成、および StrandsAIService / BedrockAIService の `grade_answer()` メソッド実装である。

**関連要件**: REQ-SM-003（回答採点/AI 評価）、REQ-SM-403（Pydantic v2）、REQ-SM-404（テストカバレッジ 80%）

---

## 1. GradeAnswerRequest Pydantic モデル

### ファイル: `backend/src/models/grading.py` (新規作成)

**参照パターン**: `backend/src/models/generate.py` の `GenerateCardsRequest`

### 1.1 フィールド定義

| フィールド | 型 | 必須 | バリデーション | 説明 |
|-----------|------|------|--------------|------|
| `user_answer` | `str` | Yes | `min_length=1`, `max_length=2000`, 空白のみ不可 | ユーザーの回答テキスト |

### 1.2 バリデーションルール

- **REQ-VAL-001** 🔵: `user_answer` は 1 文字以上 2000 文字以下であること。`Field(..., min_length=1, max_length=2000)` で制約する。
  - *根拠*: api-endpoints.md の `user_answer` バリデーション仕様（1-2000 文字、空白のみ不可）
- **REQ-VAL-002** 🔵: `user_answer` が空白文字のみ（スペース/タブ/改行）の場合は `ValueError` を raise すること。`@field_validator` で `v.strip()` が空かどうかを検証する。
  - *根拠*: api-endpoints.md のバリデーション仕様、GenerateCardsRequest の `validate_input_text` パターン
- **REQ-VAL-003** 🔵: `Config.json_schema_extra` で OpenAPI スキーマ用のサンプルを定義すること。
  - *根拠*: GenerateCardsRequest の既存パターンに準拠

### 1.3 テストケース: `TestGradeAnswerRequestValidation`

**ファイル**: `backend/tests/unit/test_grading_models.py` (新規作成)

| TC ID | テスト名 | 入力 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-MOD-001 | `test_valid_user_answer_minimum` | `user_answer="a"` (1 文字) | バリデーション OK、インスタンス生成成功 | 🔵 |
| TC-MOD-002 | `test_valid_user_answer_maximum` | `user_answer="a" * 2000` (2000 文字) | バリデーション OK、インスタンス生成成功 | 🔵 |
| TC-MOD-003 | `test_valid_user_answer_japanese` | `user_answer="東京です"` | バリデーション OK、値が保持される | 🔵 |
| TC-MOD-004 | `test_valid_user_answer_with_leading_trailing_spaces` | `user_answer=" hello "` | バリデーション OK（strip しない、空白のみでなければ通す） | 🔵 |
| TC-MOD-005 | `test_empty_user_answer` | `user_answer=""` | `ValidationError` raise | 🔵 |
| TC-MOD-006 | `test_whitespace_only_user_answer_spaces` | `user_answer="   "` | `ValidationError` raise | 🔵 |
| TC-MOD-007 | `test_whitespace_only_user_answer_mixed` | `user_answer="  \t\n  "` | `ValidationError` raise | 🔵 |
| TC-MOD-008 | `test_user_answer_too_long` | `user_answer="a" * 2001` (2001 文字) | `ValidationError` raise | 🔵 |
| TC-MOD-009 | `test_user_answer_missing` | `GradeAnswerRequest()` (フィールド未指定) | `ValidationError` raise | 🔵 |

**テスト実装パターン**:
```python
from pydantic import ValidationError
from models.grading import GradeAnswerRequest

def test_valid_user_answer_minimum():
    req = GradeAnswerRequest(user_answer="a")
    assert req.user_answer == "a"

def test_empty_user_answer():
    with pytest.raises(ValidationError):
        GradeAnswerRequest(user_answer="")
```

---

## 2. GradeAnswerResponse Pydantic モデル

### ファイル: `backend/src/models/grading.py` (同一ファイル)

### 2.1 フィールド定義

| フィールド | 型 | 必須 | 制約 | 説明 |
|-----------|------|------|------|------|
| `grade` | `int` | Yes | `ge=0, le=5` | SM-2 グレード (0-5) |
| `reasoning` | `str` | Yes | - | AI による採点理由 |
| `card_front` | `str` | Yes | - | カードの問題（参考表示用） |
| `card_back` | `str` | Yes | - | カードの正解（参考表示用） |
| `grading_info` | `Dict[str, Any]` | No | `default_factory=dict` | メタ情報 (model_used, processing_time_ms 等) |

### 2.2 設計要件

- **REQ-RES-001** 🔵: `grade` は `Field(..., ge=0, le=5)` で SM-2 スケールの範囲を強制すること。
  - *根拠*: api-endpoints.md の SRS グレード定義表 (0-5)
- **REQ-RES-002** 🔵: `grading_info` は `Dict[str, Any]` で柔軟性を保ち、`default_factory=dict` で省略可能とすること。
  - *根拠*: api-endpoints.md の `grading_info` 仕様、interfaces.py の GradingResult 設計
- **REQ-RES-003** 🔵: `card_front` と `card_back` は採点結果の参照表示用として必須フィールドとすること。
  - *根拠*: api-endpoints.md の POST /reviews/{card_id}/grade-ai レスポンス仕様

### 2.3 テストケース: `TestGradeAnswerResponseSerialization`

| TC ID | テスト名 | 内容 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-MOD-010 | `test_response_all_fields` | 全フィールド指定でインスタンス生成 | 全フィールドが正しく保持される | 🔵 |
| TC-MOD-011 | `test_response_json_serialization` | `.model_dump()` で辞書化 | grade, reasoning, card_front, card_back, grading_info が全て含まれる | 🔵 |
| TC-MOD-012 | `test_response_grade_boundary_zero` | `grade=0` | バリデーション OK | 🔵 |
| TC-MOD-013 | `test_response_grade_boundary_five` | `grade=5` | バリデーション OK | 🔵 |
| TC-MOD-014 | `test_response_grade_below_range` | `grade=-1` | `ValidationError` raise | 🔵 |
| TC-MOD-015 | `test_response_grade_above_range` | `grade=6` | `ValidationError` raise | 🔵 |
| TC-MOD-016 | `test_response_grading_info_default_empty` | `grading_info` 未指定 | `grading_info` が `{}` (空辞書) | 🔵 |
| TC-MOD-017 | `test_response_grading_info_with_metadata` | `grading_info={"model_used": "strands", "processing_time_ms": 1234}` | メタ情報が正しく保持される | 🔵 |

---

## 3. 採点プロンプト

### ファイル: `backend/src/services/prompts/grading.py` (既存ファイルの完成確認)

**現在の状態**: 既に SM2_GRADE_DEFINITIONS, GRADING_SYSTEM_PROMPT, get_grading_prompt() が実装済み。

### 3.1 確認要件

- **REQ-PRM-001** 🔵: `SM2_GRADE_DEFINITIONS` は SM-2 グレード 0-5 の全定義を含む文字列定数であること。
  - *根拠*: api-endpoints.md の SRS グレード定義表
- **REQ-PRM-002** 🔵: `GRADING_SYSTEM_PROMPT` は SM-2 グレード定義と JSON 出力形式指示 (`grade`, `reasoning`, `feedback`) を含むシステムプロンプトであること。
  - *根拠*: note.md のプロンプト仕様、TASK-0059 タスクファイル
- **REQ-PRM-003** 🔵: `get_grading_prompt(card_front, card_back, user_answer, language)` は 4 引数を受け取り、card_front, card_back, user_answer を埋め込んだプロンプト文字列を返すこと。
  - *根拠*: interfaces.py の AIService.grade_answer() シグネチャ
- **REQ-PRM-004** 🔵: `language="ja"` の場合、日本語応答指示が含まれること。`language="en"` の場合、英語応答指示が含まれること。
  - *根拠*: _types.py の LANGUAGE_INSTRUCTION 辞書
- **REQ-PRM-005** 🟡: 未知の language 値（例: `"fr"`）の場合、日本語にフォールバックすること（`LANGUAGE_INSTRUCTION.get(language, DEFAULT_LANGUAGE_INSTRUCTION)` パターン）。
  - *根拠*: 要件定義書 4.7 節のフォールバック仕様から推測
- **REQ-PRM-006** 🔵: `language` パラメータのデフォルト値は `"ja"` であること。
  - *根拠*: interfaces.py の `language: Language = "ja"` シグネチャ

### 3.2 テストケース: `TestGradingPrompts` (既存テストの拡充確認)

**ファイル**: `backend/tests/unit/test_grading_prompts.py` (既存)

既存テストは TC-005 ~ TC-008, TC-014, TC-016, TC-021, TC-023 で十分にカバーされている。TASK-0059 では既存テストが全てパスすることを確認する。追加が必要な場合は以下のテストケースを検討する。

| TC ID | テスト名 | 内容 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-PRM-001 | `test_grading_prompt_includes_all_inputs` | card_front, card_back, user_answer の 3 値が全てプロンプトに含まれること | 3 つの入力が全て埋め込まれている | 🔵 |
| TC-PRM-002 | `test_grading_prompt_system_prompt_sm2` | GRADING_SYSTEM_PROMPT に SM-2 グレード 0-5 の定義が含まれること | SM2_GRADE_DEFINITIONS の全グレードが含まれる | 🔵 |

**備考**: 上記テストは既存の TC-005, TC-006, TC-007, TC-008 で実質カバー済み。追加テストは不要な可能性が高い。

---

## 4. StrandsAIService.grade_answer() 実装

### ファイル: `backend/src/services/strands_service.py` (既存ファイル修正)

**現在の状態**: `grade_answer()` は `NotImplementedError("grade_answer is not implemented yet (Phase 3)")` を raise するスタブ。

### 4.1 実装要件

- **REQ-STR-001** 🔵: `grade_answer()` は同期メソッドとして実装すること（`async` 不使用）。既存の `generate_cards()` と同一パターン。
  - *根拠*: ai_service.py の Protocol 定義が同期シグネチャ、note.md 注意事項 1「同期メソッド（async 不使用）」
- **REQ-STR-002** 🔵: `grade_answer(card_front, card_back, user_answer, language="ja")` のシグネチャを維持すること（Protocol 準拠）。
  - *根拠*: ai_service.py の AIService Protocol 定義
- **REQ-STR-003** 🔵: `get_grading_prompt()` を使用してプロンプトを構築し、`Agent(model=self.model)` で Strands Agent を作成・実行すること。
  - *根拠*: note.md の Phase 2 実装仕様、generate_cards() の既存パターン
- **REQ-STR-004** 🔵: Agent のレスポンスを `str()` で変換後、`_parse_grading_result()` で JSON 解析すること。
  - *根拠*: generate_cards() の `str(response)` + `_parse_generation_result()` パターン
- **REQ-STR-005** 🔵: `GradingResult(grade, reasoning, model_used, processing_time_ms)` を返すこと。`model_used` は `self.model_used`、`processing_time_ms` は `time.time()` で計測すること。
  - *根拠*: ai_service.py の GradingResult dataclass 定義
- **REQ-STR-006** 🔵: 既に AIServiceError のサブクラスである例外はそのまま re-raise すること（`except AIServiceError: raise`）。
  - *根拠*: generate_cards() のエラーハンドリングパターン (L149-151)
- **REQ-STR-007** 🔵: `TimeoutError` は `AITimeoutError` にマッピングすること。
  - *根拠*: generate_cards() のエラーハンドリング (L152-153)
- **REQ-STR-008** 🔵: `ConnectionError` は `AIProviderError` にマッピングすること。
  - *根拠*: generate_cards() のエラーハンドリング (L154-155)
- **REQ-STR-009** 🔵: botocore `ClientError` の `ThrottlingException` 等は `AIRateLimitError` にマッピングすること（`_is_rate_limit_error()` ヘルパー使用）。
  - *根拠*: generate_cards() のエラーハンドリング (L161-162)、_is_rate_limit_error() 関数
- **REQ-STR-010** 🔵: その他の予期しない例外は `AIServiceError` にラップすること。
  - *根拠*: generate_cards() のエラーハンドリング (L173)
- **REQ-STR-011** 🔵: 例外チェーンを `from e` で保持すること。
  - *根拠*: generate_cards() の全 raise 文が `from e` を使用

### 4.2 _parse_grading_result() メソッド

- **REQ-STR-012** 🔵: Agent レスポンスから JSON を抽出すること。Markdown コードブロック (`\`\`\`json ... \`\`\``) とプレーン JSON の両方に対応する。
  - *根拠*: _parse_generation_result() の `re.search(r"```json\s*([\s\S]*?)\s*```", response_text)` パターン
- **REQ-STR-013** 🔵: パースされた JSON から `grade` (int) と `reasoning` (str) を抽出すること。両フィールドは必須。
  - *根拠*: note.md の _parse_grading_result() 仕様
- **REQ-STR-014** 🔵: JSON パースに失敗した場合は `AIParseError` を raise すること（`from e` で原因を保持）。
  - *根拠*: _parse_generation_result() のエラーパターン (L202-203)
- **REQ-STR-015** 🔵: `grade` または `reasoning` フィールドが欠落した場合は `AIParseError` を raise すること。
  - *根拠*: note.md の `test_parse_grading_result_missing_grade`, `test_parse_grading_result_missing_reasoning`
- **REQ-STR-016** 🔵: `grade` が整数に変換できない場合は `AIParseError` を raise すること。
  - *根拠*: note.md の `test_parse_grading_result_invalid_grade`

### 4.3 テストケース: `TestStrandsGradeAnswer`

**ファイル**: `backend/tests/unit/test_strands_service.py` (既存ファイルに追加)

**モックパターン**: 既存の `_make_mock_agent_instance()` ヘルパーを再利用する。

| TC ID | テスト名 | 内容 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-STR-001 | `test_grade_answer_success_perfect` | Agent が `{"grade": 5, "reasoning": "Perfect"}` を返す | `GradingResult(grade=5, reasoning="Perfect", ...)` が返る | 🔵 |
| TC-STR-002 | `test_grade_answer_success_zero` | Agent が `{"grade": 0, "reasoning": "No answer"}` を返す | `GradingResult(grade=0, reasoning="No answer", ...)` が返る | 🔵 |
| TC-STR-003 | `test_grade_answer_success_partial` | Agent が `{"grade": 3, "reasoning": "Partially correct"}` を返す | `GradingResult(grade=3, ...)` が返る | 🔵 |
| TC-STR-004 | `test_grade_answer_markdown_wrapped_response` | Agent が `\`\`\`json ... \`\`\`` で囲んだ JSON を返す | 正しくパースされて GradingResult が返る | 🔵 |
| TC-STR-005 | `test_grade_answer_model_used` | 正常系でレスポンスを取得 | `result.model_used` が `self.model_used` (strands_bedrock 等) と一致 | 🔵 |
| TC-STR-006 | `test_grade_answer_processing_time_ms` | 正常系でレスポンスを取得 | `result.processing_time_ms` が 0 以上の整数 | 🔵 |
| TC-STR-007 | `test_grade_answer_passes_correct_args_to_prompt` | `get_grading_prompt` への引数検証 | card_front, card_back, user_answer, language が正しく渡される | 🔵 |
| TC-STR-008 | `test_grade_answer_language_ja` | `language="ja"` で呼び出し | `get_grading_prompt` に `language="ja"` が渡される | 🔵 |
| TC-STR-009 | `test_grade_answer_language_en` | `language="en"` で呼び出し | `get_grading_prompt` に `language="en"` が渡される | 🔵 |
| TC-STR-010 | `test_grade_answer_parse_error_invalid_json` | Agent が非 JSON テキストを返す | `AIParseError` raise | 🔵 |
| TC-STR-011 | `test_grade_answer_parse_error_missing_grade` | Agent が `{"reasoning": "..."}` を返す（grade 欠落） | `AIParseError` raise | 🔵 |
| TC-STR-012 | `test_grade_answer_parse_error_missing_reasoning` | Agent が `{"grade": 5}` を返す（reasoning 欠落） | `AIParseError` raise | 🔵 |
| TC-STR-013 | `test_grade_answer_parse_error_invalid_grade_type` | Agent が `{"grade": "five", "reasoning": "..."}` を返す | `AIParseError` raise | 🔵 |
| TC-STR-014 | `test_grade_answer_timeout` | Agent が `TimeoutError` を raise | `AITimeoutError` raise | 🔵 |
| TC-STR-015 | `test_grade_answer_rate_limit` | Agent が botocore `ClientError(ThrottlingException)` を raise | `AIRateLimitError` raise | 🟡 |
| TC-STR-016 | `test_grade_answer_connection_error` | Agent が `ConnectionError` を raise | `AIProviderError` raise | 🔵 |
| TC-STR-017 | `test_grade_answer_unknown_exception` | Agent が `RuntimeError` を raise | `AIServiceError` raise | 🔵 |
| TC-STR-018 | `test_grade_answer_exception_chain_preserved` | Agent がエラーを raise | `__cause__` が保持される | 🔵 |

**テスト実装パターン**:
```python
class TestStrandsGradeAnswer:
    """StrandsAIService.grade_answer() テスト."""

    def test_grade_answer_success_perfect(self):
        """TC-STR-001: 完璧な回答で grade=5 が返る."""
        response_json = json.dumps({"grade": 5, "reasoning": "Perfect response"})
        mock_agent_instance = _make_mock_agent_instance(response_json)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            result = service.grade_answer(
                card_front="日本の首都は？",
                card_back="東京",
                user_answer="東京",
            )

        assert isinstance(result, GradingResult)
        assert result.grade == 5
        assert result.reasoning == "Perfect response"
        assert isinstance(result.processing_time_ms, int)
        assert result.processing_time_ms >= 0
```

### 4.4 既存テスト `TestStrandsServiceStubs` への影響

TASK-0059 完了後、以下の既存テストは **削除または修正が必要**:

- `TC-STUB-001` (`test_grade_answer_raises_not_implemented`): `grade_answer()` は `NotImplementedError` ではなく正常動作するようになるため、このテストは削除する。
- `TC-STUB-003` (`test_not_implemented_error_message_contains_phase3`): grade_answer 部分のアサーションを削除する。

---

## 5. BedrockAIService.grade_answer() 実装

### ファイル: `backend/src/services/bedrock.py` (既存ファイル)

**現在の状態**: `grade_answer()` は既に実装済み（L167-218）。`_invoke_with_retry()` + `_parse_json_response()` パターンで動作する。

### 5.1 確認要件

- **REQ-BDK-001** 🔵: `grade_answer()` は同期メソッドとして実装されていること（既存確認）。
  - *根拠*: bedrock.py L167 のメソッドシグネチャ
- **REQ-BDK-002** 🔵: `get_grading_prompt()` を使用してプロンプトを構築していること。
  - *根拠*: bedrock.py L193-198 の実装
- **REQ-BDK-003** 🔵: `_invoke_with_retry()` でリトライ付き API 呼び出しを行っていること。
  - *根拠*: bedrock.py L200
- **REQ-BDK-004** 🔵: `_parse_json_response()` で `required_fields=["grade", "reasoning"]` を指定して解析していること。
  - *根拠*: bedrock.py L202-206
- **REQ-BDK-005** 🔵: `grade` を `int()` に変換し、`reasoning` を `str()` に変換していること。
  - *根拠*: bedrock.py L208-209
- **REQ-BDK-006** 🔵: `GradingResult` を返し、`model_used=self.model_id`、`processing_time_ms` を含むこと。
  - *根拠*: bedrock.py L213-218

### 5.2 テストケース: `TestBedrockGradeAnswer`

**ファイル**: `backend/tests/unit/test_bedrock.py` (既存ファイルに追加)

**モックパターン**: 既存の `mock_bedrock_client` フィクスチャを再利用する。

| TC ID | テスト名 | 内容 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-BDK-001 | `test_grade_answer_success` | Bedrock が `{"grade": 3, "reasoning": "Partially correct"}` を返す | `GradingResult(grade=3, reasoning="Partially correct", ...)` が返る | 🔵 |
| TC-BDK-002 | `test_grade_answer_success_with_markdown` | Bedrock が Markdown コードブロック内の JSON を返す | 正しくパースされて GradingResult が返る | 🔵 |
| TC-BDK-003 | `test_grade_answer_model_used` | 正常系でレスポンスを取得 | `result.model_used` が `self.model_id` と一致 | 🔵 |
| TC-BDK-004 | `test_grade_answer_processing_time_ms` | 正常系でレスポンスを取得 | `result.processing_time_ms` が 0 以上の整数 | 🔵 |
| TC-BDK-005 | `test_grade_answer_parse_error` | Bedrock が無効な JSON を返す | `BedrockParseError` raise | 🔵 |
| TC-BDK-006 | `test_grade_answer_missing_grade_field` | Bedrock が `{"reasoning": "..."}` を返す（grade 欠落） | `BedrockParseError` raise | 🔵 |
| TC-BDK-007 | `test_grade_answer_missing_reasoning_field` | Bedrock が `{"grade": 3}` を返す（reasoning 欠落） | `BedrockParseError` raise | 🔵 |
| TC-BDK-008 | `test_grade_answer_timeout` | Bedrock が `ReadTimeoutError` ClientError を返す | `BedrockTimeoutError` raise | 🔵 |
| TC-BDK-009 | `test_grade_answer_rate_limit` | Bedrock が `ThrottlingException` ClientError を返す | `BedrockRateLimitError` raise（リトライ後） | 🔵 |
| TC-BDK-010 | `test_grade_answer_internal_error` | Bedrock が `InternalServerException` を返す | `BedrockInternalError` raise（リトライ後） | 🔵 |
| TC-BDK-011 | `test_grade_answer_calls_get_grading_prompt` | prompt 関数のモック検証 | `get_grading_prompt` に正しい引数が渡される | 🔵 |

**テスト実装パターン**:
```python
class TestBedrockGradeAnswer:
    """BedrockService.grade_answer() テスト."""

    @pytest.fixture
    def mock_bedrock_client(self):
        return MagicMock()

    @pytest.fixture
    def bedrock_service(self, mock_bedrock_client):
        return BedrockService(bedrock_client=mock_bedrock_client)

    def _mock_invoke_response(self, mock_client, response_text):
        """Bedrock invoke_model のモックレスポンスを設定する."""
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps({
            "content": [{"text": response_text}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_body}

    def test_grade_answer_success(self, bedrock_service, mock_bedrock_client):
        """TC-BDK-001: 正常系で GradingResult が返る."""
        self._mock_invoke_response(
            mock_bedrock_client,
            '{"grade": 3, "reasoning": "Partially correct"}'
        )

        result = bedrock_service.grade_answer(
            card_front="日本の首都は？",
            card_back="東京",
            user_answer="京都",
        )

        assert isinstance(result, GradingResult)
        assert result.grade == 3
        assert result.reasoning == "Partially correct"
```

---

## 6. _parse_grading_result() 共通要件

### 6.1 Strands 版 (_parse_grading_result)

StrandsAIService のインスタンスメソッドとして実装する。

- **REQ-PARSE-001** 🔵: Markdown コードブロック (`\`\`\`json ... \`\`\``) 内の JSON を抽出できること。
  - *根拠*: _parse_generation_result() L194 の正規表現パターン
- **REQ-PARSE-002** 🔵: プレーン JSON テキストを直接パースできること。
  - *根拠*: _parse_generation_result() L198 のフォールバック
- **REQ-PARSE-003** 🔵: `grade` (int) と `reasoning` (str) を必須フィールドとして抽出すること。
  - *根拠*: note.md の _parse_grading_result() 仕様
- **REQ-PARSE-004** 🔵: JSON パースエラーは `AIParseError` にマッピングすること（`from e` で原因保持）。
  - *根拠*: _parse_generation_result() L202-203
- **REQ-PARSE-005** 🔵: 必須フィールド欠落は `AIParseError` にマッピングすること。
  - *根拠*: note.md の test_parse_grading_result_missing_grade, test_parse_grading_result_missing_reasoning
- **REQ-PARSE-006** 🔵: `grade` が int 変換不可な場合は `AIParseError` にマッピングすること。
  - *根拠*: note.md の test_parse_grading_result_invalid_grade

### 6.2 Bedrock 版 (_parse_json_response)

既存の汎用メソッドを再利用する。追加実装は不要。

- `_parse_json_response(response_text, required_fields=["grade", "reasoning"], context="grading")` で呼び出す。
- Markdown コードブロック対応、必須フィールドチェック、BedrockParseError マッピングは既存実装でカバー済み。

---

## 7. エラーハンドリングマッピング

### 7.1 例外階層

```
AIServiceError (基底)
├── AITimeoutError    → HTTP 504
├── AIRateLimitError  → HTTP 429
├── AIProviderError   → HTTP 503
├── AIParseError      → HTTP 500
└── AIInternalError   → HTTP 500
```

### 7.2 Strands エラーマッピング

| 発生元例外 | マッピング先 | 条件 | 信頼性 |
|-----------|------------|------|--------|
| `AIServiceError` (サブクラス含む) | そのまま re-raise | `isinstance(e, AIServiceError)` | 🔵 |
| `TimeoutError` | `AITimeoutError` | Python 組み込み例外 | 🔵 |
| `ConnectionError` | `AIProviderError` | Python 組み込み例外 | 🔵 |
| `ClientError` (ThrottlingException 等) | `AIRateLimitError` | `_is_rate_limit_error(e)` が True | 🟡 |
| エラーメッセージに "timeout" 含む | `AITimeoutError` | 文字列マッチング | 🔵 |
| エラーメッセージに "connection" 含む | `AIProviderError` | 文字列マッチング | 🔵 |
| その他 | `AIServiceError` | フォールバック | 🔵 |

### 7.3 Bedrock エラーマッピング

| 発生元例外 | マッピング先 | 条件 | 信頼性 |
|-----------|------------|------|--------|
| `ClientError` (ReadTimeoutError) | `BedrockTimeoutError` | error_code チェック | 🔵 |
| `ClientError` (ThrottlingException) | `BedrockRateLimitError` | error_code チェック | 🔵 |
| `ClientError` (InternalServerException) | `BedrockInternalError` | error_code チェック | 🔵 |
| JSON パースエラー | `BedrockParseError` | `json.JSONDecodeError` | 🔵 |
| 必須フィールド欠落 | `BedrockParseError` | フィールドチェック | 🔵 |

---

## 8. 同期メソッド制約

### 8.1 設計制約

- **REQ-SYNC-001** 🔵: 全ての `grade_answer()` メソッドは同期メソッド（`def`）として実装すること。`async def` は使用しない。
  - *根拠*: note.md 注意事項 1「同期メソッド（async 不使用）」、ai_service.py Protocol 定義
- **REQ-SYNC-002** 🔵: Strands Agent の呼び出しは `agent(prompt)` で同期的に行うこと（`asyncio.wait_for` は使用しない）。
  - *根拠*: generate_cards() L133-134 の同期呼び出しパターン

**注意**: TASK-0059.md の実装例コード（Section 3, 4）では `async def` と `asyncio.wait_for` が使用されているが、これは誤りである。note.md の注意事項と既存実装パターン（ai_service.py Protocol、generate_cards() 実装）に基づき、**同期メソッド**で実装する。

---

## テストファイル構成サマリー

### 新規作成ファイル

| ファイル | テストクラス | TC 数 |
|---------|------------|-------|
| `backend/tests/unit/test_grading_models.py` | `TestGradeAnswerRequestValidation` | 9 |
| | `TestGradeAnswerResponseSerialization` | 8 |

### 既存修正ファイル

| ファイル | テストクラス | TC 数 | 変更内容 |
|---------|------------|-------|---------|
| `backend/tests/unit/test_strands_service.py` | `TestStrandsGradeAnswer` (新規追加) | 18 | grade_answer テスト追加 |
| | `TestStrandsServiceStubs` (既存修正) | -2 | stub テスト削除 |
| `backend/tests/unit/test_bedrock.py` | `TestBedrockGradeAnswer` (新規追加) | 11 | grade_answer テスト追加 |

### テスト合計

| カテゴリ | 件数 |
|---------|------|
| GradeAnswerRequest バリデーション | 9 |
| GradeAnswerResponse シリアライズ | 8 |
| StrandsAIService.grade_answer() | 18 |
| BedrockAIService.grade_answer() | 11 |
| **合計** | **46** |

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 44 | 95.7% |
| 🟡 黄信号 | 2 | 4.3% |
| 🔴 赤信号 | 0 | 0% |

**品質評価**: 高品質（青信号 95.7%、赤信号なし）

### 🟡 黄信号の項目

1. **REQ-PRM-005** (language フォールバック): 要件定義書 4.7 節からの推測。既存テスト TC-014 で検証済みだが、仕様として明示されていない。
2. **TC-STR-015** (レート制限テスト): Strands SDK が内部的に botocore ClientError をそのまま raise するかは SDK バージョン依存。_is_rate_limit_error() ヘルパーが対応済みだが、SDK 更新で変わる可能性あり。

---

## 実装ファイルサマリー

### 新規作成

| ファイル | 内容 |
|---------|------|
| `backend/src/models/grading.py` | GradeAnswerRequest, GradeAnswerResponse Pydantic モデル |
| `backend/tests/unit/test_grading_models.py` | Pydantic モデルバリデーションテスト |

### 既存修正

| ファイル | 変更内容 |
|---------|---------|
| `backend/src/services/strands_service.py` | `grade_answer()` 実装 + `_parse_grading_result()` 追加、NotImplementedError 除去 |
| `backend/src/services/prompts/grading.py` | 変更なし（既存実装で充足） |
| `backend/src/services/bedrock.py` | 変更なし（既存実装で充足） |
| `backend/tests/unit/test_strands_service.py` | `TestStrandsGradeAnswer` 追加、`TestStrandsServiceStubs` 修正 |
| `backend/tests/unit/test_bedrock.py` | `TestBedrockGradeAnswer` 追加 |
| `backend/tests/unit/test_grading_prompts.py` | 変更なし（既存テストで充足） |

---

## 依存関係

```
TASK-0054 (AI エラーハンドリング) ──┐
                                    ├── TASK-0059 (本タスク) ──> TASK-0060 (grade-ai エンドポイント)
TASK-0057 (Strands SDK 統合) ──────┘
```

---

*作成日*: 2026-02-24
*タスク*: TASK-0059 TDD Requirements Phase
*信頼性*: 🔵 44件 (95.7%) / 🟡 2件 (4.3%) / 🔴 0件 (0%)
