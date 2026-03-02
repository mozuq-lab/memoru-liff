# 認証プロバイダ切り替え コンテキストノート

**作成日**: 2026-03-02

## 技術スタック（認証関連）

### バックエンド
- AWS SAM / API Gateway HTTP API / JWT Authorizer
- `backend/template.yaml` — SAM パラメータ `KeycloakIssuer` で issuer URL を設定
- `backend/src/api/shared.py` — `get_user_id_from_context()` で JWT `sub` クレームを抽出

### フロントエンド
- `oidc-client-ts` — 汎用 OIDC クライアントライブラリ（Keycloak 固有ではない）
- `frontend/src/config/oidc.ts` — OIDC authority URL を環境変数から構築
- `frontend/src/services/auth.ts` — `UserManager` のラッパー
- `frontend/src/hooks/useAuth.ts` — 認証状態管理フック
- `frontend/src/contexts/AuthContext.tsx` — React Context

### 現在の認証フロー
1. フロントエンド: `oidc-client-ts` → Keycloak (PKCE)
2. Keycloak: JWT 発行
3. フロントエンド: `Authorization: Bearer <JWT>` ヘッダー付与
4. API Gateway: JWT Authorizer で検証（issuer + audience チェック）
5. Lambda: `sub` クレームからユーザー ID 取得

## 重要な設計判断

- バックエンドは Keycloak に直接通信しない（API Gateway が JWT 検証を担当）
- `sub` クレームのみに依存（他の Keycloak 固有クレームは未使用）
- LINE 連携は `line_user_id` として別フィールドで管理（認証とは分離）
- `requirements.txt` に Keycloak/LINE 固有の SDK 依存なし

## 関連ファイル

- `backend/template.yaml` — JWT Authorizer 設定（L252-263）
- `backend/src/api/shared.py` — ユーザー ID 抽出ロジック
- `frontend/src/config/oidc.ts` — OIDC 接続設定
- `frontend/src/services/auth.ts` — 認証サービス
- `frontend/src/hooks/useAuth.ts` — 認証フック
- `frontend/src/contexts/AuthContext.tsx` — 認証 Context

## 注意事項

- プロバイダ切り替え時、`sub` の値がプロバイダ間で異なるためユーザーデータの移行が別途必要
- Cognito + LINE Login の統合方式は設計フェーズで決定予定
