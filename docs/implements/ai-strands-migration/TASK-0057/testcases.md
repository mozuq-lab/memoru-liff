# TASK-0057: StrandsAIService 基本実装（カード生成） - テストケース設計書

**作成日**: 2026-02-23
**タスクID**: TASK-0057
**タスクタイプ**: TDD (Red -> Green -> Refactor -> Verify)
**テストファイル**: `backend/tests/unit/test_strands_service.py`（新規作成）

---

## テスト方針

### 概要

StrandsAIService クラスのテストスイート。AIService Protocol 準拠、Strands Agent 経由のカード生成、エラーハンドリング、レスポンス解析、環境別モデルプロバイダー選択、ファクトリ統合を検証する。

### 全体原則

- 全メソッドは **同期（sync）** である（async ではない）
- 外部依存（Strands Agent、BedrockModel、OllamaModel）は全て `unittest.mock` でモックする
- 例外は **AIServiceError 階層**（`services.ai_service` 由来）のみを使用する。`BedrockServiceError` は一切使用しない
- Strands SDK の Agent API は **🟡**（実装時に調整の可能性がある）
- テストカバレッジ 80% 以上を目標とする（REQ-SM-404）

### モック戦略

| モック対象 | パッチパス | 目的 |
|-----------|-----------|------|
| Strands `Agent` クラス | `services.strands_service.Agent` | Agent 初期化・呼び出しの分離 |
| `BedrockModel` | `services.strands_service.BedrockModel` | Bedrock プロバイダー初期化の分離 |
| `OllamaModel` | `services.strands_service.OllamaModel` | Ollama プロバイダー初期化の分離 |
| 環境変数 | `@patch.dict(os.environ, {...})` | 環境別動作テスト |
| `get_card_generation_prompt` | 必要に応じて `@patch` | プロンプト引数検証 |

### テストデータフィクスチャ

```python
@pytest.fixture
def mock_agent():
    """モック化された Strands Agent."""
    # Agent の __call__ メソッドをモックし、レスポンスを返す

@pytest.fixture
def valid_agent_response():
    """Agent が返す正常なレスポンステキスト."""
    return json.dumps({
        "cards": [
            {"front": "光合成とは何か？", "back": "植物が太陽光を使って...", "tags": ["生物学"]},
            {"front": "葉緑体の役割は？", "back": "光合成の場...", "tags": ["生物学", "細胞"]},
            {"front": "光合成の化学式は？", "back": "6CO2 + 6H2O → C6H12O6 + 6O2", "tags": ["化学"]},
        ]
    })

@pytest.fixture
def markdown_wrapped_response():
    """Markdown コードブロックで囲まれた JSON レスポンス."""
    return '```json\n{"cards": [{"front": "Q1", "back": "A1", "tags": ["tag1"]}]}\n```'

@pytest.fixture
def invalid_json_response():
    """JSON として解析できないレスポンス."""
    return "This is not valid JSON at all"

@pytest.fixture
def missing_cards_response():
    """cards フィールドが欠落したレスポンス."""
    return json.dumps({"data": "no cards here"})

@pytest.fixture
def all_invalid_cards_response():
    """全カードが無効なレスポンス."""
    return json.dumps({"cards": [{"front": ""}, {"back": "A2"}]})
```

### import 構成

```python
import inspect
import json
import os
import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from services.ai_service import (
    AIService,
    GeneratedCard,
    GenerationResult,
    GradingResult,
    LearningAdvice,
    DifficultyLevel,
    Language,
    AIServiceError,
    AITimeoutError,
    AIRateLimitError,
    AIParseError,
    AIProviderError,
    create_ai_service,
)
from services.strands_service import StrandsAIService
```

---

## Category 1: Protocol 準拠テスト (TC-PROTO)

### TC-PROTO-001: isinstance(StrandsAIService, AIService) が True を返す 🔵

**信頼性**: 🔵 *`ai_service.py` L109 の `@runtime_checkable AIService(Protocol)` 定義より確定*

**Given**: StrandsAIService のインスタンスを作成する（Agent・Model はモック化）
**When**: `isinstance(instance, AIService)` を評価する
**Then**: `True` が返される

```python
def test_strands_service_implements_ai_service_protocol(self):
    """StrandsAIService は AIService Protocol を満たす."""
    # Given
    with patch("services.strands_service.Agent"), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()

    # Then
    assert isinstance(service, AIService)
```

**検証根拠**: `ai_service.py` の `@runtime_checkable class AIService(Protocol)` 定義。StrandsAIService が `generate_cards`, `grade_answer`, `get_learning_advice` の 3 メソッドを持てば Protocol チェックを通過する。

---

### TC-PROTO-002: 3 メソッドが全て存在し callable である 🔵

**信頼性**: 🔵 *`ai_service.py` L113-167 の Protocol メソッド定義より確定*

**Given**: StrandsAIService のインスタンスを作成する
**When**: `hasattr` と `callable` で各メソッドを検証する
**Then**: `generate_cards`, `grade_answer`, `get_learning_advice` が全て存在し callable である

```python
def test_strands_service_has_all_protocol_methods(self):
    """Protocol 定義の 3 メソッドが全て存在する."""
    with patch("services.strands_service.Agent"), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()

    assert hasattr(service, "generate_cards") and callable(service.generate_cards)
    assert hasattr(service, "grade_answer") and callable(service.grade_answer)
    assert hasattr(service, "get_learning_advice") and callable(service.get_learning_advice)
```

---

### TC-PROTO-003: generate_cards() の引数名・デフォルト値が Protocol 定義と一致する 🔵

**信頼性**: 🔵 *`ai_service.py` L113-131 の Protocol 定義の `inspect.signature` で確認可能*

**Given**: StrandsAIService の `generate_cards` メソッド
**When**: `inspect.signature` でシグネチャを取得する
**Then**: `input_text`（必須）, `card_count`（default=5）, `difficulty`（default="medium"）, `language`（default="ja"）が存在する

```python
def test_generate_cards_signature_matches_protocol(self):
    """generate_cards() のシグネチャが Protocol と一致する."""
    with patch("services.strands_service.Agent"), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()

    sig = inspect.signature(service.generate_cards)
    params = sig.parameters

    assert "input_text" in params
    assert "card_count" in params
    assert params["card_count"].default == 5
    assert "difficulty" in params
    assert params["difficulty"].default == "medium"
    assert "language" in params
    assert params["language"].default == "ja"
```

---

## Category 2: カード生成 正常系テスト (TC-GEN)

### TC-GEN-001: 有効な入力で GenerationResult が返される 🔵

**信頼性**: 🔵 *`ai_service.py` L27-34 の GenerationResult 定義、bedrock.py L118-165 のパターンより確定*

**Given**: `input_text="光合成は植物が太陽光を..."`, `card_count=3`, `difficulty="medium"`, `language="ja"`。Agent は正常な JSON を返すようモック化。
**When**: `generate_cards()` を呼び出す
**Then**: `GenerationResult` が返され、3 枚のカードが含まれ、各カードが `front`, `back`, `suggested_tags` を持つ

```python
def test_generate_cards_happy_path(self):
    """有効な入力で GenerationResult が返される."""
    # Given
    mock_agent_instance = MagicMock()
    response_json = json.dumps({
        "cards": [
            {"front": "Q1", "back": "A1", "tags": ["tag1"]},
            {"front": "Q2", "back": "A2", "tags": ["tag2"]},
            {"front": "Q3", "back": "A3", "tags": ["tag3"]},
        ]
    })
    # Agent の呼び出し結果を設定（🟡 実際の戻り値形式は SDK に依存）
    mock_agent_instance.return_value = MagicMock()
    mock_agent_instance.return_value.__str__ = MagicMock(return_value=response_json)
    # または mock_agent_instance.return_value.message = response_json 等

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()
        result = service.generate_cards(
            input_text="光合成は植物が太陽光を使って二酸化炭素と水から有機物を合成する反応です。",
            card_count=3,
            difficulty="medium",
            language="ja",
        )

    # Then
    assert isinstance(result, GenerationResult)
    assert len(result.cards) == 3
    for card in result.cards:
        assert isinstance(card, GeneratedCard)
        assert len(card.front) > 0
        assert len(card.back) > 0
        assert isinstance(card.suggested_tags, list)
```

**注意**: Agent の戻り値形式（`str(result)` or `result.message` 等）は 🟡。実装時に SDK 仕様に合わせてモックを調整する。

---

### TC-GEN-002: input_length が入力テキストの長さと一致する 🔵

**信頼性**: 🔵 *bedrock.py L162 の `input_length=len(input_text)` パターンより確定*

**Given**: 150 文字の `input_text`
**When**: `generate_cards()` を呼び出す
**Then**: `result.input_length == 150`

```python
def test_generate_cards_input_length(self):
    """input_length が入力テキストの文字数と一致する."""
    input_text = "あ" * 150  # 150文字

    # ... Agent モック設定 ...
    result = service.generate_cards(input_text=input_text)

    assert result.input_length == 150
```

---

### TC-GEN-003: model_used が空でない文字列である 🔵

**信頼性**: 🔵 *`ai_service.py` L33 の `model_used: str` フィールド定義より確定*

**Given**: Bedrock プロバイダーを使用する構成
**When**: `generate_cards()` を呼び出す
**Then**: `result.model_used` が空でない文字列

```python
def test_generate_cards_model_used_is_nonempty_string(self):
    """model_used が空でない文字列を含む."""
    # ... Agent モック設定 ...
    result = service.generate_cards(input_text="テスト入力テキスト")

    assert isinstance(result.model_used, str)
    assert len(result.model_used) > 0
```

---

### TC-GEN-004: processing_time_ms が 0 以上の整数である 🔵

**信頼性**: 🔵 *bedrock.py L158 の `int((time.time() - start_time) * 1000)` パターンより確定*

**Given**: 正常に処理が完了する
**When**: `generate_cards()` を呼び出す
**Then**: `result.processing_time_ms >= 0` かつ `int` 型

```python
def test_generate_cards_processing_time_ms(self):
    """processing_time_ms が 0 以上の整数である."""
    # ... Agent モック設定 ...
    result = service.generate_cards(input_text="テスト入力テキスト")

    assert isinstance(result.processing_time_ms, int)
    assert result.processing_time_ms >= 0
```

---

### TC-GEN-005: get_card_generation_prompt() に正しい引数が渡される 🔵

**信頼性**: 🔵 *bedrock.py L145-150 の `get_card_generation_prompt()` 呼び出しパターンより確定*

**Given**: `card_count=7`, `difficulty="hard"`, `language="en"`
**When**: `generate_cards()` を呼び出す
**Then**: `get_card_generation_prompt(input_text, 7, "hard", "en")` が呼び出される

```python
@patch("services.strands_service.get_card_generation_prompt", return_value="mocked prompt")
def test_generate_cards_passes_correct_args_to_prompt(self, mock_prompt):
    """get_card_generation_prompt() に正しい引数が渡される."""
    input_text = "Test input"

    # ... Agent モック設定 ...
    service.generate_cards(
        input_text=input_text,
        card_count=7,
        difficulty="hard",
        language="en",
    )

    mock_prompt.assert_called_once_with(
        input_text=input_text,
        card_count=7,
        difficulty="hard",
        language="en",
    )
```

---

## Category 3: 環境別モデルプロバイダー選択テスト (TC-ENV)

### TC-ENV-001: ENVIRONMENT=dev で OllamaModel が選択される 🟡

**信頼性**: 🟡 *architecture.md の環境別プロバイダー設計より。OllamaModel のコンストラクタ引数は SDK に依存*

**Given**: `os.environ["ENVIRONMENT"] = "dev"`
**When**: `StrandsAIService()` を初期化する
**Then**: `OllamaModel` が呼び出される（`BedrockModel` は呼び出されない）

```python
@patch.dict(os.environ, {"ENVIRONMENT": "dev"})
@patch("services.strands_service.Agent")
@patch("services.strands_service.OllamaModel")
@patch("services.strands_service.BedrockModel")
def test_dev_environment_selects_ollama(self, mock_bedrock, mock_ollama, mock_agent):
    """ENVIRONMENT=dev で OllamaModel が選択される."""
    service = StrandsAIService()

    mock_ollama.assert_called_once()
    mock_bedrock.assert_not_called()
```

---

### TC-ENV-002: ENVIRONMENT=prod で BedrockModel が選択される 🟡

**信頼性**: 🟡 *architecture.md の環境別プロバイダー設計より。BedrockModel のコンストラクタ引数は SDK に依存*

**Given**: `os.environ["ENVIRONMENT"] = "prod"`
**When**: `StrandsAIService()` を初期化する
**Then**: `BedrockModel` が呼び出される（`OllamaModel` は呼び出されない）

```python
@patch.dict(os.environ, {"ENVIRONMENT": "prod"})
@patch("services.strands_service.Agent")
@patch("services.strands_service.BedrockModel")
@patch("services.strands_service.OllamaModel")
def test_prod_environment_selects_bedrock(self, mock_ollama, mock_bedrock, mock_agent):
    """ENVIRONMENT=prod で BedrockModel が選択される."""
    service = StrandsAIService()

    mock_bedrock.assert_called_once()
    mock_ollama.assert_not_called()
```

---

### TC-ENV-003: ENVIRONMENT=staging で BedrockModel が選択される 🟡

**信頼性**: 🟡 *architecture.md の環境別プロバイダー設計より*

**Given**: `os.environ["ENVIRONMENT"] = "staging"`
**When**: `StrandsAIService()` を初期化する
**Then**: `BedrockModel` が呼び出される

```python
@patch.dict(os.environ, {"ENVIRONMENT": "staging"})
@patch("services.strands_service.Agent")
@patch("services.strands_service.BedrockModel")
def test_staging_environment_selects_bedrock(self, mock_bedrock, mock_agent):
    """ENVIRONMENT=staging で BedrockModel が選択される."""
    service = StrandsAIService()

    mock_bedrock.assert_called_once()
```

---

### TC-ENV-004: ENVIRONMENT 未設定で BedrockModel がデフォルト選択される 🔵

**信頼性**: 🔵 *requirements.md REQ-3.3 のデフォルト値「prod」、安全なフォールバック方針より確定*

**Given**: `ENVIRONMENT` 環境変数が設定されていない
**When**: `StrandsAIService()` を初期化する
**Then**: `BedrockModel` がデフォルトで選択される（安全なフォールバック）

```python
@patch.dict(os.environ, {}, clear=False)
@patch("services.strands_service.Agent")
@patch("services.strands_service.BedrockModel")
def test_no_environment_defaults_to_bedrock(self, mock_bedrock, mock_agent):
    """ENVIRONMENT 未設定でも BedrockModel がデフォルト選択される."""
    os.environ.pop("ENVIRONMENT", None)
    service = StrandsAIService()

    mock_bedrock.assert_called_once()
```

**注意**: conftest.py で `os.environ["ENVIRONMENT"] = "test"` が設定されているため、テスト内で明示的に `ENVIRONMENT` を削除する必要がある。

---

### TC-ENV-005: コンストラクタの environment 引数でオーバーライドできる 🔵

**信頼性**: 🔵 *requirements.md REQ-3.1 の `__init__(environment: str | None = None)` 仕様より確定*

**Given**: `os.environ["ENVIRONMENT"] = "prod"`
**When**: `StrandsAIService(environment="dev")` を初期化する
**Then**: 環境変数を無視し `OllamaModel` が選択される

```python
@patch.dict(os.environ, {"ENVIRONMENT": "prod"})
@patch("services.strands_service.Agent")
@patch("services.strands_service.OllamaModel")
@patch("services.strands_service.BedrockModel")
def test_constructor_environment_overrides_env_var(self, mock_bedrock, mock_ollama, mock_agent):
    """コンストラクタ引数で環境変数をオーバーライドできる."""
    service = StrandsAIService(environment="dev")

    mock_ollama.assert_called_once()
    mock_bedrock.assert_not_called()
```

---

## Category 4: Phase 3 スタブメソッドテスト (TC-STUB)

### TC-STUB-001: grade_answer() が NotImplementedError を raise する 🔵

**信頼性**: 🔵 *TASK-0057.md L65-67、requirements.md REQ-4.1 より確定*

**Given**: StrandsAIService インスタンス
**When**: `grade_answer("Q", "A", "answer")` を呼び出す
**Then**: `NotImplementedError` が raise される

```python
def test_grade_answer_raises_not_implemented(self):
    """grade_answer() は NotImplementedError を raise する."""
    with patch("services.strands_service.Agent"), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()

    with pytest.raises(NotImplementedError):
        service.grade_answer(
            card_front="日本の首都は？",
            card_back="東京",
            user_answer="東京",
        )
```

---

### TC-STUB-002: get_learning_advice() が NotImplementedError を raise する 🔵

**信頼性**: 🔵 *TASK-0057.md L69-71、requirements.md REQ-4.2 より確定*

**Given**: StrandsAIService インスタンス
**When**: `get_learning_advice({"total_reviews": 10})` を呼び出す
**Then**: `NotImplementedError` が raise される

```python
def test_get_learning_advice_raises_not_implemented(self):
    """get_learning_advice() は NotImplementedError を raise する."""
    with patch("services.strands_service.Agent"), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()

    with pytest.raises(NotImplementedError):
        service.get_learning_advice(
            review_summary={"total_reviews": 10},
        )
```

---

### TC-STUB-003: NotImplementedError のメッセージに "Phase 3" を含む 🔵

**信頼性**: 🔵 *requirements.md REQ-4.1, REQ-4.2 のメッセージ仕様より確定*

**Given**: StrandsAIService インスタンス
**When**: `grade_answer()` および `get_learning_advice()` を呼び出す
**Then**: 各エラーメッセージに "Phase 3" が含まれる

```python
def test_not_implemented_error_message_contains_phase3(self):
    """NotImplementedError のメッセージに 'Phase 3' を含む."""
    with patch("services.strands_service.Agent"), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()

    with pytest.raises(NotImplementedError, match="Phase 3"):
        service.grade_answer(card_front="Q", card_back="A", user_answer="A")

    with pytest.raises(NotImplementedError, match="Phase 3"):
        service.get_learning_advice(review_summary={})
```

---

## Category 5: エラーハンドリングテスト (TC-ERR)

### TC-ERR-001: Agent タイムアウト時に AITimeoutError が raise される 🟡

**信頼性**: 🟡 *architecture.md のエラーマッピング表より。Strands SDK のタイムアウト例外クラス名は SDK に依存*

**Given**: Strands Agent 呼び出しで `TimeoutError` が発生する
**When**: `generate_cards()` を呼び出す
**Then**: `AITimeoutError` が raise される

```python
def test_agent_timeout_raises_ai_timeout_error(self):
    """Agent タイムアウト時に AITimeoutError が raise される."""
    mock_agent_instance = MagicMock()
    mock_agent_instance.side_effect = TimeoutError("Agent timed out")

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()

        with pytest.raises(AITimeoutError):
            service.generate_cards(input_text="テスト")
```

**注意**: Strands SDK が独自のタイムアウト例外を持つ場合は、そのクラスを `side_effect` に使用する。

---

### TC-ERR-002: プロバイダー接続エラー時に AIProviderError が raise される 🟡

**信頼性**: 🟡 *architecture.md のエラーマッピング表より。接続エラーの具体的な例外クラスは SDK に依存*

**Given**: モデルプロバイダー（Bedrock/Ollama）が利用不可で `ConnectionError` が発生する
**When**: `generate_cards()` を呼び出す
**Then**: `AIProviderError` が raise される

```python
def test_provider_connection_error_raises_ai_provider_error(self):
    """プロバイダー接続エラー時に AIProviderError が raise される."""
    mock_agent_instance = MagicMock()
    mock_agent_instance.side_effect = ConnectionError("Connection refused")

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()

        with pytest.raises(AIProviderError):
            service.generate_cards(input_text="テスト")
```

---

### TC-ERR-003: 不正な JSON レスポンス時に AIParseError が raise される 🔵

**信頼性**: 🔵 *bedrock.py L485-486 の `json.JSONDecodeError` → `ParseError` パターンより確定*

**Given**: Agent のレスポンスが有効な JSON でない文字列
**When**: `generate_cards()` を呼び出す（レスポンス解析フェーズでエラー発生）
**Then**: `AIParseError` が raise される

```python
def test_invalid_json_response_raises_ai_parse_error(self):
    """不正な JSON レスポンス時に AIParseError が raise される."""
    mock_agent_instance = MagicMock()
    # Agent が JSON でない文字列を返す
    mock_agent_instance.return_value = MagicMock(__str__=MagicMock(return_value="This is not JSON"))

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()

        with pytest.raises(AIParseError):
            service.generate_cards(input_text="テスト")
```

---

### TC-ERR-004: 必須フィールド "cards" 欠落時に AIParseError が raise される 🔵

**信頼性**: 🔵 *bedrock.py L448-449 の `'cards' not in data` チェックパターンより確定*

**Given**: Agent レスポンスの JSON に "cards" フィールドが存在しない
**When**: `generate_cards()` を呼び出す
**Then**: `AIParseError` が raise される

```python
def test_missing_cards_field_raises_ai_parse_error(self):
    """'cards' フィールドが欠落した場合 AIParseError が raise される."""
    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = MagicMock(
        __str__=MagicMock(return_value=json.dumps({"data": []}))
    )

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()

        with pytest.raises(AIParseError):
            service.generate_cards(input_text="テスト")
```

---

### TC-ERR-005: 例外チェーンが from e で保持される 🔵

**信頼性**: 🔵 *requirements.md REQ-5.2 のエラーメッセージ要件「from e で連鎖」より確定*

**Given**: 内部で `json.JSONDecodeError` が発生する
**When**: `AIParseError` が raise される
**Then**: `err.__cause__` が元の例外を参照している

```python
def test_exception_chain_preserved_with_from_e(self):
    """例外チェーンが __cause__ で保持される."""
    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = MagicMock(
        __str__=MagicMock(return_value="not valid json {{{")
    )

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()

        with pytest.raises(AIParseError) as exc_info:
            service.generate_cards(input_text="テスト")

        assert exc_info.value.__cause__ is not None
```

---

### TC-ERR-006: 全ての例外が AIServiceError のサブクラスである 🔵

**信頼性**: 🔵 *`ai_service.py` L72-105 の例外階層定義より確定*

**Given**: `generate_cards()` で raise される可能性のある各例外
**When**: 各例外のクラス階層を検証する
**Then**: 全て `isinstance(err, AIServiceError)` が `True`

```python
@pytest.mark.parametrize("exception_class", [
    AITimeoutError,
    AIRateLimitError,
    AIParseError,
    AIProviderError,
    AIServiceError,
])
def test_all_exceptions_are_ai_service_error_subclasses(self, exception_class):
    """StrandsAIService が使用する例外は全て AIServiceError のサブクラス."""
    assert issubclass(exception_class, AIServiceError)
    err = exception_class("test")
    assert isinstance(err, AIServiceError)
```

---

### TC-ERR-007: 未知の例外が AIServiceError にラップされる 🔵

**信頼性**: 🔵 *requirements.md REQ-5.4 の try-except 構造「未知の例外を AIServiceError にラップ」より確定*

**Given**: Agent 呼び出しで予期しない `RuntimeError` が発生する
**When**: `generate_cards()` を呼び出す
**Then**: `AIServiceError` が raise される（サブクラスではなく基底クラスでもキャッチ可能）

```python
def test_unknown_exception_wrapped_in_ai_service_error(self):
    """予期しない例外は AIServiceError にラップされる."""
    mock_agent_instance = MagicMock()
    mock_agent_instance.side_effect = RuntimeError("Something unexpected")

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()

        with pytest.raises(AIServiceError):
            service.generate_cards(input_text="テスト")
```

---

### TC-ERR-008: レート制限エラー時に AIRateLimitError が raise される 🟡

**信頼性**: 🟡 *architecture.md のエラーマッピング表より。Bedrock の ThrottlingException 等を Strands SDK がどうラップするかは SDK に依存*

**Given**: Agent 呼び出しでレート制限エラーが発生する
**When**: `generate_cards()` を呼び出す
**Then**: `AIRateLimitError` が raise される

```python
def test_rate_limit_raises_ai_rate_limit_error(self):
    """レート制限エラー時に AIRateLimitError が raise される."""
    # 🟡 Strands SDK のレート制限例外クラスに応じて side_effect を調整
    mock_agent_instance = MagicMock()
    # ClientError の ThrottlingException 等をシミュレート
    from botocore.exceptions import ClientError
    mock_agent_instance.side_effect = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate limit"}},
        "InvokeModel",
    )

    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()

        with pytest.raises(AIRateLimitError):
            service.generate_cards(input_text="テスト")
```

**注意**: Strands SDK が botocore.ClientError をそのまま伝播するか、独自例外にラップするかは SDK に依存。テスト実装時に調整が必要。

---

## Category 6: レスポンス解析テスト (TC-PARSE)

### TC-PARSE-001: 正常な JSON レスポンスからカードリストが生成される 🔵

**信頼性**: 🔵 *bedrock.py L451-478 の `_parse_response()` パターン、`ai_service.py` の GeneratedCard 定義より確定*

**Given**: `{"cards": [{"front": "Q1", "back": "A1", "tags": ["tag1"]}]}`
**When**: レスポンスを解析する
**Then**: `GeneratedCard(front="Q1", back="A1", suggested_tags=["AI生成", "tag1"])` が生成される

```python
def test_parse_valid_json_creates_generated_cards(self):
    """正常な JSON からカードが生成される."""
    # Agent が返す JSON を設定
    response = json.dumps({
        "cards": [{"front": "Q1", "back": "A1", "tags": ["tag1"]}]
    })
    # ... service.generate_cards() 呼び出し ...

    assert len(result.cards) == 1
    assert result.cards[0].front == "Q1"
    assert result.cards[0].back == "A1"
    assert "AI生成" in result.cards[0].suggested_tags
    assert "tag1" in result.cards[0].suggested_tags
```

---

### TC-PARSE-002: Markdown コードブロック内の JSON が正しく解析される 🔵

**信頼性**: 🔵 *bedrock.py L439-441 の `re.search(r"```json\s*([\s\S]*?)\s*```")` パターンより確定*

**Given**: `` ```json\n{"cards": [{"front": "Q1", "back": "A1", "tags": []}]}\n``` ``
**When**: レスポンスを解析する
**Then**: コードブロック内の JSON が正しくパースされ、1 枚のカードが返される

```python
def test_parse_markdown_wrapped_json(self):
    """Markdown コードブロック内の JSON が正しく解析される."""
    response = '```json\n{"cards": [{"front": "Q1", "back": "A1", "tags": []}]}\n```'
    # ... service.generate_cards() 呼び出し ...

    assert len(result.cards) == 1
    assert result.cards[0].front == "Q1"
```

---

### TC-PARSE-003: front / back 欠落カードがスキップされる 🔵

**信頼性**: 🔵 *bedrock.py L454-455 の `if "front" not in card_data or "back" not in card_data: continue` パターンより確定*

**Given**: `{"cards": [{"front": "Q1"}, {"front": "Q2", "back": "A2"}]}`（1 枚目は back 欠落）
**When**: レスポンスを解析する
**Then**: back 欠落の 1 枚目がスキップされ、有効な 1 枚のみ返される

```python
def test_parse_skips_cards_missing_front_or_back(self):
    """front/back 欠落カードはスキップされる."""
    response = json.dumps({
        "cards": [
            {"front": "Q1"},           # back 欠落
            {"back": "A2"},            # front 欠落
            {"front": "Q3", "back": "A3"},  # 有効
        ]
    })
    # ... service.generate_cards() 呼び出し ...

    assert len(result.cards) == 1
    assert result.cards[0].front == "Q3"
```

---

### TC-PARSE-004: 全カードが無効な場合に AIParseError が raise される 🔵

**信頼性**: 🔵 *bedrock.py L480-481 の `if not cards: raise BedrockParseError` パターンより確定*

**Given**: `{"cards": [{"front": ""}, {"back": "A2"}]}`（全て無効）
**When**: レスポンスを解析する
**Then**: `AIParseError` が raise される

```python
def test_parse_all_invalid_cards_raises_ai_parse_error(self):
    """全カードが無効な場合 AIParseError が raise される."""
    response = json.dumps({
        "cards": [
            {"front": "", "back": "A1"},   # front 空
            {"front": "Q2", "back": ""},   # back 空
            {"front": "Q3"},               # back 欠落
        ]
    })
    # ... service.generate_cards() で AIParseError を期待 ...
```

---

### TC-PARSE-005: tags フィールドがない場合に "AI生成" のみのリストとなる 🔵

**信頼性**: 🔵 *bedrock.py L463-470 の `tags = card_data.get("tags", [])` + "AI生成" 挿入パターンより確定*

**Given**: `{"cards": [{"front": "Q", "back": "A"}]}`（tags なし）
**When**: レスポンスを解析する
**Then**: `suggested_tags` が `["AI生成"]` となる

```python
def test_parse_missing_tags_defaults_to_ai_generated_only(self):
    """tags がない場合、suggested_tags は ['AI生成'] となる."""
    response = json.dumps({"cards": [{"front": "Q", "back": "A"}]})
    # ... service.generate_cards() 呼び出し ...

    assert result.cards[0].suggested_tags == ["AI生成"]
```

---

### TC-PARSE-006: "cards" フィールドがない JSON で AIParseError が raise される 🔵

**信頼性**: 🔵 *bedrock.py L448-449 の `if "cards" not in data` チェックパターンより確定*

**Given**: `{"data": [...]}`（cards キーなし）
**When**: レスポンスを解析する
**Then**: `AIParseError` が raise される

```python
def test_parse_missing_cards_key_raises_ai_parse_error(self):
    """'cards' キーがない JSON で AIParseError."""
    response = json.dumps({"data": [], "items": []})
    # ... service.generate_cards() で AIParseError を期待 ...
```

（TC-ERR-004 と同一ロジックだが、テストデータが異なる。どちらか一方に統合してもよい。）

---

### TC-PARSE-007: "AI生成" タグが既存の場合、重複追加されない 🔵

**信頼性**: 🔵 *bedrock.py L469 の `if "AI生成" not in tags and "AI Generated" not in tags` 条件より確定*

**Given**: `{"cards": [{"front": "Q", "back": "A", "tags": ["AI生成", "physics"]}]}`
**When**: レスポンスを解析する
**Then**: `suggested_tags` が `["AI生成", "physics"]`（重複なし）

```python
def test_parse_no_duplicate_ai_generated_tag(self):
    """'AI生成' タグが既存の場合は重複追加しない."""
    response = json.dumps({
        "cards": [{"front": "Q", "back": "A", "tags": ["AI生成", "physics"]}]
    })
    # ... service.generate_cards() 呼び出し ...

    assert result.cards[0].suggested_tags == ["AI生成", "physics"]
    assert result.cards[0].suggested_tags.count("AI生成") == 1
```

---

### TC-PARSE-008: tags がリストでない場合に空リストにフォールバックする 🔵

**信頼性**: 🔵 *bedrock.py L464 の `if not isinstance(tags, list): tags = []` パターンより確定*

**Given**: `{"cards": [{"front": "Q", "back": "A", "tags": "not-a-list"}]}`
**When**: レスポンスを解析する
**Then**: `suggested_tags` が `["AI生成"]` となる（不正な tags はリセットされ、"AI生成" のみ付与）

```python
def test_parse_non_list_tags_falls_back_to_empty(self):
    """tags がリストでない場合は空リストにフォールバック."""
    response = json.dumps({
        "cards": [{"front": "Q", "back": "A", "tags": "string-tag"}]
    })
    # ... service.generate_cards() 呼び出し ...

    assert result.cards[0].suggested_tags == ["AI生成"]
```

---

### TC-PARSE-009: 空カード配列で AIParseError が raise される 🔵

**信頼性**: 🔵 *bedrock.py L480-481 の `if not cards: raise` パターンより確定*

**Given**: `{"cards": []}`
**When**: レスポンスを解析する
**Then**: `AIParseError` が raise される

```python
def test_parse_empty_cards_array_raises_ai_parse_error(self):
    """空の cards 配列で AIParseError."""
    response = json.dumps({"cards": []})
    # ... service.generate_cards() で AIParseError を期待 ...
```

---

## Category 7: ファクトリ統合テスト (TC-COMPAT)

### TC-COMPAT-001: create_ai_service(use_strands=True) が StrandsAIService を返す 🔵

**信頼性**: 🔵 *`ai_service.py` L188-192 の factory 関数実装より確定*

**Given**: `USE_STRANDS` 環境変数は設定されていない
**When**: `create_ai_service(use_strands=True)` を呼び出す
**Then**: 返り値が `StrandsAIService` のインスタンスである

```python
def test_factory_returns_strands_service_when_use_strands_true(self):
    """create_ai_service(use_strands=True) が StrandsAIService を返す."""
    with patch("services.strands_service.Agent"), \
         patch("services.strands_service.BedrockModel"):
        service = create_ai_service(use_strands=True)

    assert isinstance(service, StrandsAIService)
```

**注意**: このテストは `services.strands_service` モジュールが存在し、import 可能であることを前提とする。Red フェーズではモジュール自体が存在しないため、`ImportError` で失敗する。

---

### TC-COMPAT-002: GenerationResult のフィールドが API 仕様と一致する 🔵

**信頼性**: 🔵 *`ai_service.py` L27-34 の GenerationResult 定義、api-endpoints.md のレスポンス仕様より確定*

**Given**: `generate_cards()` の正常実行
**When**: 結果の `GenerationResult` を検証する
**Then**: `cards`, `input_length`, `model_used`, `processing_time_ms` の全フィールドが存在し適切な型である

```python
def test_generation_result_has_all_required_fields(self):
    """GenerationResult が API 仕様に準拠した全フィールドを持つ."""
    # ... Agent モック設定、generate_cards() 呼び出し ...

    assert hasattr(result, "cards")
    assert hasattr(result, "input_length")
    assert hasattr(result, "model_used")
    assert hasattr(result, "processing_time_ms")

    assert isinstance(result.cards, list)
    assert isinstance(result.input_length, int)
    assert isinstance(result.model_used, str)
    assert isinstance(result.processing_time_ms, int)
```

---

## テストケースサマリー

### カテゴリ別件数

| カテゴリ | テストケース ID | 件数 |
|---------|----------------|------|
| Protocol 準拠 | TC-PROTO-001 ~ 003 | 3 |
| カード生成 正常系 | TC-GEN-001 ~ 005 | 5 |
| 環境プロバイダー | TC-ENV-001 ~ 005 | 5 |
| Phase 3 スタブ | TC-STUB-001 ~ 003 | 3 |
| エラーハンドリング | TC-ERR-001 ~ 008 | 8 |
| レスポンス解析 | TC-PARSE-001 ~ 009 | 9 |
| ファクトリ統合 | TC-COMPAT-001 ~ 002 | 2 |
| **合計** | | **35** |

### 信頼性レベル分布

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 29 | 83% |
| 🟡 黄信号 | 6 | 17% |
| 🔴 赤信号 | 0 | 0% |

**品質評価**: 高品質（青信号 83%、赤信号なし。黄信号は Strands SDK 固有の API 部分のみ）

### 信頼性レベルの判定基準

- **🔵 青信号**: `ai_service.py` の Protocol 定義、`bedrock.py` の既存パターン、`requirements.md` の仕様など、コードベースまたは設計文書から直接確認できる要件に基づくテスト
- **🟡 黄信号**: Strands Agents SDK の具体的な API（Agent 呼び出し形式、戻り値構造、例外クラス名、`BedrockModel`/`OllamaModel` のコンストラクタ引数）など、SDK ドキュメント調査時に調整が必要なテスト
- **🔴 赤信号**: 該当なし

### 🟡 黄信号テストケース一覧（実装時の調整ポイント）

| TC ID | 調整対象 | 調整内容 |
|-------|---------|---------|
| TC-ENV-001 | `OllamaModel` コンストラクタ | 引数名・形式を SDK に合わせて調整 |
| TC-ENV-002 | `BedrockModel` コンストラクタ | 引数名・形式を SDK に合わせて調整 |
| TC-ENV-003 | `BedrockModel` コンストラクタ | TC-ENV-002 と同一の調整 |
| TC-ERR-001 | Agent タイムアウト例外 | SDK のタイムアウト例外クラスに合わせて `side_effect` を調整 |
| TC-ERR-002 | プロバイダー接続例外 | SDK の接続エラー例外クラスに合わせて調整 |
| TC-ERR-008 | レート制限例外 | SDK がレート制限をどうラップするかに合わせて調整 |

---

## テストクラス構成

テストファイル `backend/tests/unit/test_strands_service.py` は以下のクラス構成とする:

```python
class TestStrandsServiceProtocol:
    """Protocol 準拠テスト (TC-PROTO-001 ~ TC-PROTO-003)."""
    ...

class TestStrandsServiceGenerateCards:
    """カード生成 正常系テスト (TC-GEN-001 ~ TC-GEN-005)."""
    ...

class TestStrandsServiceEnvironment:
    """環境別モデルプロバイダー選択テスト (TC-ENV-001 ~ TC-ENV-005)."""
    ...

class TestStrandsServiceStubs:
    """Phase 3 スタブメソッドテスト (TC-STUB-001 ~ TC-STUB-003)."""
    ...

class TestStrandsServiceErrors:
    """エラーハンドリングテスト (TC-ERR-001 ~ TC-ERR-008)."""
    ...

class TestStrandsServiceParsing:
    """レスポンス解析テスト (TC-PARSE-001 ~ TC-PARSE-009)."""
    ...

class TestStrandsServiceFactory:
    """ファクトリ統合テスト (TC-COMPAT-001 ~ TC-COMPAT-002)."""
    ...
```

---

## 実装上の注意

### Agent レスポンスのモック方法 🟡

Strands Agent の `__call__` メソッドが返すオブジェクトの構造は SDK に依存する。以下の候補がある:

1. **`str(result)` でテキストを取得**: `result.__str__()` をモック
2. **`result.message` プロパティ**: PropertyMock で設定
3. **`result["output"]["text"]`**: dict-like アクセス
4. **`result.content` 等**: SDK 固有の属性

実装時に SDK のドキュメントを確認し、テストのモック方法を確定する。

### conftest.py の ENVIRONMENT 設定

`backend/tests/conftest.py` で `os.environ["ENVIRONMENT"] = "test"` が設定されている。環境変数テスト（TC-ENV-004）では `os.environ.pop("ENVIRONMENT", None)` で明示的に削除するか、`@patch.dict(os.environ, {"ENVIRONMENT": "prod"})` で上書きする。

### BedrockServiceError の不使用

StrandsAIService のテストでは `services.bedrock` モジュールの例外クラスを一切 import しないこと。全て `services.ai_service` の AIServiceError 階層を使用する。
