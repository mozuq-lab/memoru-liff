# TASK-0053: AIService Protocol + 共通型定義 + 例外階層 - 詳細要件定義

**作成日**: 2026-02-23
**関連タスク**: [TASK-0053.md](../../../tasks/ai-strands-migration/TASK-0053.md)
**開発ノート**: [note.md](note.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: 設計文書・既存実装・EARS要件定義書を参考にした確実な要件
- 🟡 **黄信号**: 設計文書・既存実装から妥当な推測による要件
- 🔴 **赤信号**: 設計文書・既存実装にない推測による要件

## 参照文書

| 文書 | パス | 主要参照箇所 |
|------|------|-------------|
| インターフェース定義 | `docs/design/ai-strands-migration/interfaces.py` | Protocol定義、データクラス、例外階層 |
| アーキテクチャ設計 | `docs/design/ai-strands-migration/architecture.md` | システム概要、Protocol詳細設計、Factory パターン |
| 要件定義書 | `docs/spec/ai-strands-migration/requirements.md` | REQ-SM-001〜006, REQ-SM-102/103, REQ-SM-404/405 |
| 既存 BedrockService | `backend/src/services/bedrock.py` | 既存メソッドシグネチャ、例外階層、データクラス |
| 既存プロンプト定義 | `backend/src/services/prompts.py` | DifficultyLevel, Language 型エイリアス |

---

## 1. 機能要件（EARS記法）

### FR-001: AIService Protocol インターフェース定義 🔵

**信頼性**: 🔵 *interfaces.py（L116-186）・architecture.md（L194-254）・設計ヒアリング Q1/Q6 より確定*

**ファイル**: `backend/src/services/ai_service.py`（新規作成）

#### FR-001-1: Protocol クラス宣言 🔵

**EARS**: AIService Protocol が定義された**場合**、`@runtime_checkable` デコレーターが適用されており、`typing.Protocol` を継承していなければならない。

- `from typing import Protocol, runtime_checkable` を使用する
- `isinstance()` チェックを可能にするため `@runtime_checkable` を付与する
- Protocol 自体にはコンストラクタを定義しない

#### FR-001-2: generate_cards メソッド 🔵

**EARS**: AIService Protocol は `generate_cards()` メソッドを**同期メソッド**として定義しなければならない。

```python
def generate_cards(
    self,
    input_text: str,
    card_count: int = 5,
    difficulty: DifficultyLevel = "medium",
    language: Language = "ja",
) -> GenerationResult:
    ...
```

**重要判断 - 同期 vs 非同期**:

タスクファイル TASK-0053.md のコードスニペット（L57-66）では `async def` と記載されているが、以下の根拠により**同期メソッド**を採用する:

1. **既存 BedrockService の実装が同期**: `bedrock.py` L109-156 の `generate_cards()` は `def`（同期）で定義されている
2. **interfaces.py の設計が同期**: `interfaces.py` L126-146 の Protocol 定義は `def`（同期）
3. **architecture.md の設計が同期**: `architecture.md` L233-239 の Protocol 定義は `def`（同期）
4. **note.md の明示的記載**: note.md L285-286 で「Protocol methods should sync in interface layer」と明記

**結論**: 設計文書（interfaces.py, architecture.md）が実装の source of truth であり、タスクファイルの `async` 記載は設計反映前の草案である。**同期メソッドを採用する**。

#### FR-001-3: grade_answer メソッド 🔵

**EARS**: AIService Protocol は `grade_answer()` メソッドを同期メソッドとして定義しなければならない。

```python
def grade_answer(
    self,
    card_front: str,
    card_back: str,
    user_answer: str,
    language: Language = "ja",
) -> GradingResult:
    ...
```

**根拠**: interfaces.py L148-167、要件 REQ-SM-003、設計ヒアリング Q4「AI直接グレーディング」選択

#### FR-001-4: get_learning_advice メソッド 🔵

**EARS**: AIService Protocol は `get_learning_advice()` メソッドを同期メソッドとして定義しなければならない。

```python
def get_learning_advice(
    self,
    review_summary: dict,
    language: Language = "ja",
) -> LearningAdvice:
    ...
```

**注意**: `review_summary` パラメータは `dict` 型（`ReviewSummary` データクラスではない）。interfaces.py L170-173 で `review_summary: dict` と定義されている。ReviewSummary データクラスは事前クエリ結果の構造を文書化する目的で定義されるが、Protocol のメソッドシグネチャでは汎用的な `dict` を受け取る。

**根拠**: interfaces.py L170-186、要件 REQ-SM-004、設計ヒアリング Q5「事前クエリ」選択

---

### FR-002: 共通データクラス定義 🔵

**信頼性**: 🔵 *interfaces.py（L33-108）・bedrock.py（L48-64）より確定*

**ファイル**: `backend/src/services/ai_service.py`

全データクラスは `@dataclass` デコレーター（`dataclasses` モジュール）を使用し、Pydantic は使用しない。

#### FR-002-1: GeneratedCard データクラス 🔵

**EARS**: システムは GeneratedCard データクラスを定義しなければならない。既存 `bedrock.py` L48-54 の同名クラスとフィールド構成が同一でなければならない。

```python
@dataclass
class GeneratedCard:
    front: str          # 問題文
    back: str           # 解答
    suggested_tags: List[str] = field(default_factory=list)  # 推奨タグ
```

**フィールド仕様**:

| フィールド | 型 | 必須 | デフォルト | 根拠 |
|-----------|-----|------|-----------|------|
| `front` | `str` | YES | - | bedrock.py L52, interfaces.py L40 |
| `back` | `str` | YES | - | bedrock.py L53, interfaces.py L41 |
| `suggested_tags` | `List[str]` | NO | `[]` (default_factory) | bedrock.py L54, interfaces.py L42 |

**設計判断**: `field(default_factory=list)` を使用してミュータブルデフォルトの問題を回避する（note.md L332-348）。

#### FR-002-2: GenerationResult データクラス 🔵

**EARS**: システムは GenerationResult データクラスを定義しなければならない。既存 `bedrock.py` L57-64 の同名クラスとフィールド構成が同一でなければならない。

```python
@dataclass
class GenerationResult:
    cards: List[GeneratedCard]  # 生成されたカード一覧
    input_length: int           # 入力テキスト長
    model_used: str             # 使用モデル名
    processing_time_ms: int     # 処理時間(ms)
```

**フィールド仕様**:

| フィールド | 型 | 必須 | デフォルト | 根拠 |
|-----------|-----|------|-----------|------|
| `cards` | `List[GeneratedCard]` | YES | - | bedrock.py L61, interfaces.py L52 |
| `input_length` | `int` | YES | - | bedrock.py L62, interfaces.py L53 |
| `model_used` | `str` | YES | - | bedrock.py L63, interfaces.py L54 |
| `processing_time_ms` | `int` | YES | - | bedrock.py L64, interfaces.py L55 |

**設計判断**: `processing_time_ms` は `int` 型（`float` ではない）。bedrock.py L149 で `int((time.time() - start_time) * 1000)` と整数変換されている。interfaces.py L55 も `int` を採用。

#### FR-002-3: GradingResult データクラス 🔵

**EARS**: システムは GradingResult データクラスを定義しなければならない。

```python
@dataclass
class GradingResult:
    grade: int              # SRS グレード 0-5（SM-2 互換）
    reasoning: str          # AI による採点理由
    model_used: str         # 使用モデル名
    processing_time_ms: int # 処理時間(ms)
```

**フィールド仕様**:

| フィールド | 型 | 必須 | デフォルト | 根拠 |
|-----------|-----|------|-----------|------|
| `grade` | `int` | YES | - | interfaces.py L70、REQ-SM-003 |
| `reasoning` | `str` | YES | - | interfaces.py L71、設計ヒアリング Q4 |
| `model_used` | `str` | YES | - | interfaces.py L72 |
| `processing_time_ms` | `int` | YES | - | interfaces.py L73 |

**注意**: `grade` フィールドのバリデーション（0-5 範囲制約）はデータクラスレベルでは行わない。バリデーションは Pydantic モデル（GradeAnswerResponse）で実施する（TASK-0059 以降のスコープ）。

**根拠**: interfaces.py L63-73、要件 REQ-SM-003、SM-2 グレード体系

#### FR-002-4: ReviewSummary データクラス 🟡

**EARS**: システムは ReviewSummary データクラスを定義しなければならない。

```python
@dataclass
class ReviewSummary:
    total_reviews: int                          # 総復習回数
    average_grade: float                        # 平均グレード
    total_cards: int                            # 総カード数
    cards_due_today: int                        # 本日期限カード数
    streak_days: int                            # 連続学習日数
    tag_performance: dict[str, float] = field(default_factory=dict)  # タグ別正答率
    recent_review_dates: List[str] = field(default_factory=list)     # 直近の復習日
```

**フィールド仕様**:

| フィールド | 型 | 必須 | デフォルト | 信頼性 | 根拠 |
|-----------|-----|------|-----------|--------|------|
| `total_reviews` | `int` | YES | - | 🔵 | interfaces.py L88 |
| `average_grade` | `float` | YES | - | 🔵 | interfaces.py L89 |
| `total_cards` | `int` | YES | - | 🔵 | interfaces.py L90 |
| `cards_due_today` | `int` | YES | - | 🔵 | interfaces.py L91 |
| `streak_days` | `int` | YES | - | 🟡 | interfaces.py L92（計算ロジック未確定） |
| `tag_performance` | `dict[str, float]` | NO | `{}` (default_factory) | 🔵 | interfaces.py L93 |
| `recent_review_dates` | `List[str]` | NO | `[]` (default_factory) | 🟡 | interfaces.py L94（表示フォーマット未確定） |

**設計判断**:
- `recent_review_dates` は `List[str]` 型（`List[datetime]` ではない）。interfaces.py L94 で `List[str]` と定義。表示用文字列として扱う。
- `tag_performance` と `recent_review_dates` は `field(default_factory=...)` を使用してミュータブルデフォルトを回避する。
- `streak_days` の計算ロジック詳細は TASK-0046（通知時刻/タイムゾーン判定）の実装に依存する可能性がある。

#### FR-002-5: LearningAdvice データクラス 🔵

**EARS**: システムは LearningAdvice データクラスを定義しなければならない。

```python
@dataclass
class LearningAdvice:
    advice_text: str           # アドバイス本文
    weak_areas: List[str]      # 弱点分野
    recommendations: List[str] # 推奨事項
    model_used: str            # 使用モデル名
    processing_time_ms: int    # 処理時間(ms)
```

**フィールド仕様**:

| フィールド | 型 | 必須 | デフォルト | 根拠 |
|-----------|-----|------|-----------|------|
| `advice_text` | `str` | YES | - | interfaces.py L104 |
| `weak_areas` | `List[str]` | YES | - | interfaces.py L105 |
| `recommendations` | `List[str]` | YES | - | interfaces.py L106 |
| `model_used` | `str` | YES | - | interfaces.py L107 |
| `processing_time_ms` | `int` | YES | - | interfaces.py L108 |

**設計判断**: `weak_areas` と `recommendations` は必須フィールドとする（default_factory は使用しない）。interfaces.py では `field(default_factory=list)` を使用していないため、呼び出し側で必ず値を渡す。空リストの場合は `[]` を明示的に渡す。

**根拠**: interfaces.py L97-108、要件 REQ-SM-004、ユーザストーリー 3.1

---

### FR-003: 統一例外階層 🔵

**信頼性**: 🔵 *interfaces.py（L228-279）・architecture.md（L79-93）・設計ヒアリング Q6 より確定*

**ファイル**: `backend/src/services/ai_service.py`

#### FR-003-1: 基底例外クラス 🔵

**EARS**: システムは `AIServiceError` 基底例外クラスを定義しなければならない。`Exception` を直接継承する。

```python
class AIServiceError(Exception):
    """AI サービスの基底例外クラス."""
    pass
```

#### FR-003-2: 子例外クラス（5種類） 🔵

**EARS**: システムは以下の 5 つの子例外クラスを定義しなければならない。全て `AIServiceError` を継承する。

| 例外クラス | HTTP マッピング | 既存例外（TASK-0055 で移行） | 根拠 |
|-----------|----------------|--------------------------|------|
| `AITimeoutError` | 504 Gateway Timeout | `BedrockTimeoutError` | interfaces.py L237-243 |
| `AIRateLimitError` | 429 Too Many Requests | `BedrockRateLimitError` | interfaces.py L246-252 |
| `AIInternalError` | 500 Internal Server Error | `BedrockInternalError` | interfaces.py L255-261 |
| `AIParseError` | 500 Internal Server Error | `BedrockParseError` | interfaces.py L264-270 |
| `AIProviderError` | 503 Service Unavailable | （新規） | interfaces.py L273-279 |

```python
class AITimeoutError(AIServiceError):
    """AI タイムアウトエラー -> HTTP 504."""
    pass

class AIRateLimitError(AIServiceError):
    """AI レート制限エラー -> HTTP 429."""
    pass

class AIInternalError(AIServiceError):
    """AI 内部エラー -> HTTP 500."""
    pass

class AIParseError(AIServiceError):
    """AI レスポンス解析エラー -> HTTP 500."""
    pass

class AIProviderError(AIServiceError):
    """AI プロバイダーエラー -> HTTP 503."""
    pass
```

#### FR-003-3: 例外キャッチ動作 🔵

**EARS**: `AIServiceError` で catch した場合、全ての子例外が捕捉されなければならない。

```python
# 以下のコードで全子例外がキャッチされること
try:
    raise AITimeoutError("timeout")
except AIServiceError:
    pass  # ここに到達すること
```

**根拠**: 要件 REQ-SM-201（旧実装・新実装の共存）、architecture.md L79-93

---

### FR-004: ファクトリ関数 🔵

**信頼性**: 🔵 *interfaces.py（L287-298）・architecture.md（L256-273）・設計ヒアリング Q1・REQ-SM-102/103 より確定*

**ファイル**: `backend/src/services/ai_service.py`

#### FR-004-1: 関数シグネチャ 🔵

**EARS**: システムは `create_ai_service()` ファクトリ関数を定義しなければならない。

```python
def create_ai_service(use_strands: bool = None) -> AIService:
```

**パラメータ仕様**:

| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| `use_strands` | `bool \| None` | `None` | `None` の場合は `USE_STRANDS` 環境変数を参照 |

#### FR-004-2: 環境変数による判定 🔵

**EARS**: `use_strands` パラメータが `None` の**場合**、システムは `USE_STRANDS` 環境変数を参照し、`"true"`（大文字小文字不問）であれば `StrandsAIService` を、それ以外であれば `BedrockAIService` を返却しなければならない。

- `USE_STRANDS` 環境変数が未設定の場合のデフォルトは `"false"`（BedrockAIService を返却）
- **安全なデフォルト**: 環境変数が不正値の場合も BedrockAIService にフォールバック

**根拠**: REQ-SM-102/103（フィーチャーフラグ制御）

#### FR-004-3: 明示的パラメータによるオーバーライド 🔵

**EARS**: `use_strands` パラメータが明示的に指定された**場合**、環境変数の値に関わらず、指定された値に従って実装を選択しなければならない。

- `use_strands=True` -> `StrandsAIService`
- `use_strands=False` -> `BedrockAIService`

#### FR-004-4: 遅延インポート 🔵

**EARS**: ファクトリ関数は、循環インポートを防止するため、`BedrockAIService` および `StrandsAIService` のインポートを関数内部で遅延実行しなければならない。

```python
def create_ai_service(use_strands: bool = None) -> AIService:
    import os

    if use_strands is None:
        use_strands = os.getenv("USE_STRANDS", "false").lower() == "true"

    try:
        if use_strands:
            from services.strands_service import StrandsAIService
            return StrandsAIService()
        else:
            from services.bedrock import BedrockAIService
            return BedrockAIService()
    except Exception as e:
        raise AIProviderError(f"Failed to initialize AI service: {e}") from e
```

**注意**: `StrandsAIService` は TASK-0057 で実装予定のため、TASK-0053 のファクトリ関数テストでは `BedrockAIService` 側の動作検証に加え、`StrandsAIService` 側はモックで検証する。`from services.strands_service import StrandsAIService` のインポートパスは architecture.md L175 より。

#### FR-004-5: 初期化失敗時のエラー処理 🔵

**EARS**: AI サービスの初期化に失敗した**場合**、`AIProviderError` を送出しなければならない。

- 元の例外を `from e` でチェーンする
- エラーメッセージに失敗原因を含める

**根拠**: architecture.md L256-273、TASK-0053.md L195-223

---

### FR-005: 型エイリアス定義 🔵

**信頼性**: 🔵 *prompts.py（L6-7）・interfaces.py（L23-25）より確定*

**ファイル**: `backend/src/services/ai_service.py`

#### FR-005-1: DifficultyLevel 型 🔵

**EARS**: システムは `DifficultyLevel` 型エイリアスを定義しなければならない。

```python
DifficultyLevel = Literal["easy", "medium", "hard"]
```

**重要**: 既存 `prompts.py` L6 で `DifficultyLevel = Literal["easy", "medium", "hard"]` と定義されている。タスクファイル TASK-0053.md L232 では `"intermediate"` が使用されているが、**`"medium"` が正しい**。既存実装（prompts.py, bedrock.py L113）に合わせる。

#### FR-005-2: Language 型 🔵

**EARS**: システムは `Language` 型エイリアスを定義しなければならない。

```python
Language = Literal["ja", "en"]
```

**根拠**: prompts.py L7、interfaces.py L24

#### FR-005-3: 型エイリアスの再定義（prompts.py との関係） 🔵

**EARS**: `ai_service.py` モジュール内で `DifficultyLevel` と `Language` を独立して定義しなければならない。`prompts.py` からのインポートは行わない。

**理由**: 循環インポート防止。将来的には `prompts.py` が `ai_service.py` から型をインポートする方向に移行する（TASK-0054 以降のスコープ）。本タスクでは両モジュールに同一定義が並存する状態を許容する。

---

## 2. 非機能要件

### NFR-001: テストカバレッジ 🔵

**EARS**: `ai_service.py` モジュールの単体テストカバレッジは 80% 以上でなければならない。

**測定方法**:
```bash
pytest backend/tests/unit/test_ai_service.py --cov=services.ai_service --cov-report=term-missing
```

**根拠**: REQ-SM-404、CLAUDE.md 注意事項

### NFR-002: 既存テスト保護 🔵

**EARS**: 本タスクの実装後、既存の 262 件のバックエンドテストが全て通過しなければならない。

**測定方法**:
```bash
cd backend && make test
# 期待される結果: 262 tests passed
```

**根拠**: REQ-SM-405、architecture.md L391

### NFR-003: 循環インポート禁止 🔵

**EARS**: `ai_service.py` モジュールは循環インポートを発生させてはならない。

**検証方法**:
```bash
cd backend && python -c "from services.ai_service import AIService, create_ai_service"
# エラーなく完了すること
```

**根拠**: note.md L479-480

### NFR-004: Python 3.12 互換性 🔵

**EARS**: 全てのコードは Python 3.12 ランタイムで動作しなければならない。

**制約**:
- `typing.List`, `typing.Literal` を使用する（`list[str]` のようなビルトイン型ヒントとの混在を避ける）
- ただし interfaces.py L93 で `dict[str, float]` が使用されているため、`from __future__ import annotations` を冒頭に追加してフォワードリファレンスを有効化する

**根拠**: CLAUDE.md 技術スタック、architecture.md L388

### NFR-005: 後方互換性 🔵

**EARS**: 本タスクは既存の `bedrock.py` を変更してはならない。`GeneratedCard`、`GenerationResult` は `ai_service.py` に新規定義し、`bedrock.py` 内の同名クラスはそのまま残す。

**理由**: bedrock.py の既存クラスは TASK-0055 で ai_service.py からの import に切り替える。本タスクでは新旧が並存する状態を許容する。

**根拠**: note.md L487-488、TASK-0053.md L464

---

## 3. 受け入れ基準（Given/When/Then）

### AC-001: Protocol コンプライアンス検証

**Given**: `AIService` Protocol が `ai_service.py` に定義されている
**When**: Protocol のメソッド一覧を検査する
**Then**: 以下の 3 メソッドが存在する:
  - `generate_cards(self, input_text, card_count, difficulty, language) -> GenerationResult`
  - `grade_answer(self, card_front, card_back, user_answer, language) -> GradingResult`
  - `get_learning_advice(self, review_summary, language) -> LearningAdvice`

**信頼性**: 🔵

### AC-002: Protocol の runtime_checkable 検証

**Given**: `AIService` Protocol が `@runtime_checkable` で装飾されている
**When**: Protocol を満たすクラスに対して `isinstance()` を実行する
**Then**: `True` が返却される

```python
class MockService:
    def generate_cards(self, input_text, card_count=5, difficulty="medium", language="ja"):
        return GenerationResult(cards=[], input_length=0, model_used="mock", processing_time_ms=0)
    def grade_answer(self, card_front, card_back, user_answer, language="ja"):
        return GradingResult(grade=3, reasoning="", model_used="mock", processing_time_ms=0)
    def get_learning_advice(self, review_summary, language="ja"):
        return LearningAdvice(advice_text="", weak_areas=[], recommendations=[], model_used="mock", processing_time_ms=0)

assert isinstance(MockService(), AIService)
```

**信頼性**: 🔵

### AC-003: Protocol メソッドが同期であることの検証

**Given**: `AIService` Protocol が定義されている
**When**: 各メソッドが coroutine かどうかを検査する
**Then**: いずれのメソッドも coroutine ではない（`asyncio.iscoroutinefunction()` が `False` を返す）

**信頼性**: 🔵

### AC-004: GeneratedCard データクラスのインスタンス化

**Given**: `GeneratedCard` データクラスが定義されている
**When**: 必須フィールドのみでインスタンスを作成する
**Then**: `suggested_tags` がデフォルトで空リスト `[]` になる

```python
card = GeneratedCard(front="Q", back="A")
assert card.front == "Q"
assert card.back == "A"
assert card.suggested_tags == []
```

**信頼性**: 🔵

### AC-005: GenerationResult データクラスのインスタンス化

**Given**: `GenerationResult` データクラスが定義されている
**When**: 全フィールドを指定してインスタンスを作成する
**Then**: 各フィールドが正しく設定される

```python
card = GeneratedCard(front="Q", back="A")
result = GenerationResult(cards=[card], input_length=100, model_used="bedrock", processing_time_ms=1500)
assert len(result.cards) == 1
assert result.model_used == "bedrock"
assert result.processing_time_ms == 1500
```

**信頼性**: 🔵

### AC-006: GradingResult データクラスのインスタンス化

**Given**: `GradingResult` データクラスが定義されている
**When**: 全フィールドを指定してインスタンスを作成する
**Then**: 各フィールドが正しく設定される

```python
result = GradingResult(grade=4, reasoning="Correct", model_used="bedrock", processing_time_ms=500)
assert result.grade == 4
assert result.reasoning == "Correct"
```

**信頼性**: 🔵

### AC-007: ReviewSummary データクラスのインスタンス化

**Given**: `ReviewSummary` データクラスが定義されている
**When**: 必須フィールドのみでインスタンスを作成する
**Then**: `tag_performance` がデフォルトで空辞書 `{}`、`recent_review_dates` がデフォルトで空リスト `[]` になる

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

**信頼性**: 🟡（streak_days 計算ロジック未確定だが、フィールド定義自体は確定）

### AC-008: LearningAdvice データクラスのインスタンス化

**Given**: `LearningAdvice` データクラスが定義されている
**When**: 全フィールドを指定してインスタンスを作成する
**Then**: 各フィールドが正しく設定される

```python
advice = LearningAdvice(
    advice_text="Focus on verbs",
    weak_areas=["verb_conjugation"],
    recommendations=["Practice daily"],
    model_used="bedrock",
    processing_time_ms=1000,
)
assert advice.advice_text == "Focus on verbs"
assert len(advice.weak_areas) == 1
assert len(advice.recommendations) == 1
```

**信頼性**: 🔵

### AC-009: 例外継承階層の検証

**Given**: `AIServiceError` と 5 つの子例外クラスが定義されている
**When**: 各子例外の継承関係を `issubclass()` で検査する
**Then**: 全ての子例外が `AIServiceError` のサブクラスである

```python
assert issubclass(AITimeoutError, AIServiceError)
assert issubclass(AIRateLimitError, AIServiceError)
assert issubclass(AIInternalError, AIServiceError)
assert issubclass(AIParseError, AIServiceError)
assert issubclass(AIProviderError, AIServiceError)
```

**信頼性**: 🔵

### AC-010: 例外キャッチ動作の検証

**Given**: 子例外が送出される
**When**: `AIServiceError` で catch する
**Then**: 子例外が正常に捕捉される

```python
with pytest.raises(AIServiceError):
    raise AITimeoutError("Timeout")

with pytest.raises(AIServiceError):
    raise AIRateLimitError("Rate limited")
```

**信頼性**: 🔵

### AC-011: 例外メッセージの検証

**Given**: 子例外がメッセージ付きで送出される
**When**: 例外をキャッチしてメッセージを取得する
**Then**: 指定したメッセージが保持されている

```python
try:
    raise AITimeoutError("Request timed out after 30s")
except AIServiceError as e:
    assert str(e) == "Request timed out after 30s"
```

**信頼性**: 🔵

### AC-012: ファクトリ関数 - USE_STRANDS=false で BedrockAIService を返却

**Given**: 環境変数 `USE_STRANDS=false` が設定されている
**When**: `create_ai_service()` を呼び出す
**Then**: `BedrockAIService` インスタンスが返却される（モックで検証）

**信頼性**: 🔵

### AC-013: ファクトリ関数 - USE_STRANDS=true で StrandsAIService を返却

**Given**: 環境変数 `USE_STRANDS=true` が設定されている
**When**: `create_ai_service()` を呼び出す
**Then**: `StrandsAIService` インスタンスが返却される（モックで検証）

**信頼性**: 🔵

### AC-014: ファクトリ関数 - 明示的パラメータが環境変数をオーバーライド

**Given**: 環境変数 `USE_STRANDS=true` が設定されている
**When**: `create_ai_service(use_strands=False)` を呼び出す
**Then**: `BedrockAIService` インスタンスが返却される（環境変数が無視される）

**信頼性**: 🔵

### AC-015: ファクトリ関数 - 初期化失敗時に AIProviderError

**Given**: `BedrockAIService` のコンストラクタが例外を送出する
**When**: `create_ai_service(use_strands=False)` を呼び出す
**Then**: `AIProviderError` が送出される

**信頼性**: 🔵

### AC-016: ファクトリ関数 - USE_STRANDS 未設定時のデフォルト動作

**Given**: `USE_STRANDS` 環境変数が未設定である
**When**: `create_ai_service()` を呼び出す
**Then**: `BedrockAIService` インスタンスが返却される（安全なデフォルト）

**信頼性**: 🔵

### AC-017: 型エイリアスの検証

**Given**: `DifficultyLevel` と `Language` 型エイリアスが定義されている
**When**: 型エイリアスの `__args__` を検査する
**Then**: 正しいリテラル値の組が返却される

```python
assert set(get_args(DifficultyLevel)) == {"easy", "medium", "hard"}
assert set(get_args(Language)) == {"ja", "en"}
```

**信頼性**: 🔵

### AC-018: ミュータブルデフォルトの独立性検証

**Given**: `GeneratedCard` を複数インスタンス生成する
**When**: 一方の `suggested_tags` にアイテムを追加する
**Then**: 他方の `suggested_tags` は影響を受けない

```python
card1 = GeneratedCard(front="Q1", back="A1")
card2 = GeneratedCard(front="Q2", back="A2")
card1.suggested_tags.append("tag1")
assert card2.suggested_tags == []  # 独立していること
```

**信頼性**: 🔵

### AC-019: 既存テスト全通過の検証

**Given**: `ai_service.py` が新規作成されている
**When**: 全バックエンドテストを実行する (`make test`)
**Then**: 262 件の既存テストが全て通過する

**信頼性**: 🔵

---

## 4. 主要設計判断

### DD-001: 同期メソッド（async ではない） 🔵

**判断**: AIService Protocol のメソッドは同期（`def`）で定義する。

**根拠**:
- 既存 `BedrockService.generate_cards()` は同期メソッド（bedrock.py L109）
- interfaces.py の Protocol 定義は全て同期（L126, L148, L170）
- architecture.md の Protocol 定義は全て同期（L233, L241, L249）
- note.md L285-286 で「Protocol methods should sync in interface layer」と明記

**影響**: 将来的に非同期化が必要になった場合は Protocol を変更する必要がある。ただし現時点では Lambda 環境（同期ハンドラー）での動作を優先する。

### DD-002: dataclasses（Pydantic ではない） 🔵

**判断**: サービス層のデータクラスは `@dataclass` で定義する。Pydantic `BaseModel` は使用しない。

**根拠**:
- interfaces.py が全て `@dataclass` で定義
- note.md L42-43 で「ai_service.py uses only dataclasses and Protocol」と明記
- Pydantic はリクエスト/レスポンスモデル（models/ ディレクトリ）で使用（TASK-0054+ のスコープ）

**トレードオフ**: バリデーション機能がないため、`grade` の 0-5 範囲チェックなどは Pydantic モデル層で実施する。

### DD-003: runtime_checkable Protocol 🔵

**判断**: `@runtime_checkable` デコレーターを使用して `isinstance()` チェックを可能にする。

**根拠**:
- interfaces.py L116 で `class AIService(Protocol):` と定義（`@runtime_checkable` は暗黙的に想定）
- note.md L72-76 で `@runtime_checkable` の使用が明記
- TASK-0053.md L49 で `@runtime_checkable` が指定

**注意**: `@runtime_checkable` はメソッドのシグネチャまでは検証しない。メソッドの存在のみをチェックする。

### DD-004: 遅延インポートによる循環依存防止 🔵

**判断**: `create_ai_service()` 内で `BedrockAIService` / `StrandsAIService` を遅延インポートする。

**根拠**:
- architecture.md L261-272 のファクトリ関数が関数内インポートを使用
- note.md L479-480 で循環インポート防止を指定

**理由**: `bedrock.py` は `prompts.py` からインポートしている。`ai_service.py` がモジュールレベルで `bedrock.py` をインポートすると、将来 `prompts.py` が `ai_service.py` の型を参照する際に循環が発生する。

### DD-005: field(default_factory=...) によるミュータブルデフォルト 🔵

**判断**: リスト・辞書のデフォルト値には `field(default_factory=...)` を使用する。

**対象フィールド**:
- `GeneratedCard.suggested_tags`: `field(default_factory=list)`
- `ReviewSummary.tag_performance`: `field(default_factory=dict)`
- `ReviewSummary.recent_review_dates`: `field(default_factory=list)`

**根拠**: note.md L332-348、Python dataclass のミュータブルデフォルト問題

### DD-006: DifficultyLevel は "medium"（"intermediate" ではない） 🔵

**判断**: `DifficultyLevel` の中間難易度は `"medium"` とする。

**根拠**:
- 既存 `prompts.py` L6: `Literal["easy", "medium", "hard"]`
- 既存 `bedrock.py` L113: `difficulty: DifficultyLevel = "medium"`
- interfaces.py L23: `Literal["easy", "medium", "hard"]`
- タスクファイル TASK-0053.md L232 の `"intermediate"` は設計反映前の草案

### DD-007: get_learning_advice の review_summary は dict 型 🔵

**判断**: `get_learning_advice()` の `review_summary` パラメータは `dict` 型とする（`ReviewSummary` データクラスではない）。

**根拠**:
- interfaces.py L170-173: `review_summary: dict`
- architecture.md L249-253: `review_summary: dict`

**理由**: 事前クエリの結果をそのまま辞書として渡す柔軟性を確保する。`ReviewSummary` データクラスはドキュメント・テスト目的で存在するが、Protocol の型制約としては使用しない。

---

## 5. 成果物一覧

| ファイル | 操作 | 内容 |
|---------|------|------|
| `backend/src/services/ai_service.py` | 新規作成 | Protocol, データクラス, 例外階層, ファクトリ関数, 型エイリアス |
| `backend/tests/unit/test_ai_service.py` | 新規作成 | 単体テスト（AC-001〜AC-019 に対応） |

**既存ファイルへの変更**: なし（bedrock.py, prompts.py, handler.py はこのタスクでは変更しない）

---

## 6. テスト戦略

### テストファイル構成

**ファイル**: `backend/tests/unit/test_ai_service.py`

| テストカテゴリ | 対応 AC | テスト数（概算） |
|---------------|---------|----------------|
| Protocol メソッド検証 | AC-001, AC-002, AC-003 | 3-5 |
| データクラスインスタンス化 | AC-004〜AC-008, AC-018 | 7-9 |
| 例外階層検証 | AC-009〜AC-011 | 5-7 |
| ファクトリ関数検証 | AC-012〜AC-016 | 5-6 |
| 型エイリアス検証 | AC-017 | 2 |

**合計**: 約 22-29 テストケース

### TDD フロー

1. **Red フェーズ**: test_ai_service.py に全テストを記述 -> 全テスト FAIL（ai_service.py 未作成）
2. **Green フェーズ**: ai_service.py を最小限実装 -> 全テスト PASS
3. **Refactor フェーズ**: docstring・型ヒント・エラーメッセージを改善 -> 全テスト PASS + カバレッジ 80%+

---

## 7. 信頼性レベルサマリー

| カテゴリ | 🔵 青 | 🟡 黄 | 🔴 赤 |
|---------|-------|-------|-------|
| FR-001 Protocol 定義 | 4 | 0 | 0 |
| FR-002 データクラス | 4 | 1 | 0 |
| FR-003 例外階層 | 3 | 0 | 0 |
| FR-004 ファクトリ関数 | 5 | 0 | 0 |
| FR-005 型エイリアス | 3 | 0 | 0 |
| NFR 非機能要件 | 5 | 0 | 0 |
| **合計** | **24** | **1** | **0** |

**品質評価**: 高品質（🔵 96%、🔴 0%）

**🟡 の項目**:
- FR-002-4 ReviewSummary: `streak_days` の計算ロジック詳細が未確定（TASK-0046 依存）、`recent_review_dates` の表示フォーマット詳細が未確定。ただしフィールド定義（型・名前）は interfaces.py で確定済み。
