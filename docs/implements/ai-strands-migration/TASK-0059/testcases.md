# TASK-0059: 回答採点モデル・プロンプト・AI実装 - テストケース定義

## 概要

本ドキュメントは TASK-0059 の TDD Red フェーズで実装するテストケースを定義する。
対象は以下の 4 領域:

1. **Pydantic モデル** (`GradeAnswerRequest` / `GradeAnswerResponse`) のバリデーション
2. **採点プロンプト** (既存テストの充足確認)
3. **StrandsAIService.grade_answer()** の正常系・異常系テスト
4. **BedrockAIService.grade_answer()** の正常系・異常系テスト

**テストファイル構成**:

| ファイル | 状態 | テストクラス |
|---------|------|------------|
| `backend/tests/unit/test_grading_models.py` | **新規作成** | `TestGradeAnswerRequestValidation`, `TestGradeAnswerResponseSerialization` |
| `backend/tests/unit/test_grading_prompts.py` | 既存（変更なし） | 既存テストで充足 |
| `backend/tests/unit/test_strands_service.py` | **既存に追加** | `TestStrandsGradeAnswer` 追加 + `TestStrandsServiceStubs` 修正 |
| `backend/tests/unit/test_bedrock.py` | **既存に追加** | `TestBedrockGradeAnswer` 追加 |

---

## 信頼性レベル凡例

| レベル | 意味 |
|--------|------|
| 🔵 青信号 | 要件・設計文書から確定。変更リスク低い |
| 🟡 黄信号 | 推測または SDK バージョン依存。実装時に調整の可能性あり |
| 🔴 赤信号 | 未確定または高リスク。実装前に確認が必要 |

---

## 1. Pydantic モデルテスト（新規作成）

### ファイル: `backend/tests/unit/test_grading_models.py`

**インポート対象**: `backend/src/models/grading.py` (TASK-0059 で新規作成)

**参照パターン**: `backend/src/models/generate.py` の `GenerateCardsRequest`

---

### 1.1 TestGradeAnswerRequestValidation

GradeAnswerRequest の `user_answer` フィールドに対するバリデーションテスト。

| TC ID | テスト名 | 入力 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-MOD-001 | `test_valid_user_answer_minimum` | `user_answer="a"` (1 文字) | インスタンス生成成功、`req.user_answer == "a"` | 🔵 |
| TC-MOD-002 | `test_valid_user_answer_maximum` | `user_answer="a" * 2000` (2000 文字) | インスタンス生成成功 | 🔵 |
| TC-MOD-003 | `test_valid_user_answer_japanese` | `user_answer="東京です"` | インスタンス生成成功、値が保持される | 🔵 |
| TC-MOD-004 | `test_valid_user_answer_with_leading_trailing_spaces` | `user_answer=" hello "` | インスタンス生成成功（空白のみでなければ通す） | 🔵 |
| TC-MOD-005 | `test_empty_user_answer` | `user_answer=""` | `ValidationError` raise | 🔵 |
| TC-MOD-006 | `test_whitespace_only_user_answer_spaces` | `user_answer="   "` | `ValidationError` raise | 🔵 |
| TC-MOD-007 | `test_whitespace_only_user_answer_mixed` | `user_answer="  \t\n  "` | `ValidationError` raise | 🔵 |
| TC-MOD-008 | `test_user_answer_too_long` | `user_answer="a" * 2001` (2001 文字) | `ValidationError` raise | 🔵 |
| TC-MOD-009 | `test_user_answer_missing` | `GradeAnswerRequest()` (フィールド未指定) | `ValidationError` raise | 🔵 |

**テスト実装パターン**:

```python
import pytest
from pydantic import ValidationError

from models.grading import GradeAnswerRequest


class TestGradeAnswerRequestValidation:
    """GradeAnswerRequest バリデーションテスト."""

    def test_valid_user_answer_minimum(self):
        """TC-MOD-001: 最小長 (1文字) でバリデーション OK."""
        req = GradeAnswerRequest(user_answer="a")
        assert req.user_answer == "a"

    def test_valid_user_answer_maximum(self):
        """TC-MOD-002: 最大長 (2000文字) でバリデーション OK."""
        req = GradeAnswerRequest(user_answer="a" * 2000)
        assert len(req.user_answer) == 2000

    def test_valid_user_answer_japanese(self):
        """TC-MOD-003: 日本語テキストでバリデーション OK."""
        req = GradeAnswerRequest(user_answer="東京です")
        assert req.user_answer == "東京です"

    def test_valid_user_answer_with_leading_trailing_spaces(self):
        """TC-MOD-004: 前後に空白があっても内容があれば OK."""
        req = GradeAnswerRequest(user_answer=" hello ")
        assert req.user_answer == " hello "

    def test_empty_user_answer(self):
        """TC-MOD-005: 空文字列で ValidationError."""
        with pytest.raises(ValidationError):
            GradeAnswerRequest(user_answer="")

    def test_whitespace_only_user_answer_spaces(self):
        """TC-MOD-006: 空白のみで ValidationError."""
        with pytest.raises(ValidationError):
            GradeAnswerRequest(user_answer="   ")

    def test_whitespace_only_user_answer_mixed(self):
        """TC-MOD-007: タブ/改行混在の空白のみで ValidationError."""
        with pytest.raises(ValidationError):
            GradeAnswerRequest(user_answer="  \t\n  ")

    def test_user_answer_too_long(self):
        """TC-MOD-008: 2001 文字で ValidationError."""
        with pytest.raises(ValidationError):
            GradeAnswerRequest(user_answer="a" * 2001)

    def test_user_answer_missing(self):
        """TC-MOD-009: フィールド未指定で ValidationError."""
        with pytest.raises(ValidationError):
            GradeAnswerRequest()
```

---

### 1.2 TestGradeAnswerResponseSerialization

GradeAnswerResponse のフィールド制約とシリアライゼーションテスト。

| TC ID | テスト名 | 入力 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-MOD-010 | `test_response_all_fields` | 全フィールド指定 | 全フィールドが正しく保持される | 🔵 |
| TC-MOD-011 | `test_response_json_serialization` | `.model_dump()` | 全フィールドが辞書に含まれる | 🔵 |
| TC-MOD-012 | `test_response_grade_boundary_zero` | `grade=0` | バリデーション OK | 🔵 |
| TC-MOD-013 | `test_response_grade_boundary_five` | `grade=5` | バリデーション OK | 🔵 |
| TC-MOD-014 | `test_response_grade_below_range` | `grade=-1` | `ValidationError` raise | 🔵 |
| TC-MOD-015 | `test_response_grade_above_range` | `grade=6` | `ValidationError` raise | 🔵 |
| TC-MOD-016 | `test_response_grading_info_default_empty` | `grading_info` 未指定 | `grading_info` が `{}` (空辞書) | 🔵 |
| TC-MOD-017 | `test_response_grading_info_with_metadata` | メタ情報指定 | メタ情報が正しく保持される | 🔵 |

**テスト実装パターン**:

```python
from models.grading import GradeAnswerResponse


class TestGradeAnswerResponseSerialization:
    """GradeAnswerResponse シリアライゼーションテスト."""

    def _make_response(self, **overrides):
        """テスト用レスポンスインスタンスを作成するヘルパー."""
        defaults = {
            "grade": 4,
            "reasoning": "Correct with minor hesitation",
            "card_front": "日本の首都は？",
            "card_back": "東京",
            "grading_info": {"model_used": "strands", "processing_time_ms": 1234},
        }
        defaults.update(overrides)
        return GradeAnswerResponse(**defaults)

    def test_response_all_fields(self):
        """TC-MOD-010: 全フィールド指定でインスタンス生成."""
        resp = self._make_response()
        assert resp.grade == 4
        assert resp.reasoning == "Correct with minor hesitation"
        assert resp.card_front == "日本の首都は？"
        assert resp.card_back == "東京"
        assert resp.grading_info == {"model_used": "strands", "processing_time_ms": 1234}

    def test_response_json_serialization(self):
        """TC-MOD-011: model_dump() で全フィールドが含まれる."""
        resp = self._make_response()
        data = resp.model_dump()
        assert "grade" in data
        assert "reasoning" in data
        assert "card_front" in data
        assert "card_back" in data
        assert "grading_info" in data

    def test_response_grade_boundary_zero(self):
        """TC-MOD-012: grade=0 でバリデーション OK."""
        resp = self._make_response(grade=0)
        assert resp.grade == 0

    def test_response_grade_boundary_five(self):
        """TC-MOD-013: grade=5 でバリデーション OK."""
        resp = self._make_response(grade=5)
        assert resp.grade == 5

    def test_response_grade_below_range(self):
        """TC-MOD-014: grade=-1 で ValidationError."""
        with pytest.raises(ValidationError):
            self._make_response(grade=-1)

    def test_response_grade_above_range(self):
        """TC-MOD-015: grade=6 で ValidationError."""
        with pytest.raises(ValidationError):
            self._make_response(grade=6)

    def test_response_grading_info_default_empty(self):
        """TC-MOD-016: grading_info 未指定で空辞書."""
        resp = GradeAnswerResponse(
            grade=3,
            reasoning="OK",
            card_front="Q",
            card_back="A",
        )
        assert resp.grading_info == {}

    def test_response_grading_info_with_metadata(self):
        """TC-MOD-017: メタ情報が正しく保持される."""
        info = {"model_used": "strands_bedrock", "processing_time_ms": 567}
        resp = self._make_response(grading_info=info)
        assert resp.grading_info["model_used"] == "strands_bedrock"
        assert resp.grading_info["processing_time_ms"] == 567
```

---

## 2. 採点プロンプトテスト（既存充足確認）

### ファイル: `backend/tests/unit/test_grading_prompts.py`（既存、変更なし）

既存テストは以下のテストケースで TASK-0059 に必要なプロンプト要件を十分にカバーしている:

| 既存 TC ID | テストクラス | カバー内容 |
|-----------|------------|----------|
| TC-005 | `TestSM2GradeDefinitions` | SM2_GRADE_DEFINITIONS にグレード 0-5 が含まれること |
| TC-006 | `TestGradingSystemPromptContent` | GRADING_SYSTEM_PROMPT に SM-2 基準と JSON 指示が含まれること |
| TC-007 | `TestGetGradingPromptJapanese` | 日本語プロンプト生成、card_front/card_back/user_answer 埋め込み |
| TC-008 | `TestGetGradingPromptEnglish` | 英語プロンプト生成、English 指示の含有 |
| TC-014 | `TestGradingPromptLanguageFallback` | 未知の language でフォールバック |
| TC-016 | `TestGradingPromptDefaultLanguage` | language 省略時のデフォルト "ja" |
| TC-021 | `TestGradingExports` | エクスポートシンボルの型確認 |
| TC-023 | `TestGradingSystemPromptJsonFields` | JSON フィールド (grade, reasoning, feedback) の指示確認 |

**結論**: 追加テストは不要。既存テストが全てパスすれば TASK-0059 のプロンプト要件は充足される。

---

## 3. StrandsAIService.grade_answer() テスト（既存に追加）

### ファイル: `backend/tests/unit/test_strands_service.py`

**追加テストクラス**: `TestStrandsGradeAnswer`
**モックパターン**: 既存の `_make_mock_agent_instance()` ヘルパーを再利用

---

### 3.1 TestStrandsGradeAnswer（新規追加）

#### 3.1.1 正常系テスト

| TC ID | テスト名 | 内容 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-STR-001 | `test_grade_answer_success_perfect` | Agent が `{"grade": 5, "reasoning": "Perfect"}` を返す | `GradingResult(grade=5, reasoning="Perfect", ...)` | 🔵 |
| TC-STR-002 | `test_grade_answer_success_zero` | Agent が `{"grade": 0, "reasoning": "No answer"}` を返す | `GradingResult(grade=0, ...)` | 🔵 |
| TC-STR-003 | `test_grade_answer_success_partial` | Agent が `{"grade": 3, "reasoning": "Partially correct"}` を返す | `GradingResult(grade=3, ...)` | 🔵 |
| TC-STR-004 | `test_grade_answer_markdown_wrapped_response` | Agent が `` ```json ... ``` `` で囲んだ JSON を返す | 正しくパースされる | 🔵 |
| TC-STR-005 | `test_grade_answer_model_used` | 正常系レスポンス | `result.model_used` が `self.model_used` と一致 | 🔵 |
| TC-STR-006 | `test_grade_answer_processing_time_ms` | 正常系レスポンス | `result.processing_time_ms` が 0 以上の整数 | 🔵 |

#### 3.1.2 引数伝搬テスト

| TC ID | テスト名 | 内容 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-STR-007 | `test_grade_answer_passes_correct_args_to_prompt` | `get_grading_prompt` への引数検証 | card_front, card_back, user_answer, language が正しく渡される | 🔵 |
| TC-STR-008 | `test_grade_answer_language_ja` | `language="ja"` で呼び出し | `get_grading_prompt` に `language="ja"` が渡される | 🔵 |
| TC-STR-009 | `test_grade_answer_language_en` | `language="en"` で呼び出し | `get_grading_prompt` に `language="en"` が渡される | 🔵 |

#### 3.1.3 パースエラーテスト

| TC ID | テスト名 | 内容 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-STR-010 | `test_grade_answer_parse_error_invalid_json` | Agent が非 JSON テキストを返す | `AIParseError` raise | 🔵 |
| TC-STR-011 | `test_grade_answer_parse_error_missing_grade` | Agent が `{"reasoning": "..."}` を返す | `AIParseError` raise | 🔵 |
| TC-STR-012 | `test_grade_answer_parse_error_missing_reasoning` | Agent が `{"grade": 5}` を返す | `AIParseError` raise | 🔵 |
| TC-STR-013 | `test_grade_answer_parse_error_invalid_grade_type` | Agent が `{"grade": "five", "reasoning": "..."}` を返す | `AIParseError` raise | 🔵 |

#### 3.1.4 エラーハンドリングテスト

| TC ID | テスト名 | 内容 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-STR-014 | `test_grade_answer_timeout` | Agent が `TimeoutError` を raise | `AITimeoutError` raise | 🔵 |
| TC-STR-015 | `test_grade_answer_rate_limit` | Agent が botocore `ClientError(ThrottlingException)` を raise | `AIRateLimitError` raise | 🟡 |
| TC-STR-016 | `test_grade_answer_connection_error` | Agent が `ConnectionError` を raise | `AIProviderError` raise | 🔵 |
| TC-STR-017 | `test_grade_answer_unknown_exception` | Agent が `RuntimeError` を raise | `AIServiceError` raise | 🔵 |
| TC-STR-018 | `test_grade_answer_exception_chain_preserved` | Agent がエラーを raise | `__cause__` が保持される | 🔵 |

**テスト実装パターン**:

```python
class TestStrandsGradeAnswer:
    """StrandsAIService.grade_answer() テスト."""

    # --- 正常系 ---

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

    def test_grade_answer_success_zero(self):
        """TC-STR-002: 完全不正解で grade=0 が返る."""
        response_json = json.dumps({"grade": 0, "reasoning": "No answer provided"})
        mock_agent_instance = _make_mock_agent_instance(response_json)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            result = service.grade_answer(
                card_front="日本の首都は？",
                card_back="東京",
                user_answer="わかりません",
            )

        assert result.grade == 0

    def test_grade_answer_success_partial(self):
        """TC-STR-003: 部分正解で grade=3 が返る."""
        response_json = json.dumps({"grade": 3, "reasoning": "Partially correct"})
        mock_agent_instance = _make_mock_agent_instance(response_json)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            result = service.grade_answer(
                card_front="光合成の化学式は？",
                card_back="6CO2 + 6H2O → C6H12O6 + 6O2",
                user_answer="CO2と水から糖ができる",
            )

        assert result.grade == 3

    def test_grade_answer_markdown_wrapped_response(self):
        """TC-STR-004: Markdown コードブロック内 JSON が正しくパースされる."""
        response_text = '```json\n{"grade": 4, "reasoning": "Good answer"}\n```'
        mock_agent_instance = _make_mock_agent_instance(response_text)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            result = service.grade_answer(
                card_front="Q", card_back="A", user_answer="A",
            )

        assert result.grade == 4
        assert result.reasoning == "Good answer"

    def test_grade_answer_model_used(self):
        """TC-STR-005: model_used が self.model_used と一致する."""
        response_json = json.dumps({"grade": 5, "reasoning": "Perfect"})
        mock_agent_instance = _make_mock_agent_instance(response_json)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            result = service.grade_answer(
                card_front="Q", card_back="A", user_answer="A",
            )

        assert result.model_used == service.model_used

    def test_grade_answer_processing_time_ms(self):
        """TC-STR-006: processing_time_ms が 0 以上の整数."""
        response_json = json.dumps({"grade": 5, "reasoning": "Perfect"})
        mock_agent_instance = _make_mock_agent_instance(response_json)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            result = service.grade_answer(
                card_front="Q", card_back="A", user_answer="A",
            )

        assert isinstance(result.processing_time_ms, int)
        assert result.processing_time_ms >= 0

    # --- 引数伝搬 ---

    @patch("services.strands_service.get_grading_prompt", return_value="mocked prompt")
    def test_grade_answer_passes_correct_args_to_prompt(self, mock_prompt):
        """TC-STR-007: get_grading_prompt に正しい引数が渡される."""
        response_json = json.dumps({"grade": 5, "reasoning": "Perfect"})
        mock_agent_instance = _make_mock_agent_instance(response_json)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            service.grade_answer(
                card_front="日本の首都は？",
                card_back="東京",
                user_answer="東京",
                language="ja",
            )

        mock_prompt.assert_called_once_with(
            card_front="日本の首都は？",
            card_back="東京",
            user_answer="東京",
            language="ja",
        )

    @patch("services.strands_service.get_grading_prompt", return_value="mocked prompt")
    def test_grade_answer_language_ja(self, mock_prompt):
        """TC-STR-008: language='ja' が get_grading_prompt に渡される."""
        response_json = json.dumps({"grade": 5, "reasoning": "Perfect"})
        mock_agent_instance = _make_mock_agent_instance(response_json)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            service.grade_answer(
                card_front="Q", card_back="A", user_answer="A", language="ja",
            )

        assert mock_prompt.call_args.kwargs["language"] == "ja"

    @patch("services.strands_service.get_grading_prompt", return_value="mocked prompt")
    def test_grade_answer_language_en(self, mock_prompt):
        """TC-STR-009: language='en' が get_grading_prompt に渡される."""
        response_json = json.dumps({"grade": 5, "reasoning": "Perfect"})
        mock_agent_instance = _make_mock_agent_instance(response_json)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            service.grade_answer(
                card_front="Q", card_back="A", user_answer="A", language="en",
            )

        assert mock_prompt.call_args.kwargs["language"] == "en"

    # --- パースエラー ---

    def test_grade_answer_parse_error_invalid_json(self):
        """TC-STR-010: 非 JSON レスポンスで AIParseError."""
        mock_agent_instance = _make_mock_agent_instance("This is not valid JSON")

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

            with pytest.raises(AIParseError):
                service.grade_answer(
                    card_front="Q", card_back="A", user_answer="A",
                )

    def test_grade_answer_parse_error_missing_grade(self):
        """TC-STR-011: grade フィールド欠落で AIParseError."""
        response_json = json.dumps({"reasoning": "Some reasoning"})
        mock_agent_instance = _make_mock_agent_instance(response_json)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

            with pytest.raises(AIParseError):
                service.grade_answer(
                    card_front="Q", card_back="A", user_answer="A",
                )

    def test_grade_answer_parse_error_missing_reasoning(self):
        """TC-STR-012: reasoning フィールド欠落で AIParseError."""
        response_json = json.dumps({"grade": 5})
        mock_agent_instance = _make_mock_agent_instance(response_json)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

            with pytest.raises(AIParseError):
                service.grade_answer(
                    card_front="Q", card_back="A", user_answer="A",
                )

    def test_grade_answer_parse_error_invalid_grade_type(self):
        """TC-STR-013: grade が数値変換不可で AIParseError."""
        response_json = json.dumps({"grade": "five", "reasoning": "Some reasoning"})
        mock_agent_instance = _make_mock_agent_instance(response_json)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

            with pytest.raises(AIParseError):
                service.grade_answer(
                    card_front="Q", card_back="A", user_answer="A",
                )

    # --- エラーハンドリング ---

    def test_grade_answer_timeout(self):
        """TC-STR-014: TimeoutError で AITimeoutError."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.side_effect = TimeoutError("Agent timed out")

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

            with pytest.raises(AITimeoutError):
                service.grade_answer(
                    card_front="Q", card_back="A", user_answer="A",
                )

    def test_grade_answer_rate_limit(self):
        """TC-STR-015: ThrottlingException で AIRateLimitError. (🟡 SDK 依存)"""
        from botocore.exceptions import ClientError
        mock_agent_instance = MagicMock()
        mock_agent_instance.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate limit"}},
            "InvokeModel",
        )

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

            with pytest.raises(AIRateLimitError):
                service.grade_answer(
                    card_front="Q", card_back="A", user_answer="A",
                )

    def test_grade_answer_connection_error(self):
        """TC-STR-016: ConnectionError で AIProviderError."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.side_effect = ConnectionError("Connection refused")

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

            with pytest.raises(AIProviderError):
                service.grade_answer(
                    card_front="Q", card_back="A", user_answer="A",
                )

    def test_grade_answer_unknown_exception(self):
        """TC-STR-017: RuntimeError で AIServiceError."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.side_effect = RuntimeError("Something unexpected")

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

            with pytest.raises(AIServiceError):
                service.grade_answer(
                    card_front="Q", card_back="A", user_answer="A",
                )

    def test_grade_answer_exception_chain_preserved(self):
        """TC-STR-018: 例外チェーン (__cause__) が保持される."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.side_effect = ConnectionError("Connection refused")

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

            with pytest.raises(AIProviderError) as exc_info:
                service.grade_answer(
                    card_front="Q", card_back="A", user_answer="A",
                )

            assert exc_info.value.__cause__ is not None
```

---

### 3.2 TestStrandsServiceStubs 修正（既存テスト影響）

TASK-0059 実装後、`grade_answer()` は `NotImplementedError` を raise しなくなるため、以下の既存テストを修正する:

| 既存 TC ID | テスト名 | 変更内容 |
|-----------|---------|---------|
| TC-STUB-001 | `test_grade_answer_raises_not_implemented` | **削除** (grade_answer が正常動作するようになるため) |
| TC-STUB-003 | `test_not_implemented_error_message_contains_phase3` | **修正**: grade_answer の検証部分を削除し、get_learning_advice のみの検証に変更 |

**修正後のコード**:

```python
class TestStrandsServiceStubs:
    """Phase 3 スタブメソッドテスト."""

    # TC-STUB-001 は削除（grade_answer は実装済み）

    def test_get_learning_advice_raises_not_implemented(self):
        """TC-STUB-002: get_learning_advice() は NotImplementedError を raise する."""
        # (変更なし)

    def test_not_implemented_error_message_contains_phase3(self):
        """TC-STUB-003: NotImplementedError のメッセージに 'Phase 3' を含む."""
        with patch("services.strands_service.Agent"), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

        # get_learning_advice のみ検証（grade_answer は実装済み）
        with pytest.raises(NotImplementedError, match="Phase 3"):
            service.get_learning_advice(review_summary={})
```

---

## 4. BedrockAIService.grade_answer() テスト（既存に追加）

### ファイル: `backend/tests/unit/test_bedrock.py`

**追加テストクラス**: `TestBedrockGradeAnswer`
**モックパターン**: 既存の `mock_bedrock_client` / `bedrock_service` フィクスチャパターンを再利用
**補足**: BedrockService の grade_answer() は既に実装済み (L167-218)。テストは既存実装の動作を確認する。

---

### 4.1 TestBedrockGradeAnswer（新規追加）

#### 4.1.1 正常系テスト

| TC ID | テスト名 | 内容 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-BDK-001 | `test_grade_answer_success` | Bedrock が `{"grade": 3, "reasoning": "Partially correct"}` を返す | `GradingResult(grade=3, reasoning="Partially correct", ...)` | 🔵 |
| TC-BDK-002 | `test_grade_answer_success_with_markdown` | Bedrock が Markdown コードブロック内の JSON を返す | 正しくパースされる | 🔵 |
| TC-BDK-003 | `test_grade_answer_model_used` | 正常系レスポンス | `result.model_used` が `self.model_id` と一致 | 🔵 |
| TC-BDK-004 | `test_grade_answer_processing_time_ms` | 正常系レスポンス | `result.processing_time_ms` が 0 以上の整数 | 🔵 |

#### 4.1.2 パースエラーテスト

| TC ID | テスト名 | 内容 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-BDK-005 | `test_grade_answer_parse_error` | Bedrock が無効な JSON を返す | `BedrockParseError` raise | 🔵 |
| TC-BDK-006 | `test_grade_answer_missing_grade_field` | Bedrock が `{"reasoning": "..."}` を返す | `BedrockParseError` raise | 🔵 |
| TC-BDK-007 | `test_grade_answer_missing_reasoning_field` | Bedrock が `{"grade": 3}` を返す | `BedrockParseError` raise | 🔵 |

#### 4.1.3 API エラーテスト

| TC ID | テスト名 | 内容 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-BDK-008 | `test_grade_answer_timeout` | Bedrock が `ReadTimeoutError` ClientError を返す | `BedrockTimeoutError` raise | 🔵 |
| TC-BDK-009 | `test_grade_answer_rate_limit` | Bedrock が `ThrottlingException` ClientError を返す | `BedrockRateLimitError` raise（リトライ後） | 🔵 |
| TC-BDK-010 | `test_grade_answer_internal_error` | Bedrock が `InternalServerException` を返す | `BedrockInternalError` raise（リトライ後） | 🔵 |

#### 4.1.4 引数伝搬テスト

| TC ID | テスト名 | 内容 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-BDK-011 | `test_grade_answer_calls_get_grading_prompt` | prompt 関数のモック検証 | `get_grading_prompt` に正しい引数が渡される | 🔵 |

**テスト実装パターン**:

```python
from services.ai_service import GradingResult


class TestBedrockGradeAnswer:
    """BedrockService.grade_answer() テスト."""

    @pytest.fixture
    def mock_bedrock_client(self):
        return MagicMock()

    @pytest.fixture
    def bedrock_service(self, mock_bedrock_client):
        return BedrockService(bedrock_client=mock_bedrock_client)

    def _mock_invoke_response(self, mock_client, response_text):
        """Bedrock invoke_model のモックレスポンスを設定するヘルパー."""
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps({
            "content": [{"text": response_text}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_body}

    # --- 正常系 ---

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

    def test_grade_answer_success_with_markdown(self, bedrock_service, mock_bedrock_client):
        """TC-BDK-002: Markdown コードブロック内 JSON が正しくパースされる."""
        self._mock_invoke_response(
            mock_bedrock_client,
            '```json\n{"grade": 4, "reasoning": "Good answer"}\n```'
        )

        result = bedrock_service.grade_answer(
            card_front="Q", card_back="A", user_answer="A",
        )

        assert result.grade == 4
        assert result.reasoning == "Good answer"

    def test_grade_answer_model_used(self, mock_bedrock_client):
        """TC-BDK-003: model_used が self.model_id と一致する."""
        service = BedrockService(
            model_id="test-model-id",
            bedrock_client=mock_bedrock_client,
        )
        self._mock_invoke_response(
            mock_bedrock_client,
            '{"grade": 5, "reasoning": "Perfect"}'
        )

        result = service.grade_answer(
            card_front="Q", card_back="A", user_answer="A",
        )

        assert result.model_used == "test-model-id"

    def test_grade_answer_processing_time_ms(self, bedrock_service, mock_bedrock_client):
        """TC-BDK-004: processing_time_ms が 0 以上の整数."""
        self._mock_invoke_response(
            mock_bedrock_client,
            '{"grade": 5, "reasoning": "Perfect"}'
        )

        result = bedrock_service.grade_answer(
            card_front="Q", card_back="A", user_answer="A",
        )

        assert isinstance(result.processing_time_ms, int)
        assert result.processing_time_ms >= 0

    # --- パースエラー ---

    def test_grade_answer_parse_error(self, bedrock_service, mock_bedrock_client):
        """TC-BDK-005: 無効な JSON で BedrockParseError."""
        self._mock_invoke_response(
            mock_bedrock_client,
            "This is not valid JSON"
        )

        with pytest.raises(BedrockParseError):
            bedrock_service.grade_answer(
                card_front="Q", card_back="A", user_answer="A",
            )

    def test_grade_answer_missing_grade_field(self, bedrock_service, mock_bedrock_client):
        """TC-BDK-006: grade フィールド欠落で BedrockParseError."""
        self._mock_invoke_response(
            mock_bedrock_client,
            '{"reasoning": "Some reasoning"}'
        )

        with pytest.raises(BedrockParseError):
            bedrock_service.grade_answer(
                card_front="Q", card_back="A", user_answer="A",
            )

    def test_grade_answer_missing_reasoning_field(self, bedrock_service, mock_bedrock_client):
        """TC-BDK-007: reasoning フィールド欠落で BedrockParseError."""
        self._mock_invoke_response(
            mock_bedrock_client,
            '{"grade": 3}'
        )

        with pytest.raises(BedrockParseError):
            bedrock_service.grade_answer(
                card_front="Q", card_back="A", user_answer="A",
            )

    # --- API エラー ---

    def test_grade_answer_timeout(self, bedrock_service, mock_bedrock_client):
        """TC-BDK-008: ReadTimeoutError で BedrockTimeoutError."""
        mock_bedrock_client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ReadTimeoutError", "Message": "Timeout"}},
            "InvokeModel",
        )

        with pytest.raises(BedrockTimeoutError):
            bedrock_service.grade_answer(
                card_front="Q", card_back="A", user_answer="A",
            )

    def test_grade_answer_rate_limit(self, bedrock_service, mock_bedrock_client):
        """TC-BDK-009: ThrottlingException で BedrockRateLimitError（リトライ後）."""
        mock_bedrock_client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate limit"}},
            "InvokeModel",
        )

        with pytest.raises(BedrockRateLimitError):
            bedrock_service.grade_answer(
                card_front="Q", card_back="A", user_answer="A",
            )

        # リトライ: initial + 2 retries = 3 calls
        assert mock_bedrock_client.invoke_model.call_count == 3

    def test_grade_answer_internal_error(self, bedrock_service, mock_bedrock_client):
        """TC-BDK-010: InternalServerException で BedrockInternalError（リトライ後）."""
        mock_bedrock_client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "InternalServerException", "Message": "Internal"}},
            "InvokeModel",
        )

        with pytest.raises(BedrockInternalError):
            bedrock_service.grade_answer(
                card_front="Q", card_back="A", user_answer="A",
            )

        assert mock_bedrock_client.invoke_model.call_count == 3

    # --- 引数伝搬 ---

    def test_grade_answer_calls_get_grading_prompt(self, bedrock_service, mock_bedrock_client):
        """TC-BDK-011: get_grading_prompt に正しい引数が渡される."""
        self._mock_invoke_response(
            mock_bedrock_client,
            '{"grade": 5, "reasoning": "Perfect"}'
        )

        with patch("services.bedrock.get_grading_prompt", return_value="mocked") as mock_prompt:
            bedrock_service.grade_answer(
                card_front="日本の首都は？",
                card_back="東京",
                user_answer="東京",
                language="en",
            )

        mock_prompt.assert_called_once_with(
            card_front="日本の首都は？",
            card_back="東京",
            user_answer="東京",
            language="en",
        )
```

---

## 5. テストサマリー

### テストケース合計

| カテゴリ | テストクラス | 件数 |
|---------|------------|------|
| GradeAnswerRequest バリデーション | `TestGradeAnswerRequestValidation` | 9 |
| GradeAnswerResponse シリアライズ | `TestGradeAnswerResponseSerialization` | 8 |
| 採点プロンプト | (既存テストで充足) | 0 (追加なし) |
| StrandsAIService.grade_answer() | `TestStrandsGradeAnswer` | 18 |
| BedrockAIService.grade_answer() | `TestBedrockGradeAnswer` | 11 |
| **合計 (新規追加)** | | **46** |

### 既存テスト修正

| テストクラス | 変更内容 |
|------------|---------|
| `TestStrandsServiceStubs` | TC-STUB-001 削除、TC-STUB-003 の grade_answer 部分を削除 (-2) |

### 信頼性レベル分布

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 45 | 97.8% |
| 🟡 黄信号 | 1 | 2.2% |
| 🔴 赤信号 | 0 | 0% |

### 🟡 黄信号の詳細

1. **TC-STR-015** (`test_grade_answer_rate_limit`): Strands SDK が内部的に botocore `ClientError` をそのまま raise するかは SDK バージョン依存。`_is_rate_limit_error()` ヘルパーが対応済みだが、SDK 更新で変わる可能性あり。

---

## 6. テストファイル・実装ファイル対応表

| テストファイル | テスト対象 | 状態 |
|-------------|----------|------|
| `backend/tests/unit/test_grading_models.py` | `backend/src/models/grading.py` | **新規作成** |
| `backend/tests/unit/test_grading_prompts.py` | `backend/src/services/prompts/grading.py` | 既存（変更なし） |
| `backend/tests/unit/test_strands_service.py` | `backend/src/services/strands_service.py` | **追加** |
| `backend/tests/unit/test_bedrock.py` | `backend/src/services/bedrock.py` | **追加** |

---

## 7. 重要な実装ノート

### 全メソッドは同期 (sync)

- `grade_answer()` は `def` で実装（`async def` 不使用）
- TASK-0059.md のコード例では `async def` が使用されているが、これは誤り
- `ai_service.py` Protocol 定義と `generate_cards()` 既存実装に従い、同期メソッドとする
- テストでは `asyncio` 関連のモックは不要

### GradingResult は ai_service.py の dataclass を使用

- `GradingResult(grade, reasoning, model_used, processing_time_ms)` は `ai_service.py` L38-44 で定義済み
- Pydantic モデル `GradeAnswerResponse` はAPI レスポンス用の別クラス（直接テスト対象）
- テストでは `result = service.grade_answer(...)` が `GradingResult` インスタンスを返すことを検証

### get_grading_prompt のインポートパス

- **Strands**: `services.strands_service` から `get_grading_prompt` を import する必要がある（`from services.prompts.grading import get_grading_prompt`）
- **Bedrock**: `services.bedrock` では既に `.prompts` から import 済み (`from .prompts import ... get_grading_prompt ...`)
- テスト内のモック対象パスはそれぞれ `"services.strands_service.get_grading_prompt"` / `"services.bedrock.get_grading_prompt"` とする

---

*作成日*: 2026-02-24
*タスク*: TASK-0059 TDD Testcases Phase
*信頼性*: 🔵 45件 (97.8%) / 🟡 1件 (2.2%) / 🔴 0件 (0%)
