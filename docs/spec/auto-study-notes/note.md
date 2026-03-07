# Auto Study Notes コンテキストノート

**作成日**: 2026-03-07

## 技術スタック

### バックエンド
- Python 3.12 / AWS SAM (Lambda, API Gateway, DynamoDB)
- AWS Lambda Powertools / Pydantic v2
- Strands Agents SDK / Amazon Bedrock (Claude)
- AIService Protocol + Factory パターン（BedrockAIService / StrandsAIService）

### フロントエンド
- React 19 + TypeScript 5.x / Vite 7 / Tailwind CSS 4
- LIFF SDK / oidc-client-ts / React Router v7

### AI サービス
- `backend/src/services/ai_service.py`: AIService Protocol + Factory
- `backend/src/services/strands_service.py`: StrandsAIService 実装
- `backend/src/services/bedrock.py`: BedrockAIService 実装
- `backend/src/services/prompts/`: プロンプトモジュール群
- フィーチャーフラグ `USE_STRANDS` で新旧切り替え
- ローカル開発: Ollama プロバイダー

## 関連既存実装

### データモデル
- **cards テーブル**: PK=user_id, SK=card_id, front, back, deck_id, tags, created_at, updated_at
- **reviews テーブル**: PK=user_id, SK=card_id, due, interval, ease_factor, repetitions, last_reviewed_at
- **decks**: deck_id, name, description（deck_service.py で管理）
- カード上限: 2,000枚/ユーザー
- カードにはタグ（最大10個）とデッキIDが付与可能

### 既存 AI 機能
- カード生成（テキスト → フラッシュカード）
- URL からのカード生成
- 回答採点 / 学習アドバイス（Strands 移行後）

### API
- REST API（APIGatewayHttpResolver）
- JWT 認証（Keycloak OIDC）
- AI 生成 API: 10リクエスト/分のレート制限
- Lambda タイムアウト: 60秒

## 開発ルール
- タスクごとにコミット
- テストカバレッジ 80% 以上
- AWS リソースのデプロイはユーザーが手動実行

## 注意事項
- Bedrock のトークンコスト管理が重要
- キャッシュ戦略でコスト最適化が必要
- 既存の AIService Protocol に新メソッドを追加する形で統合
