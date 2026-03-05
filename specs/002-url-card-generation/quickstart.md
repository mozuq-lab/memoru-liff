# Quickstart: URL からカード自動生成

**Branch**: `002-url-card-generation` | **Date**: 2026-03-05

## 前提条件

### AWS 設定
- Amazon Bedrock の Claude Haiku 4.5 モデルアクセスが有効化済み
- AgentCore Browser が利用可能なリージョン（ap-northeast-1 推奨）
- IAM ロールに `bedrock-agentcore:*` 権限を追加済み

### ローカル開発環境
- Python 3.12+
- Node.js 20+
- Docker（DynamoDB Local, Keycloak 用）

## セットアップ

### 1. 依存関係の追加

**バックエンド**:

```bash
cd backend
pip install bedrock-agentcore strands-agents-tools beautifulsoup4 markdownify
```

`requirements.txt` に追加:
```
bedrock-agentcore>=1.0.0
strands-agents-tools>=0.3.0
beautifulsoup4>=4.12.0
markdownify>=0.13.0
```

**フロントエンド**:
追加パッケージなし（既存の API クライアントを拡張）

### 2. 環境変数

`backend/template.yaml` の Lambda 環境変数に追加:

```yaml
AGENTCORE_BROWSER_REGION: ap-northeast-1
AGENTCORE_BROWSER_TIMEOUT: "60"
URL_GENERATE_MAX_CONTENT_LENGTH: "50000"
```

### 3. ローカル開発での AgentCore Browser

ローカル開発では AgentCore Browser は利用不可（AWS マネージドサービスのため）。
代替として:

1. **HTTP fetch のみモード**: `AGENTCORE_BROWSER_ENABLED=false` で Browser 呼び出しをスキップ
2. **モックモード**: テスト用に固定 HTML レスポンスを返すモックサービスを使用

```bash
# ローカル開発時
export AGENTCORE_BROWSER_ENABLED=false

# テスト時
export AGENTCORE_BROWSER_ENABLED=mock
```

## 実装の流れ

### Phase 1: バックエンドコア

1. **URL バリデーション** (`backend/src/utils/url_validator.py`)
   - https スキーム検証
   - プライベート IP ブロック（SSRF 防止）
   - URL 長さ制限

2. **コンテンツ取得サービス** (`backend/src/services/url_content_service.py`)
   - HTTP fetch（静的ページ用）
   - SPA 判定ロジック
   - AgentCore Browser 呼び出し（SPA ページ用）
   - HTML → テキスト変換（BeautifulSoup + markdownify）

3. **チャンク分割** (`backend/src/services/content_chunker.py`)
   - 見出しベースのセクション分割
   - 3,000 文字以下のチャンク生成
   - コンテキスト情報の付与

4. **URL 生成プロンプト** (`backend/src/services/prompts/url_generate.py`)
   - 既存の `generate.py` をベースに URL コンテンツ向けに拡張
   - カードタイプ別のプロンプト分岐

5. **API エンドポイント** (`backend/src/api/handlers/ai_handler.py`)
   - `POST /cards/generate-from-url` ハンドラー
   - Pydantic モデルによるバリデーション

### Phase 2: フロントエンド

6. **URL 入力コンポーネント** (`frontend/src/components/UrlInput.tsx`)
   - URL 入力フォーム + バリデーション表示

7. **生成オプション** (`frontend/src/components/GenerateOptions.tsx`)
   - カードタイプ選択（Q&A / 用語定義 / 穴埋め）
   - 枚数目安スライダー

8. **プログレス表示** (`frontend/src/components/GenerateProgress.tsx`)
   - 3 段階プログレスバー

9. **GeneratePage 拡張** (`frontend/src/pages/GeneratePage.tsx`)
   - テキスト/URL タブ切替
   - URL 生成フロー統合

### Phase 3: インフラ・テスト

10. **SAM テンプレート更新** (`backend/template.yaml`)
    - UrlGenerateFunction 定義
    - IAM ポリシー追加

11. **テスト作成**
    - ユニットテスト: URL バリデーション、SPA 判定、チャンク分割
    - インテグレーションテスト: API エンドポイント（モック AI）
    - フロントエンドテスト: コンポーネントテスト

## 動作確認

### バックエンド API テスト

```bash
# ローカル API 起動
cd backend
make local-api

# URL 生成テスト（HTTP fetch モード）
curl -X POST http://localhost:8080/cards/generate-from-url \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Functions",
    "card_type": "qa",
    "target_count": 5,
    "language": "ja"
  }'
```

### フロントエンド開発

```bash
cd frontend
npm run dev
# http://localhost:3000 → ナビゲーション → 「カード生成」→ 「URL から生成」タブ
```

## 注意事項

- AgentCore Browser の利用にはコストが発生する（秒単位課金）
- ローカル開発では HTTP fetch モードまたはモックモードを使用
- SSRF 防止のため、内部ネットワークへのアクセスはブロックされる
- 著作権に配慮し、個人学習目的での利用に限定すること
