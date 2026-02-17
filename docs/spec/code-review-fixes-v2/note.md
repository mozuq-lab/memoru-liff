# code-review-fixes-v2 コンテキストノート

**作成日**: 2026-02-17
**元レビュー**: [CODE_REVIEW_2026-02-16.md](../../CODE_REVIEW_2026-02-16.md)
**前回修正**: [code-review-remediation](../code-review-remediation/requirements.md)

## 概要

2026-02-16 実施の第2回全体コードレビュー（Claude Opus 4.6 + OpenAI Codex MCP経由）で検出された Critical 2件 + High 6件 = 計8件を修正するための要件定義。第1回レビュー修正（TASK-0023〜0041）は全完了済みだが、API契約不一致（CR-01）とレスポンス契約不一致（H-02）が再指摘されたほか、新規6件が検出された。

## 対象スコープ

- **Critical (P0)**: 2件（CR-01, CR-02）
- **High (P1)**: 6件（H-01〜H-06）
- **Medium/Low**: 対象外（付録として記載）

## 前回修正との関係

| 第2回ID | 第1回対応 | 状況 |
|---------|----------|------|
| CR-01 | TASK-0023 (C-01) | 再指摘: SAM/handler/frontend の3レイヤー不一致が残存 |
| H-02 | TASK-0024 (C-02) | 再指摘: レスポンス形式不一致 + unlink API未使用 |
| CR-02 | なし | 新規: card_count トランザクション整合性 |
| H-01 | なし | 新規: LINE連携本人性検証 |
| H-03 | なし | 新規: 通知時刻/タイムゾーン判定 |
| H-04 | なし | 新規: 環境変数名不一致 |
| H-05 | なし | 新規: requests依存未宣言 |
| H-06 | なし | 新規: OIDCクライアントID設定ドリフト |

## 技術スタック

### バックエンド
- **Python 3.12** + AWS SAM (Lambda, API Gateway, DynamoDB)
- **AWS Lambda Powertools** (Logger, Tracer, Event Handler)
- **Pydantic v2** データバリデーション

### フロントエンド
- **React + TypeScript** + Vite
- **LIFF SDK** + **oidc-client-ts**

### 認証
- **Keycloak** (ECS/Fargate) + OIDC + PKCE

### インフラ
- **CloudFormation** (SAM/CloudFront/Keycloak)
- **DynamoDB**, **CloudFront + S3**, **API Gateway**

## ヒアリング決定事項

1. **APIルート統一方針**: 設計文書（api-endpoints.md）の定義を正とする
2. **LINE連携検証**: LIFF IDトークンをサーバー側で検証する方式
3. **HTTPライブラリ**: httpx に統一（requests を置換）
4. **OIDCクライアントID**: `liff-client` に統一
5. **環境変数名**: `VITE_API_BASE_URL` に統一
6. **Medium/Low**: 付録として記載、別途対応

## 主要な修正カテゴリ

### 1. API契約の整合性 (CR-01, H-02)
- 設定更新: SAM `PUT /users/me` → `PUT /users/me/settings` に修正
- レビュー送信: SAM `POST /reviews` → `POST /reviews/{cardId}` に修正
- LINE連携: SAM に `POST /users/link-line` を追加、frontend パスを修正
- レスポンスDTO統一、unlinkLine API使用

### 2. データ整合性 (CR-02)
- card_count: `if_not_exists` で安全な加算
- TransactionCanceledException の正確なエラー分類
- delete_card での card_count 減算
- カード作成前の get_or_create_user

### 3. セキュリティ (H-01)
- LIFF IDトークンのサーバー側検証
- LINE IDトークン検証API連携

### 4. 通知機能 (H-03)
- ユーザーごとのタイムゾーン対応
- notification_time との一致判定

### 5. 設定整合性 (H-04, H-05, H-06)
- 環境変数名 `VITE_API_BASE_URL` 統一
- httpx 統一（requests 除去）
- OIDC クライアントID `liff-client` 統一

## 関連ファイル

### Backend
- `backend/template.yaml` - SAM テンプレート（API イベント定義）
- `backend/src/api/handler.py` - API ルート定義
- `backend/src/services/card_service.py` - カード管理（card_count トランザクション）
- `backend/src/services/line_service.py` - LINE サービス（requests → httpx）
- `backend/src/services/notification_service.py` - 通知サービス（時刻判定）
- `backend/src/services/user_service.py` - ユーザー管理
- `backend/src/services/review_service.py` - レビューサービス
- `backend/requirements.txt` - Python 依存関係

### Frontend
- `frontend/src/services/api.ts` - API クライアント
- `frontend/src/pages/LinkLinePage.tsx` - LINE 連携ページ
- `frontend/src/types/user.ts` - User 型定義

### Infrastructure
- `infrastructure/keycloak/realm-export.json` - Keycloak 設定（client_id）

### CI/CD
- `.github/workflows/deploy.yml` - デプロイワークフロー（環境変数、client_id）
- `frontend/e2e/fixtures/auth.fixture.ts` - E2E テスト（client_id）

## テスト方針

- 既存テストの更新 + 回帰テスト確認
- 新規テストの追加（修正箇所ごと）
- API 契約テスト（3レイヤー整合性検証）の検討

## 注意事項

- API 契約の統一は設計文書（api-endpoints.md）を単一ソースとする
- AWS リソースの実際のデプロイはユーザーが手動で実施
- LINE IDトークン検証には LINE Login API のエンドポイント利用が必要
