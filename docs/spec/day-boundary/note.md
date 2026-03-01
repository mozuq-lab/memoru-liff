# day-boundary コンテキストノート

**作成日**: 2026-03-01

## 技術スタック

- **バックエンド**: Python 3.12 / AWS SAM (Lambda, API Gateway, DynamoDB)
- **フロントエンド**: React 19 + TypeScript 5.x / Vite 7 / Tailwind CSS 4
- **認証**: Keycloak (OIDC + PKCE)
- **SRS**: SM-2 アルゴリズム

## 関連ファイル

### バックエンド
| ファイル | 役割 |
|---------|------|
| `backend/src/services/srs.py` | SM-2 アルゴリズム。`calculate_sm2()` で `next_review_at = now + timedelta(days=interval)` を計算 |
| `backend/src/services/review_service.py` | レビューサービス。`submit_review()` → `calculate_sm2()` → カード更新 |
| `backend/src/services/card_service.py` | カードサービス。`get_due_cards()` で `next_review_at <= now` クエリ。`update_card()` で interval 更新時に `next_review_at` 再計算 |
| `backend/src/services/deck_service.py` | デッキサービス。`_get_deck_due_counts()` で due カウント計算 |
| `backend/src/models/user.py` | ユーザーモデル。`settings` dict に `notification_time`, `timezone` を格納 |
| `backend/src/services/user_service.py` | ユーザーサービス。`update_settings()` で設定更新 |
| `backend/src/api/handlers/review_handler.py` | レビュー API ハンドラー |
| `backend/src/api/handlers/cards_handler.py` | カード API ハンドラー（UserService インポート済み） |
| `backend/src/api/handlers/user_handler.py` | ユーザー API ハンドラー |

### フロントエンド
| ファイル | 役割 |
|---------|------|
| `frontend/src/types/user.ts` | User, UpdateUserRequest 型定義 |
| `frontend/src/pages/SettingsPage.tsx` | 設定ページ（通知時間設定あり） |
| `frontend/src/services/api.ts` | API サービス（updateUser, getDueCards） |

## 現在の問題

`next_review_at` がフル datetime (時分秒含む) で保存・比較されるため、復習した時刻より早くアプリを開くと当日分のカードが表示されない。

## 既存パターン

- ユーザー設定は `User.settings` dict に格納（DynamoDB の Map 型）
- `UserSettingsRequest` で Pydantic バリデーション
- `user_service.update_settings()` で DynamoDB 更新
- 設定ページは radio ボタン形式の選択 UI
- 通知サービスで `zoneinfo.ZoneInfo` によるタイムゾーン変換パターンあり

## 注意事項

- クエリロジック (`next_review_at <= now`) は変更不要（書き込み時正規化で対応）
- 新規カード作成時の `next_review_at = now` は変更不要（即座に復習可能）
- 既存データのマイグレーション不要（次回復習時に自然正規化）
