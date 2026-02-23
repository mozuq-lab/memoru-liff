# TASK-0053: AIService Protocol + 共通型定義 + 例外階層 - テストケース定義

**作成日**: 2026-02-23
**テストファイル**: `backend/tests/unit/test_ai_service.py`
**テスト対象**: `backend/src/services/ai_service.py`（新規作成）
**関連要件**: [requirements.md](requirements.md)

---

## テスト方針

- **同期メソッドのみ**: `pytest.mark.asyncio` は使用しない（全メソッドは `def`）
- **テストパターン**: 既存 `test_bedrock.py` の class ベース構成に従う
- **モック**: `unittest.mock.MagicMock`, `unittest.mock.patch` を使用
- **ファクトリ関数テスト**: `BedrockAIService` / `StrandsAIService` は遅延インポートされるため `patch` でモック化
- **pytest fixtures**: class 内 fixture + module レベル fixture

---

## インポート構成

```python
import asyncio
import pytest
from dataclasses import fields
from typing import get_args, get_type_hints
from unittest.mock import MagicMock, patch

from services.ai_service import (
    AIService,
    AIServiceError,
    AITimeoutError,
    AIRateLimitError,
    AIInternalError,
    AIParseError,
    AIProviderError,
    GeneratedCard,
    GenerationResult,
    GradingResult,
    LearningAdvice,
    ReviewSummary,
    DifficultyLevel,
    Language,
    create_ai_service,
)
```

---

## カテゴリ 1: AIService Protocol テスト

**テストクラス**: `TestAIServiceProtocol`

### TC-PROTO-001: Protocol は 3 つの必須メソッドを持つ

**対応 AC**: AC-001
**対応 FR**: FR-001-2, FR-001-3, FR-001-4

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_protocol_has_required_methods` |
| 事前条件 | `AIService` Protocol がインポート済み |
| 操作 | `AIService` のメソッド名一覧を取得する（`get_type_hints` または `dir` で確認） |
| 期待結果 | `generate_cards`, `grade_answer`, `get_learning_advice` の 3 メソッドが存在する |
| 検証方法 | `hasattr(AIService, 'generate_cards')` 等で確認 |

### TC-PROTO-002: Protocol は runtime_checkable である

**対応 AC**: AC-002
**対応 FR**: FR-001-1

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_protocol_is_runtime_checkable` |
| 事前条件 | `AIService` Protocol がインポート済み |
| 操作 | Protocol の全メソッドを実装したモッククラスを定義し、`isinstance()` チェックを実行 |
| 期待結果 | `isinstance(MockService(), AIService)` が `True` を返す |
| 検証方法 | `assert isinstance(mock_instance, AIService)` |

**モッククラス定義**:
```python
class _ConformingService:
    def generate_cards(self, input_text, card_count=5, difficulty="medium", language="ja"):
        pass

    def grade_answer(self, card_front, card_back, user_answer, language="ja"):
        pass

    def get_learning_advice(self, review_summary, language="ja"):
        pass
```

### TC-PROTO-003: Protocol を満たさないクラスは isinstance チェックに失敗する

**対応 AC**: AC-002（逆テスト）
**対応 FR**: FR-001-1

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_non_conforming_class_fails_isinstance` |
| 事前条件 | `AIService` Protocol がインポート済み |
| 操作 | メソッドが不足するクラスに対して `isinstance()` チェックを実行 |
| 期待結果 | `isinstance(NonConformingService(), AIService)` が `False` を返す |
| 検証方法 | `assert not isinstance(non_conforming_instance, AIService)` |

**非適合クラス定義**:
```python
class _NonConformingService:
    def generate_cards(self, input_text):
        pass
    # grade_answer, get_learning_advice が欠けている
```

### TC-PROTO-004: Protocol メソッドは同期（非 async）である

**対応 AC**: AC-003
**対応 FR**: FR-001-2, FR-001-3, FR-001-4

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_protocol_methods_are_sync` |
| 事前条件 | `AIService` Protocol がインポート済み、`asyncio` がインポート済み |
| 操作 | 各 Protocol メソッドに対して `asyncio.iscoroutinefunction()` を呼び出す |
| 期待結果 | 3 メソッド全てで `False` が返る |
| 検証方法 | `assert not asyncio.iscoroutinefunction(AIService.generate_cards)` 等 |

### TC-PROTO-005: generate_cards メソッドシグネチャが期待通りである

**対応 AC**: AC-001
**対応 FR**: FR-001-2

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_generate_cards_signature` |
| 事前条件 | `AIService` Protocol がインポート済み、`inspect` がインポート済み |
| 操作 | `inspect.signature(AIService.generate_cards)` でシグネチャを取得し、パラメータ名・デフォルト値を検証 |
| 期待結果 | パラメータ: `self`, `input_text`, `card_count`(default=5), `difficulty`(default="medium"), `language`(default="ja") |
| 検証方法 | `sig.parameters` のキーとデフォルト値を assert |

### TC-PROTO-006: grade_answer メソッドシグネチャが期待通りである

**対応 AC**: AC-001
**対応 FR**: FR-001-3

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_grade_answer_signature` |
| 事前条件 | `AIService` Protocol がインポート済み、`inspect` がインポート済み |
| 操作 | `inspect.signature(AIService.grade_answer)` でシグネチャを取得 |
| 期待結果 | パラメータ: `self`, `card_front`, `card_back`, `user_answer`, `language`(default="ja") |
| 検証方法 | `sig.parameters` のキーとデフォルト値を assert |

### TC-PROTO-007: get_learning_advice メソッドシグネチャが期待通りである

**対応 AC**: AC-001
**対応 FR**: FR-001-4

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_get_learning_advice_signature` |
| 事前条件 | `AIService` Protocol がインポート済み、`inspect` がインポート済み |
| 操作 | `inspect.signature(AIService.get_learning_advice)` でシグネチャを取得 |
| 期待結果 | パラメータ: `self`, `review_summary`, `language`(default="ja") |
| 検証方法 | `sig.parameters` のキーとデフォルト値を assert |

---

## カテゴリ 2: データクラステスト

**テストクラス**: `TestDataClasses`

### TC-DATA-001: GeneratedCard - 必須フィールドのみで作成

**対応 AC**: AC-004
**対応 FR**: FR-002-1

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_generated_card_required_fields_only` |
| 事前条件 | `GeneratedCard` がインポート済み |
| 操作 | `GeneratedCard(front="Q", back="A")` を作成 |
| 期待結果 | `front == "Q"`, `back == "A"`, `suggested_tags == []` |
| 検証方法 | 各フィールドの値を assert |

### TC-DATA-002: GeneratedCard - 全フィールド指定で作成

**対応 AC**: AC-004
**対応 FR**: FR-002-1

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_generated_card_with_all_fields` |
| 事前条件 | `GeneratedCard` がインポート済み |
| 操作 | `GeneratedCard(front="Q", back="A", suggested_tags=["tag1", "tag2"])` を作成 |
| 期待結果 | `suggested_tags == ["tag1", "tag2"]` |
| 検証方法 | フィールド値を assert |

### TC-DATA-003: GenerationResult - 全フィールド指定で作成

**対応 AC**: AC-005
**対応 FR**: FR-002-2

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_generation_result_creation` |
| 事前条件 | `GenerationResult`, `GeneratedCard` がインポート済み |
| 操作 | `GeneratedCard` を含む `GenerationResult` を作成 |
| 期待結果 | `cards` リストに `GeneratedCard` インスタンスを含む、`input_length == 100`, `model_used == "bedrock"`, `processing_time_ms == 1500` |
| 検証方法 | 各フィールドの値と型を assert |

```python
card = GeneratedCard(front="Q", back="A")
result = GenerationResult(cards=[card], input_length=100, model_used="bedrock", processing_time_ms=1500)
assert len(result.cards) == 1
assert isinstance(result.cards[0], GeneratedCard)
assert result.input_length == 100
assert result.model_used == "bedrock"
assert result.processing_time_ms == 1500
```

### TC-DATA-004: GradingResult - 全フィールド指定で作成

**対応 AC**: AC-006
**対応 FR**: FR-002-3

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_grading_result_creation` |
| 事前条件 | `GradingResult` がインポート済み |
| 操作 | `GradingResult(grade=4, reasoning="Correct", model_used="bedrock", processing_time_ms=500)` を作成 |
| 期待結果 | `grade == 4`, `reasoning == "Correct"`, `model_used == "bedrock"`, `processing_time_ms == 500` |
| 検証方法 | 各フィールドの値を assert |

### TC-DATA-005: GradingResult - grade は int 型である

**対応 AC**: AC-006
**対応 FR**: FR-002-3

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_grading_result_grade_is_int` |
| 事前条件 | `GradingResult` がインポート済み |
| 操作 | `GradingResult` インスタンスの `grade` フィールドの型を検証 |
| 期待結果 | `isinstance(result.grade, int)` が `True` |
| 検証方法 | `assert isinstance(result.grade, int)` |

### TC-DATA-006: LearningAdvice - 全フィールド指定で作成

**対応 AC**: AC-008
**対応 FR**: FR-002-5

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_learning_advice_creation` |
| 事前条件 | `LearningAdvice` がインポート済み |
| 操作 | 全フィールドを指定して `LearningAdvice` を作成 |
| 期待結果 | 各フィールドが正しく設定される |
| 検証方法 | 各フィールドの値を assert |

```python
advice = LearningAdvice(
    advice_text="Focus on verbs",
    weak_areas=["verb_conjugation"],
    recommendations=["Practice daily"],
    model_used="bedrock",
    processing_time_ms=1000,
)
assert advice.advice_text == "Focus on verbs"
assert advice.weak_areas == ["verb_conjugation"]
assert advice.recommendations == ["Practice daily"]
assert advice.model_used == "bedrock"
assert advice.processing_time_ms == 1000
```

### TC-DATA-007: LearningAdvice - weak_areas と recommendations はリスト型

**対応 AC**: AC-008
**対応 FR**: FR-002-5

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_learning_advice_lists` |
| 事前条件 | `LearningAdvice` がインポート済み |
| 操作 | `LearningAdvice` インスタンスの `weak_areas` と `recommendations` の型を検証 |
| 期待結果 | 両方とも `list` 型 |
| 検証方法 | `assert isinstance(advice.weak_areas, list)` 等 |

### TC-DATA-008: ReviewSummary - 必須フィールドのみで作成

**対応 AC**: AC-007
**対応 FR**: FR-002-4

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_review_summary_required_fields_only` |
| 事前条件 | `ReviewSummary` がインポート済み |
| 操作 | 必須フィールドのみで `ReviewSummary` を作成 |
| 期待結果 | `tag_performance == {}`, `recent_review_dates == []` |
| 検証方法 | デフォルト値を assert |

```python
summary = ReviewSummary(
    total_reviews=100,
    average_grade=3.5,
    total_cards=50,
    cards_due_today=10,
    streak_days=7,
)
assert summary.tag_performance == {}
assert summary.recent_review_dates == []
```

### TC-DATA-009: ReviewSummary - 全フィールド指定で作成

**対応 AC**: AC-007
**対応 FR**: FR-002-4

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_review_summary_with_all_fields` |
| 事前条件 | `ReviewSummary` がインポート済み |
| 操作 | 全フィールドを指定して `ReviewSummary` を作成 |
| 期待結果 | 全フィールドが正しく設定される |
| 検証方法 | 各フィールドの値を assert |

```python
summary = ReviewSummary(
    total_reviews=100,
    average_grade=3.5,
    total_cards=50,
    cards_due_today=10,
    streak_days=7,
    tag_performance={"math": 0.8, "science": 0.6},
    recent_review_dates=["2026-02-23", "2026-02-22"],
)
assert summary.tag_performance == {"math": 0.8, "science": 0.6}
assert isinstance(summary.tag_performance, dict)
assert summary.recent_review_dates == ["2026-02-23", "2026-02-22"]
```

### TC-DATA-010: GeneratedCard - ミュータブルデフォルトの独立性

**対応 AC**: AC-018
**対応 FR**: FR-002-1 (DD-005)

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_generated_card_mutable_default_independence` |
| 事前条件 | `GeneratedCard` がインポート済み |
| 操作 | 2 つの `GeneratedCard` をデフォルト `suggested_tags` で作成し、一方に要素を追加 |
| 期待結果 | 他方の `suggested_tags` は影響を受けない |
| 検証方法 | 変更後に他方のリストが空であることを assert |

```python
card1 = GeneratedCard(front="Q1", back="A1")
card2 = GeneratedCard(front="Q2", back="A2")
card1.suggested_tags.append("tag1")
assert card2.suggested_tags == []
assert card1.suggested_tags == ["tag1"]
```

### TC-DATA-011: ReviewSummary - tag_performance ミュータブルデフォルトの独立性

**対応 AC**: AC-018（拡張）
**対応 FR**: FR-002-4 (DD-005)

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_review_summary_mutable_default_independence` |
| 事前条件 | `ReviewSummary` がインポート済み |
| 操作 | 2 つの `ReviewSummary` をデフォルトで作成し、一方の `tag_performance` にエントリを追加 |
| 期待結果 | 他方の `tag_performance` は空辞書のまま |
| 検証方法 | 変更後に他方の辞書が空であることを assert |

```python
summary1 = ReviewSummary(total_reviews=10, average_grade=3.0, total_cards=5, cards_due_today=2, streak_days=1)
summary2 = ReviewSummary(total_reviews=20, average_grade=4.0, total_cards=10, cards_due_today=3, streak_days=2)
summary1.tag_performance["math"] = 0.9
assert summary2.tag_performance == {}
```

### TC-DATA-012: ReviewSummary - recent_review_dates ミュータブルデフォルトの独立性

**対応 AC**: AC-018（拡張）
**対応 FR**: FR-002-4 (DD-005)

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_review_summary_recent_dates_mutable_default_independence` |
| 事前条件 | `ReviewSummary` がインポート済み |
| 操作 | 2 つの `ReviewSummary` をデフォルトで作成し、一方の `recent_review_dates` にアイテムを追加 |
| 期待結果 | 他方の `recent_review_dates` は空リストのまま |
| 検証方法 | 変更後に他方のリストが空であることを assert |

```python
summary1 = ReviewSummary(total_reviews=10, average_grade=3.0, total_cards=5, cards_due_today=2, streak_days=1)
summary2 = ReviewSummary(total_reviews=20, average_grade=4.0, total_cards=10, cards_due_today=3, streak_days=2)
summary1.recent_review_dates.append("2026-02-23")
assert summary2.recent_review_dates == []
```

---

## カテゴリ 3: 例外階層テスト

**テストクラス**: `TestExceptionHierarchy`

### TC-EXC-001: AIServiceError は Exception のサブクラス

**対応 AC**: AC-009
**対応 FR**: FR-003-1

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_ai_service_error_is_exception_subclass` |
| 事前条件 | `AIServiceError` がインポート済み |
| 操作 | `issubclass(AIServiceError, Exception)` を検証 |
| 期待結果 | `True` |
| 検証方法 | `assert issubclass(AIServiceError, Exception)` |

### TC-EXC-002: 全 5 子例外は AIServiceError のサブクラス

**対応 AC**: AC-009
**対応 FR**: FR-003-2

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_all_child_exceptions_are_subclasses` |
| 事前条件 | 全例外クラスがインポート済み |
| 操作 | 各子例外に対して `issubclass(ChildError, AIServiceError)` を検証 |
| 期待結果 | 5 つ全て `True` |
| 検証方法 | parametrize で 5 例外を検証 |

```python
@pytest.mark.parametrize("exc_class", [
    AITimeoutError,
    AIRateLimitError,
    AIInternalError,
    AIParseError,
    AIProviderError,
])
def test_all_child_exceptions_are_subclasses(self, exc_class):
    assert issubclass(exc_class, AIServiceError)
```

### TC-EXC-003: 各子例外は AIServiceError で catch できる

**対応 AC**: AC-010
**対応 FR**: FR-003-3

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_child_exceptions_caught_by_base` |
| 事前条件 | 全例外クラスがインポート済み |
| 操作 | 各子例外を raise し、`except AIServiceError` で catch |
| 期待結果 | 全ての子例外が `AIServiceError` の except 節で捕捉される |
| 検証方法 | `pytest.raises(AIServiceError)` で各子例外を検証 |

```python
@pytest.mark.parametrize("exc_class", [
    AITimeoutError,
    AIRateLimitError,
    AIInternalError,
    AIParseError,
    AIProviderError,
])
def test_child_exceptions_caught_by_base(self, exc_class):
    with pytest.raises(AIServiceError):
        raise exc_class("test error")
```

### TC-EXC-004: 各子例外は自身の型で catch できる

**対応 AC**: AC-010（補完）
**対応 FR**: FR-003-2

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_child_exceptions_caught_by_own_type` |
| 事前条件 | 全例外クラスがインポート済み |
| 操作 | 各子例外を raise し、自身の型で catch |
| 期待結果 | 各例外が自身の型の except 節で捕捉される |
| 検証方法 | `pytest.raises(exc_class)` で検証 |

```python
@pytest.mark.parametrize("exc_class", [
    AITimeoutError,
    AIRateLimitError,
    AIInternalError,
    AIParseError,
    AIProviderError,
])
def test_child_exceptions_caught_by_own_type(self, exc_class):
    with pytest.raises(exc_class):
        raise exc_class("test error")
```

### TC-EXC-005: 例外メッセージが保持される

**対応 AC**: AC-011
**対応 FR**: FR-003-2

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_exception_message_preserved` |
| 事前条件 | 全例外クラスがインポート済み |
| 操作 | メッセージ付きで各子例外を raise し、catch 後にメッセージを検証 |
| 期待結果 | `str(e)` が元のメッセージと一致する |
| 検証方法 | `str(e) == expected_message` |

```python
@pytest.mark.parametrize("exc_class,message", [
    (AITimeoutError, "Request timed out after 30s"),
    (AIRateLimitError, "Too many requests"),
    (AIInternalError, "Internal server error"),
    (AIParseError, "Failed to parse response"),
    (AIProviderError, "Provider initialization failed"),
])
def test_exception_message_preserved(self, exc_class, message):
    with pytest.raises(AIServiceError) as exc_info:
        raise exc_class(message)
    assert str(exc_info.value) == message
```

### TC-EXC-006: AIServiceError 自体もインスタンス化・送出できる

**対応 AC**: AC-009（補完）
**対応 FR**: FR-003-1

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_base_exception_can_be_raised` |
| 事前条件 | `AIServiceError` がインポート済み |
| 操作 | `AIServiceError` を直接 raise し、catch する |
| 期待結果 | `Exception` の except 節で捕捉される |
| 検証方法 | `pytest.raises(Exception)` で検証 |

---

## カテゴリ 4: ファクトリ関数テスト

**テストクラス**: `TestCreateAIService`

**共通モック戦略**:
- `BedrockAIService` と `StrandsAIService` は遅延インポートされるため、`patch` でモジュールレベルのインポートをモック化する
- `patch("services.ai_service.os.getenv", ...)` ではなく `patch.dict("os.environ", ...)` で環境変数を制御する（ファクトリ関数が `os.getenv` を内部で呼び出すため）
- 実装クラスのインポート先をモック: `patch("services.bedrock.BedrockAIService")` / `patch("services.strands_service.StrandsAIService")`

**注意**: ファクトリ関数は関数内で `from services.bedrock import BedrockAIService` のように遅延インポートを行う。このため、テストでは `patch` のターゲットをインポート元モジュール（`services.bedrock.BedrockAIService`）に設定する。

### TC-FACT-001: USE_STRANDS=false で BedrockAIService を返却

**対応 AC**: AC-012
**対応 FR**: FR-004-2

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_create_with_use_strands_false_env` |
| 事前条件 | 環境変数 `USE_STRANDS=false` |
| 操作 | `create_ai_service()` を呼び出す |
| 期待結果 | `BedrockAIService()` が返却される（モックで検証） |
| 検証方法 | `BedrockAIService` のコンストラクタが呼ばれたことを assert |

```python
@patch.dict("os.environ", {"USE_STRANDS": "false"})
@patch("services.bedrock.BedrockAIService")
def test_create_with_use_strands_false_env(self, mock_bedrock_cls):
    mock_bedrock_cls.return_value = MagicMock()
    result = create_ai_service()
    mock_bedrock_cls.assert_called_once()
    assert result == mock_bedrock_cls.return_value
```

### TC-FACT-002: USE_STRANDS=true で StrandsAIService を返却

**対応 AC**: AC-013
**対応 FR**: FR-004-2

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_create_with_use_strands_true_env` |
| 事前条件 | 環境変数 `USE_STRANDS=true` |
| 操作 | `create_ai_service()` を呼び出す |
| 期待結果 | `StrandsAIService()` が返却される（モックで検証） |
| 検証方法 | `StrandsAIService` のコンストラクタが呼ばれたことを assert |

```python
@patch.dict("os.environ", {"USE_STRANDS": "true"})
@patch("services.strands_service.StrandsAIService")
def test_create_with_use_strands_true_env(self, mock_strands_cls):
    mock_strands_cls.return_value = MagicMock()
    result = create_ai_service()
    mock_strands_cls.assert_called_once()
    assert result == mock_strands_cls.return_value
```

### TC-FACT-003: USE_STRANDS 未設定時はデフォルトで BedrockAIService

**対応 AC**: AC-016
**対応 FR**: FR-004-2

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_create_default_without_env_var` |
| 事前条件 | `USE_STRANDS` 環境変数が未設定 |
| 操作 | `create_ai_service()` を呼び出す |
| 期待結果 | `BedrockAIService()` が返却される |
| 検証方法 | `BedrockAIService` のコンストラクタが呼ばれたことを assert |

```python
@patch.dict("os.environ", {}, clear=True)
@patch("services.bedrock.BedrockAIService")
def test_create_default_without_env_var(self, mock_bedrock_cls):
    # USE_STRANDS が環境変数にない状態を保証
    import os
    os.environ.pop("USE_STRANDS", None)
    mock_bedrock_cls.return_value = MagicMock()
    result = create_ai_service()
    mock_bedrock_cls.assert_called_once()
```

### TC-FACT-004: use_strands=False 明示パラメータが環境変数をオーバーライド

**対応 AC**: AC-014
**対応 FR**: FR-004-3

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_create_explicit_false_overrides_env` |
| 事前条件 | 環境変数 `USE_STRANDS=true`（Strands を指す環境） |
| 操作 | `create_ai_service(use_strands=False)` を呼び出す |
| 期待結果 | 環境変数が `true` でも `BedrockAIService()` が返却される |
| 検証方法 | `BedrockAIService` のコンストラクタが呼ばれたことを assert |

```python
@patch.dict("os.environ", {"USE_STRANDS": "true"})
@patch("services.bedrock.BedrockAIService")
def test_create_explicit_false_overrides_env(self, mock_bedrock_cls):
    mock_bedrock_cls.return_value = MagicMock()
    result = create_ai_service(use_strands=False)
    mock_bedrock_cls.assert_called_once()
```

### TC-FACT-005: use_strands=True 明示パラメータが環境変数をオーバーライド

**対応 AC**: AC-014（逆方向）
**対応 FR**: FR-004-3

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_create_explicit_true_overrides_env` |
| 事前条件 | 環境変数 `USE_STRANDS=false`（Bedrock を指す環境） |
| 操作 | `create_ai_service(use_strands=True)` を呼び出す |
| 期待結果 | 環境変数が `false` でも `StrandsAIService()` が返却される |
| 検証方法 | `StrandsAIService` のコンストラクタが呼ばれたことを assert |

```python
@patch.dict("os.environ", {"USE_STRANDS": "false"})
@patch("services.strands_service.StrandsAIService")
def test_create_explicit_true_overrides_env(self, mock_strands_cls):
    mock_strands_cls.return_value = MagicMock()
    result = create_ai_service(use_strands=True)
    mock_strands_cls.assert_called_once()
```

### TC-FACT-006: 初期化失敗時に AIProviderError を送出

**対応 AC**: AC-015
**対応 FR**: FR-004-5

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_create_raises_provider_error_on_init_failure` |
| 事前条件 | `BedrockAIService` のコンストラクタが例外を送出するようモック |
| 操作 | `create_ai_service(use_strands=False)` を呼び出す |
| 期待結果 | `AIProviderError` が送出される |
| 検証方法 | `pytest.raises(AIProviderError)` で検証 |

```python
@patch("services.bedrock.BedrockAIService", side_effect=RuntimeError("init failed"))
def test_create_raises_provider_error_on_init_failure(self, mock_bedrock_cls):
    with pytest.raises(AIProviderError) as exc_info:
        create_ai_service(use_strands=False)
    assert "Failed to initialize AI service" in str(exc_info.value)
```

### TC-FACT-007: 初期化失敗時に元の例外がチェーンされる

**対応 AC**: AC-015（補完）
**対応 FR**: FR-004-5

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_create_chains_original_exception` |
| 事前条件 | `BedrockAIService` のコンストラクタが `RuntimeError` を送出するようモック |
| 操作 | `create_ai_service(use_strands=False)` を呼び出す |
| 期待結果 | `AIProviderError.__cause__` が元の `RuntimeError` |
| 検証方法 | `exc_info.value.__cause__` が `RuntimeError` インスタンスであることを assert |

```python
@patch("services.bedrock.BedrockAIService", side_effect=RuntimeError("init failed"))
def test_create_chains_original_exception(self, mock_bedrock_cls):
    with pytest.raises(AIProviderError) as exc_info:
        create_ai_service(use_strands=False)
    assert isinstance(exc_info.value.__cause__, RuntimeError)
```

### TC-FACT-008: USE_STRANDS の大文字小文字不問（"True", "TRUE"）

**対応 AC**: AC-012/AC-013（補完）
**対応 FR**: FR-004-2

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_create_env_case_insensitive` |
| 事前条件 | 環境変数 `USE_STRANDS` に大文字小文字の変種を設定 |
| 操作 | 各値で `create_ai_service()` を呼び出す |
| 期待結果 | `"True"`, `"TRUE"`, `"true"` で `StrandsAIService`、それ以外で `BedrockAIService` |
| 検証方法 | parametrize で複数値を検証 |

```python
@pytest.mark.parametrize("env_value", ["True", "TRUE", "true"])
def test_create_env_case_insensitive_true(self, env_value):
    with patch.dict("os.environ", {"USE_STRANDS": env_value}):
        with patch("services.strands_service.StrandsAIService") as mock_strands_cls:
            mock_strands_cls.return_value = MagicMock()
            result = create_ai_service()
            mock_strands_cls.assert_called_once()
```

---

## カテゴリ 5: 型エイリアステスト

**テストクラス**: `TestTypeAliases`

### TC-TYPE-001: DifficultyLevel は "easy", "medium", "hard" の 3 値

**対応 AC**: AC-017
**対応 FR**: FR-005-1

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_difficulty_level_values` |
| 事前条件 | `DifficultyLevel` がインポート済み |
| 操作 | `get_args(DifficultyLevel)` で定義されたリテラル値を取得 |
| 期待結果 | `{"easy", "medium", "hard"}` と一致する |
| 検証方法 | `assert set(get_args(DifficultyLevel)) == {"easy", "medium", "hard"}` |

### TC-TYPE-002: Language は "ja", "en" の 2 値

**対応 AC**: AC-017
**対応 FR**: FR-005-2

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_language_values` |
| 事前条件 | `Language` がインポート済み |
| 操作 | `get_args(Language)` で定義されたリテラル値を取得 |
| 期待結果 | `{"ja", "en"}` と一致する |
| 検証方法 | `assert set(get_args(Language)) == {"ja", "en"}` |

### TC-TYPE-003: DifficultyLevel は "intermediate" を含まない

**対応 AC**: AC-017（補完）
**対応 FR**: FR-005-1 (DD-006)

| 項目 | 内容 |
|------|------|
| テスト関数名 | `test_difficulty_level_does_not_include_intermediate` |
| 事前条件 | `DifficultyLevel` がインポート済み |
| 操作 | `get_args(DifficultyLevel)` に `"intermediate"` が含まれないことを検証 |
| 期待結果 | `"intermediate" not in get_args(DifficultyLevel)` |
| 検証方法 | `assert "intermediate" not in get_args(DifficultyLevel)` |

---

## テストケースサマリー

| カテゴリ | テストクラス | テスト数 | 対応 AC |
|---------|-------------|---------|---------|
| 1. Protocol | `TestAIServiceProtocol` | 7 | AC-001, AC-002, AC-003 |
| 2. データクラス | `TestDataClasses` | 12 | AC-004 ~ AC-008, AC-018 |
| 3. 例外階層 | `TestExceptionHierarchy` | 6 | AC-009 ~ AC-011 |
| 4. ファクトリ関数 | `TestCreateAIService` | 8 | AC-012 ~ AC-016 |
| 5. 型エイリアス | `TestTypeAliases` | 3 | AC-017 |
| **合計** | | **36** | |

**注**: TC-EXC-002 ~ TC-EXC-005 は `pytest.mark.parametrize` を使用するため、実行時テスト数は parametrize 展開により増加する（例: 5 子例外 x 4 テスト = 20 実行）。テストケース定義数としては上記 36 件。

---

## ファクトリ関数テストのモック戦略補足

ファクトリ関数 `create_ai_service()` は関数内部で遅延インポートを行う:

```python
def create_ai_service(use_strands: bool = None) -> AIService:
    if use_strands:
        from services.strands_service import StrandsAIService
        return StrandsAIService()
    else:
        from services.bedrock import BedrockAIService
        return BedrockAIService()
```

この遅延インポートをテストでモックするために、以下の 2 つの手法が考えられる:

### 手法 A: インポート元をパッチ（推奨）

```python
@patch("services.bedrock.BedrockAIService")
def test_example(self, mock_cls):
    mock_cls.return_value = MagicMock()
    result = create_ai_service(use_strands=False)
    mock_cls.assert_called_once()
```

**利点**: 遅延インポートが実際のモジュールから取得するため、インポート元をパッチすれば関数内で取得されるクラスもモック化される。

### 手法 B: builtins.__import__ をパッチ（フォールバック）

`StrandsAIService` がまだ存在しないモジュール（`services.strands_service`）にある場合、手法 A だと `ModuleNotFoundError` が発生する可能性がある。その場合は以下を使用:

```python
import sys
from unittest.mock import MagicMock

mock_strands_module = MagicMock()
mock_strands_cls = MagicMock()
mock_strands_module.StrandsAIService = mock_strands_cls

with patch.dict("sys.modules", {"services.strands_service": mock_strands_module}):
    result = create_ai_service(use_strands=True)
    mock_strands_cls.assert_called_once()
```

**推奨**: `StrandsAIService` のテスト（TC-FACT-002, TC-FACT-005, TC-FACT-008）では手法 B を使用する。`services.strands_service` モジュールが TASK-0057 まで存在しないため。

`BedrockAIService` のテスト（TC-FACT-001, TC-FACT-003, TC-FACT-004）では手法 A を使用する。`services.bedrock` モジュールは既存のため。
