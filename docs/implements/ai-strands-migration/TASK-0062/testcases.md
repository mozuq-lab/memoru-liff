# TASK-0062: 学習アドバイス AI 実装 + GET /advice エンドポイント - テストケース定義

## 概要

本ドキュメントは TASK-0062 の TDD Red フェーズで作成するテストケースの詳細を定義する。
3 つのテストファイルに分散して 55 件のテストケースを実装する。

### テストファイル構成

| ファイル | 対象コンポーネント | テストクラス | TC 数 |
|---------|-------------------|-------------|-------|
| `backend/tests/unit/test_strands_service.py` | StrandsAIService.get_learning_advice() | `TestStrandsAdvice` | 15 |
| `backend/tests/unit/test_bedrock.py` | BedrockService.get_learning_advice() | `TestBedrockGetLearningAdvice` | 12 |
| `backend/tests/unit/test_handler_advice.py` | advice_handler Lambda | 6 クラス | 28 |
| **合計** | | | **55** |

### 既存テスト削除（Green フェーズで実施）

| ファイル | テスト | 理由 |
|---------|--------|------|
| `test_strands_service.py` | TC-STUB-002 `test_get_learning_advice_raises_not_implemented` | get_learning_advice() 本実装により不要 |
| `test_strands_service.py` | TC-STUB-003 `test_not_implemented_error_message_contains_phase3` | 同上 |
| `test_handler_ai_service_factory.py` | TC-056-015 `test_advice_handler_returns_501` | advice_handler 本実装により不要 |

---

## Part A: StrandsAIService.get_learning_advice() テスト

**ファイル**: `backend/tests/unit/test_strands_service.py`
**テストクラス**: `TestStrandsAdvice`（既存ファイルに追加）

### フィクスチャ・ヘルパー

既存の `_make_mock_agent_instance()` ヘルパーをそのまま再利用する。

```python
# 既存ヘルパー（再利用）
def _make_mock_agent_instance(response_text: str) -> MagicMock:
    """Agent インスタンスのモックを作成するヘルパー."""
    mock_response = MagicMock()
    mock_response.__str__ = MagicMock(return_value=response_text)
    mock_agent = MagicMock()
    mock_agent.return_value = mock_response
    return mock_agent
```

### テストデータ

```python
# 正常な get_learning_advice レスポンス JSON
VALID_ADVICE_JSON = json.dumps({
    "advice_text": "数学の復習頻度を上げましょう。",
    "weak_areas": ["数学", "物理"],
    "recommendations": ["毎日10枚のカードを復習する", "弱点タグを重点的に復習"],
})

# Markdown コードブロック付きレスポンス
MARKDOWN_ADVICE_JSON = '```json\n' + VALID_ADVICE_JSON + '\n```'

# review_summary テストデータ
SAMPLE_REVIEW_SUMMARY = {"total_reviews": 50, "average_grade": 3.5}
```

### TC-STR-ADV-001: test_get_learning_advice_success

**テスト目的**: 正常な JSON レスポンスから LearningAdvice dataclass が返ることを確認。
**テスト要件**: REQ-STR-ADV-001, REQ-STR-ADV-004
**信頼性**: 🔵

```python
def test_get_learning_advice_success(self):
    """TC-STR-ADV-001: 有効なレスポンスで LearningAdvice が返される."""
    # Given: Agent が正常な JSON レスポンスを返す
    response_json = json.dumps({
        "advice_text": "数学の復習頻度を上げましょう。",
        "weak_areas": ["数学", "物理"],
        "recommendations": ["毎日10枚のカードを復習する", "弱点タグを重点的に復習"],
    })
    mock_agent_instance = _make_mock_agent_instance(response_json)

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()
        # When
        result = service.get_learning_advice(
            review_summary={"total_reviews": 50},
            language="ja",
        )

    # Then
    assert isinstance(result, LearningAdvice)
    assert result.advice_text == "数学の復習頻度を上げましょう。"
    assert isinstance(result.weak_areas, list)
    assert result.weak_areas == ["数学", "物理"]
    assert isinstance(result.recommendations, list)
    assert len(result.recommendations) == 2
```

### TC-STR-ADV-002: test_get_learning_advice_markdown_wrapped

**テスト目的**: Markdown コードブロック内の JSON が正しく解析されることを確認。
**テスト要件**: REQ-STR-ADV-007
**信頼性**: 🔵

```python
def test_get_learning_advice_markdown_wrapped(self):
    """TC-STR-ADV-002: Markdown コードブロック内 JSON が正しくパースされる."""
    # Given: Agent が ```json ... ``` 形式で返す
    response_text = '```json\n{"advice_text": "Study more math.", "weak_areas": ["math"], "recommendations": ["Review daily"]}\n```'
    mock_agent_instance = _make_mock_agent_instance(response_text)

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()
        # When
        result = service.get_learning_advice(
            review_summary={"total_reviews": 10},
        )

    # Then
    assert result.advice_text == "Study more math."
    assert result.weak_areas == ["math"]
    assert result.recommendations == ["Review daily"]
```

### TC-STR-ADV-003: test_get_learning_advice_model_used

**テスト目的**: model_used が service.model_used と一致することを確認。
**テスト要件**: REQ-STR-ADV-005
**信頼性**: 🔵

```python
def test_get_learning_advice_model_used(self):
    """TC-STR-ADV-003: model_used が self.model_used と一致する."""
    response_json = json.dumps({
        "advice_text": "Advice", "weak_areas": [], "recommendations": [],
    })
    mock_agent_instance = _make_mock_agent_instance(response_json)

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()
        result = service.get_learning_advice(review_summary={})

    assert result.model_used == service.model_used
```

### TC-STR-ADV-004: test_get_learning_advice_processing_time_ms

**テスト目的**: processing_time_ms が 0 以上の整数であることを確認。
**テスト要件**: REQ-STR-ADV-006
**信頼性**: 🔵

```python
def test_get_learning_advice_processing_time_ms(self):
    """TC-STR-ADV-004: processing_time_ms が 0 以上の整数."""
    response_json = json.dumps({
        "advice_text": "Advice", "weak_areas": [], "recommendations": [],
    })
    mock_agent_instance = _make_mock_agent_instance(response_json)

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()
        result = service.get_learning_advice(review_summary={})

    assert isinstance(result.processing_time_ms, int)
    assert result.processing_time_ms >= 0
```

### TC-STR-ADV-005: test_get_learning_advice_passes_args_to_prompt

**テスト目的**: get_advice_prompt に正しい引数（review_summary, language）が渡されることを確認。
**テスト要件**: REQ-STR-ADV-002
**信頼性**: 🔵

```python
@patch("services.strands_service.get_advice_prompt", return_value="mocked prompt")
def test_get_learning_advice_passes_args_to_prompt(self, mock_prompt):
    """TC-STR-ADV-005: get_advice_prompt に正しい引数が渡される."""
    response_json = json.dumps({
        "advice_text": "Advice", "weak_areas": [], "recommendations": [],
    })
    mock_agent_instance = _make_mock_agent_instance(response_json)

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()
        service.get_learning_advice(
            review_summary={"total_reviews": 10},
            language="ja",
        )

    mock_prompt.assert_called_once_with(
        review_summary={"total_reviews": 10},
        language="ja",
    )
```

### TC-STR-ADV-006: test_get_learning_advice_language_en

**テスト目的**: language="en" が get_advice_prompt に渡されることを確認。
**テスト要件**: REQ-STR-ADV-002
**信頼性**: 🔵

```python
@patch("services.strands_service.get_advice_prompt", return_value="mocked prompt")
def test_get_learning_advice_language_en(self, mock_prompt):
    """TC-STR-ADV-006: language='en' が get_advice_prompt に渡される."""
    response_json = json.dumps({
        "advice_text": "Advice", "weak_areas": [], "recommendations": [],
    })
    mock_agent_instance = _make_mock_agent_instance(response_json)

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()
        service.get_learning_advice(
            review_summary={}, language="en",
        )

    assert mock_prompt.call_args.kwargs["language"] == "en"
```

### TC-STR-ADV-007: test_get_learning_advice_parse_error_invalid_json

**テスト目的**: 非 JSON レスポンスで AIParseError が raise されることを確認。
**テスト要件**: REQ-STR-ADV-008
**信頼性**: 🔵

```python
def test_get_learning_advice_parse_error_invalid_json(self):
    """TC-STR-ADV-007: 非 JSON レスポンスで AIParseError."""
    mock_agent_instance = _make_mock_agent_instance("This is not valid JSON")

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()

        with pytest.raises(AIParseError):
            service.get_learning_advice(review_summary={})
```

### TC-STR-ADV-008: test_get_learning_advice_parse_error_missing_advice_text

**テスト目的**: advice_text フィールド欠損で AIParseError が raise されることを確認。
**テスト要件**: REQ-STR-ADV-009
**信頼性**: 🔵

```python
def test_get_learning_advice_parse_error_missing_advice_text(self):
    """TC-STR-ADV-008: advice_text 欠損で AIParseError."""
    response_json = json.dumps({"weak_areas": [], "recommendations": []})
    mock_agent_instance = _make_mock_agent_instance(response_json)

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()

        with pytest.raises(AIParseError):
            service.get_learning_advice(review_summary={})
```

### TC-STR-ADV-009: test_get_learning_advice_parse_error_missing_weak_areas

**テスト目的**: weak_areas フィールド欠損で AIParseError が raise されることを確認。
**テスト要件**: REQ-STR-ADV-009
**信頼性**: 🔵

```python
def test_get_learning_advice_parse_error_missing_weak_areas(self):
    """TC-STR-ADV-009: weak_areas 欠損で AIParseError."""
    response_json = json.dumps({"advice_text": "Advice", "recommendations": []})
    mock_agent_instance = _make_mock_agent_instance(response_json)

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()

        with pytest.raises(AIParseError):
            service.get_learning_advice(review_summary={})
```

### TC-STR-ADV-010: test_get_learning_advice_parse_error_missing_recommendations

**テスト目的**: recommendations フィールド欠損で AIParseError が raise されることを確認。
**テスト要件**: REQ-STR-ADV-009
**信頼性**: 🔵

```python
def test_get_learning_advice_parse_error_missing_recommendations(self):
    """TC-STR-ADV-010: recommendations 欠損で AIParseError."""
    response_json = json.dumps({"advice_text": "Advice", "weak_areas": []})
    mock_agent_instance = _make_mock_agent_instance(response_json)

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()

        with pytest.raises(AIParseError):
            service.get_learning_advice(review_summary={})
```

### TC-STR-ADV-011: test_get_learning_advice_timeout

**テスト目的**: TimeoutError で AITimeoutError が raise されることを確認。
**テスト要件**: REQ-STR-ADV-010
**信頼性**: 🔵

```python
def test_get_learning_advice_timeout(self):
    """TC-STR-ADV-011: TimeoutError で AITimeoutError."""
    mock_agent_instance = MagicMock()
    mock_agent_instance.side_effect = TimeoutError("Agent timed out")

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()

        with pytest.raises(AITimeoutError):
            service.get_learning_advice(review_summary={})
```

### TC-STR-ADV-012: test_get_learning_advice_connection_error

**テスト目的**: ConnectionError で AIProviderError が raise されることを確認。
**テスト要件**: REQ-STR-ADV-011
**信頼性**: 🔵

```python
def test_get_learning_advice_connection_error(self):
    """TC-STR-ADV-012: ConnectionError で AIProviderError."""
    mock_agent_instance = MagicMock()
    mock_agent_instance.side_effect = ConnectionError("Connection refused")

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()

        with pytest.raises(AIProviderError):
            service.get_learning_advice(review_summary={})
```

### TC-STR-ADV-013: test_get_learning_advice_rate_limit

**テスト目的**: ClientError (ThrottlingException) で AIRateLimitError が raise されることを確認。
**テスト要件**: REQ-STR-ADV-012
**信頼性**: 🟡（SDK の例外伝搬方式に依存）

```python
def test_get_learning_advice_rate_limit(self):
    """TC-STR-ADV-013: ThrottlingException で AIRateLimitError. (🟡 SDK 依存)"""
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
            service.get_learning_advice(review_summary={})
```

### TC-STR-ADV-014: test_get_learning_advice_unknown_exception

**テスト目的**: 予期しない例外（RuntimeError）が AIServiceError にラップされることを確認。
**テスト要件**: REQ-STR-ADV-013
**信頼性**: 🔵

```python
def test_get_learning_advice_unknown_exception(self):
    """TC-STR-ADV-014: RuntimeError で AIServiceError."""
    mock_agent_instance = MagicMock()
    mock_agent_instance.side_effect = RuntimeError("Something unexpected")

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()

        with pytest.raises(AIServiceError):
            service.get_learning_advice(review_summary={})
```

### TC-STR-ADV-015: test_get_learning_advice_exception_chain_preserved

**テスト目的**: 例外チェーン (__cause__) が保持されることを確認。
**テスト要件**: REQ-STR-ADV-014
**信頼性**: 🔵

```python
def test_get_learning_advice_exception_chain_preserved(self):
    """TC-STR-ADV-015: 例外チェーン (__cause__) が保持される."""
    mock_agent_instance = MagicMock()
    mock_agent_instance.side_effect = ConnectionError("Connection refused")

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()

        with pytest.raises(AIProviderError) as exc_info:
            service.get_learning_advice(review_summary={})

        assert exc_info.value.__cause__ is not None
```

---

## Part B: BedrockService.get_learning_advice() テスト

**ファイル**: `backend/tests/unit/test_bedrock.py`
**テストクラス**: `TestBedrockGetLearningAdvice`（既存ファイルに追加）

### フィクスチャ

既存の `TestBedrockGradeAnswer` と同一パターンのフィクスチャを使用する。

```python
class TestBedrockGetLearningAdvice:
    """BedrockService.get_learning_advice() テスト (TC-BDK-ADV-001 ~ TC-BDK-ADV-012).

    BedrockService.get_learning_advice() は既に実装済み (bedrock.py L220-267)。
    テストは既存実装の動作を確認する。
    """

    @pytest.fixture
    def mock_bedrock_client(self):
        """Create mock Bedrock client."""
        return MagicMock()

    @pytest.fixture
    def bedrock_service(self, mock_bedrock_client):
        """Create BedrockService with mock client."""
        return BedrockService(bedrock_client=mock_bedrock_client)

    def _mock_invoke_response(self, mock_client, response_text):
        """Bedrock invoke_model のモックレスポンスを設定するヘルパー."""
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps({
            "content": [{"text": response_text}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_body}
```

### 追加 import

```python
from services.ai_service import LearningAdvice  # 既存 import リストに追加
```

### TC-BDK-ADV-001: test_get_learning_advice_success

**テスト目的**: 正常系で LearningAdvice が返ることを確認。
**テスト要件**: REQ-BDK-ADV-001, REQ-BDK-ADV-004
**信頼性**: 🔵

```python
def test_get_learning_advice_success(self, bedrock_service, mock_bedrock_client):
    """TC-BDK-ADV-001: 正常系で LearningAdvice が返る."""
    self._mock_invoke_response(
        mock_bedrock_client,
        '{"advice_text": "数学を復習しましょう", "weak_areas": ["数学"], "recommendations": ["毎日復習"]}'
    )

    result = bedrock_service.get_learning_advice(
        review_summary={"total_reviews": 50},
    )

    assert isinstance(result, LearningAdvice)
    assert result.advice_text == "数学を復習しましょう"
    assert result.weak_areas == ["数学"]
    assert result.recommendations == ["毎日復習"]
```

### TC-BDK-ADV-002: test_get_learning_advice_with_markdown

**テスト目的**: Markdown コードブロック内 JSON が正しくパースされることを確認。
**テスト要件**: REQ-BDK-ADV-007
**信頼性**: 🔵

```python
def test_get_learning_advice_with_markdown(self, bedrock_service, mock_bedrock_client):
    """TC-BDK-ADV-002: Markdown コードブロック内 JSON が正しくパースされる."""
    self._mock_invoke_response(
        mock_bedrock_client,
        '```json\n{"advice_text": "Study more", "weak_areas": ["math"], "recommendations": ["Review"]}\n```'
    )

    result = bedrock_service.get_learning_advice(
        review_summary={"total_reviews": 10},
    )

    assert result.advice_text == "Study more"
    assert result.weak_areas == ["math"]
```

### TC-BDK-ADV-003: test_get_learning_advice_model_used

**テスト目的**: model_used が self.model_id と一致することを確認。
**テスト要件**: REQ-BDK-ADV-005
**信頼性**: 🔵

```python
def test_get_learning_advice_model_used(self, mock_bedrock_client):
    """TC-BDK-ADV-003: model_used が self.model_id と一致する."""
    service = BedrockService(
        model_id="test-model-id",
        bedrock_client=mock_bedrock_client,
    )
    self._mock_invoke_response(
        mock_bedrock_client,
        '{"advice_text": "Advice", "weak_areas": [], "recommendations": []}'
    )

    result = service.get_learning_advice(review_summary={})

    assert result.model_used == "test-model-id"
```

### TC-BDK-ADV-004: test_get_learning_advice_processing_time_ms

**テスト目的**: processing_time_ms が 0 以上の整数であることを確認。
**テスト要件**: REQ-BDK-ADV-006
**信頼性**: 🔵

```python
def test_get_learning_advice_processing_time_ms(self, bedrock_service, mock_bedrock_client):
    """TC-BDK-ADV-004: processing_time_ms が 0 以上の整数."""
    self._mock_invoke_response(
        mock_bedrock_client,
        '{"advice_text": "Advice", "weak_areas": [], "recommendations": []}'
    )

    result = bedrock_service.get_learning_advice(review_summary={})

    assert isinstance(result.processing_time_ms, int)
    assert result.processing_time_ms >= 0
```

### TC-BDK-ADV-005: test_get_learning_advice_calls_get_advice_prompt

**テスト目的**: get_advice_prompt に正しい引数が渡されることを確認。
**テスト要件**: REQ-BDK-ADV-002
**信頼性**: 🔵

```python
def test_get_learning_advice_calls_get_advice_prompt(self, bedrock_service, mock_bedrock_client):
    """TC-BDK-ADV-005: get_advice_prompt に正しい引数が渡される."""
    self._mock_invoke_response(
        mock_bedrock_client,
        '{"advice_text": "Advice", "weak_areas": [], "recommendations": []}'
    )

    with patch("services.bedrock.get_advice_prompt", return_value="mocked") as mock_prompt:
        bedrock_service.get_learning_advice(
            review_summary={"total_reviews": 10},
            language="en",
        )

    mock_prompt.assert_called_once_with(
        review_summary={"total_reviews": 10},
        language="en",
    )
```

### TC-BDK-ADV-006: test_get_learning_advice_parse_error

**テスト目的**: 無効な JSON で BedrockParseError が raise されることを確認。
**テスト要件**: REQ-BDK-ADV-008
**信頼性**: 🔵

```python
def test_get_learning_advice_parse_error(self, bedrock_service, mock_bedrock_client):
    """TC-BDK-ADV-006: 無効な JSON で BedrockParseError."""
    self._mock_invoke_response(
        mock_bedrock_client,
        "This is not valid JSON"
    )

    with pytest.raises(BedrockParseError):
        bedrock_service.get_learning_advice(review_summary={})
```

### TC-BDK-ADV-007: test_get_learning_advice_missing_advice_text

**テスト目的**: advice_text フィールド欠落で BedrockParseError が raise されることを確認。
**テスト要件**: REQ-BDK-ADV-009
**信頼性**: 🔵

```python
def test_get_learning_advice_missing_advice_text(self, bedrock_service, mock_bedrock_client):
    """TC-BDK-ADV-007: advice_text 欠落で BedrockParseError."""
    self._mock_invoke_response(
        mock_bedrock_client,
        '{"weak_areas": [], "recommendations": []}'
    )

    with pytest.raises(BedrockParseError):
        bedrock_service.get_learning_advice(review_summary={})
```

### TC-BDK-ADV-008: test_get_learning_advice_missing_weak_areas

**テスト目的**: weak_areas フィールド欠落で BedrockParseError が raise されることを確認。
**テスト要件**: REQ-BDK-ADV-009
**信頼性**: 🔵

```python
def test_get_learning_advice_missing_weak_areas(self, bedrock_service, mock_bedrock_client):
    """TC-BDK-ADV-008: weak_areas 欠落で BedrockParseError."""
    self._mock_invoke_response(
        mock_bedrock_client,
        '{"advice_text": "Advice", "recommendations": []}'
    )

    with pytest.raises(BedrockParseError):
        bedrock_service.get_learning_advice(review_summary={})
```

### TC-BDK-ADV-009: test_get_learning_advice_missing_recommendations

**テスト目的**: recommendations フィールド欠落で BedrockParseError が raise されることを確認。
**テスト要件**: REQ-BDK-ADV-009
**信頼性**: 🔵

```python
def test_get_learning_advice_missing_recommendations(self, bedrock_service, mock_bedrock_client):
    """TC-BDK-ADV-009: recommendations 欠落で BedrockParseError."""
    self._mock_invoke_response(
        mock_bedrock_client,
        '{"advice_text": "Advice", "weak_areas": []}'
    )

    with pytest.raises(BedrockParseError):
        bedrock_service.get_learning_advice(review_summary={})
```

### TC-BDK-ADV-010: test_get_learning_advice_timeout

**テスト目的**: ReadTimeoutError で BedrockTimeoutError が raise されることを確認。
**テスト要件**: REQ-BDK-ADV-010
**信頼性**: 🔵

```python
def test_get_learning_advice_timeout(self, bedrock_service, mock_bedrock_client):
    """TC-BDK-ADV-010: ReadTimeoutError で BedrockTimeoutError."""
    mock_bedrock_client.invoke_model.side_effect = ClientError(
        {"Error": {"Code": "ReadTimeoutError", "Message": "Timeout"}},
        "InvokeModel",
    )

    with pytest.raises(BedrockTimeoutError):
        bedrock_service.get_learning_advice(review_summary={})
```

### TC-BDK-ADV-011: test_get_learning_advice_rate_limit

**テスト目的**: ThrottlingException で BedrockRateLimitError が raise され、リトライが 3 回行われることを確認。
**テスト要件**: REQ-BDK-ADV-011
**信頼性**: 🔵

```python
def test_get_learning_advice_rate_limit(self, bedrock_service, mock_bedrock_client):
    """TC-BDK-ADV-011: ThrottlingException で BedrockRateLimitError（リトライ後）."""
    mock_bedrock_client.invoke_model.side_effect = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate limit"}},
        "InvokeModel",
    )

    with pytest.raises(BedrockRateLimitError):
        bedrock_service.get_learning_advice(review_summary={})

    # リトライ: initial + 2 retries = 3 calls
    assert mock_bedrock_client.invoke_model.call_count == 3
```

### TC-BDK-ADV-012: test_get_learning_advice_internal_error

**テスト目的**: InternalServerException で BedrockInternalError が raise され、リトライが 3 回行われることを確認。
**テスト要件**: REQ-BDK-ADV-012
**信頼性**: 🔵

```python
def test_get_learning_advice_internal_error(self, bedrock_service, mock_bedrock_client):
    """TC-BDK-ADV-012: InternalServerException で BedrockInternalError（リトライ後）."""
    mock_bedrock_client.invoke_model.side_effect = ClientError(
        {"Error": {"Code": "InternalServerException", "Message": "Internal"}},
        "InvokeModel",
    )

    with pytest.raises(BedrockInternalError):
        bedrock_service.get_learning_advice(review_summary={})

    assert mock_bedrock_client.invoke_model.call_count == 3
```

---

## Part C: advice_handler Lambda テスト

**ファイル**: `backend/tests/unit/test_handler_advice.py`（新規作成）

### ファイルヘッダー・import

```python
"""TASK-0062: GET /advice エンドポイントのテスト。

advice_handler Lambda ハンドラーの本実装に対するテストケース。
構造的前提:
- advice_handler は独立 Lambda 関数（app/APIGatewayHttpResolver 経由ではない）
- 生の API Gateway HTTP API v2 イベントを直接受け取る
- レスポンスは Lambda プロキシ統合形式の dict（statusCode, headers, body）
- GET リクエストのためリクエストボディのパースは不要
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from api.handler import advice_handler
from services.ai_service import (
    AIInternalError,
    AIParseError,
    AIProviderError,
    AIRateLimitError,
    AIServiceError,
    AITimeoutError,
    LearningAdvice,
    ReviewSummary,
)
```

### イベント構築ヘルパー

`_make_grade_ai_event()` と同一パターンで `_make_advice_event()` を定義する。

```python
def _make_advice_event(
    user_id: str = "test-user-id",
    query_params: dict | None = None,
    authorizer: dict | None = None,
) -> dict:
    """advice_handler 用の API Gateway HTTP API v2 イベントを構築する。

    Args:
        user_id: JWT claims の sub クレーム。
        query_params: クエリストリングパラメータ（language 等）。
        authorizer: リクエストコンテキストの authorizer。None の場合は標準 JWT 形式。

    Returns:
        API Gateway HTTP API v2 形式のイベント辞書。
    """
    if authorizer is None:
        authorizer = {
            "jwt": {
                "claims": {"sub": user_id},
                "scopes": ["openid", "profile"],
            }
        }
    event = {
        "version": "2.0",
        "routeKey": "GET /advice",
        "rawPath": "/advice",
        "rawQueryString": "",
        "pathParameters": None,
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "api-id",
            "authorizer": authorizer,
            "http": {"method": "GET"},
            "requestId": "test-request-id",
            "routeKey": "GET /advice",
            "stage": "$default",
        },
        "headers": {"content-type": "application/json"},
        "isBase64Encoded": False,
    }
    if query_params:
        event["queryStringParameters"] = query_params
    return event
```

### 共通フィクスチャ

```python
@pytest.fixture
def mock_review_service():
    """ReviewService のモック。ReviewSummary を返す。

    パッチ対象: api.handler.review_service（モジュールレベルグローバル変数）
    """
    with patch("api.handler.review_service") as mock:
        mock.get_review_summary.return_value = ReviewSummary(
            total_reviews=100,
            average_grade=3.5,
            total_cards=50,
            cards_due_today=10,
            streak_days=5,
            tag_performance={"math": 0.8, "science": 0.6},
            recent_review_dates=["2026-02-24", "2026-02-23"],
        )
        yield mock


@pytest.fixture
def mock_ai_service():
    """create_ai_service のモック。LearningAdvice を返す。

    パッチ対象: api.handler.create_ai_service（インポートされた関数）

    Yields:
        tuple: (mock_factory, mock_service)
    """
    with patch("api.handler.create_ai_service") as mock_factory:
        mock_service = MagicMock()
        mock_service.get_learning_advice.return_value = LearningAdvice(
            advice_text="数学の復習頻度を上げましょう。",
            weak_areas=["数学", "物理"],
            recommendations=["毎日10枚のカードを復習する", "弱点タグを重点的に復習"],
            model_used="test-model",
            processing_time_ms=800,
        )
        mock_factory.return_value = mock_service
        yield mock_factory, mock_service
```

---

### カテゴリ A: 認証テスト（TestAdviceHandlerAuth）

#### TC-062-AUTH-001: test_advice_returns_401_when_no_authorizer

**テスト目的**: authorizer が空辞書の場合に HTTP 401 を返すことを確認。
**テスト要件**: REQ-ADV-AUTH-001, REQ-ADV-AUTH-002
**信頼性**: 🔵

```python
class TestAdviceHandlerAuth:
    """認証関連テスト（TC-062-AUTH-001 ~ 003）。"""

    def test_advice_returns_401_when_no_authorizer(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-AUTH-001: authorizer が空の場合に HTTP 401 を返すことを確認."""
        event = _make_advice_event(authorizer={})

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 401
        body = json.loads(response["body"])
        assert body["error"] == "Unauthorized"
```

#### TC-062-AUTH-002: test_advice_returns_401_when_no_sub_claim

**テスト目的**: JWT claims に sub がない場合に HTTP 401 を返すことを確認。
**テスト要件**: REQ-ADV-AUTH-002
**信頼性**: 🔵

```python
    def test_advice_returns_401_when_no_sub_claim(self, lambda_context):
        """TC-062-AUTH-002: JWT claims に sub がない場合に HTTP 401 を返すことを確認."""
        authorizer = {"jwt": {"claims": {"iss": "https://keycloak.example.com"}}}
        event = _make_advice_event(authorizer=authorizer)

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 401
        body = json.loads(response["body"])
        assert body["error"] == "Unauthorized"
```

#### TC-062-AUTH-003: test_advice_extracts_user_id_from_jwt_claims

**テスト目的**: authorizer.jwt.claims.sub から user_id を正しく抽出し ReviewService に渡すことを確認。
**テスト要件**: REQ-ADV-AUTH-001
**信頼性**: 🔵

```python
    def test_advice_extracts_user_id_from_jwt_claims(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-AUTH-003: JWT claims.sub から user_id を正しく抽出することを確認."""
        event = _make_advice_event(user_id="user-abc-123")

        advice_handler(event, lambda_context)

        mock_review_service.get_review_summary.assert_called_once_with("user-abc-123")
```

---

### カテゴリ B: データフローテスト（TestAdviceHandlerFlow）

#### TC-062-FLOW-001: test_advice_calls_get_review_summary

**テスト目的**: review_service.get_review_summary(user_id) が呼ばれることを確認。
**テスト要件**: REQ-ADV-FLOW-001
**信頼性**: 🔵

```python
class TestAdviceHandlerFlow:
    """データフロー関連テスト（TC-062-FLOW-001 ~ 005）。"""

    def test_advice_calls_get_review_summary(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-FLOW-001: review_service.get_review_summary が呼ばれることを確認."""
        event = _make_advice_event()

        advice_handler(event, lambda_context)

        mock_review_service.get_review_summary.assert_called_once_with("test-user-id")
```

#### TC-062-FLOW-002: test_advice_calls_create_ai_service_factory

**テスト目的**: create_ai_service() ファクトリーが 1 回呼ばれることを確認。
**テスト要件**: REQ-ADV-FLOW-003
**信頼性**: 🔵

```python
    def test_advice_calls_create_ai_service_factory(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-FLOW-002: create_ai_service() ファクトリーが 1 回呼ばれることを確認."""
        mock_factory, _ = mock_ai_service
        event = _make_advice_event()

        advice_handler(event, lambda_context)

        mock_factory.assert_called_once()
```

#### TC-062-FLOW-003: test_advice_passes_review_summary_dict_to_ai_service

**テスト目的**: ReviewSummary を dict に変換して ai_service.get_learning_advice に渡すことを確認。
**テスト要件**: REQ-ADV-FLOW-002
**信頼性**: 🔵

```python
    def test_advice_passes_review_summary_dict_to_ai_service(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-FLOW-003: ReviewSummary が dict に変換されて AI サービスに渡されることを確認."""
        _, mock_service = mock_ai_service
        event = _make_advice_event()

        advice_handler(event, lambda_context)

        # get_learning_advice が呼ばれたことを確認
        mock_service.get_learning_advice.assert_called_once()
        call_kwargs = mock_service.get_learning_advice.call_args.kwargs
        # review_summary は dict であること
        assert isinstance(call_kwargs["review_summary"], dict)
        # 元の ReviewSummary のフィールドが含まれること
        assert call_kwargs["review_summary"]["total_reviews"] == 100
        assert call_kwargs["review_summary"]["average_grade"] == 3.5
```

#### TC-062-FLOW-004: test_advice_passes_language_param_to_ai_service

**テスト目的**: queryStringParameters の language=en が AI サービスに渡されることを確認。
**テスト要件**: REQ-ADV-FLOW-004
**信頼性**: 🔵

```python
    def test_advice_passes_language_param_to_ai_service(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-FLOW-004: language=en が AI サービスに渡されることを確認."""
        _, mock_service = mock_ai_service
        event = _make_advice_event(query_params={"language": "en"})

        advice_handler(event, lambda_context)

        call_kwargs = mock_service.get_learning_advice.call_args.kwargs
        assert call_kwargs["language"] == "en"
```

#### TC-062-FLOW-005: test_advice_uses_default_language_ja

**テスト目的**: queryStringParameters なしの場合にデフォルト "ja" が使われることを確認。
**テスト要件**: REQ-ADV-FLOW-004
**信頼性**: 🔵

```python
    def test_advice_uses_default_language_ja(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-FLOW-005: queryStringParameters なしでデフォルト language=ja を確認."""
        _, mock_service = mock_ai_service
        event = _make_advice_event()  # query_params なし

        advice_handler(event, lambda_context)

        call_kwargs = mock_service.get_learning_advice.call_args.kwargs
        assert call_kwargs["language"] == "ja"
```

---

### カテゴリ C: 正常系レスポンステスト（TestAdviceHandlerSuccess）

#### TC-062-RES-001: test_advice_success_returns_200

**テスト目的**: 成功時に HTTP 200 が返ることを確認。
**テスト要件**: REQ-ADV-RES-001
**信頼性**: 🔵

```python
class TestAdviceHandlerSuccess:
    """正常系レスポンステスト（TC-062-RES-001 ~ 008）。"""

    def test_advice_success_returns_200(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-RES-001: 正常系で HTTP 200 が返ることを確認."""
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 200
```

#### TC-062-RES-002: test_advice_success_response_contains_advice_text

**テスト目的**: レスポンスに advice_text が含まれることを確認。
**テスト要件**: REQ-ADV-RES-002
**信頼性**: 🔵

```python
    def test_advice_success_response_contains_advice_text(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-RES-002: レスポンスに advice_text が正しく含まれることを確認."""
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        body = json.loads(response["body"])
        assert body["advice_text"] == "数学の復習頻度を上げましょう。"
```

#### TC-062-RES-003: test_advice_success_response_contains_weak_areas

**テスト目的**: レスポンスに weak_areas が含まれることを確認。
**テスト要件**: REQ-ADV-RES-002
**信頼性**: 🔵

```python
    def test_advice_success_response_contains_weak_areas(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-RES-003: レスポンスに weak_areas が正しく含まれることを確認."""
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        body = json.loads(response["body"])
        assert body["weak_areas"] == ["数学", "物理"]
```

#### TC-062-RES-004: test_advice_success_response_contains_recommendations

**テスト目的**: レスポンスに recommendations が含まれることを確認。
**テスト要件**: REQ-ADV-RES-002
**信頼性**: 🔵

```python
    def test_advice_success_response_contains_recommendations(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-RES-004: レスポンスに recommendations が正しく含まれることを確認."""
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        body = json.loads(response["body"])
        assert len(body["recommendations"]) == 2
        assert "毎日10枚のカードを復習する" in body["recommendations"]
```

#### TC-062-RES-005: test_advice_success_response_contains_study_stats

**テスト目的**: レスポンスに study_stats が含まれ、ReviewSummary のフィールドが正しいことを確認。
**テスト要件**: REQ-ADV-RES-003
**信頼性**: 🔵

```python
    def test_advice_success_response_contains_study_stats(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-RES-005: レスポンスに study_stats が正しく含まれることを確認."""
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        body = json.loads(response["body"])
        assert "study_stats" in body
        stats = body["study_stats"]
        assert stats["total_reviews"] == 100
        assert stats["average_grade"] == 3.5
        assert stats["total_cards"] == 50
        assert stats["cards_due_today"] == 10
        assert stats["streak_days"] == 5
```

#### TC-062-RES-006: test_advice_success_response_contains_advice_info

**テスト目的**: レスポンスに advice_info（model_used, processing_time_ms）が含まれることを確認。
**テスト要件**: REQ-ADV-RES-004
**信頼性**: 🔵

```python
    def test_advice_success_response_contains_advice_info(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-RES-006: レスポンスに advice_info が正しく含まれることを確認."""
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        body = json.loads(response["body"])
        assert "advice_info" in body
        assert body["advice_info"]["model_used"] == "test-model"
        assert body["advice_info"]["processing_time_ms"] == 800
```

#### TC-062-RES-007: test_advice_success_response_is_json

**テスト目的**: Content-Type が application/json であることを確認。
**テスト要件**: REQ-ADV-RES-005
**信頼性**: 🔵

```python
    def test_advice_success_response_is_json(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-RES-007: Content-Type が application/json であることを確認."""
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 200
        assert response["headers"]["Content-Type"] == "application/json"
```

#### TC-062-RES-008: test_advice_success_full_e2e_flow

**テスト目的**: カスタム user_id, ReviewSummary, AI 結果での一連フローを E2E で検証。
**テスト要件**: REQ-ADV-FLOW-001, REQ-ADV-FLOW-002, REQ-ADV-RES-001 ~ 004
**信頼性**: 🔵

```python
    def test_advice_success_full_e2e_flow(self, lambda_context):
        """TC-062-RES-008: 認証 -> ReviewSummary -> AI -> レスポンスの一連 E2E フロー."""
        with patch("api.handler.review_service") as mock_rs, \
             patch("api.handler.create_ai_service") as mock_factory:
            # カスタム ReviewSummary
            mock_rs.get_review_summary.return_value = ReviewSummary(
                total_reviews=200,
                average_grade=4.0,
                total_cards=80,
                cards_due_today=15,
                streak_days=10,
                tag_performance={"english": 0.9},
                recent_review_dates=["2026-02-24"],
            )
            # カスタム AI 結果
            mock_service = MagicMock()
            mock_service.get_learning_advice.return_value = LearningAdvice(
                advice_text="英語の学習は順調です。",
                weak_areas=["英語リスニング"],
                recommendations=["リスニング教材を追加する"],
                model_used="claude-3-haiku",
                processing_time_ms=600,
            )
            mock_factory.return_value = mock_service

            event = _make_advice_event(
                user_id="e2e-user",
                query_params={"language": "ja"},
            )

            response = advice_handler(event, lambda_context)

        # 全フィールドを検証
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["advice_text"] == "英語の学習は順調です。"
        assert body["weak_areas"] == ["英語リスニング"]
        assert body["recommendations"] == ["リスニング教材を追加する"]
        assert body["study_stats"]["total_reviews"] == 200
        assert body["study_stats"]["average_grade"] == 4.0
        assert body["study_stats"]["total_cards"] == 80
        assert body["study_stats"]["cards_due_today"] == 15
        assert body["study_stats"]["streak_days"] == 10
        assert body["advice_info"]["model_used"] == "claude-3-haiku"
        assert body["advice_info"]["processing_time_ms"] == 600

        # コール引数を検証
        mock_rs.get_review_summary.assert_called_once_with("e2e-user")
        mock_factory.assert_called_once()
        call_kwargs = mock_service.get_learning_advice.call_args.kwargs
        assert call_kwargs["review_summary"]["total_reviews"] == 200
        assert call_kwargs["language"] == "ja"
```

---

### カテゴリ D: AI エラーハンドリングテスト（TestAdviceHandlerAIErrors）

#### TC-062-ERR-001: test_advice_returns_504_on_ai_timeout

**テスト目的**: AITimeoutError が HTTP 504 にマッピングされることを確認。
**テスト要件**: REQ-ADV-ERR-001
**信頼性**: 🔵

```python
class TestAdviceHandlerAIErrors:
    """AI エラーハンドリングテスト（TC-062-ERR-001 ~ 007）。

    _map_ai_error_to_http() を使用した AI 例外の HTTP マッピングを検証。
    """

    def test_advice_returns_504_on_ai_timeout(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-ERR-001: AITimeoutError が HTTP 504 にマッピングされることを確認."""
        _, mock_service = mock_ai_service
        mock_service.get_learning_advice.side_effect = AITimeoutError("timeout")
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 504
        body = json.loads(response["body"])
        assert body["error"] == "AI service timeout"
```

#### TC-062-ERR-002: test_advice_returns_429_on_ai_rate_limit

**テスト目的**: AIRateLimitError が HTTP 429 にマッピングされることを確認。
**テスト要件**: REQ-ADV-ERR-002
**信頼性**: 🔵

```python
    def test_advice_returns_429_on_ai_rate_limit(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-ERR-002: AIRateLimitError が HTTP 429 にマッピングされることを確認."""
        _, mock_service = mock_ai_service
        mock_service.get_learning_advice.side_effect = AIRateLimitError("rate limit")
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 429
        body = json.loads(response["body"])
        assert body["error"] == "AI service rate limit exceeded"
```

#### TC-062-ERR-003: test_advice_returns_503_on_ai_provider_error

**テスト目的**: AIProviderError が HTTP 503 にマッピングされることを確認。
**テスト要件**: REQ-ADV-ERR-003
**信頼性**: 🔵

```python
    def test_advice_returns_503_on_ai_provider_error(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-ERR-003: AIProviderError が HTTP 503 にマッピングされることを確認."""
        _, mock_service = mock_ai_service
        mock_service.get_learning_advice.side_effect = AIProviderError("provider down")
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 503
        body = json.loads(response["body"])
        assert body["error"] == "AI service unavailable"
```

#### TC-062-ERR-004: test_advice_returns_500_on_ai_parse_error

**テスト目的**: AIParseError が HTTP 500 にマッピングされることを確認。
**テスト要件**: REQ-ADV-ERR-004
**信頼性**: 🔵

```python
    def test_advice_returns_500_on_ai_parse_error(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-ERR-004: AIParseError が HTTP 500 にマッピングされることを確認."""
        _, mock_service = mock_ai_service
        mock_service.get_learning_advice.side_effect = AIParseError("invalid json")
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error"] == "AI service response parse error"
```

#### TC-062-ERR-005: test_advice_returns_500_on_ai_internal_error

**テスト目的**: AIInternalError が HTTP 500 にマッピングされることを確認。
**テスト要件**: REQ-ADV-ERR-005
**信頼性**: 🔵

```python
    def test_advice_returns_500_on_ai_internal_error(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-ERR-005: AIInternalError が HTTP 500 にマッピングされることを確認."""
        _, mock_service = mock_ai_service
        mock_service.get_learning_advice.side_effect = AIInternalError("internal failure")
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error"] == "AI service error"
```

#### TC-062-ERR-006: test_advice_returns_503_on_factory_init_failure

**テスト目的**: create_ai_service() 自体が AIProviderError を raise した場合に HTTP 503 を返すことを確認。
**テスト要件**: REQ-ADV-ERR-006
**信頼性**: 🔵

```python
    def test_advice_returns_503_on_factory_init_failure(
        self, lambda_context, mock_review_service
    ):
        """TC-062-ERR-006: ファクトリー初期化失敗で HTTP 503 を返すことを確認."""
        with patch("api.handler.create_ai_service") as mock_factory:
            mock_factory.side_effect = AIProviderError(
                "Failed to initialize AI service"
            )
            event = _make_advice_event()

            response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 503
        body = json.loads(response["body"])
        assert body["error"] == "AI service unavailable"
```

#### TC-062-ERR-007: test_advice_returns_500_on_unexpected_exception

**テスト目的**: 予期しない例外（RuntimeError 等）が HTTP 500 にマッピングされることを確認。
**テスト要件**: REQ-ADV-ERR-007
**信頼性**: 🔵

```python
    def test_advice_returns_500_on_unexpected_exception(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-ERR-007: 予期しない例外が HTTP 500 にマッピングされることを確認."""
        _, mock_service = mock_ai_service
        mock_service.get_learning_advice.side_effect = RuntimeError("unexpected")
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error"] == "Internal Server Error"
```

---

### カテゴリ E: DB/ReviewService エラーテスト（TestAdviceHandlerDBErrors）

#### TC-062-DB-001: test_advice_handles_review_service_exception

**テスト目的**: review_service.get_review_summary が例外を raise した場合に HTTP 500 を返すことを確認。
**テスト要件**: REQ-ADV-ERR-007（予期しない例外の汎用ハンドリング）
**信頼性**: 🔵

```python
class TestAdviceHandlerDBErrors:
    """DB/ReviewService エラーテスト（TC-062-DB-001 ~ 002）。"""

    def test_advice_handles_review_service_exception(
        self, lambda_context, mock_ai_service
    ):
        """TC-062-DB-001: ReviewService 例外で HTTP 500 を返すことを確認."""
        with patch("api.handler.review_service") as mock_rs:
            mock_rs.get_review_summary.side_effect = Exception("DB connection error")
            event = _make_advice_event()

            response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error"] == "Internal Server Error"
```

#### TC-062-DB-002: test_advice_works_with_empty_review_summary

**テスト目的**: ReviewSummary が全ゼロ（復習履歴なし）でも正常にアドバイスが返ることを確認。
**テスト要件**: REQ-ADV-RES-001
**信頼性**: 🔵

```python
    def test_advice_works_with_empty_review_summary(
        self, lambda_context, mock_ai_service
    ):
        """TC-062-DB-002: 全ゼロの ReviewSummary でも HTTP 200 が返ることを確認."""
        with patch("api.handler.review_service") as mock_rs:
            mock_rs.get_review_summary.return_value = ReviewSummary(
                total_reviews=0,
                average_grade=0.0,
                total_cards=0,
                cards_due_today=0,
                streak_days=0,
            )
            event = _make_advice_event()

            response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 200
```

---

### カテゴリ F: ロギングテスト（TestAdviceHandlerLogging）

#### TC-062-LOG-001: test_advice_logs_request_info

**テスト目的**: リクエスト受信時に logger.info で user_id を記録することを確認。
**テスト要件**: REQ-ADV-LOG-001
**信頼性**: 🔵

```python
class TestAdviceHandlerLogging:
    """ロギング関連テスト（TC-062-LOG-001 ~ 003）。"""

    def test_advice_logs_request_info(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-LOG-001: リクエスト受信時のロギングを確認."""
        event = _make_advice_event(user_id="log-test-user")

        with patch("api.handler.logger") as mock_logger:
            advice_handler(event, lambda_context)

        info_calls_str = str(mock_logger.info.call_args_list)
        assert "log-test-user" in info_calls_str
```

#### TC-062-LOG-002: test_advice_logs_success_info

**テスト目的**: 成功時に logger.info で成功関連情報を記録することを確認。
**テスト要件**: REQ-ADV-LOG-002
**信頼性**: 🔵

```python
    def test_advice_logs_success_info(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-LOG-002: 成功時のロギングを確認."""
        event = _make_advice_event()

        with patch("api.handler.logger") as mock_logger:
            advice_handler(event, lambda_context)

        # logger.info が少なくとも 1 回呼ばれていること（リクエスト + 成功ログ）
        assert mock_logger.info.call_count >= 2
```

#### TC-062-LOG-003: test_advice_logs_ai_error

**テスト目的**: AI エラー発生時に logger.warning または logger.error で記録することを確認。
**テスト要件**: REQ-ADV-LOG-003
**信頼性**: 🔵

```python
    def test_advice_logs_ai_error(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-LOG-003: AI エラー時のロギングを確認."""
        _, mock_service = mock_ai_service
        mock_service.get_learning_advice.side_effect = AITimeoutError("timeout")
        event = _make_advice_event()

        with patch("api.handler.logger") as mock_logger:
            advice_handler(event, lambda_context)

        assert mock_logger.warning.called or mock_logger.error.called
```

---

## テストケースサマリー

### Part A: StrandsAIService テスト（15 件）

| TC ID | テスト名 | カテゴリ | 信頼性 |
|-------|---------|---------|--------|
| TC-STR-ADV-001 | `test_get_learning_advice_success` | 正常系 | 🔵 |
| TC-STR-ADV-002 | `test_get_learning_advice_markdown_wrapped` | 正常系 | 🔵 |
| TC-STR-ADV-003 | `test_get_learning_advice_model_used` | 正常系 | 🔵 |
| TC-STR-ADV-004 | `test_get_learning_advice_processing_time_ms` | 正常系 | 🔵 |
| TC-STR-ADV-005 | `test_get_learning_advice_passes_args_to_prompt` | 引数伝搬 | 🔵 |
| TC-STR-ADV-006 | `test_get_learning_advice_language_en` | 引数伝搬 | 🔵 |
| TC-STR-ADV-007 | `test_get_learning_advice_parse_error_invalid_json` | パースエラー | 🔵 |
| TC-STR-ADV-008 | `test_get_learning_advice_parse_error_missing_advice_text` | パースエラー | 🔵 |
| TC-STR-ADV-009 | `test_get_learning_advice_parse_error_missing_weak_areas` | パースエラー | 🔵 |
| TC-STR-ADV-010 | `test_get_learning_advice_parse_error_missing_recommendations` | パースエラー | 🔵 |
| TC-STR-ADV-011 | `test_get_learning_advice_timeout` | エラーハンドリング | 🔵 |
| TC-STR-ADV-012 | `test_get_learning_advice_connection_error` | エラーハンドリング | 🔵 |
| TC-STR-ADV-013 | `test_get_learning_advice_rate_limit` | エラーハンドリング | 🟡 |
| TC-STR-ADV-014 | `test_get_learning_advice_unknown_exception` | エラーハンドリング | 🔵 |
| TC-STR-ADV-015 | `test_get_learning_advice_exception_chain_preserved` | エラーハンドリング | 🔵 |

### Part B: BedrockService テスト（12 件）

| TC ID | テスト名 | カテゴリ | 信頼性 |
|-------|---------|---------|--------|
| TC-BDK-ADV-001 | `test_get_learning_advice_success` | 正常系 | 🔵 |
| TC-BDK-ADV-002 | `test_get_learning_advice_with_markdown` | 正常系 | 🔵 |
| TC-BDK-ADV-003 | `test_get_learning_advice_model_used` | 正常系 | 🔵 |
| TC-BDK-ADV-004 | `test_get_learning_advice_processing_time_ms` | 正常系 | 🔵 |
| TC-BDK-ADV-005 | `test_get_learning_advice_calls_get_advice_prompt` | 引数伝搬 | 🔵 |
| TC-BDK-ADV-006 | `test_get_learning_advice_parse_error` | パースエラー | 🔵 |
| TC-BDK-ADV-007 | `test_get_learning_advice_missing_advice_text` | パースエラー | 🔵 |
| TC-BDK-ADV-008 | `test_get_learning_advice_missing_weak_areas` | パースエラー | 🔵 |
| TC-BDK-ADV-009 | `test_get_learning_advice_missing_recommendations` | パースエラー | 🔵 |
| TC-BDK-ADV-010 | `test_get_learning_advice_timeout` | API エラー | 🔵 |
| TC-BDK-ADV-011 | `test_get_learning_advice_rate_limit` | API エラー | 🔵 |
| TC-BDK-ADV-012 | `test_get_learning_advice_internal_error` | API エラー | 🔵 |

### Part C: advice_handler テスト（28 件）

| TC ID | テスト名 | クラス | カテゴリ | 信頼性 |
|-------|---------|--------|---------|--------|
| TC-062-AUTH-001 | `test_advice_returns_401_when_no_authorizer` | TestAdviceHandlerAuth | 認証 | 🔵 |
| TC-062-AUTH-002 | `test_advice_returns_401_when_no_sub_claim` | TestAdviceHandlerAuth | 認証 | 🔵 |
| TC-062-AUTH-003 | `test_advice_extracts_user_id_from_jwt_claims` | TestAdviceHandlerAuth | 認証 | 🔵 |
| TC-062-FLOW-001 | `test_advice_calls_get_review_summary` | TestAdviceHandlerFlow | データフロー | 🔵 |
| TC-062-FLOW-002 | `test_advice_calls_create_ai_service_factory` | TestAdviceHandlerFlow | データフロー | 🔵 |
| TC-062-FLOW-003 | `test_advice_passes_review_summary_dict_to_ai_service` | TestAdviceHandlerFlow | データフロー | 🔵 |
| TC-062-FLOW-004 | `test_advice_passes_language_param_to_ai_service` | TestAdviceHandlerFlow | データフロー | 🔵 |
| TC-062-FLOW-005 | `test_advice_uses_default_language_ja` | TestAdviceHandlerFlow | データフロー | 🔵 |
| TC-062-RES-001 | `test_advice_success_returns_200` | TestAdviceHandlerSuccess | 正常系 | 🔵 |
| TC-062-RES-002 | `test_advice_success_response_contains_advice_text` | TestAdviceHandlerSuccess | 正常系 | 🔵 |
| TC-062-RES-003 | `test_advice_success_response_contains_weak_areas` | TestAdviceHandlerSuccess | 正常系 | 🔵 |
| TC-062-RES-004 | `test_advice_success_response_contains_recommendations` | TestAdviceHandlerSuccess | 正常系 | 🔵 |
| TC-062-RES-005 | `test_advice_success_response_contains_study_stats` | TestAdviceHandlerSuccess | 正常系 | 🔵 |
| TC-062-RES-006 | `test_advice_success_response_contains_advice_info` | TestAdviceHandlerSuccess | 正常系 | 🔵 |
| TC-062-RES-007 | `test_advice_success_response_is_json` | TestAdviceHandlerSuccess | 正常系 | 🔵 |
| TC-062-RES-008 | `test_advice_success_full_e2e_flow` | TestAdviceHandlerSuccess | 正常系 | 🔵 |
| TC-062-ERR-001 | `test_advice_returns_504_on_ai_timeout` | TestAdviceHandlerAIErrors | AI エラー | 🔵 |
| TC-062-ERR-002 | `test_advice_returns_429_on_ai_rate_limit` | TestAdviceHandlerAIErrors | AI エラー | 🔵 |
| TC-062-ERR-003 | `test_advice_returns_503_on_ai_provider_error` | TestAdviceHandlerAIErrors | AI エラー | 🔵 |
| TC-062-ERR-004 | `test_advice_returns_500_on_ai_parse_error` | TestAdviceHandlerAIErrors | AI エラー | 🔵 |
| TC-062-ERR-005 | `test_advice_returns_500_on_ai_internal_error` | TestAdviceHandlerAIErrors | AI エラー | 🔵 |
| TC-062-ERR-006 | `test_advice_returns_503_on_factory_init_failure` | TestAdviceHandlerAIErrors | AI エラー | 🔵 |
| TC-062-ERR-007 | `test_advice_returns_500_on_unexpected_exception` | TestAdviceHandlerAIErrors | AI エラー | 🔵 |
| TC-062-DB-001 | `test_advice_handles_review_service_exception` | TestAdviceHandlerDBErrors | DB エラー | 🔵 |
| TC-062-DB-002 | `test_advice_works_with_empty_review_summary` | TestAdviceHandlerDBErrors | DB エラー | 🔵 |
| TC-062-LOG-001 | `test_advice_logs_request_info` | TestAdviceHandlerLogging | ロギング | 🔵 |
| TC-062-LOG-002 | `test_advice_logs_success_info` | TestAdviceHandlerLogging | ロギング | 🔵 |
| TC-062-LOG-003 | `test_advice_logs_ai_error` | TestAdviceHandlerLogging | ロギング | 🔵 |

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 54 | 98.2% |
| 🟡 黄信号 | 1 | 1.8% |
| 🔴 赤信号 | 0 | 0% |

### 黄信号の理由

| TC ID | 理由 |
|-------|------|
| TC-STR-ADV-013 | Strands SDK 経由の `ClientError (ThrottlingException)` のレート制限マッピングは SDK の例外伝搬方式に依存。`_is_rate_limit_error()` のフォールバック文字列マッチに依存する可能性がある。 |

---

## パターン対照表

各テストファイルで使用するパターンの出典。

| パターン | 参照ファイル | 行 |
|---------|------------|-----|
| `_make_mock_agent_instance()` ヘルパー | `test_strands_service.py` | L84-94 |
| `_mock_invoke_response()` ヘルパー | `test_bedrock.py` (TestBedrockGradeAnswer) | L366-371 |
| `_make_advice_event()` ヘルパー | `test_handler_grade_ai.py` の `_make_grade_ai_event()` | L33-86 |
| `mock_review_service` フィクスチャ | `test_handler_grade_ai.py` の `mock_card_service` | L94-105 |
| `mock_ai_service` フィクスチャ | `test_handler_grade_ai.py` の `mock_ai_service` | L108-126 |
| `lambda_context` フィクスチャ | `conftest.py` | L84-94 |
| StrandsAIService Agent + BedrockModel パッチ | `test_strands_service.py` 全テスト | 全体 |
| BedrockService フィクスチャ | `test_bedrock.py` (TestBedrockGradeAnswer) | L356-363 |

---

*作成日*: 2026-02-24
*タスク*: TASK-0062 TDD testcases Phase
*テスト合計*: 55 件（🔵 54 件 / 🟡 1 件 / 🔴 0 件）
