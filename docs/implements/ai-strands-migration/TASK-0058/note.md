# TASK-0058: カード生成 API 互換性検証 + 移行テスト
## TDD Tasknote (タスクノート)

**作成日時**: 2026-02-23
**タスクタイプ**: TDD (Test-Driven Development)
**推定工数**: 8時間
**信頼性**: 🔵 (12項目全て青信号)

---

## 1. タスク概要

このタスクは、**USE_STRANDS フラグの true/false 両方でカード生成 API が同一のレスポンス形式を返すことを検証する**ための TDD フェーズです。

### 関連タスク
- **前提タスク**: TASK-0057 (StrandsAIService 実装完了), TASK-0055 (AIService Factory 実装)
- **後続タスク**: TASK-0063 (本番環境 移行スクリプト)

### 成果物
- `backend/tests/unit/test_migration_compat.py` (新規)
- `backend/tests/integration/test_migration_integration.py` (新規)

---

## 2. 技術背景

### 現在の実装状況

1. **TASK-0057 完了**: StrandsAIService がカード生成機能を実装
   - AWS Strands Agents SDK を使用
   - AIService Protocol に準拠
   - BedrockService と同じインターフェース `generate_cards()`

2. **TASK-0055 完了**: AIService Factory の実装
   - `create_ai_service(use_strands: bool | None = None)` 関数
   - 環境変数 `USE_STRANDS` に基づいて実装を切り替え
   - デフォルト: `USE_STRANDS="false"` → BedrockService
   - 明示設定: `USE_STRANDS="true"` → StrandsAIService

3. **既存実装**: BedrockService テストスイート
   - `test_bedrock.py`: 100+ テストケース
   - `test_handler.py`: 160+ テストケース（カード生成含む）
   - カバレッジ: 80%以上

### API 互換性の要件

**GenerateCardsResponse フォーマット（確定）**:
```python
@dataclass
class GenerateCardsResponse:
    """カード生成 API レスポンス."""
    generated_cards: List[GeneratedCardResponse]  # CardGenerated DTO
    generation_info: GenerationInfoResponse       # メタデータ

@dataclass
class GeneratedCardResponse:
    id: str                    # カードID（UUID）
    question: str              # 問題文
    answer: str                # 正答
    explanation: str           # 説明
    difficulty: str            # 難易度
    tags: List[str]            # タグ配列

@dataclass
class GenerationInfoResponse:
    model_used: str            # 使用モデル名
    generation_tokens: int     # 使用トークン数
    processing_time_ms: int    # 処理時間
```

### エラーハンドリング互換性

両方のサービスが同一の HTTP ステータスコードを返すことを検証:

| エラーシナリオ | Expected Status | Error Code | マッピング |
|---|---|---|---|
| Agent/Bedrock タイムアウト | 504 | GENERATION_TIMEOUT | AITimeoutError → 504 |
| レート制限超過 | 429 | RATE_LIMITED | AIRateLimitError → 429 |
| JSON 解析エラー | 500 | PARSE_ERROR | AIParseError → 500 |
| 内部エラー | 500 | INTERNAL_ERROR | AIInternalError → 500 |
| 入力バリデーション失敗 | 400 | VALIDATION_ERROR | ValidationError → 400 |
| ユーザー未認証 | 401 | UNAUTHORIZED | UnauthorizedError → 401 |
| ユーザー未登録 | 404 | USER_NOT_FOUND | UserNotFoundError → 404 |

---

## 3. テスト設計

### テストファイル構成

#### A. 単体テスト: `backend/tests/unit/test_migration_compat.py` (新規)

**テストクラス分類**:

1. **TestAPIResponseCompatibility** (TC-COMPAT-001 ~ TC-COMPAT-006)
   - 両サービスのレスポンス形式の一致検証
   - 成功時の GenerateCardsResponse スキーマ確認
   - エラーレスポンス形式の確認

2. **TestErrorHandlingCompatibility** (TC-ERROR-001 ~ TC-ERROR-008)
   - 各エラーシナリオで同じ HTTP ステータス確認
   - タイムアウト (504), レート制限 (429), 解析エラー (500) など

3. **TestFeatureFlagBehavior** (TC-FLAG-001 ~ TC-FLAG-003)
   - USE_STRANDS=true で StrandsAIService を使用
   - USE_STRANDS=false で BedrockService を使用
   - フラグ未設定時のデフォルト動作

4. **TestExistingTestProtection** (TC-PROTECT-001 ~ TC-PROTECT-002)
   - 既存テスト 260+ の継続実行確認
   - カバレッジ 80% 以上の維持確認

#### B. 統合テスト: `backend/tests/integration/test_migration_integration.py` (新規)

**テストシナリオ**:

1. **TestE2ECompatibility** (TC-E2E-001 ~ TC-E2E-003)
   - API Gateway 経由でのエンドツーエンド確認
   - USE_STRANDS=true/false 両方で動作確認
   - レスポンス形式の一致確認

---

## 4. テストケース詳細

### 4.1 API レスポンス形式一致テスト (TC-COMPAT-001 ~ TC-COMPAT-006)

#### TC-COMPAT-001: USE_STRANDS=true での成功レスポンス
```python
Given:
  - USE_STRANDS=true
  - StrandsAIService がモック済み
  - 有効なプロンプト入力
When:
  - POST /cards/generate を呼び出す
Then:
  - ステータスコード 200
  - レスポンスが GenerateCardsResponse スキーマに準拠
  - generated_cards 配列に 5 枚のカードが含まれる
  - generation_info に model_used, generation_tokens, processing_time_ms が含まれる
```

実装例：
```python
def test_response_format_use_strands_true(self):
    """USE_STRANDS=true でレスポンス形式が正しい"""
    with patch.dict(os.environ, {"USE_STRANDS": "true"}):
        with patch("services.strands_service.Agent") as mock_agent:
            # モック設定
            mock_agent.return_value.return_value = json.dumps({
                "cards": [
                    {"front": "Q", "back": "A", "tags": []}
                    for _ in range(5)
                ]
            })

            service = create_ai_service(use_strands=True)
            result = service.generate_cards("test text", card_count=5)

            # スキーマ検証
            assert isinstance(result, GenerationResult)
            assert len(result.cards) == 5
            assert result.model_used == "strands_bedrock"
            assert result.processing_time_ms > 0
```

#### TC-COMPAT-002: USE_STRANDS=false での成功レスポンス
```python
Given:
  - USE_STRANDS=false
  - BedrockService がモック済み
  - 有効なプロンプト入力
When:
  - POST /cards/generate を呼び出す
Then:
  - ステータスコード 200
  - レスポンスが GenerateCardsResponse スキーマに準拠
  - TC-COMPAT-001 と同じ構造
```

#### TC-COMPAT-003 ~ TC-COMPAT-006: スキーマ詳細検証
- 各カードに id (UUID), question, answer, explanation, difficulty, tags が存在
- generation_info の各フィールド型の確認
- null チェック、空配列ハンドリング

### 4.2 エラーハンドリング互換性テスト (TC-ERROR-001 ~ TC-ERROR-008)

#### TC-ERROR-001: タイムアウト (504)
```python
Given:
  - Agent/Bedrock がタイムアウト例外を raise
  - USE_STRANDS=true/false 両方
When:
  - POST /cards/generate を呼び出す
Then:
  - HTTP ステータス 504
  - error.code == "GENERATION_TIMEOUT"
```

実装例：
```python
def test_timeout_error_both_services(self):
    """タイムアウトエラーが両方のサービスで 504 を返す"""

    # USE_STRANDS=true の場合
    with patch.dict(os.environ, {"USE_STRANDS": "true"}):
        with patch("services.strands_service.Agent") as mock_agent:
            mock_agent.return_value.side_effect = TimeoutError("Agent timeout")

            service = create_ai_service(use_strands=True)
            with pytest.raises(AITimeoutError):
                service.generate_cards("test")

    # USE_STRANDS=false の場合
    with patch.dict(os.environ, {"USE_STRANDS": "false"}):
        with patch("services.bedrock.boto3.client") as mock_client:
            mock_client.return_value.invoke_model.side_effect = \
                ClientError({"Error": {"Code": "RequestTimeout"}}, "invoke_model")

            service = create_ai_service(use_strands=False)
            with pytest.raises(AITimeoutError):
                service.generate_cards("test")
```

#### TC-ERROR-002: レート制限 (429)
```python
Given: レート制限エラーがモック済み
Then: HTTP ステータス 429, error.code == "RATE_LIMITED"
```

#### TC-ERROR-003: JSON 解析エラー (500)
```python
Given: JSON パースエラーがモック済み
Then: HTTP ステータス 500, error.code == "PARSE_ERROR"
```

#### TC-ERROR-004 ~ TC-ERROR-008: 他のエラーケース
- 内部エラー (500)
- バリデーションエラー (400)
- ユーザー未認証 (401)
- ユーザー未登録 (404)

### 4.3 フィーチャーフラグ切替テスト (TC-FLAG-001 ~ TC-FLAG-003)

#### TC-FLAG-001: USE_STRANDS=true での切替
```python
def test_feature_flag_true():
    """USE_STRANDS=true で StrandsAIService が返される"""
    with patch.dict(os.environ, {"USE_STRANDS": "true"}):
        service = create_ai_service()
        assert isinstance(service, StrandsAIService)
        assert service.model_used == "strands_bedrock"
```

#### TC-FLAG-002: USE_STRANDS=false での切替
```python
def test_feature_flag_false():
    """USE_STRANDS=false で BedrockService が返される"""
    with patch.dict(os.environ, {"USE_STRANDS": "false"}):
        service = create_ai_service()
        assert isinstance(service, BedrockService)
```

#### TC-FLAG-003: フラグ未設定時のデフォルト動作
```python
def test_feature_flag_default():
    """USE_STRANDS 未設定時はデフォルト値を使用"""
    with patch.dict(os.environ, {}, clear=True):
        # architecture.md で指定されたデフォルト値を確認
        service = create_ai_service()
        # デフォルト値が false の場合
        assert isinstance(service, BedrockService)
```

### 4.4 既存テスト保護テスト (TC-PROTECT-001 ~ TC-PROTECT-002)

#### TC-PROTECT-001: BedrockService 既存テスト継続実行
```python
def test_existing_bedrock_tests_still_pass():
    """TASK-0057 前の test_bedrock.py が全て通過"""
    # pytest で test_bedrock.py を再実行
    # 100+ テストが全て PASS することを確認
    result = pytest.main(["-v", "tests/unit/test_bedrock.py"])
    assert result == 0
```

#### TC-PROTECT-002: API ハンドラー既存テスト継続実行
```python
def test_existing_handler_tests_still_pass():
    """TASK-0057 前の test_handler.py が全て通過"""
    # pytest で test_handler.py を再実行
    # 160+ テストが全て PASS することを確認
    result = pytest.main(["-v", "tests/unit/test_handler.py"])
    assert result == 0
```

---

## 5. 統合テスト設計

### 5.1 エンドツーエンド互換性テスト (TC-E2E-001 ~ TC-E2E-003)

#### TC-E2E-001: USE_STRANDS=true での API 動作確認
```python
@pytest.fixture
def lambda_context_with_strands_true():
    """USE_STRANDS=true の Lambda コンテキスト"""
    with patch.dict(os.environ, {"USE_STRANDS": "true"}):
        yield

def test_e2e_api_with_strands_true(lambda_context_with_strands_true):
    """API Gateway を経由した E2E テスト (USE_STRANDS=true)"""
    # API Gateway イベントをシミュレート
    event = {
        "requestContext": {"authorizer": {"claims": {"sub": "test-user"}}},
        "body": json.dumps({
            "text": "光合成について説明してください",
            "card_count": 5,
            "difficulty": "medium",
            "language": "ja"
        }),
        "path": "/cards/generate",
        "httpMethod": "POST"
    }

    # handler.py の generate_cards_handler を呼び出す
    response = handler.lambda_handler(event, {})

    # レスポンス検証
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "generated_cards" in body
    assert len(body["generated_cards"]) == 5
    assert "generation_info" in body
    assert body["generation_info"]["model_used"] == "strands_bedrock"
```

#### TC-E2E-002: USE_STRANDS=false での API 動作確認
```python
def test_e2e_api_with_strands_false():
    """API Gateway を経由した E2E テスト (USE_STRANDS=false)"""
    with patch.dict(os.environ, {"USE_STRANDS": "false"}):
        # 同様のイベント処理
        response = handler.lambda_handler(event, {})

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        # レスポンス形式は TC-E2E-001 と同一
        assert "generated_cards" in body
        assert "generation_info" in body
        # model_used は異なる可能性あり
        # ("bedrock" 等)
```

#### TC-E2E-003: エラーレスポンス一致確認
```python
def test_e2e_error_compatibility():
    """エラーレスポンス形式が両サービスで一致"""
    # バリデーションエラー (400) のテスト
    event = {
        "requestContext": {"authorizer": {"claims": {"sub": "test-user"}}},
        "body": json.dumps({"text": "", "card_count": 0}),  # 無効な入力
        "path": "/cards/generate",
        "httpMethod": "POST"
    }

    for use_strands in ["true", "false"]:
        with patch.dict(os.environ, {"USE_STRANDS": use_strands}):
            response = handler.lambda_handler(event, {})
            assert response["statusCode"] == 400
            body = json.loads(response["body"])
            assert "error" in body
```

---

## 6. テスト実装上の注意点

### 6.1 モック戦略

**Strands Agent のモック**:
```python
@patch("services.strands_service.Agent")
def test_with_mocked_agent(mock_agent):
    # Agent のコンストラクタはモックし、モデルは注入
    mock_instance = MagicMock()
    mock_instance.return_value = json.dumps({"cards": [...]})
    mock_agent.return_value = mock_instance
```

**Bedrock クライアントのモック**:
```python
@patch("services.bedrock.boto3.client")
def test_with_mocked_bedrock(mock_boto_client):
    mock_client = MagicMock()
    mock_client.invoke_model.return_value = {
        "body": StringIO(json.dumps({"cards": [...]}))
    }
    mock_boto_client.return_value = mock_client
```

### 6.2 環境変数管理

```python
import pytest
from unittest.mock import patch

@pytest.fixture
def use_strands_true():
    """USE_STRANDS=true に設定"""
    with patch.dict(os.environ, {"USE_STRANDS": "true"}):
        yield

@pytest.fixture
def use_strands_false():
    """USE_STRANDS=false に設定"""
    with patch.dict(os.environ, {"USE_STRANDS": "false"}):
        yield
```

### 6.3 エラーの同期化確認

StrandsAIService と BedrockService の例外マッピングが一致しているか確認:

```python
def test_error_mapping_consistency():
    """両サービスのエラーマッピングが同じ"""

    # 対応表の確認
    mapping_table = {
        AITimeoutError: 504,
        AIRateLimitError: 429,
        AIParseError: 500,
        AIInternalError: 500,
        AIProviderError: 503,
    }

    # handler.py の _map_ai_error_to_http 関数で確認
    for error_type, expected_status in mapping_table.items():
        error = error_type("test error")
        response = handler._map_ai_error_to_http(error)
        assert response.status_code == expected_status
```

---

## 7. 実装フロー (TDD Phase)

### Phase 1: Red - テスト作成 (`/tsumiki:tdd-red`)

**成果物**: `test_migration_compat.py` + `test_migration_integration.py`

```bash
# 1. テストスケルトンを作成
# 2. すべてのテストケース (TC-COMPAT-001 ~ TC-E2E-003) を記述
# 3. 既存テストに依存しないモックを整備
# 4. pytest で実行 → すべてのテストが失敗することを確認
```

**チェックリスト**:
- [ ] test_migration_compat.py が作成される
- [ ] test_migration_integration.py が作成される
- [ ] 12+ テストケースが実装される
- [ ] テスト実行で全て失敗を確認 (赤フェーズ)

### Phase 2: Green - 実装確認 (`/tsumiki:tdd-green`)

**対象ファイル**: 既存実装の確認のみ（新規コード修正は不要）

```bash
# 1. ai_service.py (TASK-0053) の実装確認
#    - Protocol と例外階層
#    - create_ai_service() 関数
# 2. strands_service.py (TASK-0057) の実装確認
#    - generate_cards() メソッド
#    - エラーハンドリング
# 3. bedrock.py の実装確認
#    - 既存エラーマッピング
# 4. handler.py (TASK-0056) の実装確認
#    - _map_ai_error_to_http() 関数
#    - POST /cards/generate エンドポイント
# 5. テスト実行 → すべてのテストが成功することを確認
```

**チェックリスト**:
- [ ] USE_STRANDS フラグが環境変数で動作
- [ ] StrandsAIService と BedrockService が同じインターフェース
- [ ] エラーマッピングが一致
- [ ] pytest で全テスト成功を確認 (緑フェーズ)

### Phase 3: Refactor - テスト整理 (`/tsumiki:tdd-refactor`)

**対象**: test_migration_compat.py + test_migration_integration.py

```python
# 1. テストヘルパー関数の実装
def create_mock_agent_response(cards_count: int = 5) -> str:
    """モック Agent レスポンスを生成"""
    cards = [
        {"front": f"Q{i}", "back": f"A{i}", "tags": ["test"]}
        for i in range(cards_count)
    ]
    return json.dumps({"cards": cards})

def assert_response_schema(response: Dict[str, Any]) -> None:
    """GenerateCardsResponse スキーマを検証"""
    assert "generated_cards" in response
    assert "generation_info" in response
    assert isinstance(response["generated_cards"], list)
    # ... その他の検証

# 2. マジックナンバーの定数化
DEFAULT_CARD_COUNT = 5
DEFAULT_PROCESSING_TIME_MS = 1000
VALID_DIFFICULTIES = ["easy", "medium", "hard"]

# 3. テスト重複の削除
# - 共通のフィクスチャを活用
# - パラメータ化テストを使用

# 4. ドキュメント整備
# - docstring の追加
# - テストのカテゴリ分類をコメント化
```

**チェックリスト**:
- [ ] テストコードが DRY 原則に従う
- [ ] マジックナンバーが定数化される
- [ ] ヘルパー関数が実装される
- [ ] コードレビュー推奨事項が反映される

### Phase 4: Verify - 最終確認 (`/tsumiki:tdd-verify-complete`)

```bash
# 1. 全テストの再実行
pytest -v backend/tests/unit/test_migration_compat.py
pytest -v backend/tests/integration/test_migration_integration.py

# 2. 既存テストが継続して成功することを確認
pytest -v backend/tests/unit/test_bedrock.py
pytest -v backend/tests/unit/test_handler.py

# 3. カバレッジ確認
pytest --cov=src/services --cov-report=term-missing

# 4. デプロイ確認
make build
```

**チェックリスト**:
- [ ] 新規テスト全て成功 (test_migration_compat.py)
- [ ] 統合テスト全て成功 (test_migration_integration.py)
- [ ] 既存テスト 260+ 全て成功
- [ ] カバレッジ 80%+ 達成
- [ ] ビルド成功 (make build)

---

## 8. 既存テストとの関係

### 保護対象

| テストファイル | テスト数 | 対象機能 |
|---|---|---|
| test_bedrock.py | 100+ | BedrockService (既存実装) |
| test_handler.py | 160+ | API ハンドラー全般 |
| **合計** | **260+** | カード生成・エラーハンドリング |

### 互換性確認

```python
# 全既存テストが引き続き PASS することを確認
# これにより、StrandsAIService への移行が既存機能を損なわないことを保証

# usecase:
# USE_STRANDS=false (デフォルト) で実行
# → BedrockService が使用される
# → 既存テストが全て PASS
# → 新規テストでも同じレスポンス形式を確認
```

---

## 9. チェックリスト

### 実装前の確認事項

- [ ] TASK-0057 (StrandsAIService) の実装が完了している
- [ ] TASK-0055 (AIService Factory) の実装が完了している
- [ ] TASK-0056 (handler.py 統合) の実装が完了している
- [ ] api_service.py の Protocol と例外が定義されている
- [ ] 既存テスト 260+ が全て PASS する

### Red Phase (テスト作成)

- [ ] test_migration_compat.py を新規作成
- [ ] TestAPIResponseCompatibility クラス実装 (TC-COMPAT-001 ~ TC-COMPAT-006)
- [ ] TestErrorHandlingCompatibility クラス実装 (TC-ERROR-001 ~ TC-ERROR-008)
- [ ] TestFeatureFlagBehavior クラス実装 (TC-FLAG-001 ~ TC-FLAG-003)
- [ ] TestExistingTestProtection クラス実装 (TC-PROTECT-001 ~ TC-PROTECT-002)
- [ ] test_migration_integration.py を新規作成
- [ ] TestE2ECompatibility クラス実装 (TC-E2E-001 ~ TC-E2E-003)
- [ ] 全テストを実行 → 赤フェーズ確認 (すべて失敗)

### Green Phase (実装確認)

- [ ] USE_STRANDS 環境変数の動作確認
- [ ] StrandsAIService の generate_cards() 動作確認
- [ ] BedrockService の既存機能動作確認
- [ ] エラーマッピングの一致確認
- [ ] 全テストを実行 → 緑フェーズ確認 (すべて成功)
- [ ] 既存テスト 260+ も全て成功することを確認

### Refactor Phase (テスト整理)

- [ ] ヘルパー関数を実装 (create_mock_agent_response など)
- [ ] マジックナンバーを定数化
- [ ] テストの重複を削除
- [ ] docstring を追加
- [ ] コードをリーダブルに整理

### Verify Phase (最終確認)

- [ ] 全新規テストが成功 (test_migration_compat.py)
- [ ] 全統合テストが成功 (test_migration_integration.py)
- [ ] 全既存テストが成功 (test_bedrock.py, test_handler.py)
- [ ] カバレッジ 80%+ を達成
- [ ] ビルド成功 (make build)
- [ ] コードレビュー対応完了

---

## 10. 注意事項

### 1. テスト実行の順序
- 新規テストのみ実行: `pytest backend/tests/unit/test_migration_compat.py`
- 既存テスト + 新規テスト: `pytest backend/tests/`
- 統合テストは最後に実行

### 2. モックの管理
- StrandsAIService のモックでは Agent クラスをモック
- BedrockService のモックでは boto3 クライアントをモック
- 同期性を確認するため、両方で同じテストデータを使用

### 3. 環境変数の初期化
- テスト間での環境変数の汚染を防ぐため、`patch.dict(os.environ)` を使用
- テスト完了後に環境変数が復元されることを確認

### 4. 既存テスト保護
- TASK-0057 完了後も test_bedrock.py が全て PASS することを確認
- test_handler.py の POST /cards/generate テストが全て PASS することを確認
- カバレッジが 80% 以上を維持することを確認

### 5. API レスポンス形式
- GenerateCardsResponse は API レスポンス DTO (handler.py で使用)
- GenerationResult は サービス層の内部型 (ai_service.py で定義)
- API ハンドラーでの変換処理を確認

### 6. エラーハンドリングの対応
- StrandsAIService の例外が BedrockService と同じ hierarchy に従う
- _map_ai_error_to_http() で両方のサービスの例外を処理する
- エラーレスポンス形式が統一されていることを確認

---

## 11. 参考リソース

### 関連タスク
- [TASK-0053: AIService Protocol + 共通型定義](../../TASK-0053.md) - ai_service.py
- [TASK-0057: StrandsAIService 基本実装](../../TASK-0057.md) - strands_service.py
- [TASK-0055: BedrockAIService Protocol 準拠改修](../../TASK-0055.md) - bedrock.py
- [TASK-0056: handler.py AIServiceFactory 統合](../../TASK-0056.md) - handler.py, template.yaml

### 設計文書
- [requirements.md](../../../spec/ai-strands-migration/requirements.md) - REQ-SM-002, REQ-SM-402, REQ-SM-404/405
- [architecture.md](../../../design/ai-strands-migration/architecture.md) - 全体アーキテクチャ
- [api-endpoints.md](../../../design/ai-strands-migration/api-endpoints.md) - API 仕様
- [interfaces.py](../../../design/ai-strands-migration/interfaces.py) - インターフェース定義
- [dataflow.md](../../../design/ai-strands-migration/dataflow.md) - データフロー

### テスト関連
- [backend/tests/unit/test_bedrock.py](../../../../backend/tests/unit/test_bedrock.py) - 既存テスト
- [backend/tests/unit/test_handler.py](../../../../backend/tests/unit/test_handler.py) - 既存テスト
- [backend/tests/unit/test_strands_service.py](../../../../backend/tests/unit/test_strands_service.py) - TASK-0057 テスト

### プロジェクト基本
- [CLAUDE.md](../../../../CLAUDE.md) - 開発ガイドライン
- [overview.md](../../overview.md) - タスク概要

---

## 12. まとめ

このタスクは、**TDD アプローチで API 互換性を検証する重要なマイルストーン**です。

### 検証ポイント
1. **API レスポンス形式の完全一致** - GenerateCardsResponse が両方のサービスで同じ
2. **エラーハンドリングの統一** - HTTP ステータスコードが両方で同じ
3. **既存テスト保護** - 260+ テストが継続して成功
4. **フラグの動的切替** - USE_STRANDS で実装を切り替え可能

### 品質指標
- テストカバレッジ: 80%+
- テスト成功率: 100% (赤→緑→リファクタ→確認)
- 既存テスト互換性: 260+ テスト全て成功

このタスク完了後、**Phase 2 が完了**し、TASK-0063 の本番環境移行スクリプトへと進むことができます。
