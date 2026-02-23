# TDD 要件定義書: TASK-0055 BedrockAIService Protocol 準拠改修

**機能名**: ai-strands-migration
**タスクID**: TASK-0055
**要件名**: BedrockAIService Protocol 準拠改修
**タスク種別**: TDD (Red -> Green -> Refactor)
**作成日**: 2026-02-23

---

## 1. 機能の概要

### 何をする機能か 🔵

既存の `BedrockService` クラス（`backend/src/services/bedrock.py`）を、TASK-0053 で定義された `AIService` Protocol に完全準拠するよう改修する。具体的には以下の3点を実施する:

1. **新規メソッド追加**: `grade_answer()` と `get_learning_advice()` を実装し、既存の `generate_cards()` と合わせて Protocol の全メソッドを実装する
2. **例外階層統合**: 既存の `BedrockServiceError` 階層を `AIServiceError` 階層に統合する（多重継承による後方互換性維持）
3. **型の統一**: `ai_service.py` で定義された共通型（`GenerationResult`, `GradingResult`, `LearningAdvice`）を返すよう統一する

### どのような問題を解決するか 🔵

- 現状 `BedrockService` は `generate_cards()` のみ実装しており、`AIService` Protocol の 3 メソッド中 1 メソッドしか満たしていない
- 例外クラスが `BedrockServiceError` 独自階層であり、`AIServiceError` 統一階層と互換性がない
- `create_ai_service()` ファクトリが `BedrockService` を返しても、Protocol として不完全なため `grade_answer()` / `get_learning_advice()` を呼べない

**参照した EARS 要件**: REQ-SM-002, REQ-SM-003, REQ-SM-004, REQ-SM-103, REQ-SM-402, REQ-SM-405
**参照した設計文書**: `docs/design/ai-strands-migration/architecture.md` (AIService Protocol 詳細設計)

### 想定されるユーザー 🔵

- **開発者**: `AIService` Protocol を通じて AI 機能を利用する handler.py や他のサービスモジュール
- **TASK-0056 以降の実装者**: handler.py の AIServiceFactory 統合時に Protocol 準拠した BedrockService が必要

### システム内での位置づけ 🔵

```
AIService Protocol (ai_service.py - TASK-0053)
    |
    +-- BedrockService (bedrock.py - 本タスク TASK-0055)  ← 既存改修
    |       |-- generate_cards()  ← 既存維持
    |       |-- grade_answer()    ← 新規追加
    |       `-- get_learning_advice()  ← 新規追加
    |
    +-- StrandsAIService (strands_service.py - TASK-0057)  ← 将来実装
    |
    `-- create_ai_service() Factory (ai_service.py)
            `-- USE_STRANDS=false → BedrockService を返す
```

Phase 1（基盤構築）の核となるタスクであり、TASK-0056（handler.py 統合）と TASK-0058（Strands カード生成移行互換性検証）の前提条件。

---

## 2. 入力・出力の仕様

### 2.1 generate_cards() - 既存維持 🔵

**シグネチャ（変更なし）**:
```python
def generate_cards(
    self,
    input_text: str,
    card_count: int = 5,
    difficulty: DifficultyLevel = "medium",  # Literal["easy", "medium", "hard"]
    language: Language = "ja",  # Literal["ja", "en"]
) -> GenerationResult:
```

| パラメータ | 型 | 制約 | デフォルト |
|-----------|------|------|-----------|
| `input_text` | `str` | 10-2000文字 | (必須) |
| `card_count` | `int` | 1-10 | 5 |
| `difficulty` | `DifficultyLevel` | "easy" / "medium" / "hard" | "medium" |
| `language` | `Language` | "ja" / "en" | "ja" |

**戻り値**: `GenerationResult`（`ai_service.py` の型を使用）
```python
@dataclass
class GenerationResult:
    cards: List[GeneratedCard]  # GeneratedCard(front, back, suggested_tags)
    input_length: int
    model_used: str
    processing_time_ms: int
```

**重要**: 既存の `bedrock.py` 内部で定義された `GeneratedCard` / `GenerationResult` dataclass は、`ai_service.py` で定義された同名 dataclass と**フィールドが完全に一致**している。実装時には `ai_service.py` の型を import して使用するか、既存の内部定義をそのまま維持するかの判断が必要。Protocol の structural subtyping により、フィールドが一致していれば互換性は保たれる。

**信頼性**: 🔵 既存実装（`bedrock.py:109-156`）と `ai_service.py` Protocol 定義から確定

### 2.2 grade_answer() - 新規追加 🔵

**シグネチャ**:
```python
def grade_answer(
    self,
    card_front: str,
    card_back: str,
    user_answer: str,
    language: Language = "ja",
) -> GradingResult:
```

| パラメータ | 型 | 制約 | デフォルト |
|-----------|------|------|-----------|
| `card_front` | `str` | カード問題文 | (必須) |
| `card_back` | `str` | カード正解 | (必須) |
| `user_answer` | `str` | ユーザー回答 | (必須) |
| `language` | `Language` | "ja" / "en" | "ja" |

**戻り値**: `GradingResult`
```python
@dataclass
class GradingResult:
    grade: int          # 0-5 (SM-2 SRS グレード)
    reasoning: str      # AI による採点理由
    model_used: str     # 使用モデル ID
    processing_time_ms: int  # 処理時間 (ms)
```

**内部処理フロー**:
1. `get_grading_prompt(card_front, card_back, user_answer, language)` でプロンプト生成
2. `_invoke_claude(prompt)` → 既存メソッドで Bedrock API 呼び出し（`_invoke_with_retry` 経由）
3. レスポンス JSON をパース → `GradingResult` を構築
4. 処理時間を計測して返却

**Bedrock API レスポンス期待形式**（プロンプト `GRADING_SYSTEM_PROMPT` で指定）:
```json
{
  "grade": 4,
  "reasoning": "正確な回答です。",
  "feedback": "よくできました。"
}
```

**信頼性**: 🔵 `ai_service.py` Protocol 定義 + `prompts/grading.py` の `GRADING_SYSTEM_PROMPT` JSON 指示から確定

### 2.3 get_learning_advice() - 新規追加 🔵

**シグネチャ**:
```python
def get_learning_advice(
    self,
    review_summary: dict,
    language: Language = "ja",
) -> LearningAdvice:
```

**注意**: `ai_service.py` の Protocol 定義では `review_summary: dict` 型であるが、`prompts/advice.py` の `get_advice_prompt()` は `Union[dict, ReviewSummary]` を受け付ける。BedrockService の実装では Protocol に合わせて `dict` 型を受け取り、そのまま `get_advice_prompt()` に渡す。

| パラメータ | 型 | 制約 | デフォルト |
|-----------|------|------|-----------|
| `review_summary` | `dict` | 復習統計データ | (必須) |
| `language` | `Language` | "ja" / "en" | "ja" |

**`review_summary` dict の期待キー**:
```python
{
    "total_reviews": int,      # 総復習回数
    "average_grade": float,    # 平均グレード (0.0-5.0)
    "total_cards": int,        # 総カード数
    "cards_due_today": int,    # 本日期限カード数
    "streak_days": int,        # 連続学習日数
    "tag_performance": dict,   # タグ別正答率 {tag: score}
}
```

**戻り値**: `LearningAdvice`
```python
@dataclass
class LearningAdvice:
    advice_text: str           # アドバイス本文
    weak_areas: List[str]      # 弱点分野
    recommendations: List[str] # 推奨事項
    model_used: str            # 使用モデル ID
    processing_time_ms: int    # 処理時間 (ms)
```

**内部処理フロー**:
1. `get_advice_prompt(review_summary, language)` でプロンプト生成
2. `_invoke_claude(prompt)` → 既存メソッドで Bedrock API 呼び出し（`_invoke_with_retry` 経由）
3. レスポンス JSON をパース → `LearningAdvice` を構築
4. 処理時間を計測して返却

**Bedrock API レスポンス期待形式**（プロンプト `ADVICE_SYSTEM_PROMPT` で指定）:
```json
{
  "advice_text": "アドバイス本文...",
  "weak_areas": ["分野1", "分野2"],
  "recommendations": ["推奨事項1", "推奨事項2"]
}
```

**信頼性**: 🔵 `ai_service.py` Protocol 定義 + `prompts/advice.py` の `ADVICE_SYSTEM_PROMPT` JSON 指示から確定

### 2.4 データフロー 🔵

```
[caller]
  |
  v
BedrockService.grade_answer() / get_learning_advice()
  |
  +--> prompts/grading.py::get_grading_prompt()  OR  prompts/advice.py::get_advice_prompt()
  |       |
  |       v
  |     プロンプト文字列
  |
  +--> BedrockService._invoke_with_retry(prompt)
  |       |
  |       +--> _invoke_claude(prompt)  -- Bedrock API (invoke_model)
  |       |       |
  |       |       v
  |       |     レスポンステキスト (JSON 文字列)
  |       |
  |       +--> [retry on RateLimit/InternalError with Full Jitter]
  |
  +--> JSON パース → GradingResult / LearningAdvice 構築
  |
  v
[戻り値: GradingResult / LearningAdvice]
```

**参照した設計文書**: `docs/design/ai-strands-migration/dataflow.md` (機能2, 機能3 のシーケンス図)

---

## 3. 制約条件

### 3.1 メソッドは同期 (非 async) 🔵

**Protocol 定義の確認結果**: `ai_service.py` の `AIService` Protocol では全メソッドが `def`（非 async）で定義されている。既存の `BedrockService.generate_cards()` も同期メソッドである。新規追加する `grade_answer()` と `get_learning_advice()` も**同期メソッド**として実装する。

```python
# ai_service.py Protocol 定義（実際のコード）
class AIService(Protocol):
    def generate_cards(...) -> GenerationResult: ...      # sync
    def grade_answer(...) -> GradingResult: ...           # sync
    def get_learning_advice(...) -> LearningAdvice: ...   # sync
```

**注意**: タスクノート（note.md）では `async def` と記載されている箇所があるが、**実際のコード**（`ai_service.py` と `bedrock.py`）は全て同期メソッドである。実装は実際のコードに従う。

**信頼性**: 🔵 `ai_service.py` と `bedrock.py` の実際のコードから確定

### 3.2 既存 API の完全互換性 🔵

- `generate_cards()` のシグネチャ・動作・戻り値は一切変更しない
- 既存テスト（`test_bedrock.py` の 24 テストケース）が全て通過すること
- `BedrockService` のコンストラクタ（`__init__(self, model_id=None, bedrock_client=None)`）は変更しない

**参照した EARS 要件**: REQ-SM-402, REQ-SM-405

### 3.3 例外階層の後方互換性 🔵

既存の例外クラスを AIServiceError 階層に統合しつつ、既存コードで `except BedrockServiceError` を使っている箇所が引き続き動作すること。

**多重継承による統合**:
```python
# 現状
class BedrockServiceError(Exception): ...
class BedrockTimeoutError(BedrockServiceError): ...

# 改修後
class BedrockServiceError(AIServiceError): ...                          # Exception + AIServiceError
class BedrockTimeoutError(AITimeoutError, BedrockServiceError): ...     # catch both hierarchies
class BedrockRateLimitError(AIRateLimitError, BedrockServiceError): ...
class BedrockInternalError(AIInternalError, BedrockServiceError): ...
class BedrockParseError(AIParseError, BedrockServiceError): ...
```

**後方互換性保証**:
- `except BedrockServiceError` → `BedrockTimeoutError` 等をキャッチ可能（既存動作維持）
- `except AIServiceError` → 同じ例外をキャッチ可能（新規コードで利用可能）
- `except AITimeoutError` → `BedrockTimeoutError` をキャッチ可能（Protocol 統一ハンドリング）

**信頼性**: 🔵 `docs/design/ai-strands-migration/architecture.md` エラーハンドリング設計から確定

### 3.4 Bedrock API 呼び出しパターン 🔵

新規メソッドは既存の `_invoke_with_retry()` → `_invoke_claude()` パターンを再利用する:

- `_invoke_claude(prompt)`: Bedrock `invoke_model` API を呼び出し、テキストレスポンスを返す
- `_invoke_with_retry(prompt)`: Full Jitter 指数バックオフでリトライ（RateLimit / InternalError のみ、Timeout はリトライしない）
- `MAX_RETRIES = 2`（初回 + 2回リトライ = 最大3回）

**信頼性**: 🔵 `bedrock.py:173-211` の既存実装から確定

### 3.5 JSON レスポンスパース 🔵

`grade_answer()` と `get_learning_advice()` は Bedrock のレスポンステキストから JSON をパースする。`generate_cards()` が既に持つ `_parse_response()` と同様のパターンだが、レスポンス形式が異なるため、新規のパースロジックが必要。

- `grade_answer()` パース対象: `{"grade": int, "reasoning": str, "feedback": str}`
- `get_learning_advice()` パース対象: `{"advice_text": str, "weak_areas": list, "recommendations": list}`
- JSON でない場合、マークダウンコードブロック（` ```json ... ``` `）からの抽出も考慮する
- パース失敗時は `BedrockParseError`（`AIParseError` でもキャッチ可能）を送出

**信頼性**: 🔵 既存 `_parse_response()` パターン + `GRADING_SYSTEM_PROMPT` / `ADVICE_SYSTEM_PROMPT` の JSON 指示から確定

### 3.6 パフォーマンス要件 🔵

| メソッド | レスポンス目標 | 備考 |
|---------|-------------|------|
| `generate_cards()` | 30秒以内 | 既存ベースライン維持 |
| `grade_answer()` | 10秒以内 | 単純な推論タスク |
| `get_learning_advice()` | 15秒以内 | データ集計 + 推論 |

**参照した EARS 要件**: REQ-SM-401, NFR-SM-001, NFR-SM-002, NFR-SM-003

### 3.7 テストカバレッジ 🔵

- テストカバレッジ 80% 以上を維持（REQ-SM-404）
- 既存テスト（`test_bedrock.py` 24テストケース）が全て通過（REQ-SM-405）

**参照した EARS 要件**: REQ-SM-404, REQ-SM-405
**参照した設計文書**: `docs/design/ai-strands-migration/architecture.md` 互換性制約

---

## 4. 想定される使用例

### 4.1 正常系: grade_answer() 成功 🔵

```python
service = BedrockService()
result = service.grade_answer(
    card_front="日本の首都は？",
    card_back="東京",
    user_answer="東京",
    language="ja",
)
# result.grade == 5 (完璧な回答)
# result.reasoning == "正確な回答です。..."
# result.model_used == "anthropic.claude-3-haiku-20240307-v1:0"
# result.processing_time_ms > 0
```

**参照した設計文書**: `docs/design/ai-strands-migration/api-endpoints.md` POST /reviews/{card_id}/grade-ai レスポンス例

### 4.2 正常系: get_learning_advice() 成功 🔵

```python
service = BedrockService()
result = service.get_learning_advice(
    review_summary={
        "total_reviews": 100,
        "average_grade": 3.2,
        "total_cards": 50,
        "cards_due_today": 10,
        "streak_days": 5,
        "tag_performance": {"生物学": 3.8, "有機化学": 2.1},
    },
    language="ja",
)
# result.advice_text == "あなたの学習傾向を..."
# result.weak_areas == ["有機化学"]
# result.recommendations == ["有機化学のカードを重点的に..."]
# result.model_used == "anthropic.claude-3-haiku-20240307-v1:0"
# result.processing_time_ms > 0
```

**参照した設計文書**: `docs/design/ai-strands-migration/api-endpoints.md` GET /advice レスポンス例

### 4.3 正常系: generate_cards() 既存互換 🔵

```python
service = BedrockService(bedrock_client=mock_client)
result = service.generate_cards(
    input_text="テスト入力テキスト",
    card_count=3,
    difficulty="medium",
    language="ja",
)
# 既存と全く同じ動作
# result.cards: List[GeneratedCard]
# result.model_used: str
# result.processing_time_ms: int
```

### 4.4 エラー系: Bedrock API タイムアウト 🔵

```python
# Bedrock API がタイムアウトした場合
service.grade_answer(card_front="Q", card_back="A", user_answer="A")
# → BedrockTimeoutError が送出される
# → except AITimeoutError でもキャッチ可能
# → リトライなし（タイムアウトはリトライしない既存方針）
```

### 4.5 エラー系: Bedrock API レート制限 🔵

```python
# Bedrock API がスロットリングした場合
service.grade_answer(card_front="Q", card_back="A", user_answer="A")
# → Full Jitter 指数バックオフで最大2回リトライ
# → 全リトライ失敗時に BedrockRateLimitError が送出される
# → except AIRateLimitError でもキャッチ可能
```

### 4.6 エラー系: JSON パースエラー 🔵

```python
# Bedrock レスポンスが不正な JSON の場合
service.grade_answer(card_front="Q", card_back="A", user_answer="A")
# → BedrockParseError が送出される
# → except AIParseError でもキャッチ可能
```

### 4.7 エッジケース: grade_answer() の grade 値が範囲外 🟡

```python
# AI が grade: 6 や grade: -1 を返した場合の処理
# → grade 値のバリデーション（0-5 にクランプするか、エラーにするか）
# 設計判断: grade が 0-5 範囲外の場合は AIParseError を送出
```

**信頼性**: 🟡 プロンプトで JSON 形式を指定しているが、AI の出力は保証されないため、バリデーションの具体的動作は実装時の判断。SM-2 グレード定義（0-5）が確立されているため、範囲外はエラーとするのが妥当。

### 4.8 エッジケース: 空の weak_areas / recommendations 🟡

```python
# AI が空リストを返した場合
result = service.get_learning_advice(review_summary={...})
# result.weak_areas == []
# result.recommendations == []
# → 正常系として処理（空リストは有効な値）
```

**信頼性**: 🟡 `ADVICE_SYSTEM_PROMPT` はリストを要求するが空リストの処理は明記なし。空リストは許容するのが妥当。

### 4.9 例外階層の互換性確認 🔵

```python
# 既存コード（引き続き動作）
try:
    service.generate_cards(...)
except BedrockServiceError as e:
    # BedrockTimeoutError, BedrockRateLimitError 等をキャッチ

# 新規コード（Protocol 統一ハンドリング）
try:
    service.grade_answer(...)
except AIServiceError as e:
    # 同じ例外をキャッチ可能

# 型チェック
assert issubclass(BedrockServiceError, AIServiceError)
assert issubclass(BedrockTimeoutError, AITimeoutError)
assert issubclass(BedrockTimeoutError, BedrockServiceError)
assert issubclass(BedrockTimeoutError, AIServiceError)
```

**参照した EARS 要件**: REQ-SM-201 (旧実装・新実装の共存)
**参照した設計文書**: `docs/design/ai-strands-migration/architecture.md` エラーハンドリング

---

## 5. EARS 要件・設計文書との対応関係

### 参照したユーザストーリー
- **2.1**: 復習時にユーザーの回答を AI が採点し SRS グレードを提案（grade_answer）
- **3.1**: 学習履歴を AI が分析しパーソナライズされたアドバイスを提供（get_learning_advice）

### 参照した機能要件
- **REQ-SM-002**: 既存カード生成機能のインターフェース維持
- **REQ-SM-003**: AI による回答採点・評価機能の提供
- **REQ-SM-004**: AI による学習アドバイス機能の提供
- **REQ-SM-103**: USE_STRANDS=false 時の既存 boto3 実装フォールバック
- **REQ-SM-402**: 既存 API レスポンス形式互換性
- **REQ-SM-405**: 既存テスト保護

### 参照した非機能要件
- **NFR-SM-001**: カード生成レスポンスタイム 30秒以内
- **NFR-SM-002**: 回答採点レスポンスタイム 10秒以内
- **NFR-SM-003**: 学習アドバイスレスポンスタイム 15秒以内
- **REQ-SM-401**: Lambda タイムアウト機能別設定
- **REQ-SM-404**: テストカバレッジ 80% 以上

### 参照した Edge ケース
- **EDGE-SM-001**: AI マルチステップ推論中のタイムアウト処理

### 参照した設計文書
- **アーキテクチャ**: `docs/design/ai-strands-migration/architecture.md` - AIService Protocol 詳細設計、エラーハンドリング、コンポーネント構成
- **データフロー**: `docs/design/ai-strands-migration/dataflow.md` - 機能2（回答採点）、機能3（学習アドバイス）のシーケンス図
- **型定義**: `docs/design/ai-strands-migration/interfaces.py` - AIService Protocol、GradingResult、LearningAdvice、ReviewSummary
- **API 仕様**: `docs/design/ai-strands-migration/api-endpoints.md` - POST /reviews/{card_id}/grade-ai、GET /advice

### 参照した実装ファイル
- `backend/src/services/ai_service.py` - AIService Protocol 定義、共通型、例外階層（TASK-0053 成果物）
- `backend/src/services/bedrock.py` - 既存 BedrockService 実装（332行、改修対象）
- `backend/src/services/prompts/grading.py` - `get_grading_prompt()`, `GRADING_SYSTEM_PROMPT`（TASK-0054 成果物）
- `backend/src/services/prompts/advice.py` - `get_advice_prompt()`, `ADVICE_SYSTEM_PROMPT`（TASK-0054 成果物）
- `backend/tests/unit/test_bedrock.py` - 既存テスト 24 ケース（維持対象）

---

## 6. 実装対象ファイルの変更サマリー

### 変更ファイル

| ファイル | 変更内容 | 変更規模 |
|---------|---------|---------|
| `backend/src/services/bedrock.py` | import 更新、例外統合、grade_answer/get_learning_advice 追加 | ~200行追加 |
| `backend/tests/unit/test_bedrock.py` | 新規テストケース追加（Protocol準拠、grade_answer、get_learning_advice、例外階層） | ~150行追加 |

### 変更なしファイル

| ファイル | 理由 |
|---------|------|
| `backend/src/services/ai_service.py` | TASK-0053 で完成済み |
| `backend/src/services/prompts/` | TASK-0054 で完成済み |
| その他のハンドラー・モデル | TASK-0056 以降で対応 |

---

## 7. 信頼性レベルサマリー

| 項目 | 信頼性 | 根拠 |
|------|--------|------|
| generate_cards() 既存維持 | 🔵 | 既存実装コードから確定、変更なし |
| grade_answer() メソッドシグネチャ | 🔵 | ai_service.py Protocol 定義から確定 |
| get_learning_advice() メソッドシグネチャ | 🔵 | ai_service.py Protocol 定義から確定 |
| GradingResult 型定義 | 🔵 | ai_service.py dataclass から確定 |
| LearningAdvice 型定義 | 🔵 | ai_service.py dataclass から確定 |
| 例外階層統合（多重継承） | 🔵 | architecture.md エラーハンドリング設計から確定 |
| _invoke_with_retry 再利用 | 🔵 | 既存 bedrock.py 実装パターンから確定 |
| プロンプト関数の利用 | 🔵 | prompts/grading.py, advice.py の実装から確定 |
| JSON パースロジック | 🔵 | GRADING_SYSTEM_PROMPT, ADVICE_SYSTEM_PROMPT の JSON 指示から確定 |
| 同期メソッド（非 async） | 🔵 | ai_service.py Protocol と bedrock.py 実装の両方が sync |
| grade 値範囲外の処理 | 🟡 | SM-2 定義は確立だが、バリデーション方法は実装判断 |
| 空リスト（weak_areas 等）の許容 | 🟡 | プロンプトは非空を期待するが、空リストの明示的な仕様なし |

### 統計

- 🔵 **青信号**: 10件 (83%)
- 🟡 **黄信号**: 2件 (17%)
- 🔴 **赤信号**: 0件 (0%)

**総合品質**: ✅ **高品質**（青信号 83%、赤信号なし）
