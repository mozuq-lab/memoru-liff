# TASK-0057: StrandsAIService 基本実装（カード生成） - 詳細要件書

**作成日**: 2026-02-23
**タスクID**: TASK-0057
**タスクタイプ**: TDD (Red -> Green -> Refactor -> Verify)
**要件名**: ai-strands-migration
**推定工数**: 8 時間

---

## 概要

StrandsAIService クラスを `backend/src/services/strands_service.py` に新規実装する。AWS Strands Agents SDK を使用したカード生成機能を提供し、既存の AIService Protocol に準拠する。環境変数に基づくモデルプロバイダー選択（Bedrock / Ollama）、統一エラーハンドリング、レスポンス解析を含む。

## 参照文書

| 文書 | パス |
|------|------|
| タスク定義 | `docs/tasks/ai-strands-migration/TASK-0057.md` |
| タスクノート | `docs/implements/ai-strands-migration/TASK-0057/note.md` |
| 要件定義 | `docs/spec/ai-strands-migration/requirements.md` |
| 受け入れ基準 | `docs/spec/ai-strands-migration/acceptance-criteria.md` |
| アーキテクチャ | `docs/design/ai-strands-migration/architecture.md` |
| API 仕様 | `docs/design/ai-strands-migration/api-endpoints.md` |
| インターフェース | `docs/design/ai-strands-migration/interfaces.py` |
| AIService Protocol | `backend/src/services/ai_service.py` |
| 既存 BedrockService | `backend/src/services/bedrock.py` |
| プロンプトモジュール | `backend/src/services/prompts/` |

---

## REQ-1: StrandsAIService クラスが AIService Protocol を実装する 🔵

**信頼性**: 🔵 *`backend/src/services/ai_service.py` の `@runtime_checkable AIService(Protocol)` 定義より確定*

**関連要件**: REQ-SM-002, REQ-SM-402

### 1.1 クラス定義とモジュール配置

**信頼性**: 🔵 *architecture.md のディレクトリ構造、ai_service.py の factory 関数の import パスより確定*

- ファイルパス: `backend/src/services/strands_service.py`（新規作成）
- クラス名: `StrandsAIService`
- `isinstance(StrandsAIService(), AIService)` が `True` を返すこと（`@runtime_checkable` Protocol）
- `from services.strands_service import StrandsAIService` の import パスで使用可能であること
  - 根拠: `ai_service.py` L190 の `from services.strands_service import StrandsAIService`

### 1.2 Protocol メソッドの完全実装

**信頼性**: 🔵 *`backend/src/services/ai_service.py` L113-167 の Protocol メソッド定義より確定*

StrandsAIService は AIService Protocol が定義する以下の 3 メソッドを全て持つこと:

| メソッド | シグネチャ | TASK-0057 での実装 |
|---------|-----------|-------------------|
| `generate_cards()` | `(self, input_text: str, card_count: int = 5, difficulty: DifficultyLevel = "medium", language: Language = "ja") -> GenerationResult` | 完全実装 |
| `grade_answer()` | `(self, card_front: str, card_back: str, user_answer: str, language: Language = "ja") -> GradingResult` | `NotImplementedError` を raise |
| `get_learning_advice()` | `(self, review_summary: dict, language: Language = "ja") -> LearningAdvice` | `NotImplementedError` を raise |

### 1.3 型の import 元

**信頼性**: 🔵 *`backend/src/services/ai_service.py` の定義より確定*

以下の型は `services.ai_service` モジュールから import すること:

- `GeneratedCard`, `GenerationResult` (戻り値)
- `GradingResult`, `LearningAdvice` (Phase 3 用スタブ戻り値型)
- `DifficultyLevel`, `Language` (引数型)
- `AIServiceError`, `AITimeoutError`, `AIRateLimitError`, `AIParseError`, `AIProviderError` (例外型)

**注意**: `bedrock.py` で定義されている `GeneratedCard`, `GenerationResult` ではなく、`ai_service.py` で定義されているものを使用すること。

### テストケース

- **TC-PROTO-001**: `StrandsAIService` インスタンスが `isinstance(instance, AIService)` を満たすこと 🔵
- **TC-PROTO-002**: `generate_cards`, `grade_answer`, `get_learning_advice` の 3 メソッドが全て存在すること 🔵
- **TC-PROTO-003**: `generate_cards()` の引数名・デフォルト値が Protocol 定義と一致すること 🔵

---

## REQ-2: generate_cards() メソッドが Strands Agent 経由でカードを生成する 🔵

**信頼性**: 🔵 *architecture.md のデータフロー設計、既存 bedrock.py L118-165 の generate_cards() パターンより確定*

**関連要件**: REQ-SM-002, REQ-SM-402

### 2.1 メソッドシグネチャ

**信頼性**: 🔵 *`backend/src/services/ai_service.py` L113-131 の Protocol 定義より確定*

```python
def generate_cards(
    self,
    input_text: str,
    card_count: int = 5,
    difficulty: DifficultyLevel = "medium",
    language: Language = "ja",
) -> GenerationResult:
```

- 引数名・型・デフォルト値は Protocol 定義と完全一致すること
- 戻り値は `GenerationResult` dataclass であること

### 2.2 プロンプト生成

**信頼性**: 🔵 *`backend/src/services/prompts/generate.py` の `get_card_generation_prompt()` 関数、bedrock.py L145-150 のパターンより確定*

- `get_card_generation_prompt(input_text, card_count, difficulty, language)` を呼び出してユーザープロンプトを生成すること
- import パス: `from services.prompts import get_card_generation_prompt`

### 2.3 Strands Agent の呼び出し

**信頼性**: 🟡 *architecture.md の StrandsAIService 設計より。Strands SDK の具体的な API（Agent 初期化・呼び出し形式）は SDK ドキュメントに依存*

- Strands `Agent` クラスを使用してプロンプトを送信すること
- Agent にはシステムプロンプトとモデルプロバイダーを設定すること
- Agent 呼び出し形式: `agent(user_prompt)` を想定（SDK 調査時に確認）

```python
from strands import Agent

agent = Agent(
    model=self.model,
    system_prompt=system_prompt,
)
result = agent(user_prompt)
```

### 2.4 処理時間計測

**信頼性**: 🔵 *bedrock.py L142, L158 の `time.time()` パターンより確定*

- `generate_cards()` の処理開始から終了まで `time.time()` で計測すること
- `GenerationResult.processing_time_ms` にミリ秒単位で格納すること
- 計算式: `int((time.time() - start_time) * 1000)`

### 2.5 GenerationResult の構築

**信頼性**: 🔵 *`backend/src/services/ai_service.py` L27-34 の GenerationResult 定義、api-endpoints.md のレスポンス形式より確定*

返却する `GenerationResult` は以下のフィールドを含むこと:

| フィールド | 型 | 値 |
|-----------|------|-----|
| `cards` | `List[GeneratedCard]` | 解析済みカードリスト |
| `input_length` | `int` | `len(input_text)` |
| `model_used` | `str` | 使用モデルの識別子（例: `"strands_bedrock"`, `"strands_ollama"`） |
| `processing_time_ms` | `int` | 処理時間（ミリ秒） |

### テストケース

- **TC-GEN-001**: 有効な入力で `GenerationResult` が返されること（正常系） 🔵
  - Given: `input_text="光合成は植物が..."`, `card_count=3`, `difficulty="medium"`, `language="ja"`
  - When: `generate_cards()` を呼び出す
  - Then: `GenerationResult` に 3 枚のカードが含まれ、各カードが `front`, `back`, `suggested_tags` を持つ

- **TC-GEN-002**: `input_length` が入力テキストの長さと一致すること 🔵
  - Given: `input_text` の長さが 150 文字
  - When: `generate_cards()` を呼び出す
  - Then: `result.input_length == 150`

- **TC-GEN-003**: `model_used` が現在のモデルプロバイダーを反映すること 🔵
  - Given: Bedrock プロバイダーを使用
  - When: `generate_cards()` を呼び出す
  - Then: `result.model_used` が空でない文字列

- **TC-GEN-004**: `processing_time_ms` が 0 以上の整数であること 🔵
  - Given: 正常に処理が完了する
  - When: `generate_cards()` を呼び出す
  - Then: `result.processing_time_ms >= 0`

- **TC-GEN-005**: `get_card_generation_prompt()` に正しい引数が渡されること 🔵
  - Given: `card_count=7`, `difficulty="hard"`, `language="en"`
  - When: `generate_cards()` を呼び出す
  - Then: `get_card_generation_prompt(input_text, 7, "hard", "en")` が呼び出される

---

## REQ-3: 環境変数に基づくモデルプロバイダー選択 🟡

**信頼性**: 🟡 *architecture.md の環境別プロバイダー切替設計より確定。ただし Strands SDK の `BedrockModel`/`OllamaModel` の具体的コンストラクタ引数は SDK ドキュメントに依存*

**関連要件**: REQ-SM-005, REQ-SM-101

### 3.1 `__init__()` メソッド

**信頼性**: 🔵 *architecture.md の初期化設計、note.md Part 3 のパターンより確定*

```python
def __init__(self, environment: str | None = None):
```

- `environment` が `None` の場合、`os.getenv("ENVIRONMENT", "prod")` を使用すること
- `_create_model()` を呼び出してモデルプロバイダーを初期化すること
- Strands Agent インスタンスを生成し、インスタンス変数に保存すること

### 3.2 `_create_model()` メソッド

**信頼性**: 🟡 *architecture.md の設計より。`BedrockModel`/`OllamaModel` のコンストラクタ引数は SDK に依存*

環境変数 `ENVIRONMENT` の値に応じてモデルプロバイダーを選択する:

| ENVIRONMENT | プロバイダー | 環境変数 |
|-------------|-------------|---------|
| `prod` | `BedrockModel` | `BEDROCK_MODEL_ID`（デフォルト: `anthropic.claude-3-haiku-20240307-v1:0`） |
| `staging` | `BedrockModel` | `BEDROCK_MODEL_ID`（デフォルト: `anthropic.claude-3-haiku-20240307-v1:0`） |
| `dev` | `OllamaModel` | `OLLAMA_HOST`（デフォルト: `http://localhost:11434`）, `OLLAMA_MODEL`（デフォルト: `llama3.2`） |
| 未設定 | `BedrockModel` | デフォルト（安全なフォールバック） |

```python
from strands.models import BedrockModel, OllamaModel
```

### 3.3 環境変数参照

**信頼性**: 🔵 *note.md Part 2 の環境変数一覧、template.yaml 設定より確定*

| 変数名 | 用途 | デフォルト値 |
|--------|------|-------------|
| `ENVIRONMENT` | 実行環境判定 | `"prod"` |
| `BEDROCK_MODEL_ID` | Bedrock モデル ID | `"anthropic.claude-3-haiku-20240307-v1:0"` |
| `OLLAMA_HOST` | Ollama サーバー URL | `"http://localhost:11434"` |
| `OLLAMA_MODEL` | Ollama モデル名 | `"llama3.2"` |

### テストケース

- **TC-ENV-001**: `ENVIRONMENT=dev` で `OllamaModel` が選択されること 🟡
  - Given: `os.environ["ENVIRONMENT"] = "dev"`
  - When: `StrandsAIService()` を初期化する
  - Then: 内部モデルが `OllamaModel` のインスタンスである

- **TC-ENV-002**: `ENVIRONMENT=prod` で `BedrockModel` が選択されること 🟡
  - Given: `os.environ["ENVIRONMENT"] = "prod"`
  - When: `StrandsAIService()` を初期化する
  - Then: 内部モデルが `BedrockModel` のインスタンスである

- **TC-ENV-003**: `ENVIRONMENT=staging` で `BedrockModel` が選択されること 🟡
  - Given: `os.environ["ENVIRONMENT"] = "staging"`
  - When: `StrandsAIService()` を初期化する
  - Then: 内部モデルが `BedrockModel` のインスタンスである

- **TC-ENV-004**: `ENVIRONMENT` 未設定で `BedrockModel` がデフォルト選択されること 🔵
  - Given: `ENVIRONMENT` 環境変数が設定されていない
  - When: `StrandsAIService()` を初期化する
  - Then: 内部モデルが `BedrockModel` のインスタンスである（安全なフォールバック）

- **TC-ENV-005**: コンストラクタの `environment` 引数で環境変数をオーバーライドできること 🔵
  - Given: `os.environ["ENVIRONMENT"] = "prod"`
  - When: `StrandsAIService(environment="dev")` を初期化する
  - Then: 環境変数を無視し `OllamaModel` が選択される

---

## REQ-4: grade_answer() と get_learning_advice() が NotImplementedError を raise する 🔵

**信頼性**: 🔵 *TASK-0057.md L65-71 のスタブ仕様、architecture.md の Phase 3 計画より確定*

**関連要件**: REQ-SM-003, REQ-SM-004（Phase 3 で実装予定）

### 4.1 grade_answer() スタブ

**信頼性**: 🔵 *ai_service.py L133-151 の Protocol シグネチャ、TASK-0057.md L65-67 より確定*

```python
def grade_answer(
    self,
    card_front: str,
    card_back: str,
    user_answer: str,
    language: Language = "ja",
) -> GradingResult:
    raise NotImplementedError("grade_answer is not implemented yet (Phase 3)")
```

- Protocol 定義と完全一致するシグネチャであること
- 呼び出し時に `NotImplementedError` を raise すること
- エラーメッセージに Phase 3 で実装予定であることを含むこと

### 4.2 get_learning_advice() スタブ

**信頼性**: 🔵 *ai_service.py L153-167 の Protocol シグネチャ、TASK-0057.md L69-71 より確定*

```python
def get_learning_advice(
    self,
    review_summary: dict,
    language: Language = "ja",
) -> LearningAdvice:
    raise NotImplementedError("get_learning_advice is not implemented yet (Phase 3)")
```

- Protocol 定義と完全一致するシグネチャであること
- 呼び出し時に `NotImplementedError` を raise すること
- エラーメッセージに Phase 3 で実装予定であることを含むこと

### テストケース

- **TC-STUB-001**: `grade_answer()` が `NotImplementedError` を raise すること 🔵
  - Given: `StrandsAIService` インスタンス
  - When: `grade_answer("Q", "A", "answer")` を呼び出す
  - Then: `NotImplementedError` が raise される

- **TC-STUB-002**: `get_learning_advice()` が `NotImplementedError` を raise すること 🔵
  - Given: `StrandsAIService` インスタンス
  - When: `get_learning_advice({"total_reviews": 10})` を呼び出す
  - Then: `NotImplementedError` が raise される

- **TC-STUB-003**: `NotImplementedError` のメッセージに "Phase 3" を含むこと 🔵
  - Given: `StrandsAIService` インスタンス
  - When: 各スタブメソッドを呼び出す
  - Then: エラーメッセージに "Phase 3" が含まれる

---

## REQ-5: エラーハンドリングが AIServiceError 階層に統一されていること 🔵

**信頼性**: 🔵 *`backend/src/services/ai_service.py` L72-105 の例外階層定義、architecture.md のエラーハンドリング設計より確定*

**関連要件**: REQ-SM-002（既存互換）、設計ヒアリング Q6「統一例外階層」

### 5.1 Strands SDK 例外から AIServiceError へのマッピング

**信頼性**: 🟡 *architecture.md のエラーマッピング表より。Strands SDK が発生させる具体的な例外クラスは SDK ドキュメントに依存*

| Strands SDK / ランタイム例外 | マッピング先 | HTTP ステータス |
|------------------------------|-------------|----------------|
| タイムアウト関連例外（`TimeoutError`, SDK のタイムアウト例外） | `AITimeoutError` | 504 |
| レート制限例外（Bedrock `ThrottlingException` 等） | `AIRateLimitError` | 429 |
| プロバイダー接続エラー（Ollama 未起動、Bedrock 障害等） | `AIProviderError` | 503 |
| JSON パースエラー（`json.JSONDecodeError`） | `AIParseError` | 500 |
| レスポンス構造不正（必須フィールド欠落等） | `AIParseError` | 500 |
| その他予期しない例外 | `AIServiceError`（基底） | 500 |

### 5.2 エラーメッセージ要件

**信頼性**: 🔵 *bedrock.py のエラーメッセージパターンより確定*

- エラーメッセージはデバッグに有用な情報を含むこと
- 元の例外を `from e` で連鎖させること（スタックトレース保持）
- AIParseError の場合、問題のあるフィールド名や JSON 位置を含むこと

### 5.3 BedrockServiceError を使用しないこと

**信頼性**: 🔵 *note.md Part 3 のエラーハンドリング方針「Do NOT use BedrockServiceError in new code」より確定*

- StrandsAIService は `BedrockServiceError` およびそのサブクラスを一切使用しないこと
- `services.ai_service` モジュールで定義された統一例外階層のみを使用すること

### 5.4 generate_cards() 内の try-except 構造

**信頼性**: 🔵 *bedrock.py の例外処理パターン、architecture.md のエラーフロー設計より確定*

`generate_cards()` は以下の構造で例外を捕捉・変換すること:

```python
def generate_cards(self, ...):
    try:
        # Agent 呼び出し + レスポンス解析
        ...
    except AIServiceError:
        # 既にマッピング済みの例外はそのまま再 raise
        raise
    except Exception as e:
        # 未知の例外を AIServiceError にラップ
        raise AIServiceError(f"Unexpected error: {e}") from e
```

### テストケース

- **TC-ERR-001**: Agent タイムアウト時に `AITimeoutError` が raise されること 🟡
  - Given: Strands Agent 呼び出しでタイムアウトが発生
  - When: `generate_cards()` を呼び出す
  - Then: `AITimeoutError` が raise される

- **TC-ERR-002**: プロバイダー接続エラー時に `AIProviderError` が raise されること 🟡
  - Given: モデルプロバイダー（Bedrock/Ollama）が利用不可
  - When: `generate_cards()` を呼び出す
  - Then: `AIProviderError` が raise される

- **TC-ERR-003**: 不正な JSON レスポンス時に `AIParseError` が raise されること 🔵
  - Given: Agent のレスポンスが有効な JSON でない
  - When: レスポンス解析を試みる
  - Then: `AIParseError` が raise される

- **TC-ERR-004**: 必須フィールド欠落時に `AIParseError` が raise されること 🔵
  - Given: Agent レスポンスの JSON に "cards" フィールドが存在しない
  - When: レスポンス解析を試みる
  - Then: `AIParseError` が raise され、メッセージに "cards" を含む

- **TC-ERR-005**: 例外チェーンが `from e` で保持されること 🔵
  - Given: 内部で `json.JSONDecodeError` が発生
  - When: `AIParseError` が raise される
  - Then: `err.__cause__` が元の例外を参照している

- **TC-ERR-006**: 全ての例外が `AIServiceError` のサブクラスであること 🔵
  - Given: `generate_cards()` で raise される可能性のある例外
  - When: 各例外のクラス階層を検証する
  - Then: 全て `isinstance(err, AIServiceError)` が `True`

---

## REQ-6: Strands Agent レスポンスから GenerationResult への解析 🔵

**信頼性**: 🔵 *bedrock.py L425-490 の `_parse_response()` パターン、interfaces.py の GeneratedCard 定義より確定*

### 6.1 `_parse_generation_result()` メソッド

**信頼性**: 🔵 *TASK-0057.md L140-164 の設計、bedrock.py の解析パターンより確定*

Strands Agent のレスポンスを `GenerationResult` に変換するプライベートメソッドを実装する。

### 6.2 レスポンスフォーマット対応

**信頼性**: 🟡 *Strands Agent のレスポンス形式は SDK に依存。bedrock.py の 2 形式対応パターンを踏襲*

以下の 2 種類のフォーマットに対応すること:

1. **プレーン JSON**: `{"cards": [...]}`
2. **Markdown コードブロック**: `` ```json\n{...}\n``` ``

Agent のレスポンスからテキスト部分を抽出し、上記 2 形式を検出・パースすること。

### 6.3 カード要素の解析ルール

**信頼性**: 🔵 *bedrock.py L452-478 の解析ルール、ai_service.py の GeneratedCard 定義より確定*

各カード要素について以下のルールを適用する:

| フィールド | 必須 | 型 | 処理 |
|-----------|------|-----|------|
| `front` | Yes | `str` | 前後空白を trim。空文字の場合スキップ |
| `back` | Yes | `str` | 前後空白を trim。空文字の場合スキップ |
| `tags` | No | `List[str]` | 存在しない場合は空リスト。リストでない場合は空リストにフォールバック |

- `front` または `back` が欠落しているカードはスキップすること（エラーにしない）
- 全てのカードがスキップされた場合（有効なカードが 0 枚）、`AIParseError` を raise すること
- `suggested_tags` は `tags` フィールドから構築すること

### 6.4 "AI生成" タグの自動付与

**信頼性**: 🔵 *bedrock.py L469-470 の既存パターンより確定*

- 各カードのタグリストに `"AI生成"` が含まれていない場合、先頭に `"AI生成"` を挿入すること
- `"AI Generated"` が含まれている場合は `"AI生成"` の追加をスキップすること

### テストケース

- **TC-PARSE-001**: 正常な JSON レスポンスからカードリストが生成されること 🔵
  - Given: `{"cards": [{"front": "Q1", "back": "A1", "tags": ["tag1"]}]}`
  - When: レスポンスを解析する
  - Then: `GeneratedCard(front="Q1", back="A1", suggested_tags=["AI生成", "tag1"])` が生成される

- **TC-PARSE-002**: Markdown コードブロック内の JSON が正しく解析されること 🔵
  - Given: `` ```json\n{"cards": [...]}\n``` ``
  - When: レスポンスを解析する
  - Then: コードブロック内の JSON が正しくパースされる

- **TC-PARSE-003**: `front` / `back` 欠落カードがスキップされること 🔵
  - Given: `{"cards": [{"front": "Q1"}, {"front": "Q2", "back": "A2"}]}`
  - When: レスポンスを解析する
  - Then: `back` 欠落の 1 枚目がスキップされ、有効な 1 枚のみ返される

- **TC-PARSE-004**: 全カードが無効な場合に `AIParseError` が raise されること 🔵
  - Given: `{"cards": [{"front": ""}, {"back": "A2"}]}`
  - When: レスポンスを解析する
  - Then: `AIParseError` が raise される

- **TC-PARSE-005**: `tags` フィールドがない場合に空リストとなること 🔵
  - Given: `{"cards": [{"front": "Q", "back": "A"}]}`（tags なし）
  - When: レスポンスを解析する
  - Then: `suggested_tags` が `["AI生成"]` となる

- **TC-PARSE-006**: `"cards"` フィールドがない JSON で `AIParseError` が raise されること 🔵
  - Given: `{"data": [...]}`（cards キーなし）
  - When: レスポンスを解析する
  - Then: `AIParseError` が raise される

- **TC-PARSE-007**: `"AI生成"` タグが既存の場合、重複追加されないこと 🔵
  - Given: `{"cards": [{"front": "Q", "back": "A", "tags": ["AI生成", "physics"]}]}`
  - When: レスポンスを解析する
  - Then: `suggested_tags` が `["AI生成", "physics"]`（重複なし）

---

## REQ-7: Protocol 準拠検証 🔵

**信頼性**: 🔵 *ai_service.py L109 の `@runtime_checkable` 定義、bedrock.py のパターンより確定*

**関連要件**: REQ-SM-002, REQ-SM-402

### 7.1 runtime_checkable Protocol による型検証

**信頼性**: 🔵 *ai_service.py の `@runtime_checkable class AIService(Protocol)` より確定*

- `isinstance(StrandsAIService(), AIService)` が `True` であること
- `AIService` Protocol は `@runtime_checkable` で定義されているため、ランタイムでの `isinstance` チェックが可能

### 7.2 ファクトリ関数との統合

**信頼性**: 🔵 *ai_service.py L171-198 の `create_ai_service()` 実装より確定*

- `create_ai_service(use_strands=True)` が `StrandsAIService` インスタンスを返すこと
- 返されたインスタンスの `generate_cards()` が正常に動作すること

### 7.3 API レスポンス形式の互換性

**信頼性**: 🔵 *api-endpoints.md の POST /cards/generate レスポンス仕様、REQ-SM-402 より確定*

StrandsAIService の `generate_cards()` が返す `GenerationResult` は、BedrockService の `generate_cards()` と同一のデータ構造であること:

```python
GenerationResult(
    cards=[
        GeneratedCard(
            front="問題文",
            back="解答",
            suggested_tags=["AI生成", "タグ1"],
        )
    ],
    input_length=150,
    model_used="strands_bedrock",
    processing_time_ms=3500,
)
```

### テストケース

- **TC-COMPAT-001**: `create_ai_service(use_strands=True)` が `StrandsAIService` を返すこと 🔵
  - Given: `USE_STRANDS` 環境変数は設定されていない
  - When: `create_ai_service(use_strands=True)` を呼び出す
  - Then: 返り値が `StrandsAIService` のインスタンスである

- **TC-COMPAT-002**: `GenerationResult` のフィールドが API レスポンス仕様と一致すること 🔵
  - Given: `generate_cards()` の正常実行
  - When: 結果の `GenerationResult` を検証する
  - Then: `cards`, `input_length`, `model_used`, `processing_time_ms` の全フィールドが存在する

---

## 非機能要件

### NF-1: テストカバレッジ 80% 以上 🔵

**信頼性**: 🔵 *REQ-SM-404、CLAUDE.md のテスト要件より確定*

- `backend/src/services/strands_service.py` のテストカバレッジが 80% 以上であること
- 測定コマンド: `pytest backend/tests/unit/test_strands_service.py --cov=backend/src/services/strands_service --cov-report=term-missing`

### NF-2: 既存テストを破壊しないこと 🔵

**信頼性**: 🔵 *REQ-SM-405、CLAUDE.md の注意事項より確定*

- `backend/tests/unit/test_bedrock.py` を含む既存 260+ テストが全てパスし続けること
- StrandsAIService は新規ファイルであり、既存モジュールを変更しないこと
- 検証コマンド: `pytest backend/tests/ -v`

### NF-3: コーディング規約準拠 🔵

**信頼性**: 🔵 *CLAUDE.md のコーディング規約より確定*

- PEP 8 準拠（snake_case for functions/variables, CamelCase for classes）
- 全関数・メソッドに型ヒントを付与すること
- Google スタイルの docstring を各 public メソッドに付与すること（Args/Returns/Raises）
- Python 3.12 の型記法を使用すること

---

## テストケースサマリー

### カテゴリ別件数

| カテゴリ | テストケース ID | 件数 |
|---------|----------------|------|
| Protocol 準拠 | TC-PROTO-001 ~ 003 | 3 |
| カード生成 | TC-GEN-001 ~ 005 | 5 |
| 環境プロバイダー | TC-ENV-001 ~ 005 | 5 |
| Phase 3 スタブ | TC-STUB-001 ~ 003 | 3 |
| エラーハンドリング | TC-ERR-001 ~ 006 | 6 |
| レスポンス解析 | TC-PARSE-001 ~ 007 | 7 |
| 互換性 | TC-COMPAT-001 ~ 002 | 2 |
| **合計** | | **31** |

### 信頼性レベル分布

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 25 | 81% |
| 🟡 黄信号 | 6 | 19% |
| 🔴 赤信号 | 0 | 0% |

**品質評価**: 高品質（青信号 81%、赤信号なし。黄信号は Strands SDK 固有の API 部分のみ）

### 信頼性レベルの判定基準

- **🔵 青信号**: `ai_service.py` の Protocol 定義、`bedrock.py` の既存パターン、`interfaces.py` の型定義、`api-endpoints.md` のレスポンス仕様など、コードベースまたは設計文書から直接確認できる要件
- **🟡 黄信号**: Strands Agents SDK の具体的な API（Agent 初期化形式、例外クラス名、`BedrockModel`/`OllamaModel` のコンストラクタ引数）など、SDK ドキュメント調査が必要な要件
- **🔴 赤信号**: 該当なし

---

## モック戦略

### テスト実装で使用するモックの方針

| モック対象 | モック手法 | 理由 |
|-----------|-----------|------|
| Strands `Agent` クラス | `@patch('services.strands_service.Agent')` | 外部 SDK 呼び出しの分離 |
| `BedrockModel` / `OllamaModel` | `@patch('services.strands_service.BedrockModel')` | モデルプロバイダー初期化の分離 |
| 環境変数 | `@patch.dict(os.environ, {...})` | 環境別テスト |
| `get_card_generation_prompt()` | 必要に応じて `@patch` | プロンプト生成の分離（オプション） |

### テストデータフィクスチャ

```python
@pytest.fixture
def valid_agent_response():
    """Agent が返す正常なレスポンステキスト."""
    return json.dumps({
        "cards": [
            {"front": "光合成とは何か？", "back": "植物が太陽光を使って...", "tags": ["生物学"]},
            {"front": "葉緑体の役割は？", "back": "光合成の場...", "tags": ["生物学", "細胞"]},
        ]
    })

@pytest.fixture
def invalid_json_response():
    """JSON として解析できないレスポンス."""
    return "This is not valid JSON"

@pytest.fixture
def missing_cards_response():
    """cards フィールドが欠落したレスポンス."""
    return json.dumps({"data": "no cards here"})
```

---

## 実装ファイル一覧

| ファイル | アクション | 説明 |
|---------|----------|------|
| `backend/src/services/strands_service.py` | 新規作成 | StrandsAIService 本体 |
| `backend/tests/unit/test_strands_service.py` | 新規作成 | テストスイート（31 テストケース） |
| `docs/tasks/ai-strands-migration/TASK-0057.md` | 更新 | 完了条件チェックボックス |

---

## 実装順序（TDD フェーズ）

### Red フェーズ
1. `backend/tests/unit/test_strands_service.py` を作成
2. 全 31 テストケースを実装（`StrandsAIService` がまだ存在しないため全て失敗）
3. `pytest` でテストが失敗することを確認

### Green フェーズ
1. `backend/src/services/strands_service.py` を作成
2. `__init__()` + `_create_model()` を実装
3. `generate_cards()` を実装
4. `_parse_generation_result()` を実装
5. `grade_answer()` / `get_learning_advice()` の `NotImplementedError` スタブを実装
6. エラーハンドリングを実装
7. 全テストがパスすることを確認

### Refactor フェーズ
1. 重複コードの抽出
2. エラーメッセージの改善
3. 型ヒント・docstring の充実
4. import の最適化

### Verify フェーズ
1. カバレッジ 80% 以上の確認
2. 既存テストが全てパスすることの確認
3. TASK-0057.md の完了条件更新
