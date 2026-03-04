# Cognito LINE Login 外部 IdP 統合 コンテキストノート

**作成日**: 2026-03-03

## 技術スタック（認証関連）

### インフラ（CDK）
- `infrastructure/cdk/lib/cognito-stack.ts` — Cognito UserPool + Client（LINE IdP 未設定）
- `infrastructure/cdk/bin/app.ts` — スタックインスタンス化（dev/prod）
- CDK v2 (`aws-cdk-lib ^2.240.0`)
- `aws-cdk-lib/aws-cognito` — `UserPoolIdentityProviderOidc` が LINE 登録に使用可能

### フロントエンド
- `oidc-client-ts` — 汎用 OIDC クライアント（Cognito Hosted UI 経由で動作）
- `frontend/src/config/oidc.ts` — OIDC authority/client_id を環境変数から取得（OIDC 汎用化済み）
- `frontend/src/services/liff.ts` — LIFF SDK ラッパー（`liff.init`, `getProfile`, `getIDToken`）
- `frontend/src/services/auth.ts` — `UserManager` ラッパー

### バックエンド
- `backend/template.yaml` — API Gateway JWT Authorizer（`OidcIssuer`/`OidcAudience` パラメータ化済み）
- `backend/src/api/shared.py` — JWT `sub` クレーム抽出（プロバイダ非依存）
- `backend/src/services/line_service.py` — LINE ID トークン検証 + Webhook 処理
- `backend/src/api/handlers/user_handler.py` — `/users/link-line` エンドポイント

## 現在の認証フロー

### OIDC 認証（API 認可用）
1. フロントエンド: `oidc-client-ts` → Keycloak/Cognito (PKCE)
2. IdP: JWT 発行
3. フロントエンド: `Authorization: Bearer <JWT>` ヘッダー付与
4. API Gateway: JWT Authorizer で検証
5. Lambda: `sub` クレームからユーザー ID 取得

### LINE 連携（現状: 手動リンク）
1. LIFF SDK: `liff.getIDToken()` で LINE ID トークン取得
2. フロントエンド: `POST /users/link-line` に ID トークン送信
3. バックエンド: LINE API で ID トークン検証 → `line_user_id` 取得
4. DynamoDB: `user_id`（OIDC sub）に `line_user_id` を紐付け

## 方式A のターゲットフロー

```
ユーザー → oidc-client-ts → Cognito Hosted UI → 「LINE でログイン」ボタン
  → LINE Login OIDC 認証 → Cognito がトークン取得
  → Cognito JWT 発行（sub = Cognito UUID）
  → API Gateway JWT Authorizer で検証
```

## 重要な設計判断

- OIDC 汎用化（TASK-0123〜0125）完了済み。プロバイダ固有のコードは排除済み
- Cognito Hosted UI 経由のリダイレクトを許容（カスタム UI は不要）
- メール+パスワード認証と LINE Login の両方を Hosted UI で提供
- LINE ユーザー ID の自動連携は本要件のスコープ外（後続タスクで対応）
- 既存の手動リンク機能（`/users/link-line`）はそのまま維持

## 関連ファイル

### 変更対象
- `infrastructure/cdk/lib/cognito-stack.ts` — LINE 外部 IdP 追加、Client 更新
- `infrastructure/cdk/bin/app.ts` — LINE Login チャネル情報の Props 追加

### 変更不要（確認済み）
- `frontend/src/config/oidc.ts` — OIDC 汎用化済み、Cognito Hosted UI と互換
- `frontend/src/services/auth.ts` — プロバイダ非依存
- `backend/template.yaml` — OidcIssuer/OidcAudience パラメータ化済み
- `backend/src/api/shared.py` — sub クレーム抽出のみ
- `backend/src/services/line_service.py` — 手動リンク機能は維持

## 注意事項

- LINE Login は標準の `.well-known/openid-configuration` を提供しない可能性がある → CDK で手動エンドポイント指定が必要
- Cognito が発行する `sub` は Cognito 独自の UUID であり、LINE の `sub`（`U` + 32文字）とは異なる
- LINE の属性（name, picture）は Cognito のカスタム属性にマッピング可能
- `cognitoDomainPrefix` はグローバル一意である必要がある
