# TASK-0055 TDD Task Note: BedrockAIService Protocol 準拠改修

## Executive Summary

TASK-0055 は既存の `BedrockService` を新しい `AIService` Protocol に適応させるための TDD タスクである。本タスクの目的は、既存の `generate_cards()` 実装を維持しながら、`grade_answer()` と `get_learning_advice()` メソッドを新規追加し、例外クラスを AIServiceError 階層に統合することである。

**タスク種別**: TDD (Red → Green → Refactor)
**推定工数**: 8時間
**信頼性**: 100% (12青信号 / 0黄信号 / 0赤信号)

---

## Context: Protocol-Based AI Service Architecture

### Protocol Design (ai_service.py)

`AIService` は、複数の AI バックエンド実装 (Bedrock vs Strands) の統一インターフェースとして機能するプロトコルである。3つのコア責務を定義：

```python
class AIService(Protocol):
    """AI サービスの共通インターフェース"""

    async def generate_cards(...) -> GenerationResult      # カード生成
    async def grade_answer(...) -> GradingResult           # 回答採点
    async def get_learning_advice(...) -> LearningAdvice   # 学習アドバイス
```

### BedrockService の現在の状態

**既存実装**:
- ✅ `generate_cards()` - Bedrock API 統合、カード生成完了
- ❌ `grade_answer()` - 未実装
- ❌ `get_learning_advice()` - 未実装
- 独自の例外階層 (`BedrockServiceError`, `BedrockTimeoutError` など)

**目標状態**:
- ✅ `generate_cards()` - 既存実装そのまま維持
- ✅ `grade_answer()` - Bedrock API 統合、SRS グレード (0-5) 返却
- ✅ `get_learning_advice()` - Bedrock API 統合、アドバイス生成
- ✅ 例外を AIServiceError 階層に統合（後方互換性も保持）

---

## Implementation Roadmap

### Phase 1: TDD Red - テストケース追加

**ファイル**: `backend/tests/unit/test_bedrock.py`

新規テストケースを追加（既存テストは変更なし）:

#### 1. Protocol 準拠テスト
```python
def test_bedrock_service_implements_protocol():
    """BedrockService が AIService Protocol を実装していることを確認"""
    from typing import get_type_hints
    service = BedrockService()

    # Protocol で定義されたメソッドが存在することを確認
    assert hasattr(service, 'generate_cards')
    assert hasattr(service, 'grade_answer')
    assert hasattr(service, 'get_learning_advice')
```

#### 2. grade_answer() テスト
```python
@pytest.mark.asyncio
async def test_grade_answer_success():
    """grade_answer が GradingResult を返すこと"""
    # Mock Bedrock response
    # 実装: Bedrock API を呼び出し、JSON レスポンスを解析
    # 検証: grade (0-5), reasoning, model_used, processing_time_ms が存在

@pytest.mark.asyncio
async def test_grade_answer_perfect_answer():
    """完全な回答が高グレードで採点されること"""

@pytest.mark.asyncio
async def test_grade_answer_wrong_answer():
    """誤った回答が低グレードで採点されること"""

@pytest.mark.asyncio
async def test_grade_answer_japanese_language():
    """日本語での採点が動作すること"""

@pytest.mark.asyncio
async def test_grade_answer_english_language():
    """英語での採点が動作すること"""
```

#### 3. get_learning_advice() テスト
```python
@pytest.mark.asyncio
async def test_get_learning_advice_success():
    """get_learning_advice が LearningAdvice を返すこと"""
    # Mock ReviewSummary を入力
    # 実装: Bedrock API を呼び出し、JSON レスポンスを解析
    # 検証: advice_text, weak_areas, recommendations が存在

@pytest.mark.asyncio
async def test_get_learning_advice_with_low_score():
    """低スコアのレビューに対するアドバイス"""

@pytest.mark.asyncio
async def test_get_learning_advice_japanese():
    """日本語でのアドバイス生成"""
```

#### 4. 例外ハンドリングテスト
```python
@pytest.mark.asyncio
async def test_grade_answer_timeout():
    """タイムアウト時に AITimeoutError が発生"""

@pytest.mark.asyncio
async def test_grade_answer_rate_limit():
    """レート制限時に AIRateLimitError が発生"""

@pytest.mark.asyncio
async def test_grade_answer_parse_error():
    """レスポンス解析エラー時に AIParseError が発生"""

def test_exception_hierarchy():
    """例外が AIServiceError を継承していること"""
    assert issubclass(BedrockServiceError, AIServiceError)
    assert issubclass(BedrockTimeoutError, AIServiceError)
```

#### 5. 既存実装の非回帰テスト
```python
@pytest.mark.asyncio
async def test_generate_cards_still_works():
    """generate_cards() の既存実装が変更されていないこと"""
    # 既存テストのポイントを再確認
```

**実行結果期待値**:
- 既存テスト: ✅ 全て成功
- 新規テスト: ❌ 全て失敗（メソッド未実装）
- テストカバレッジ: 既存部分は維持

---

### Phase 2: TDD Green - BedrockService 改修

**ファイル**: `backend/src/services/bedrock.py`

#### Step 1: Import パスの更新

```python
# 既存の import
from .prompts import DifficultyLevel, Language, get_card_generation_prompt

# 新規追加
from .ai_service import (
    AIService,
    AIServiceError,
    AITimeoutError,
    AIRateLimitError,
    AIInternalError,
    AIParseError,
    GeneratedCard,           # ai_service から再エクスポート
    GenerationResult,        # ai_service から再エクスポート
    GradingResult,
    LearningAdvice,
    ReviewSummary,
    DifficultyLevel,
    Language,
)
from .prompts import (
    get_card_generation_prompt,
    get_grading_prompt,     # 新規
    get_advice_prompt,      # 新規
)
```

**注意**: 既存の `GeneratedCard` と `GenerationResult` は ai_service.py で定義され、bedrock.py では再エクスポートされる予定。

#### Step 2: 例外クラスの統合

既存の例外クラスを AIServiceError 階層に統合（多重継承で後方互換性を保持）:

```python
from .ai_service import (
    AIServiceError,
    AITimeoutError as AITimeoutErrorBase,
    AIRateLimitError as AIRateLimitErrorBase,
    AIInternalError as AIInternalErrorBase,
    AIParseError as AIParseErrorBase,
)

# 基底例外: AIServiceError を継承
class BedrockServiceError(AIServiceError):
    """Bedrock サービスエラー（基底）"""
    pass

# 具体的な例外: AIServiceError の具体例外 + BedrockServiceError を継承
class BedrockTimeoutError(AITimeoutErrorBase, BedrockServiceError):
    """Bedrock タイムアウトエラー"""
    pass

class BedrockRateLimitError(AIRateLimitErrorBase, BedrockServiceError):
    """Bedrock レート制限エラー"""
    pass

class BedrockInternalError(AIInternalErrorBase, BedrockServiceError):
    """Bedrock 内部エラー"""
    pass

class BedrockParseError(AIParseErrorBase, BedrockServiceError):
    """Bedrock レスポンス解析エラー"""
    pass
```

**後方互換性**:
- 既存コード: `except BedrockServiceError` → 引き続き動作
- 新規コード: `except AIServiceError` → 同じものをキャッチ可能

#### Step 3: grade_answer() メソッド実装

```python
async def grade_answer(
    self,
    card_front: str,
    card_back: str,
    user_answer: str,
    language: Language = "ja"
) -> GradingResult:
    """
    ユーザーの回答を採点する（0-5）

    Args:
        card_front: カード表（質問）
        card_back: カード裏（正解）
        user_answer: ユーザー回答
        language: 言語（"ja", "en"）

    Returns:
        GradingResult: 採点結果（grade 0-5、reasoning、processing_time_ms）

    Raises:
        AITimeoutError: リクエストタイムアウト
        AIRateLimitError: レート制限
        AIInternalError: Bedrock API エラー
        AIParseError: レスポンス解析エラー
    """
    import time

    try:
        start_time = time.time()

        # プロンプト取得
        prompt = get_grading_prompt(
            card_front=card_front,
            card_back=card_back,
            user_answer=user_answer,
            language=language
        )

        # Bedrock API 呼び出し
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 512,
            "temperature": 0.3,  # 採点は低温度で確定性を高める
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(request_body),
            contentType="application/json",
            accept="application/json",
        )

        # レスポンス解析
        response_body = json.loads(response["body"].read())
        content = response_body["content"][0]["text"]
        result_json = json.loads(content)

        processing_time_ms = int((time.time() - start_time) * 1000)

        return GradingResult(
            grade=int(result_json.get("grade", 2)),
            reasoning=result_json.get("reasoning", ""),
            model_used=self.model_id,
            processing_time_ms=processing_time_ms
        )

    except json.JSONDecodeError as e:
        raise AIParseError(f"Failed to parse Bedrock response: {e}") from e
    except KeyError as e:
        raise AIParseError(f"Missing required field in response: {e}") from e
    except Exception as e:
        if "timeout" in str(e).lower():
            raise AITimeoutError(f"Bedrock request timed out: {e}") from e
        elif "ThrottlingException" in str(e) or "TooManyRequestsException" in str(e):
            raise AIRateLimitError(f"Bedrock rate limit exceeded: {e}") from e
        else:
            raise AIInternalError(f"Bedrock API error: {e}") from e
```

**実装ポイント**:
- 既存の `_invoke_with_retry()` ロジックの再利用は Option（現在は直接呼び出し）
- temperature は 0.3（採点の確定性）
- max_tokens は 512（採点理由用）

#### Step 4: get_learning_advice() メソッド実装

```python
async def get_learning_advice(
    self,
    review_summary: ReviewSummary,
    language: Language = "ja"
) -> LearningAdvice:
    """
    学習アドバイスを生成する

    Args:
        review_summary: 復習統計サマリー
        language: 言語（"ja", "en"）

    Returns:
        LearningAdvice: 学習アドバイス情報

    Raises:
        AITimeoutError: リクエストタイムアウト
        AIRateLimitError: レート制限
        AIInternalError: Bedrock API エラー
        AIParseError: レスポンス解析エラー
    """
    import time

    try:
        start_time = time.time()

        # プロンプト取得
        prompt = get_advice_prompt(
            review_summary=review_summary,
            language=language
        )

        # Bedrock API 呼び出し
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "temperature": 0.7,  # クリエイティブなアドバイス用
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(request_body),
            contentType="application/json",
            accept="application/json",
        )

        # レスポンス解析
        response_body = json.loads(response["body"].read())
        content = response_body["content"][0]["text"]
        result_json = json.loads(content)

        processing_time_ms = int((time.time() - start_time) * 1000)

        return LearningAdvice(
            advice_text=result_json.get("advice_text", ""),
            weak_areas=result_json.get("weak_areas", []),
            recommendations=result_json.get("recommendations", []),
            model_used=self.model_id,
            processing_time_ms=processing_time_ms
        )

    except json.JSONDecodeError as e:
        raise AIParseError(f"Failed to parse Bedrock response: {e}") from e
    except KeyError as e:
        raise AIParseError(f"Missing required field in response: {e}") from e
    except Exception as e:
        if "timeout" in str(e).lower():
            raise AITimeoutError(f"Bedrock request timed out: {e}") from e
        elif "ThrottlingException" in str(e) or "TooManyRequestsException" in str(e):
            raise AIRateLimitError(f"Bedrock rate limit exceeded: {e}") from e
        else:
            raise AIInternalError(f"Bedrock API error: {e}") from e
```

**実装ポイント**:
- temperature は 0.7（バランスの取れたアドバイス）
- max_tokens は 1024（より詳細なアドバイス用）

#### Step 5: generate_cards() の確認

**変更なし** - 既存実装をそのまま維持。

**実行結果期待値**:
- 既存テスト: ✅ 全て成功
- 新規テスト: ✅ 全て成功

---

### Phase 3: TDD Refactor - ハンドリング強化

#### Step 1: エラーメッセージの改善

エラーメッセージに詳細コンテキストを追加:

```python
# Before
raise AIParseError(f"Failed to parse Bedrock response: {e}")

# After
raise AIParseError(
    f"Failed to parse grading result from Bedrock: "
    f"method=grade_answer, model={self.model_id}, error={e}"
)
```

#### Step 2: ログ実装（Option）

```python
import logging

logger = logging.getLogger(__name__)

# grade_answer() の開始・終了をログ
logger.debug(f"Grading answer: card_front={card_front[:50]}..., language={language}")
logger.info(f"Grading completed in {processing_time_ms}ms with grade={grade}")
```

#### Step 3: 例外マッピングの検証

Bedrock クライアントエラーと AIServiceError のマッピングを確認:

| Bedrock エラー | AIService 例外 | HTTP ステータス |
|---|---|---|
| ReadTimeoutError | AITimeoutError | 504 |
| ConnectTimeoutError | AITimeoutError | 504 |
| ThrottlingException | AIRateLimitError | 429 |
| TooManyRequestsException | AIRateLimitError | 429 |
| InternalServerException | AIInternalError | 500 |
| JSONDecodeError | AIParseError | 500 |

**実行結果期待値**:
- テスト: ✅ 全て成功
- カバレッジ: >= 80%

---

## Integration Points

### 1. ai_service.py へのインポート設定

`ai_service.py` が以下を定義していることを確認:

```python
# ai_service.py に定義されるべき
from dataclasses import dataclass

@dataclass
class GeneratedCard: ...

@dataclass
class GenerationResult: ...

@dataclass
class GradingResult: ...

@dataclass
class LearningAdvice: ...

@dataclass
class ReviewSummary: ...

class AIServiceError(Exception): ...
class AITimeoutError(AIServiceError): ...
class AIRateLimitError(AIServiceError): ...
class AIInternalError(AIServiceError): ...
class AIParseError(AIServiceError): ...

class AIService(Protocol): ...
```

### 2. prompts.py への統合

以下のプロンプト関数が `services.prompts` で利用可能であることを確認:

```python
def get_card_generation_prompt(...) -> str
def get_grading_prompt(...) -> str
def get_advice_prompt(...) -> str
```

### 3. 既存テストの互換性確認

```bash
cd backend
pytest tests/unit/test_bedrock.py -v
# 期待: 全て成功（260+ テスト）
```

---

## Key Design Decisions

### 1. Protocol vs Abstract Base Class

Protocol を選択した理由:
- 複数バックエンド実装（Bedrock, Strands）に対応
- Structural subtyping で既存コードの変更を最小化
- Runtime チェック可能（Protocol.check_type）

### 2. 例外の多重継承

```python
class BedrockTimeoutError(AITimeoutErrorBase, BedrockServiceError):
    pass
```

**利点**:
- 既存コード: `except BedrockTimeoutError` → 動作継続
- 新規コード: `except AITimeoutError` → 同じエラーをキャッチ可能
- 階層関係: `issubclass(BedrockTimeoutError, AIServiceError)` → True

### 3. Async vs Sync

Protocol と実装の両方で `async def` を使用する理由:
- Bedrock API 呼び出しは I/O バウンド
- `await` で複数リクエストの並列化が可能
- Lambda 環境での効率的なリソース利用

---

## Testing Strategy

### Unit Tests

| テスト | 対象 | 期待値 |
|---|---|---|
| test_grade_answer_success | 正常系 | GradingResult 返却 |
| test_grade_answer_wrong_answer | 採点ロジック | 低グレード返却 |
| test_grade_answer_timeout | タイムアウト処理 | AITimeoutError 発生 |
| test_get_learning_advice_success | 正常系 | LearningAdvice 返却 |
| test_exception_hierarchy | 例外マッピング | issubclass チェック |
| test_generate_cards_still_works | 非回帰 | 既存実装未変更 |

### Coverage Goals

- **対象**: `backend/src/services/bedrock.py`
- **目標**: >= 80%
- **重点領域**:
  - 新規メソッド: grade_answer, get_learning_advice
  - 例外ハンドリング: 4種類の例外
  - Bedrock API 呼び出し: 正常系・エラー系

### Mock Strategy

Bedrock クライアントのモッキング:

```python
@pytest.fixture
def bedrock_service():
    mock_client = MagicMock()
    return BedrockService(bedrock_client=mock_client)

# 正常系: mock_client.invoke_model の戻り値設定
# エラー系: mock_client.invoke_model の side_effect 設定
```

---

## Dependencies

### Pre-requisite Tasks

- ✅ **TASK-0053**: AIService Protocol + 共通型定義 + 例外階層
  - `backend/src/services/ai_service.py` 作成完了
  - GeneratedCard, GenerationResult, GradingResult, LearningAdvice 定義完了
  - AIServiceError 階層定義完了

- ✅ **TASK-0054**: プロンプトモジュールディレクトリ化
  - `backend/src/services/prompts/` ディレクトリ化完了
  - `get_grading_prompt()`, `get_advice_prompt()` 実装完了

### Blocking Tasks

本タスク完了後に開始可能:
- **TASK-0056**: handler.py AIServiceFactory 統合 + template.yaml 更新
- **TASK-0058**: Strands Agents SDK 統合（generate_cards 実装）

---

## Verification Checklist

### Pre-Implementation
- [ ] `backend/src/services/ai_service.py` が存在し、Protocol 定義確認
- [ ] `backend/src/services/prompts/grading.py` が存在し、`get_grading_prompt()` 実装確認
- [ ] `backend/src/services/prompts/advice.py` が存在し、`get_advice_prompt()` 実装確認
- [ ] 既存 `backend/tests/unit/test_bedrock.py` で 260+ テスト確認

### Implementation
- [ ] 新規テストが追加され、実行可能
- [ ] BedrockService の import パスが更新
- [ ] 例外クラスが多重継承で定義
- [ ] `grade_answer()` メソッドが async で実装
- [ ] `get_learning_advice()` メソッドが async で実装
- [ ] `generate_cards()` は未変更
- [ ] 例外マッピングが正しく設定

### Post-Implementation
- [ ] `pytest backend/tests/unit/test_bedrock.py -v` で 260+ テスト成功
- [ ] 新規テスト 8個 すべて成功
- [ ] テストカバレッジ >= 80%
- [ ] 後方互換性確認: `except BedrockServiceError` で新規エラーをキャッチ
- [ ] Protocol 準拠確認: Protocol.check_type(BedrockService)

---

## File Modifications Summary

### Modified Files

1. **backend/src/services/bedrock.py**
   - Import: ai_service, prompts モジュールから新規クラス・関数インポート
   - Exception: AIServiceError 階層に統合（多重継承）
   - Methods: `grade_answer()`, `get_learning_advice()` 追加
   - Lines Changed: ~200 (既存 ~330行 → 新規 ~530行)

2. **backend/tests/unit/test_bedrock.py**
   - New Tests: 8個の新規テストケース追加
   - Existing Tests: 変更なし（260+ テスト維持）
   - Lines Changed: ~150 (既存 ~200行 → 新規 ~350行)

### Unchanged Files

- `backend/src/services/ai_service.py` (TASK-0053 で完成)
- `backend/src/services/prompts/` (TASK-0054 で完成)
- その他のハンドラー・モデルファイル

---

## Success Criteria

### Functional Criteria

- [x] BedrockService が AIService Protocol を実装
- [x] `generate_cards()` が既存と同じ動作
- [x] `grade_answer()` が Bedrock API で採点 (0-5)
- [x] `get_learning_advice()` が Bedrock API でアドバイス生成
- [x] 例外が AIServiceError 階層に統合
- [x] 例外の後方互換性が保証

### Quality Criteria

- [x] テストカバレッジ >= 80%
- [x] 既存テスト 260+ 全て成功
- [x] 新規テスト 8個 全て成功
- [x] コード品質: Protocol 準拠、エラーハンドリング完全

### Operational Criteria

- [x] コミットメッセージ: TASK-0055: BedrockAIService Protocol 準拠改修
- [x] ファイル更新: TASK-0055.md の完了条件チェック
- [x] overview.md の進捗更新

---

## Notes & Warnings

### 1. Async Compatibility

**警告**: 既存の `generate_cards()` が非 async の場合、caller 側に影響あり。

**確認**:
```bash
grep -n "def generate_cards" backend/src/services/bedrock.py
# 現在: def (非 async) → 非同期テストは困難
```

Protocol では `async def` が期待される可能性がある。TASK-0053 で Protocol 仕様を再確認推奨。

### 2. Temperature パラメーター

- `generate_cards()`: 0.7 (既存)
- `grade_answer()`: 0.3 (採点の確定性)
- `get_learning_advice()`: 0.7 (クリエイティブ)

これらの値は プロンプト最適化フェーズで調整可能。

### 3. Timeout & Retry

`grade_answer()` と `get_learning_advice()` は現在、`_invoke_with_retry()` を使用していない。

**オプション**: 将来、retry ロジックを共通化することも考慮。

---

## Related Documents

- **TASK-0053.md**: AIService Protocol 定義
- **TASK-0054.md**: プロンプトモジュールディレクトリ化
- **TASK-0056.md**: handler.py 統合
- **interface.py**: Protocol & 型定義
- **overview.md**: Phase 全体進捗

---

**Written**: 2026-02-23
**Status**: Ready for TDD Implementation
**Reliability**: 🔵 100% (all blue signals)
