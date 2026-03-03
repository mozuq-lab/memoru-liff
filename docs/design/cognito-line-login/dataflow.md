# Cognito LINE Login 外部 IdP 統合 データフロー図

**作成日**: 2026-03-03
**関連アーキテクチャ**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/cognito-line-login/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・設計文書・ユーザヒアリングを参考にした確実なフロー
- 🟡 **黄信号**: EARS要件定義書・設計文書・ユーザヒアリングから妥当な推測によるフロー
- 🔴 **赤信号**: EARS要件定義書・設計文書・ユーザヒアリングにない推測によるフロー

---

## システム全体のデータフロー 🔵

**信頼性**: 🔵 *auth-provider-switch architecture.md・note.md ターゲットフローより*

```mermaid
flowchart TD
    U[ユーザー] --> LIFF[LIFF アプリ]
    LIFF --> OIDC[oidc-client-ts]
    OIDC -->|"リダイレクト"| HUI[Cognito Hosted UI]

    HUI -->|"LINE でログイン"| LINE_AUTH[LINE Login OIDC]
    HUI -->|"メール+PW"| COGNITO_AUTH[Cognito 内部認証]

    LINE_AUTH -->|"認可コード"| COGNITO_FED[Cognito フェデレーション]
    COGNITO_FED -->|"トークン交換"| LINE_TOKEN[LINE Token Endpoint]
    LINE_TOKEN -->|"LINE JWT"| COGNITO_FED
    COGNITO_FED -->|"属性マッピング"| COGNITO_UP[Cognito UserPool]

    COGNITO_AUTH --> COGNITO_UP

    COGNITO_UP -->|"Cognito JWT 発行"| HUI
    HUI -->|"リダイレクト + code"| OIDC
    OIDC -->|"Bearer JWT"| APIGW[API Gateway]
    APIGW -->|"JWT 検証"| LAMBDA[Lambda Backend]
```

## 主要機能のデータフロー

### フロー1: LINE Login 経由の認証 🔵

**信頼性**: 🔵 *note.md ターゲットフロー・auth-provider-switch architecture.md 方式A・ユーザヒアリングより*

**関連要件**: REQ-001, REQ-004, REQ-005

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant LIFF as LIFF アプリ
    participant OIDC as oidc-client-ts
    participant HUI as Cognito Hosted UI
    participant LINE as LINE Login
    participant COG as Cognito UserPool
    participant APIGW as API Gateway
    participant BE as Lambda Backend

    U->>LIFF: アプリ起動
    LIFF->>OIDC: signinRedirect()
    OIDC->>HUI: リダイレクト（PKCE code_challenge 付き）

    Note over HUI: メール認証フォーム + LINE ボタン表示

    U->>HUI: 「LINE でログイン」クリック
    HUI->>LINE: OIDC Authorization Request<br/>(client_id, redirect_uri, scope=openid profile)
    LINE->>U: LINE ログイン画面表示
    U->>LINE: LINE 認証情報入力
    LINE->>HUI: 認可コード返却

    HUI->>LINE: Token Request（認可コード + client_secret）
    LINE-->>HUI: LINE JWT（sub, name, picture）

    HUI->>COG: 属性マッピング（LINE sub → Cognito user）
    COG->>COG: Cognito ユーザー作成/更新
    COG-->>HUI: Cognito 認可コード

    HUI->>OIDC: リダイレクト（Cognito 認可コード）
    OIDC->>COG: Token Request（PKCE code_verifier）
    COG-->>OIDC: Cognito JWT（access_token, id_token, refresh_token）

    OIDC->>LIFF: 認証完了
    LIFF->>APIGW: API リクエスト（Authorization: Bearer JWT）
    APIGW->>APIGW: JWT 検証（OidcIssuer = Cognito）
    APIGW->>BE: 検証済みリクエスト
    BE->>BE: JWT sub からユーザー ID 取得
    BE-->>LIFF: API レスポンス
```

**詳細ステップ**:
1. `oidc-client-ts` が Cognito Hosted UI にリダイレクト（PKCE フロー）
2. Hosted UI に LINE ログインボタンとメール認証フォームが表示
3. ユーザーが LINE ボタンをクリック → LINE Login の認証画面に遷移
4. LINE 認証完了後、Cognito が LINE のトークンを受け取り属性マッピング
5. Cognito がフェデレーテッドユーザーを作成/更新し、Cognito JWT を発行
6. `oidc-client-ts` が Cognito JWT を受け取り、API リクエストに使用

### フロー2: メール+パスワード認証（既存、変更なし） 🔵

**信頼性**: 🔵 *既存実装・OIDC 汎用化済み設計より*

**関連要件**: REQ-005

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant OIDC as oidc-client-ts
    participant HUI as Cognito Hosted UI
    participant COG as Cognito UserPool

    U->>OIDC: ログイン操作
    OIDC->>HUI: リダイレクト（PKCE）
    U->>HUI: メール+パスワード入力
    HUI->>COG: 認証
    COG-->>HUI: Cognito JWT
    HUI->>OIDC: リダイレクト（認可コード）
    OIDC->>COG: Token Request（PKCE）
    COG-->>OIDC: Cognito JWT
```

このフローは LINE IdP 追加前後で変更なし。`supportedIdentityProviders` に `COGNITO` が含まれている限り動作する。

### フロー3: CDK デプロイフロー 🔵

**信頼性**: 🔵 *REQ-001・REQ-006・REQ-007・既存 CDK デプロイパターンより*

**関連要件**: REQ-001, REQ-006, REQ-007

```mermaid
sequenceDiagram
    participant DEV as 開発者
    participant CDK as CDK CLI
    participant CFN as CloudFormation
    participant COG as Cognito

    DEV->>DEV: 環境変数に LINE Channel ID/Secret を設定
    DEV->>CDK: npx cdk deploy MemoruCognitoDev

    CDK->>CDK: app.ts 読み込み<br/>process.env.LINE_LOGIN_CHANNEL_ID 取得

    alt LINE Channel ID/Secret が設定されている場合
        CDK->>CFN: UserPoolIdentityProviderOidc 作成
        CFN->>COG: LINE IdP 登録
        CFN->>COG: UserPoolClient 更新<br/>(COGNITO + LINE)
        COG-->>DEV: Hosted UI に LINE ボタン追加
    else LINE Channel ID/Secret が未設定の場合
        CDK->>CFN: 既存リソースのみ（LINE IdP なし）
        COG-->>DEV: Hosted UI はメール認証のみ（既存動作）
    end
```

**詳細ステップ**:
1. 開発者が `LINE_LOGIN_CHANNEL_ID` / `LINE_LOGIN_CHANNEL_SECRET` 環境変数を設定
2. `npx cdk deploy` 実行 → `app.ts` が `process.env` から Props を取得
3. `cognito-stack.ts` が Props を判定し、LINE IdP を条件付きで作成
4. CloudFormation が Cognito リソースを更新

## データ処理パターン

### 同期処理 🔵

**信頼性**: 🔵 *Cognito フェデレーション仕様より*

- **LINE OIDC トークン交換**: Cognito が LINE Token Endpoint を同期的に呼び出し、トークンを取得
- **属性マッピング**: トークン取得後、即座に Cognito ユーザー属性にマッピング
- **CDK デプロイ**: CloudFormation による同期的なリソース作成/更新

### 非同期処理

**該当なし** — 本要件のスコープでは非同期処理は発生しない。

## エラーハンドリングフロー 🟡

**信頼性**: 🟡 *Cognito フェデレーション・LINE Login の一般的な動作から妥当な推測*

```mermaid
flowchart TD
    A[認証エラー発生] --> B{エラー種別}

    B -->|LINE Login 拒否| C[ユーザーが LINE 認証をキャンセル]
    C --> D[Cognito Hosted UI に戻る<br/>メール認証でリトライ可能]

    B -->|LINE OIDC エラー| E[LINE Token Endpoint 応答なし]
    E --> F[Cognito がエラー返却]
    F --> D

    B -->|Cognito 設定エラー| G[CDK デプロイ時のバリデーション]
    G --> H[CloudFormation ロールバック]

    B -->|属性マッピングエラー| I[LINE 属性が期待と異なる]
    I --> J[Cognito がデフォルト値で処理<br/>ユーザー作成は成功]
```

**重要**: LINE Login 障害時でもメール+パスワード認証は独立して動作する（フォールバック）。

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **設計ヒアリング記録**: [design-interview.md](design-interview.md)
- **要件定義**: [requirements.md](../../spec/cognito-line-login/requirements.md)

## 信頼性レベルサマリー

- 🔵 青信号: 8件 (89%)
- 🟡 黄信号: 1件 (11%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質 — 既存の OIDC フロー設計とユーザヒアリングに基づく確実なデータフロー設計。
