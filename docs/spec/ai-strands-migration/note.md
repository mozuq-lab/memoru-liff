# AI Strands Migration 開発コンテキストノート

## 作成日時
2026-02-23

## プロジェクト概要

### プロジェクト名
Memoru LIFF (AI Strands Migration Phase)

### プロジェクトの目的
現在、Amazon Bedrock boto3クライアントを使用した直接的なAIカード生成機能を、AWS Strands Agents SDKを使用した実装へ移行する。

Strands AgentsはAWSの次世代型エージェントフレームワークで、マルチステップの複雑なAI推論タスクをサポートし、より高度な機能（思考チェーン、ツール呼び出し、複合推論）を提供する。

**参照元**: CLAUDE.md

## 技術スタック

### 使用技術・フレームワーク
- **言語**: Python 3.12
- **フレームワーク**: AWS SAM (Serverless Application Model)
- **ランタイム**: AWS Lambda
- **パッケージマネージャー**: pip
- **現在のAI連携**: Amazon Bedrock (boto3を使用した直接呼び出し)
- **移行先**: AWS Strands Agents SDK

### アーキテクチャパターン
- **アーキテクチャスタイル**: サーバーレスアーキテクチャ
- **設計パターン**:
  - 単層モノリシック（単一Lambda関数で複数エンドポイント）
  - サービスレイヤーパターン（ビジネスロジック分離）
- **ディレクトリ構成**: AWS SAM標準構成
  - `backend/src/api/` - REST API ハンドラー
  - `backend/src/services/` - ビジネスロジック（Bedrockサービス含む）
  - `backend/src/models/` - Pydantic データモデル
  - `backend/tests/unit/` - ユニットテスト

**参照元**: CLAUDE.md, template.yaml

## 開発ルール

### プロジェクト固有のルール
1. **タスク駆動型開発**: Tsumiki Kairo ワークフローを使用
   - タスクファイルは `docs/tasks/ai-strands-migration/TASK-XXXX.md` に管理
   - 要件定義は `docs/spec/ai-strands-migration/` に保存
   - 設計文書は `docs/design/ai-strands-migration/` に保存

2. **テスト要件（CLAUDE.md）**:
   - テストカバレッジ 80% 以上を目標とする
   - ユニットテスト（pytest）を主体とする

3. **デプロイメント**: AWS SAM を使用した Infrastructure as Code

### コーディング規約
- **命名規則**: Python PEP 8 準拠（snake_case）
- **型チェック**: Pydantic v2 を使用した型安全性の確保
- **コメント**: Google スタイルのドキュメントストリング

### テスト要件
- **テストフレームワーク**: pytest
- **カバレッジ要件**: 80% 以上
- **テストパターン**: ユニットテスト、モックを使用した外部API呼び出しのテスト

**参照元**: CLAUDE.md, requirements-dev.txt

## 既存の要件定義

### 現在の実装（状況分析）

#### 既存AI カード生成機能の概要
**ファイル**: `backend/src/services/bedrock.py`

現在の実装は以下の特徴を持つ：

1. **BedrockService クラス**:
   - `anthropic.claude-3-haiku-20240307-v1:0` をデフォルトモデルとして使用
   - 環境変数 `BEDROCK_MODEL_ID` でモデル指定可能
   - boto3クライアントを使用した直接的なAWS Bedrock API呼び出し

2. **主要メソッド**:
   - `generate_cards()`: テキストからフラッシュカードを生成（5〜10枚）
   - `_invoke_with_retry()`: リトライロジック（最大2回）
   - `_invoke_claude()`: Bedrock API 直接呼び出し
   - `_parse_response()`: JSON レスポンス解析
   - `_retry_with_jitter()`: Full Jitter指数バックオフ（30秒キャップ）

3. **エラーハンドリング**:
   - `BedrockTimeoutError`: API タイムアウト（リトライなし）
   - `BedrockRateLimitError`: レート制限（リトライあり）
   - `BedrockInternalError`: サーバーエラー（リトライあり）
   - `BedrockParseError`: レスポンス解析エラー

4. **プロンプト管理**:
   - ファイル: `backend/src/services/prompts.py`
   - 言語対応: 日本語（ja）、英語（en）
   - 難易度レベル: easy、medium、hard
   - プロンプトは各言語・難易度で最適化

5. **API統合**:
   - エンドポイント: `POST /cards/generate`
   - ハンドラー: `backend/src/api/handler.py`
   - 認証: Keycloak JWT（API Gateway Authorizer）

#### テスト状況
**ファイル**: `backend/tests/unit/test_bedrock.py`

- テストクラス数: 6クラス
- テストメソッド数: 20+ メソッド
- カバレッジ対象:
  - プロンプト生成
  - レスポンス解析（JSON、タグ、バリデーション）
  - API呼び出し（成功、タイムアウト、レート制限、内部エラー）
  - リトライロジック（フェイルフレンドリー、回数検証）
  - Full Jitterアルゴリズム

### 移行要件（推論）

#### Strands Agents SDKへの移行
以下の点を検討する必要がある：

1. **SDK導入**:
   - AWS Strands Agents SDK のインストール
   - Bedrock モデルサポート確認（Claude 3 Haiku対応）

2. **実装パターンの変更**:
   - `AgentAction` / `AgentStep` などの新しいAPI パターン適用
   - ツール呼び出し（Tool Use）の実装検討
   - 思考チェーン（Chain of Thought）の活用検討

3. **後方互換性**:
   - 既存の `generate_cards()` メソッドインターフェース維持
   - API レスポンス形式の維持（GenerationResult型）
   - エラーハンドリングの整合性

4. **パフォーマンス考慮**:
   - Strands Agents のレイテンシー（現在：30秒以内）
   - リトライロジックの再評価

## 既存の設計文書

### アーキテクチャ設計
**ファイル**: `docs/design/memoru-liff/architecture.md`

#### AI連携コンポーネント
- **サービス**: Amazon Bedrock
- **用途**: AIカード生成、（将来）回答採点
- **モデル**: Claude 3 Haiku（デフォルト）、カスタマイズ可能
- **統合レベル**: Lambda関数内での直接呼び出し

#### Lambda 関数構成
- **api-main** 関数が `generate_cards` エンドポイントを処理
- IAM ポリシー: `bedrock:InvokeModel` 権限付与
- タイムアウト設定: 30秒（グローバル）

### データフロー
**ファイル**: `docs/design/memoru-liff/dataflow.md`

カード生成フロー：
1. フロントエンド → POST /cards/generate（テキスト、難易度、言語）
2. API Lambda → BedrockService.generate_cards()
3. BedrockService → Bedrock API （JSON形式でプロンプト送信）
4. Bedrock → JSON形式で複数カードを返却
5. BedrockService → 解析・バリデーション
6. API Lambda → JSON レスポンス（カード配列）
7. フロントエンド → DynamoDB に保存

### API仕様
**ファイル**: `docs/design/memoru-liff/api-endpoints.md`

```
POST /cards/generate
- リクエスト: { text, card_count, difficulty, language }
- レスポンス: { cards: [...], model_used, processing_time_ms }
- 認証: JWT (Keycloak)
- エラー: 400, 500, 503
```

## 関連実装

### 現在のコード構成

#### BedrockService の主要コンポーネント
**ファイル**: `backend/src/services/bedrock.py` (332行)

```python
# 主要クラス
class GeneratedCard:
    """生成されたフラッシュカード（Pydantic dataclass）"""
    front: str      # 問題文
    back: str       # 解答
    suggested_tags: List[str]  # 推奨タグ

class GenerationResult:
    """カード生成結果メタデータ"""
    cards: List[GeneratedCard]
    input_length: int
    model_used: str
    processing_time_ms: int

class BedrockService:
    """Bedrockインテグレーション（boto3ベース）"""
    # タイムアウト: 30秒
    # リトライ: 最大2回（レート制限、内部エラーのみ）
    # 指数バックオフ: Full Jitter方式
```

#### API ハンドラー統合
**ファイル**: `backend/src/api/handler.py`

- `from services.bedrock import BedrockService`
- エンドポイント `POST /cards/generate` 処理
- エラーハンドリング: ビジネスロジックエラーを HTTP ステータスにマッピング

#### プロンプト管理
**ファイル**: `backend/src/services/prompts.py` (96行)

- 言語別・難易度別テンプレート
- JSON 出力形式の強制

#### テスト構成
**ファイル**: `backend/tests/unit/test_bedrock.py` (337行)

6つのテストクラス：
1. `TestPrompts` - プロンプト生成テスト
2. `TestBedrockServiceParsing` - JSON 解析テスト
3. `TestBedrockServiceInvoke` - API 呼び出しテスト
4. `TestBedrockServiceRetry` - リトライロジック
5. `TestBedrockServiceJitter` - Full Jitter アルゴリズム
6. `TestGenerateCardsValidation` - 入力検証

### 使用可能な共通モジュール・ユーティリティ

#### 認証・認可
- **Keycloak OIDC**: API Gateway Authorizer での JWT検証
- ユーザー特定: JWT トークンから `sub` クレーム取得

#### DynamoDB アクセス
- **Cards Table**: ユーザー別カード管理
- **Reviews Table**: 復習履歴管理
- Pydantic モデルとの連携（シリアライズ）

#### ロギング・トレーシング
- **AWS Lambda Powertools**: 構造化ロギング、トレーシング機能
- 環境変数 `LOG_LEVEL`: DEBUG/INFO（環境別切り替え）

#### エラーハンドリング
- 標準的なカスタム例外クラス群（BedrockServiceError のパターンを参照）

**参照元**:
- `backend/src/services/bedrock.py`
- `backend/src/services/prompts.py`
- `backend/tests/unit/test_bedrock.py`
- `backend/template.yaml` (Lines 43-46, 250-253)

## 技術的制約

### パフォーマンス制約
- **Bedrock API タイムアウト**: 30秒以内（Lambda Timeout と同じ）
- **Lambda実行時間**: API = 30秒、Due Push Job = 300秒
- **DynamoDB**: 1アイテム最大 400KB
- **APIレスポンス目標**: 95%ile 3秒以内（非生成エンドポイント）

### セキュリティ制約
- **認証**: すべてのAPI呼び出しに JWT認証必須（LINE Webhook除く）
- **認可**: ユーザーは自分のカードのみアクセス可能
- **シークレット管理**: Secrets Manager を使用（LINE Channel Secret）
- **Bedrock IAM**: `bedrock:InvokeModel` 権限は Lambda実行ロールに付与

### 互換性制約
- **Python**: 3.12 ランタイム
- **Pydantic**: v2 （型安全性の確保）
- **boto3**: >=1.34.0

### データ制約
- **プロンプト最大長**: Bedrock Claude の Context Window（Haiku: 200K トークン）
- **生成カード数**: 1〜10 枚（ユーザー要求値でバリデーション）

**参照元**: CLAUDE.md, template.yaml, architecture.md

## 注意事項

### 開発時の注意点
1. **Strands Agents SDK 安定性**: 初期段階のSDKであれば、破壊的変更の可能性あり
2. **Bedrock モデルサポート確認**: Claude 3 Haiku がStrands Agents で完全サポートされているか確認
3. **後方互換性**: 既存テストを保持し、移行中も機能を提供すること

### デプロイ・運用時の注意点
1. **段階的移行**: 新実装をフィーチャーフラグで制御し、段階的にロールアウト
2. **メトリクス監視**: Strands Agents のレイテンシー、エラー率を CloudWatch で監視
3. **フォールバック**: Strands Agents 失敗時の代替手段を検討

### セキュリティ上の注意点
1. **IAM ポリシー**: `bedrock:InvokeModel` アクセスは Lambda実行ロールのみ
2. **プロンプトインジェクション対策**: ユーザー入力のバリデーション・エスケープ
3. **レスポンス検証**: Strands Agents からの出力を必ず検証

### パフォーマンス上の注意点
1. **タイムアウト設定**: Strands Agents は複雑な推論を行うため、レイテンシー増加の可能性
2. **リトライ戦略の再評価**: エージェント特有の失敗モードに対応
3. **キャッシング検討**: 同じプロンプトへの重複呼び出しを減らす工夫

## Git情報

### 現在のブランチ
HEAD (main ブランチ)

### 最近のコミット
```
73a4b3f TASK-0051: ローカル環境 E2E 動作確認
bae8c11 TASK-0050: DynamoDB Local SigV4 問題解決
9300781 TASK-0049: JWT フォールバック テスト検証
d375beb TASK-0048: ローカル開発環境 基盤構築
4fe30f7 TASK-0047: 設定整合性統一（環境変数名・OIDCクライアントID）
```

### 開発状況
- main ブランチ: 安定版（code-review-fixes-v2 完了）
- 次フェーズ: AI Strands Migration 準備中
- ローカル開発環境: 構築完了、E2E テスト確認済み

## 収集したファイル一覧

### プロジェクト基本情報
- [CLAUDE.md](../../../CLAUDE.md)
- [backend/template.yaml](../../../backend/template.yaml)
- [backend/requirements.txt](../../../backend/requirements.txt)

### 既存実装（AI関連）
- [backend/src/services/bedrock.py](../../../backend/src/services/bedrock.py) - BedrockService 実装 (332行)
- [backend/src/services/prompts.py](../../../backend/src/services/prompts.py) - プロンプトテンプレート (96行)
- [backend/src/api/handler.py](../../../backend/src/api/handler.py) - API ハンドラー（bedrock 統合）
- [backend/tests/unit/test_bedrock.py](../../../backend/tests/unit/test_bedrock.py) - テストスイート (337行)

### 設計文書
- [docs/design/memoru-liff/architecture.md](../../../docs/design/memoru-liff/architecture.md)
- [docs/design/memoru-liff/dataflow.md](../../../docs/design/memoru-liff/dataflow.md)
- [docs/design/memoru-liff/api-endpoints.md](../../../docs/design/memoru-liff/api-endpoints.md)

### 要件定義（初期実装）
- [docs/spec/memoru-liff/requirements.md](../../../docs/spec/memoru-liff/requirements.md)

---

## まとめ

このタスクノートは AI Strands Migration の開発背景を整理したものである。

**現在の状況**:
- BedrockService は boto3 を使用した直接的な Bedrock API呼び出しで実装済み
- テストカバレッジ 80% 以上で堅牢性を確保
- Full Jitter 指数バックオフでレート制限に対応

**移行の目的**:
- AWS Strands Agents SDK を活用した、より高度なAI推論機能への拡張準備
- エージェント機能（ツール呼び出し、複合推論）への道を開く
- 長期的なAI機能の進化に対応

**開発のポイント**:
- 既存の `generate_cards()` インターフェース互換性を維持
- テストスイートの継続性確保
- 段階的な移行と堅牢なフォールバック

**注意**: すべてのファイルパスはプロジェクトルートからの相対パスで記載しています。
