# code-review-remediation コンテキストノート

**作成日**: 2026-02-15
**元レビュー**: [CODE_REVIEW_2026-02-15.md](../../CODE_REVIEW_2026-02-15.md)

## 概要

2026-02-15 実施の全体コードレビュー（Claude Opus 4.6 × 3 + OpenAI Codex）で検出された Critical/High レベルの問題 19 件を修正するための要件定義。

## 対象スコープ

- **Critical**: 7 件（本番デプロイ前に即座対応）
- **High**: 12 件（早急に対応）
- **Medium/Low/Info**: 対象外（別途対応）

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

## 主要な修正カテゴリ

### 1. API 契約の整合性 (C-01, C-02)
- Backend のルート定義と SAM テンプレートのパスが不一致
- Backend レスポンスモデルと Frontend 型定義が不一致
- 手動統一アプローチ（OpenAPI スキーマは使用しない）

### 2. 認証フローの完成 (C-03, C-07, H-08, H-09)
- OIDC コールバック未実装
- 環境変数バリデーション未呼び出し
- トークンリフレッシュ未実装
- ProtectedRoute の無限ループリスク

### 3. セキュリティ修正 (C-06, H-02, H-03)
- LINE 署名検証のタイミング攻撃対策
- CSP の unsafe-inline/unsafe-eval 除去
- Keycloak HTTPS 強制

### 4. IAM/権限修正 (C-04)
- DuePush Lambda の Users テーブル書き込み権限不足

### 5. API クライアント修正 (C-05)
- 204 No Content レスポンスの JSON パースエラー

### 6. データ整合性 (H-01, H-05, H-06)
- datetime naive/aware 混在の統一
- 通知スケジュール cron 式の修正
- カード数制限の Race Condition 対策

### 7. パフォーマンス/UX (H-07, H-10)
- Bedrock リトライのジッター追加
- Context API メモ化

### 8. インフラ最適化 (H-04, H-11, H-12)
- LINE 連携解除エンドポイント追加
- NAT Gateway コスト最適化
- CloudWatch Logs 保存期間設定

## 関連ファイル

### Backend
- `backend/src/api/handler.py` - API ルート定義
- `backend/src/services/line_service.py` - LINE 署名検証
- `backend/src/services/card_service.py` - カード管理
- `backend/src/services/srs.py` - SRS アルゴリズム
- `backend/src/services/bedrock.py` - Bedrock クライアント
- `backend/src/services/notification_service.py` - 通知サービス
- `backend/src/services/user_service.py` - ユーザー管理
- `backend/src/models/card.py` - Card モデル
- `backend/src/models/user.py` - User モデル
- `backend/template.yaml` - SAM テンプレート

### Frontend
- `frontend/src/pages/CallbackPage.tsx` - OIDC コールバック
- `frontend/src/services/api.ts` - API クライアント
- `frontend/src/services/auth.ts` - 認証サービス
- `frontend/src/config/oidc.ts` - OIDC 設定
- `frontend/src/main.tsx` - アプリエントリ
- `frontend/src/components/common/ProtectedRoute.tsx` - 認証ガード
- `frontend/src/contexts/CardsContext.tsx` - カード Context
- `frontend/src/contexts/AuthContext.tsx` - 認証 Context
- `frontend/src/types/card.ts` - Card 型
- `frontend/src/types/user.ts` - User 型

### Infrastructure
- `infrastructure/liff-hosting/template.yaml` - CloudFront CSP
- `infrastructure/keycloak/template.yaml` - Keycloak 構成

## テスト方針

- 既存テストの更新 + 回帰テスト確認
- 新規テストの追加（修正箇所ごと）
- E2E テストの skip 解除は対象外

## Phase 構成

- **Phase 1**: Critical 7 件（1 週間以内）
- **Phase 2**: High 12 件（2 週間以内）

## 注意事項

- API 契約の統一は手動で実施（OpenAPI スキーマ自動生成は導入しない）
- インフラ変更（IAM, CSP, Keycloak, NAT Gateway, CloudWatch）を含む
- AWS リソースの実際のデプロイはユーザーが手動で実施
