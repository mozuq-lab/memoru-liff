# card-references コンテキストノート

**作成日**: 2026-03-05

## 技術スタック

### バックエンド
- Python 3.12 / AWS SAM (Lambda, API Gateway, DynamoDB)
- Pydantic v2 モデルバリデーション

### フロントエンド
- React 19 + TypeScript 5.x / Vite 7 / Tailwind CSS 4
- LIFF SDK / React Router v7

## 関連する既存実装

### データモデル
- **Card** (`backend/src/models/card.py`): `front`, `back`, `deck_id?`, `tags[]`, SRS フィールド
- **CreateCardRequest**: `front`, `back`, `deck_id?`, `tags[]`
- **UpdateCardRequest**: `front?`, `back?`, `deck_id?`, `tags?`, `interval?`
- **CardResponse**: Card の全フィールドを返却
- **Card (frontend)** (`frontend/src/types/card.ts`): バックエンドの CardResponse に対応する TypeScript 型

### カードサービス
- `backend/src/services/card_service.py` — `create_card`, `update_card`, `get_card` 等
- `create_card`: Card オブジェクトを生成し `to_dynamodb_item()` で DynamoDB に保存
- `update_card`: UpdateExpression を動的に構築して DynamoDB を更新
- `Card.from_dynamodb_item()`: DynamoDB アイテムから Card を復元（`tags` は `item.get("tags", [])` で後方互換）

### フロントエンド画面
- **CardForm** (`frontend/src/components/CardForm.tsx`): 表面・裏面の編集フォーム。新規作成・編集で共用
- **CardDetailPage** (`frontend/src/pages/CardDetailPage.tsx`): カード詳細・編集画面。表示モードと編集モードを切り替え
- **ReviewPage**: 復習画面。裏面表示時にカード情報を表示

### API
- `POST /cards` — カード作成
- `PUT /cards/{card_id}` — カード更新
- `GET /cards/{card_id}` — カード取得
- フロントエンド API サービス: `frontend/src/services/api.ts`

## 注意事項

- `references` は `tags` と同様のリスト型フィールドだが、各要素が `type` と `value` を持つオブジェクト型
- DynamoDB はスキーマレスのため、既存カードに `references` フィールドは存在しない。`from_dynamodb_item()` で `item.get("references", [])` とすることで後方互換を確保する（`tags` と同じパターン）
- 新規 API エンドポイントは不要。既存の CRUD API に references を含めるだけで実現可能
- CardForm は現在 `onSave(front, back)` のシグネチャで、references を扱うには拡張が必要
