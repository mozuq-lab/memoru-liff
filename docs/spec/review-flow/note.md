# review-flow コンテキストノート

**作成日**: 2026-02-25

## 技術スタック

### バックエンド
- Python 3.12 / AWS SAM (Lambda, API Gateway, DynamoDB)
- AWS Lambda Powertools
- Pydantic v2
- SM-2アルゴリズム実装済み (`backend/src/services/srs.py`)

### フロントエンド
- React + TypeScript
- Vite / React Router v6
- Tailwind CSS
- oidc-client-ts (Keycloak OIDC)

## 既存実装状況

### バックエンド（実装済み）
- `POST /reviews/{card_id}` - 復習結果記録 (grade 0-5)
  - ファイル: `backend/src/api/handler.py` (submit_review)
  - サービス: `backend/src/services/review_service.py`
  - SM-2計算: `backend/src/services/srs.py`
- `GET /cards/due` - 復習対象カード取得
  - レスポンス: due_cards, total_due_count, next_due_date

### フロントエンド（実装済み）
- API クライアント: `frontend/src/services/api.ts`
  - `reviewsApi.submitReview(cardId, grade)` → `POST /reviews/{cardId}`
  - `cardsApi.getDueCards()` → `GET /cards/due`
- CardsPage タブフィルタ: 「復習対象」/「すべて」タブ
- HomePage: 「復習を始める」ボタン（現在 `/cards?tab=due` に遷移）

### フロントエンド（未実装）
- ReviewPage（復習画面） - **今回の実装対象**
- フリップアニメーション
- 採点UI (0-5ボタン)
- 進捗バー
- 復習完了画面

## 関連ファイル

### バックエンド
- `backend/src/api/handler.py` - APIエンドポイント定義
- `backend/src/services/review_service.py` - 復習サービス
- `backend/src/services/srs.py` - SM-2アルゴリズム
- `backend/src/models/review.py` - レビューモデル

### フロントエンド
- `frontend/src/services/api.ts` - APIクライアント
- `frontend/src/pages/HomePage.tsx` - ホーム画面
- `frontend/src/pages/CardsPage.tsx` - カード一覧画面
- `frontend/src/contexts/CardsContext.tsx` - カードコンテキスト
- `frontend/src/components/Navigation.tsx` - ナビゲーションバー
- `frontend/src/types/card.ts` - カード型定義

## 注意事項

- バックエンドAPIは完成済み。フロントエンドの復習画面UIのみ新規実装
- SM-2アルゴリズムの採点は0-5の6段階（バックエンド側のバリデーション済み）
- ナビゲーションバーの「復習」アイコン追加は今回スコープ外
- LINE Webhook経由の復習（ストーリー5.1）は別機能。今回はLIFF内の復習画面
