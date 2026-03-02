# 認証プロバイダ切り替え アーキテクチャ設計

**作成日**: 2026-03-02
**関連要件定義**: [requirements.md](../../spec/auth-provider-switch/requirements.md)
**ヒアリング記録**: [design-interview.md](design-interview.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・設計文書・ユーザヒアリングを参考にした確実な設計
- 🟡 **黄信号**: EARS要件定義書・設計文書・ユーザヒアリングから妥当な推測による設計
- 🔴 **赤信号**: EARS要件定義書・設計文書・ユーザヒアリングにない推測による設計

---

## システム概要 🔵

**信頼性**: 🔵 *要件定義書・ユーザヒアリングより*

認証プロバイダ（Keycloak / Amazon Cognito）をデプロイ時の設定変更のみで切り替え可能にする。OIDC 標準に準拠した汎用的な設定構造にリファクタリングし、プロバイダ固有の命名・URL構築ロジックを除去する。

## 設計方針 🔵

**信頼性**: 🔵 *要件定義 REQ-003, REQ-004・ユーザヒアリングより*

- **コード変更ゼロ原則**: プロバイダ切り替えはパラメータ/環境変数の変更のみ
- **OIDC 標準準拠**: プロバイダ固有の処理を排除し、標準 OIDC Discovery に依存
- **既存アーキテクチャ維持**: API Gateway JWT Authorizer + `oidc-client-ts` の構成はそのまま

---

## 変更対象のアーキテクチャ

### Before（現状）🔵

**信頼性**: 🔵 *既存実装 `backend/template.yaml`, `frontend/src/config/oidc.ts` より*

```
[フロントエンド]                         [バックエンド]

oidc.ts                                 template.yaml
├─ VITE_KEYCLOAK_URL                    ├─ KeycloakIssuer (パラメータ)
├─ VITE_KEYCLOAK_REALM                  ├─ audience: ["liff-client"] (固定値)
├─ VITE_KEYCLOAK_CLIENT_ID              └─ KEYCLOAK_ISSUER (Lambda環境変数)
└─ authority: ${URL}/realms/${REALM}
   (Keycloak固有のURL構築)
```

**問題点**:
- パラメータ名・環境変数名が `Keycloak` 固有
- `authority` URL の構築が `${URL}/realms/${REALM}` という Keycloak 固有形式
- `audience` がハードコードされており、Cognito では異なる値が必要

### After（変更後）🔵

**信頼性**: 🔵 *要件定義 REQ-001, REQ-002・OIDC標準仕様より*

```
[フロントエンド]                         [バックエンド]

oidc.ts                                 template.yaml
├─ VITE_OIDC_AUTHORITY                  ├─ OidcIssuer (パラメータ)
├─ VITE_OIDC_CLIENT_ID                  ├─ OidcAudience (パラメータ)
└─ authority: ${VITE_OIDC_AUTHORITY}    └─ OIDC_ISSUER (Lambda環境変数)
   (環境変数をそのまま使用)
```

---

## ファイル別変更設計

### 1. `backend/template.yaml` 🔵

**信頼性**: 🔵 *要件定義 REQ-001・既存実装 `template.yaml:36-39,260-263` より*

#### パラメータ変更

```yaml
# Before
Parameters:
  KeycloakIssuer:
    Type: String
    Default: https://keycloak.example.com/realms/memoru
    Description: Keycloak OIDC Issuer URL

# After
Parameters:
  OidcIssuer:
    Type: String
    Default: https://keycloak.example.com/realms/memoru
    Description: OIDC Issuer URL (Keycloak or Cognito)

  OidcAudience:
    Type: String
    Default: liff-client
    Description: OIDC Audience (client_id registered in the IdP)
```

#### JWT Authorizer 変更

```yaml
# Before
Auth:
  DefaultAuthorizer: JwtAuthorizer
  Authorizers:
    JwtAuthorizer:
      JwtConfiguration:
        issuer: !Ref KeycloakIssuer
        audience:
          - liff-client

# After
Auth:
  DefaultAuthorizer: JwtAuthorizer
  Authorizers:
    JwtAuthorizer:
      JwtConfiguration:
        issuer: !Ref OidcIssuer
        audience:
          - !Ref OidcAudience
```

#### Lambda 環境変数変更

```yaml
# Before
Environment:
  Variables:
    KEYCLOAK_ISSUER: !Ref KeycloakIssuer

# After
Environment:
  Variables:
    OIDC_ISSUER: !Ref OidcIssuer
```

### 2. `frontend/src/config/oidc.ts` 🔵

**信頼性**: 🔵 *要件定義 REQ-002・既存実装 `oidc.ts:11-13,44-47` より*

#### 環境変数変更

```typescript
// Before
const KEYCLOAK_URL = import.meta.env.VITE_KEYCLOAK_URL || '';
const KEYCLOAK_REALM = import.meta.env.VITE_KEYCLOAK_REALM || '';
const KEYCLOAK_CLIENT_ID = import.meta.env.VITE_KEYCLOAK_CLIENT_ID || '';

// After
const OIDC_AUTHORITY = import.meta.env.VITE_OIDC_AUTHORITY || '';
const OIDC_CLIENT_ID = import.meta.env.VITE_OIDC_CLIENT_ID || '';
```

#### OIDC 設定変更

```typescript
// Before
export const oidcConfig: UserManagerSettings = {
  authority: `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}`,
  client_id: KEYCLOAK_CLIENT_ID,
  // ...
};

// After
export const oidcConfig: UserManagerSettings = {
  authority: OIDC_AUTHORITY,
  client_id: OIDC_CLIENT_ID,
  // ... (他のプロパティは変更なし)
};
```

#### バリデーション変更

```typescript
// Before
const requiredVars = [
  { name: 'VITE_KEYCLOAK_URL', value: KEYCLOAK_URL },
  { name: 'VITE_KEYCLOAK_REALM', value: KEYCLOAK_REALM },
  { name: 'VITE_KEYCLOAK_CLIENT_ID', value: KEYCLOAK_CLIENT_ID },
];

// After
const requiredVars = [
  { name: 'VITE_OIDC_AUTHORITY', value: OIDC_AUTHORITY },
  { name: 'VITE_OIDC_CLIENT_ID', value: OIDC_CLIENT_ID },
];
```

### 3. 環境変数ファイル（`.env` / `.env.example`）🟡

**信頼性**: 🟡 *要件定義から妥当な推測（既存の `.env` ファイル構成を未確認）*

#### Keycloak 使用時

```env
# Backend (SAM parameter overrides)
OidcIssuer=https://keycloak.example.com/realms/memoru
OidcAudience=liff-client

# Frontend
VITE_OIDC_AUTHORITY=https://keycloak.example.com/realms/memoru
VITE_OIDC_CLIENT_ID=liff-client
```

#### Cognito 使用時

```env
# Backend (SAM parameter overrides)
OidcIssuer=https://cognito-idp.ap-northeast-1.amazonaws.com/ap-northeast-1_XXXXXXXXX
OidcAudience=xxxxxxxxxxxxxxxxxxxxxxxxxx

# Frontend
VITE_OIDC_AUTHORITY=https://cognito-idp.ap-northeast-1.amazonaws.com/ap-northeast-1_XXXXXXXXX
VITE_OIDC_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 4. 変更不要なファイル 🔵

**信頼性**: 🔵 *既存実装の分析結果より*

| ファイル | 理由 |
|----------|------|
| `backend/src/api/shared.py` | `sub` クレーム取得のみ。プロバイダ非依存 |
| `frontend/src/services/auth.ts` | `oidc-client-ts` の `UserManager` API はプロバイダ非依存 |
| `frontend/src/hooks/useAuth.ts` | 認証状態管理のみ。`oidcConfig` を参照しない |
| `frontend/src/contexts/AuthContext.tsx` | Context 層はプロバイダ非依存 |
| `backend/src/services/*` | ビジネスロジック層は認証に依存しない |

### 5. テストファイルの影響 🟡

**信頼性**: 🟡 *既存テスト構成から妥当な推測*

| ファイル | 影響 |
|----------|------|
| `backend/tests/conftest.py` | モック issuer URL がテストに影響しないか確認が必要 |
| `frontend/src/config/__tests__/` | 環境変数名の変更に伴いテストの更新が必要 |

---

## Cognito 使用時の LINE Login 統合（選択肢併記）🟡

**信頼性**: 🟡 *要件定義 REQ-404・ユーザヒアリング「設計フェーズで決定」より*

### 方式A: Cognito 外部 IdP として LINE Login を登録

```
ユーザー → Cognito Hosted UI → LINE Login (OIDC外部IdP) → Cognito → JWT発行
```

**メリット**:
- フロントエンドのコード変更不要（`oidc-client-ts` → Cognito の OIDC エンドポイント）
- Cognito がトークン変換を担当
- 既存の認証フローがそのまま動作

**デメリット**:
- Cognito Hosted UI の経由が必要（カスタマイズ制限あり）
- LINE Login を OIDC プロバイダとして Cognito に登録する設定が必要

### 方式B: LIFF トークン → Cognito カスタム認証フロー

```
ユーザー → LIFF SDK → LINE アクセストークン取得 → カスタム Lambda → Cognito InitiateAuth → JWT発行
```

**メリット**:
- LIFF 環境内でシームレスな認証体験
- Cognito Hosted UI 不要

**デメリット**:
- カスタム認証 Lambda の新規開発が必要
- LIFF 固有のフローになり、LIFF 外（ネイティブアプリ等）では使えない

### 推奨 🟡

方式A を推奨する。理由：
- REQ-003（コード変更不要）の原則に合致
- OIDC 標準フローの維持
- ネイティブアプリ展開時にも同じフローが使える

---

## セキュリティ考慮 🔵

**信頼性**: 🔵 *既存セキュリティ設計・OIDC標準より*

- **PKCE フロー**: 両プロバイダとも Authorization Code + PKCE を使用（`oidc-client-ts` のデフォルト）
- **JWT 検証**: API Gateway JWT Authorizer が issuer + audience を検証（プロバイダ非依存）
- **トークンリフレッシュ**: `oidc-client-ts` の `automaticSilentRenew` が標準 OIDC エンドポイントを使用
- **CORS**: ネイティブアプリはブラウザではないので CORS 制約を受けない。LIFF は既存設定を維持

---

## 関連文書

- **データフロー**: [dataflow.md](dataflow.md)
- **要件定義**: [requirements.md](../../spec/auth-provider-switch/requirements.md)
- **既存アーキテクチャ**: [architecture.md](../memoru-liff/architecture.md)

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 10件 | 77% |
| 🟡 黄信号 | 3件 | 23% |
| 🔴 赤信号 | 0件 | 0% |

**品質評価**: ✅ 高品質（青信号が77%以上、赤信号なし）
