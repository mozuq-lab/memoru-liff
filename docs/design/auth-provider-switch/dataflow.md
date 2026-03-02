# 認証プロバイダ切り替え データフロー図

**作成日**: 2026-03-02
**関連アーキテクチャ**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/auth-provider-switch/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・設計文書・ユーザヒアリングを参考にした確実なフロー
- 🟡 **黄信号**: EARS要件定義書・設計文書・ユーザヒアリングから妥当な推測によるフロー
- 🔴 **赤信号**: EARS要件定義書・設計文書・ユーザヒアリングにない推測によるフロー

---

## 認証フロー（プロバイダ共通）🔵

**信頼性**: 🔵 *既存実装・OIDC標準フローより*

変更後の認証フローは Keycloak / Cognito どちらでも同一です。`oidc-client-ts` が OIDC Discovery エンドポイント（`${authority}/.well-known/openid-configuration`）を自動取得するため、`authority` URL を差し替えるだけでプロバイダが切り替わります。

```
┌──────────┐     ┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│ ユーザー  │     │ フロントエンド │     │ OIDCプロバイダ     │     │ API Gateway │
│          │     │ (oidc-client │     │ (Keycloak or     │     │ + Lambda    │
│          │     │  -ts)        │     │  Cognito)        │     │             │
└────┬─────┘     └──────┬──────┘     └────────┬─────────┘     └──────┬──────┘
     │                  │                      │                      │
     │  1. ログイン      │                      │                      │
     │─────────────────▶│                      │                      │
     │                  │                      │                      │
     │                  │  2. OIDC Discovery   │                      │
     │                  │  GET ${authority}/    │                      │
     │                  │  .well-known/        │                      │
     │                  │  openid-configuration│                      │
     │                  │─────────────────────▶│                      │
     │                  │                      │                      │
     │                  │  3. エンドポイント情報 │                      │
     │                  │◀─────────────────────│                      │
     │                  │                      │                      │
     │  4. 認証リダイレクト│                      │                      │
     │◀─────────────────│                      │                      │
     │                  │                      │                      │
     │  5. ログイン画面   │                      │                      │
     │─────────────────────────────────────────▶│                      │
     │                  │                      │                      │
     │  6. 認証コード     │                      │                      │
     │◀─────────────────────────────────────────│                      │
     │                  │                      │                      │
     │  7. コールバック    │                      │                      │
     │─────────────────▶│                      │                      │
     │                  │                      │                      │
     │                  │  8. トークン交換      │                      │
     │                  │  (code → JWT)        │                      │
     │                  │  + PKCE verifier     │                      │
     │                  │─────────────────────▶│                      │
     │                  │                      │                      │
     │                  │  9. JWT (access +    │                      │
     │                  │     refresh token)   │                      │
     │                  │◀─────────────────────│                      │
     │                  │                      │                      │
     │                  │  10. API呼び出し                             │
     │                  │  Authorization: Bearer <JWT>                │
     │                  │────────────────────────────────────────────▶│
     │                  │                      │                      │
     │                  │                      │  11. JWT検証          │
     │                  │                      │  issuer: ${OidcIssuer}│
     │                  │                      │  audience: ${Oidc     │
     │                  │                      │   Audience}           │
     │                  │                      │                      │
     │                  │                      │  12. sub クレーム抽出  │
     │                  │                      │  → user_id として使用 │
     │                  │                      │                      │
     │                  │  13. APIレスポンス                           │
     │                  │◀────────────────────────────────────────────│
     │                  │                      │                      │
     │  14. 画面表示     │                      │                      │
     │◀─────────────────│                      │                      │
```

**ポイント**:
- ステップ 2-3: `oidc-client-ts` が `authority` URL から OIDC Discovery を自動実行
- ステップ 11: API Gateway JWT Authorizer が `issuer` + `audience` で JWT を検証
- ステップ 12: Lambda は `sub` クレームのみを使用（プロバイダ非依存）

---

## プロバイダ別の authority URL 🔵

**信頼性**: 🔵 *Keycloak・Cognito の公式ドキュメントより*

| プロバイダ | authority URL 形式 | OIDC Discovery URL |
|-----------|-------------------|-------------------|
| Keycloak | `https://{host}/realms/{realm}` | `https://{host}/realms/{realm}/.well-known/openid-configuration` |
| Cognito | `https://cognito-idp.{region}.amazonaws.com/{userPoolId}` | `https://cognito-idp.{region}.amazonaws.com/{userPoolId}/.well-known/openid-configuration` |

どちらも標準 OIDC Discovery に対応しているため、`oidc-client-ts` と API Gateway JWT Authorizer がそのまま動作します。

---

## デプロイ時の切り替えフロー 🔵

**信頼性**: 🔵 *要件定義 REQ-004・ユーザヒアリングより*

```
管理者

  │  1. 環境変数ファイルを編集
  │     (.env / samconfig.toml)
  │
  ├──▶ [バックエンド]
  │    sam deploy \
  │      --parameter-overrides \
  │        OidcIssuer=https://cognito-idp... \
  │        OidcAudience=xxxxxxxxxxxx
  │
  │    → template.yaml の JWT Authorizer が
  │      新しい issuer/audience で構成される
  │    → Lambda 環境変数 OIDC_ISSUER が更新される
  │
  └──▶ [フロントエンド]
       VITE_OIDC_AUTHORITY=https://cognito-idp...
       VITE_OIDC_CLIENT_ID=xxxxxxxxxxxx
       npm run build && deploy to S3/CloudFront

       → oidc-client-ts が新しい authority で
         OIDC Discovery を実行
```

**コード変更**: なし（設定値の変更のみ）

---

## トークンリフレッシュフロー（プロバイダ共通）🔵

**信頼性**: 🔵 *既存実装 `frontend/src/services/auth.ts:113-117` より*

```
┌─────────────┐                    ┌──────────────────┐
│ フロントエンド │                    │ OIDCプロバイダ     │
│ (oidc-client │                    │ (Keycloak or     │
│  -ts)        │                    │  Cognito)        │
└──────┬──────┘                    └────────┬─────────┘
       │                                    │
       │  automaticSilentRenew = true       │
       │                                    │
       │  [トークン期限切れ検知]               │
       │                                    │
       │  signinSilent()                    │
       │  (refresh_token → 新JWT)           │
       │───────────────────────────────────▶│
       │                                    │
       │  新しい access_token + refresh_token│
       │◀───────────────────────────────────│
       │                                    │
       │  [AuthContext 状態更新]              │
       │  apiClient.setAccessToken(新token)  │
```

`oidc-client-ts` の `signinSilent()` は OIDC Discovery で取得した token_endpoint を使うため、プロバイダを意識しません。

---

## エラーハンドリング 🟡

**信頼性**: 🟡 *既存実装パターンから妥当な推測*

### 設定ミスによるエラー

| エラーケース | 発生箇所 | 挙動 |
|-------------|---------|------|
| `VITE_OIDC_AUTHORITY` が空 | フロントエンド起動時 | `validateOidcConfig()` が例外をスロー |
| `VITE_OIDC_AUTHORITY` が無効な URL | OIDC Discovery 時 | `oidc-client-ts` がネットワークエラー |
| `OidcIssuer` が無効な URL | API Gateway デプロイ時 | CloudFormation デプロイエラー |
| `OidcAudience` が不一致 | API 呼び出し時 | 401 Unauthorized |
| issuer と audience の組み合わせ不整合 | API 呼び出し時 | 401 Unauthorized |

---

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **要件定義**: [requirements.md](../../spec/auth-provider-switch/requirements.md)

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 6件 | 86% |
| 🟡 黄信号 | 1件 | 14% |
| 🔴 赤信号 | 0件 | 0% |

**品質評価**: ✅ 高品質（青信号が86%、赤信号なし）
