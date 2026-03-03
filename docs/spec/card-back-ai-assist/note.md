# card-back-ai-assist コンテキストノート

**作成日**: 2026-03-03

## 技術スタック

### バックエンド
- Python 3.12 / AWS SAM (Lambda, API Gateway, DynamoDB)
- Strands Agents SDK / Amazon Bedrock (Claude Haiku 4.5)
- 既存 AI サービス: `StrandsAIService`（カード生成）、`BedrockService`（フォールバック）

### フロントエンド
- React 19 + TypeScript 5.x / Vite 7 / Tailwind CSS 4
- LIFF SDK / React Router v7

## 関連する既存実装

### カード作成フロー
- **手動作成**: `CardForm` コンポーネント（`frontend/src/components/CardForm.tsx`）
  - 表面・裏面の textarea、保存・キャンセルボタン
- **AI 生成**: `GeneratePage`（`frontend/src/pages/GeneratePage.tsx`）
  - テキスト入力 → AI が表裏両方を自動生成 → 編集・選択して保存

### データモデル
- **Card**: `front`（1-1000 文字）、`back`（1-2000 文字）、`tags`、SRS フィールド
- **CreateCardRequest**: `front`, `back`, `deck_id?`, `tags[]`
- **GenerateCardsRequest**: `input_text`, `card_count`, `difficulty`, `language`

### AI サービス
- `backend/src/services/ai_service.py` — `AIService` Protocol
- `backend/src/services/strands_service.py` — Strands Agent 実装
- `backend/src/services/prompts/generate.py` — プロンプト定義
- モデル: `claude-haiku-4-5-20251001-v1:0`

### API エンドポイント
- `POST /cards` — カード作成
- `POST /cards/generate` — AI カード生成
- `PUT /cards/{card_id}` — カード更新
- ハンドラー: `backend/src/api/ai_handler.py`

## 注意事項

- 既存の `AIService` Protocol に新メソッドを追加する形が自然
- `CardForm` は新規作成と編集の両方で使用されている
- AI 呼び出しは非同期で、タイムアウトは 30 秒
- エラーハンドリング: `AITimeoutError`, `AIRateLimitError`, `AIParseError`, `AIProviderError`
