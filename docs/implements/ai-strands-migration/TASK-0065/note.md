# TASK-0065: 全体統合テスト + 品質確認 - タスクノート

**タスクID**: TASK-0065
**タイトル**: 全体統合テスト + 品質確認
**要件名**: ai-strands-migration
**フェーズ**: Phase 4 - ローカル開発 + 最終検証
**作成日**: 2026-02-24

---

## 1. 技術スタック

### バックエンド言語
- **Python 3.12** - Lambda ランタイム（SAM template.yaml で Runtime: python3.12）
- **pytest 8.3.5** - テストフレームワーク

### AWS・インフラ
- **AWS SAM** (AWS Serverless Application Model) - Lambda 関数定義・デプロイ
- **Amazon Bedrock** - AI 推論エンドポイント（prod/staging 環境）
- **Ollama** - ローカル AI 推論（dev 環境）
- **AWS Strands Agents SDK** - マイグレーション対象の AI SDK

### 依存ライブラリ
- **Pydantic v2** - データモデル検証
- **boto3 + botocore** - AWS サービス連携（Bedrock）
- **strands** - AWS Strands SDK

---

## 2. テスト統計情報

### 全テスト数
- **合計テスト数: 687テスト** (pytest --collect-only)
- **既存テスト数: 260+ テスト**（Phase 1-3 で実装済み）
- **新規テスト**: Phase 1-4 で追加（AI Strands SDK 関連）

### テストファイル一覧（AI Strands 関連）
```
backend/tests/unit/
  ├── test_ai_service.py                  # AIService Protocol テスト
  ├── test_strands_service.py             # StrandsAIService 実装テスト
  ├── test_bedrock.py                     # BedrockService 実装テスト
  ├── test_strands_import.py              # Strands SDK インポート確認
  ├── test_generate_prompts.py            # カード生成プロンプトテスト
  ├── test_grading_prompts.py             # 採点プロンプトテスト
  ├── test_advice_prompts.py              # アドバイスプロンプトテスト
  ├── test_prompts_package.py             # プロンプトパッケージテスト
  ├── test_bedrock_protocol.py            # Bedrock Protocol 準拠性テスト
  ├── test_migration_compat.py            # マイグレーション互換性テスト
  ├── test_grading_models.py              # 採点モデルテスト
  ├── test_advice_models.py               # アドバイスモデルテスト
  ├── test_handler_grade_ai.py            # /grade ハンドラーテスト
  └── test_handler_advice.py              # /advice ハンドラーテスト

backend/tests/integration/
  └── test_integration.py                 # 統合テスト
```

---

## 3. AIService Protocol 定義

### ファイルパス
`/Volumes/external/dev/memoru-liff/backend/src/services/ai_service.py`

### Protocol メソッド（3つ）

#### 1. generate_cards()
```python
def generate_cards(
    self,
    input_text: str,
    card_count: int = 5,
    difficulty: DifficultyLevel = "medium",
    language: Language = "ja",
) -> GenerationResult
```
**目的**: テキストからフラッシュカードを自動生成
**パラメータ**:
- `input_text`: 生成元テキスト（10-2000文字）
- `card_count`: 生成カード数（1-10、デフォルト5）
- `difficulty`: 難易度（"easy", "medium", "hard"）
- `language`: 出力言語（"ja", "en"）

**戻り値**: GenerationResult
- `cards: List[GeneratedCard]` - 生成されたカード
- `input_length: int` - 入力テキスト長
- `model_used: str` - 使用モデル（"strands_bedrock" or "strands_ollama"）
- `processing_time_ms: int` - 処理時間（ミリ秒）

#### 2. grade_answer()
```python
def grade_answer(
    self,
    card_front: str,
    card_back: str,
    user_answer: str,
    language: Language = "ja",
) -> GradingResult
```
**目的**: ユーザーの回答を AI で採点
**パラメータ**:
- `card_front`: カードの問題文
- `card_back`: カードの正解
- `user_answer`: ユーザーの回答
- `language`: 言語（"ja", "en"）

**戻り値**: GradingResult
- `grade: int` - SRS グレード（0-5）
- `reasoning: str` - 採点理由（日本語）
- `model_used: str` - 使用モデル
- `processing_time_ms: int` - 処理時間

#### 3. get_learning_advice()
```python
def get_learning_advice(
    self,
    review_summary: dict,
    language: Language = "ja",
) -> LearningAdvice
```
**目的**: 学習履歴に基づく AI アドバイスを生成
**パラメータ**:
- `review_summary`: 復習履歴の集計データ（事前クエリ結果）
- `language`: 言語

**戻り値**: LearningAdvice
- `advice_text: str` - アドバイス本文（日本語）
- `weak_areas: List[str]` - 弱点分野のリスト
- `recommendations: List[str]` - 学習推奨事項のリスト
- `model_used: str` - 使用モデル
- `processing_time_ms: int` - 処理時間

---

## 4. AI サービスエンドポイント

### 3つのエンドポイント

#### 1. POST /cards/generate
**ハンドラー**: `backend/src/services/prompts/generate.py`
**プロトコルメソッド**: `generate_cards()`
**リクエスト例**:
```json
{
  "input_text": "日本の首都について...",
  "card_count": 5,
  "difficulty": "medium",
  "language": "ja"
}
```
**レスポンス**:
```json
{
  "cards": [
    {
      "front": "日本の首都は？",
      "back": "東京",
      "suggested_tags": ["geography", "japan"]
    }
  ],
  "input_length": 150,
  "model_used": "strands_bedrock",
  "processing_time_ms": 1234
}
```

#### 2. POST /reviews/{cardId}/grade-ai
**ハンドラー**: `backend/src/services/prompts/grading.py`
**プロトコルメソッド**: `grade_answer()`
**リクエスト例**:
```json
{
  "card_front": "日本の首都は？",
  "card_back": "東京",
  "user_answer": "Tokyo",
  "language": "ja"
}
```
**レスポンス**:
```json
{
  "grade": 4,
  "reasoning": "英語で正解を答えましたが、質問は日本語でした",
  "model_used": "strands_bedrock",
  "processing_time_ms": 890
}
```

#### 3. GET /advice
**ハンドラー**: `backend/src/services/prompts/advice.py`
**プロトコルメソッド**: `get_learning_advice()`
**リクエスト例**:
```json
{
  "review_summary": {
    "total_reviews": 50,
    "average_grade": 3.5,
    "total_cards": 20,
    "cards_due_today": 5,
    "streak_days": 3
  },
  "language": "ja"
}
```
**レスポンス**:
```json
{
  "advice_text": "最近は回答精度が上がっています。毎日5分の復習を継続してください。",
  "weak_areas": ["grammar", "kanji"],
  "recommendations": ["複文法を重点的に学習", "漢字の書き練習を増やす"],
  "model_used": "strands_ollama",
  "processing_time_ms": 2100
}
```

---

## 5. AI サービス実装

### 2つの実装クラス

#### 1. StrandsAIService
**ファイル**: `/Volumes/external/dev/memoru-liff/backend/src/services/strands_service.py`
**概要**: AWS Strands Agents SDK を使用した実装

**主要メソッド**:
- `__init__(environment=None)`: 初期化（環境変数 ENVIRONMENT を参照）
- `_create_model()`: モデルプロバイダーの選択・初期化
- `generate_cards()`: カード生成（Protocol に準拠）
- `grade_answer()`: 回答採点
- `get_learning_advice()`: 学習アドバイス

**環境対応**:
- `environment == "dev"`: OllamaModel（http://localhost:11434、llama3.2）
- `environment == "prod"` or "staging"`: BedrockModel（Claude 3 Haiku）

**環境変数**:
```
ENVIRONMENT=dev|prod|staging    # 実行環境
OLLAMA_HOST=http://localhost:11434  # Ollama ホスト（dev のみ）
OLLAMA_MODEL=llama3.2           # Ollama モデル（dev のみ）
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0  # Bedrock モデルID
```

#### 2. BedrockService
**ファイル**: `/Volumes/external/dev/memoru-liff/backend/src/services/bedrock.py`
**概要**: Amazon Bedrock を使用した実装（従来方式）

**主要メソッド**:
- `__init__(model_id=None, bedrock_client=None)`: 初期化
- `generate_cards()`: カード生成
- `grade_answer()`: 回答採点
- `get_learning_advice()`: 学習アドバイス

**定数**:
```python
DEFAULT_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 2
```

---

## 6. フィーチャーフラグ

### USE_STRANDS 環境変数

**用途**: 実装の選択分岐（StrandsAIService vs BedrockService）

**仕組み**: `ai_service.py` の `create_ai_service()` ファクトリ関数
```python
def create_ai_service(use_strands: bool | None = None) -> AIService:
    if use_strands is None:
        use_strands = os.getenv("USE_STRANDS", "false").lower() == "true"

    if use_strands:
        from services.strands_service import StrandsAIService
        return StrandsAIService()
    else:
        from services.bedrock import BedrockService
        return BedrockService()
```

**設定例**:
```bash
# Strands SDK 使用（Ollama）
export USE_STRANDS=true

# Bedrock 使用（従来方式）
export USE_STRANDS=false
```

---

## 7. エラーハンドリング階層

### AIServiceError 基底クラス
**ファイル**: `backend/src/services/ai_service.py`
**継承関係**:

```
AIServiceError (基底)
  ├── AITimeoutError
  │   └── HTTP 504 (Gateway Timeout)
  │
  ├── AIRateLimitError
  │   └── HTTP 429 (Too Many Requests)
  │
  ├── AIInternalError
  │   └── HTTP 500 (Internal Server Error)
  │
  ├── AIParseError
  │   └── HTTP 500 (Internal Server Error)
  │   └── AI レスポンス解析失敗時
  │
  └── AIProviderError
      └── HTTP 503 (Service Unavailable)
      └── プロバイダー初期化失敗時
```

### Bedrock 固有例外
BedrockService では以下の追加例外クラスを定義:
```python
BedrockServiceError (AIServiceError)
  ├── BedrockTimeoutError (AITimeoutError も継承)
  ├── BedrockRateLimitError (AIRateLimitError も継承)
  ├── BedrockInternalError (AIInternalError も継承)
  └── BedrockParseError (AIParseError も継承)
```

### エラーハンドリングパターン

**統一パターン**:
```python
try:
    result = service.generate_cards(input_text)
except AITimeoutError as e:
    logger.error("AI timeout", extra={"error_code": "AI_TIMEOUT"})
    return {"statusCode": 504, "body": "Processing timeout"}
except AIRateLimitError as e:
    logger.error("Rate limit", extra={"error_code": "RATE_LIMIT"})
    return {"statusCode": 429, "body": "Too many requests"}
except AIServiceError as e:
    logger.error("AI error", extra={"error_code": "AI_ERROR"})
    return {"statusCode": 500, "body": "AI processing failed"}
```

---

## 8. プロンプト管理

### ディレクトリ構造
```
backend/src/services/prompts/
  ├── __init__.py              # エクスポート・ファクトリ関数
  ├── _types.py                # プロンプト関連型定義
  ├── generate.py              # カード生成プロンプト
  ├── grading.py               # 採点プロンプト
  └── advice.py                # アドバイスプロンプト
```

### 3つのプロンプトモジュール

#### 1. generate.py（カード生成）
**関数**: `get_card_generation_prompt()`
**戻り値**: システムプロンプト + ユーザープロンプト
**含むテンプレート変数**:
- `{input_text}` - 生成元テキスト
- `{card_count}` - 生成カード数
- `{difficulty}` - 難易度

#### 2. grading.py（回答採点）
**関数**: `get_grading_prompt()`
**定数**: `GRADING_SYSTEM_PROMPT`
**含むテンプレート変数**:
- `{card_front}` - 問題文
- `{card_back}` - 正解
- `{user_answer}` - ユーザー回答

#### 3. advice.py（学習アドバイス）
**関数**: `get_advice_prompt()`
**定数**: `ADVICE_SYSTEM_PROMPT`
**含むテンプレート変数**:
- `{total_reviews}` - 復習総数
- `{average_grade}` - 平均グレード
- `{weak_areas}` - 弱点分野

### プロンプト設計原則

1. **システムプロンプトの分離**: ユーザー入力と明確に分離
2. **テンプレート変数の使用**: format() で安全に埋め込み
3. **入力検証**: 危険な文字列のフィルタリング
4. **言語対応**: 日本語/英語の出力を制御可能

---

## 9. テストカバレッジ目標

### 全体目標
- **全体**: 80% 以上

### モジュール別目標
| モジュール | 目標 | 説明 |
|-----------|------|------|
| `ai_service.py` | 85% | Protocol 定義と Factory 関数 |
| `strands_service.py` | 85% | Strands SDK 統合実装 |
| `bedrock.py` | 80% | Bedrock API 統合 |
| `prompts/` | 75% | プロンプトテンプレート |
| `handlers/` | 80% | Lambda ハンドラー |

### カバレッジ確認コマンド
```bash
cd backend
pytest --cov=src --cov-report=term-missing --cov-report=html
open htmlcov/index.html  # macOS
```

---

## 10. 型安全性確認（mypy）

### 実行方法
```bash
cd backend
mypy src/ --strict
```

### 確認項目

#### Protocol 準拠性
- ✓ AIService Protocol のすべてのメソッドが実装されている
- ✓ メソッド署名（戻り値、パラメータ型）が完全に一致
- ✓ Optional[T] 型の処理が正しい
- ✓ Union 型の分岐が網羅的

#### 型指定の完全性
- ✓ すべての関数パラメータに型注釈がある
- ✓ すべての関数戻り値に型注釈がある
- ✓ 型キャストが不要な設計になっている

---

## 11. ログ出力規約

### ログレベルの使い分け

#### INFO レベル
ユーザー向けの重要な操作
```python
logger.info(
    "Grade card started",
    extra={
        "card_id": card_id,
        "service": "strands",
        "environment": "dev"
    }
)
```

#### DEBUG レベル
開発者向けの詳細情報
```python
logger.debug(
    "Strands request prepared",
    extra={
        "prompt_tokens": prompt_tokens,
        "model": "llama3.2",
        "timestamp": timestamp
    }
)
```

#### WARNING レベル
潜在的な問題（フォールバック、リトライ）
```python
logger.warning(
    "Fallback to Bedrock",
    extra={
        "reason": "Ollama timeout",
        "retry_attempt": 1
    }
)
```

#### ERROR レベル
エラー発生時の詳細
```python
logger.error(
    "Grade process failed",
    extra={
        "card_id": card_id,
        "error_code": "GRADE_FAILED",
        "exception_type": type(e).__name__
    },
    exc_info=True
)
```

### ログ出力数の目安
- 全体: 150+ ログステートメント
- `grep -r "logger\." src/ | wc -l` で確認

---

## 12. セキュリティ（プロンプトインジェクション対策）

### 対策方針

#### 1. ユーザー入力の検証
```python
def validate_user_input(text: str) -> None:
    if len(text) > MAX_LENGTH:
        raise InputValidationError("Text too long")
    if contains_prompt_injection_patterns(text):
        raise InputValidationError("Suspicious input detected")
```

#### 2. プロンプトテンプレートの分離
```python
# ✓ 良い例：定数とユーザー入力を分離
GRADE_PROMPT = """
You are a Japanese language learning tutor.
Evaluate the student's answer objectively.
Card content: {card_content}
User answer: {user_answer}
Your evaluation:
"""

prompt = GRADE_PROMPT.format(
    card_content=sanitize(card_content),
    user_answer=sanitize(user_answer)
)
```

#### 3. システムプロンプトの保護
- ✓ システムプロンプトにはユーザー入力を含まない
- ✓ モデルの指示がオーバーライドされない設計
- ✓ 新規命令が注入されるリスク回避

### 検査チェックリスト
- [ ] すべてのユーザー入力がサニタイズされている
- [ ] テンプレートがユーザー入力で破壊されない
- [ ] システムプロンプトが保護されている
- [ ] SQL インジェクション的な攻撃パターンの検出

---

## 13. 既存テスト保護

### 非回帰テスト戦略

**目標**: 260+ の既存テストを全て保護（全て成功）

**確認コマンド**:
```bash
cd backend
pytest -v --tb=short 2>&1 | tee test-results.log

# テスト数確認
grep -c "PASSED" test-results.log  # 260+ であることを確認
```

**テストファイルの行数確認**:
```bash
find tests/ -name "test_*.py" -o -name "*_test.py" | xargs wc -l | tail -1
# 出力例: 12000 total （260+ テストケース）
```

---

## 14. 統合テスト手順

### Step 1: ローカルサービス起動（30秒）
```bash
cd backend
make local-all
# 出力: DynamoDB, Keycloak, Ollama が起動
```

**起動確認**:
```bash
# 別ターミナルで確認
curl -s http://localhost:8001 | grep -q "DynamoDB"     # DynamoDB Admin
curl -s http://localhost:8180/health/ready             # Keycloak
curl -s http://localhost:11434/api/tags | grep -q "name"  # Ollama
```

### Step 2: バックエンド API 起動（10秒）
```bash
cd backend
make local-api
# ポート: 8080
```

### Step 3: USE_STRANDS フラグで動作確認

#### テストケース A: USE_STRANDS=true（Ollama）
```bash
export USE_STRANDS=true

# /cards/generate（カード生成）
curl -X POST http://localhost:8080/cards/generate \
  -H "Content-Type: application/json" \
  -d '{
    "input_text": "日本の首都は東京です",
    "card_count": 3,
    "difficulty": "medium",
    "language": "ja"
  }'

# 期待される応答:
# {
#   "cards": [...],
#   "input_length": 15,
#   "model_used": "strands_ollama",
#   "processing_time_ms": 1234
# }

# /reviews/test-001/grade-ai（採点）
curl -X POST http://localhost:8080/reviews/test-001/grade-ai \
  -H "Content-Type: application/json" \
  -d '{
    "card_front": "日本の首都は？",
    "card_back": "東京",
    "user_answer": "Tokyo",
    "language": "ja"
  }'

# /advice（アドバイス）
curl -X POST http://localhost:8080/advice \
  -H "Content-Type: application/json" \
  -d '{
    "review_summary": {
      "total_reviews": 50,
      "average_grade": 3.5,
      "total_cards": 20,
      "cards_due_today": 5,
      "streak_days": 3
    },
    "language": "ja"
  }'
```

#### テストケース B: USE_STRANDS=false（Bedrock）
```bash
export USE_STRANDS=false
# 同じ curl コマンドを実行（AWS credentials が必要）
# model_used フィールドが "strands_bedrock" になること確認
```

### Step 4: レスポンスフォーマット検証

**各エンドポイント共通**:
- ✓ HTTP ステータス 200
- ✓ Content-Type: application/json
- ✓ body がフォーマット仕様を満たす

---

## 15. ドキュメント更新タスク

### 15.1 CLAUDE.md 更新

**ファイル**: `/Volumes/external/dev/memoru-liff/CLAUDE.md`
**セクション**: "ai-strands-migration（AI Strands SDK 移行）"

**更新内容**:
```markdown
#### ai-strands-migration（AI Strands SDK 移行）
- [x] Phase 1: 基盤構築 (TASK-0052 ~ TASK-0054)
- [x] Phase 2: Strands SDK 統合実装 (TASK-0055 ~ TASK-0059)
- [x] Phase 3: エラーハンドリング + アーキテクチャ強化 (TASK-0060 ~ TASK-0063)
- [x] Phase 4: ローカル開発 + 最終検証 (TASK-0064 ~ TASK-0065)

**最終状態**: ✅ 完了 - Bedrock から Strands Agents SDK へのマイグレーション完了
```

### 15.2 overview.md 更新

**ファイル**: `docs/tasks/ai-strands-migration/overview.md`
**内容**: 全タスク（TASK-0052～TASK-0065）の状態を `[x]` に更新

**更新フォーマット**:
```markdown
| Task ID | 要件コード | タスク名 | 状態 | Hours |
|---------|-----------|---------|------|-------|
| TASK-0052 | REQ-SM-001 | Strands Agents SDK 依存追加 + ビルド確認 | [x] | 4 |
| ... (中略) ...
| TASK-0065 | REQ-SM-404/405 | 全体統合テスト + 品質確認 | [x] | 6 |

**Phase 完了条件**:
- [x] 全テスト通過（260+ テスト）
- [x] テストカバレッジ 80% 以上
- [x] 全エンドポイント動作確認
- [x] コードレビュー観点確認完了
```

---

## 16. 完了条件チェックリスト

### テスト関連
- [ ] `make test` で全テスト通過（687テスト）
- [ ] テストカバレッジが 80% 以上（`--cov-report`で確認）
- [ ] 既存テスト 260+ が全て PASSED
- [ ] Protocol 準拠性テスト成功

### 動作確認
- [ ] USE_STRANDS=true で /cards/generate が HTTP 200 応答
- [ ] USE_STRANDS=true で /reviews/{cardId}/grade-ai が HTTP 200 応答
- [ ] USE_STRANDS=true で /advice が HTTP 200 応答
- [ ] USE_STRANDS=false で同上のエンドポイントが HTTP 200 応答（Bedrock）

### コード品質
- [ ] `mypy src/ --strict` でエラー 0 件
- [ ] エラーハンドリングパターンが統一されている
- [ ] ログ出力に error_code が含まれている
- [ ] プロンプトインジェクション対策が実装されている

### ドキュメント
- [ ] CLAUDE.md が更新されている
- [ ] overview.md のタスク一覧が更新されている
- [ ] test-results.log, htmlcov/ が保存されている
- [ ] mypy-results.log が保存されている

---

## 17. 主要ファイルマップ

| ファイルパス | 説明 | 行数 概算 |
|-----------|------|---------|
| `src/services/ai_service.py` | AIService Protocol 定義 | 199 |
| `src/services/strands_service.py` | Strands SDK 統合実装 | 300+ |
| `src/services/bedrock.py` | Bedrock API 統合実装 | 250+ |
| `src/services/prompts/__init__.py` | プロンプトファクトリ | 50+ |
| `src/services/prompts/generate.py` | カード生成プロンプト | 80+ |
| `src/services/prompts/grading.py` | 採点プロンプト + テンプレート | 100+ |
| `src/services/prompts/advice.py` | アドバイスプロンプト + テンプレート | 100+ |
| `tests/unit/test_ai_service.py` | Protocol テスト | 100+ |
| `tests/unit/test_strands_service.py` | Strands実装テスト | 150+ |
| `tests/unit/test_bedrock.py` | Bedrock実装テスト | 150+ |
| `tests/unit/test_generate_prompts.py` | 生成プロンプトテスト | 80+ |
| `tests/unit/test_grading_prompts.py` | 採点プロンプトテスト | 100+ |
| `tests/unit/test_advice_prompts.py` | アドバイスプロンプトテスト | 100+ |

---

## 18. トラブルシューティング

### 問題: テストが 260 件より少ない
**原因**: 新規テストファイルが src/ 配下に混在
**解決**: `tests/unit/` 配下のみをカウント

### 問題: USE_STRANDS=false でテストが失敗
**原因**: AWS credentials が未設定
**解決**: `aws configure` で credentials を設定

### 問題: Ollama が応答しない
**原因**: `make local-all` が完全に起動していない
**解決**: `curl http://localhost:11434/api/tags` で確認

### 問題: mypy strict で型エラーが多い
**原因**: 古いバージョンの型注釈を使用
**解決**: Protocol 定義を確認し、全て統一

---

## 19. 参考資料リンク

- **タスクファイル**: `/Volumes/external/dev/memoru-liff/docs/tasks/ai-strands-migration/TASK-0065.md`
- **概要**: `/Volumes/external/dev/memoru-liff/docs/tasks/ai-strands-migration/overview.md`
- **要件定義**: `/Volumes/external/dev/memoru-liff/docs/spec/ai-strands-migration/requirements.md`
- **設計文書**: `/Volumes/external/dev/memoru-liff/docs/design/ai-strands-migration/architecture.md`
- **API仕様**: `/Volumes/external/dev/memoru-liff/docs/design/ai-strands-migration/api-endpoints.md`

---

**ノート作成日**: 2026-02-24
**ステータス**: タスク開始準備完了
