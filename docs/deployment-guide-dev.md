# Memoru LIFF - 開発環境デプロイ手順書（Cognito + LINE Login 構成）

> 対象: AWS 開発環境（dev）を Cognito ベースでゼロから構築する手順
>
> LINE Login 統合方式: **方式A — Cognito 外部 OIDC IdP として LINE Login を登録**
>
> 認証フロー: `ユーザー → Cognito Hosted UI → LINE Login (OIDC) → Cognito JWT 発行`

### 前提: 実装タスクとの依存関係

本手順書の **Step 3（Cognito LINE Login 外部 IdP 設定）** は、以下の CDK 実装が完了していることが前提となる:

- `cognito-stack.ts` への `UserPoolIdentityProviderOidc`（LINE）追加
- `UserPoolClient` の `supportedIdentityProviders` に LINE を追加
- 属性マッピングの定義

**CDK 実装が未完了の場合は AWS Console から手動設定が可能**（手順は Step 3 に記載）。

## 目次

1. [前提条件](#1-前提条件)
2. [Step 1: AWS 環境の初期設定](#step-1-aws-環境の初期設定)
3. [Step 2: CDK — Cognito スタックのデプロイ](#step-2-cdk--cognito-スタックのデプロイ)
4. [Step 3: Cognito LINE Login 外部 IdP 設定](#step-3-cognito-line-login-外部-idp-設定)
5. [Step 4: CDK — LIFF Hosting スタックのデプロイ](#step-4-cdk--liff-hosting-スタックのデプロイ)
6. [Step 5: LINE Secrets の登録](#step-5-line-secrets-の登録)
7. [Step 6: バックエンドのデプロイ（SAM）](#step-6-バックエンドのデプロイsam)
8. [Step 7: Cognito コールバック URL の更新](#step-7-cognito-コールバック-url-の更新)
9. [Step 8: フロントエンドのビルドとデプロイ](#step-8-フロントエンドのビルドとデプロイ)
10. [Step 9: LINE Developer Console の設定](#step-9-line-developer-console-の設定)
11. [Step 10: Amazon Bedrock モデルアクセスの有効化](#step-10-amazon-bedrock-モデルアクセスの有効化)
12. [Step 10b: （オプション）AgentCore Memory のセットアップ](#step-10b-オプションagentcore-memory-のセットアップ)
13. [Step 11: 動作確認](#step-11-動作確認)
14. [付録: デプロイ後の値一覧](#付録-デプロイ後の値一覧)
15. [付録: トラブルシューティング](#付録-トラブルシューティング)

---

## 1. 前提条件

### 必要なツール

| ツール | バージョン | インストール確認 |
|--------|-----------|-----------------|
| AWS CLI | v2 | `aws --version` |
| AWS CDK CLI | v2 | `npx cdk --version` |
| AWS SAM CLI | v1.x | `sam --version` |
| Node.js | v20+ | `node --version` |
| Python | 3.12 | `python3 --version` |
| Docker | 最新 | `docker --version` |

### AWS アカウント要件

- AWS アカウントが作成済みであること
- IAM ユーザーまたはロールに以下の権限があること:
  - CloudFormation / CDK 操作: `AdministratorAccess` または必要な権限セット
  - SAM デプロイ: `AWSCloudFormationFullAccess`, `AWSLambda_FullAccess`, `AmazonDynamoDBFullAccess`, `AmazonAPIGatewayAdministrator`, `IAMFullAccess`
- AWS CLI が `ap-northeast-1` リージョンで設定済みであること

```bash
# 確認
aws sts get-caller-identity
aws configure get region  # → ap-northeast-1
```

### LINE Developer Console 要件

- LINE Developers Console でプロバイダーが作成済み
- **Messaging API チャネル** が作成済み
- **LINE Login チャネル** が作成済み（LIFF 用）
  - チャネルの **Channel ID** と **Channel Secret** を控えておくこと（Step 3 で使用）
  - 「LINE Login」タブで **ウェブアプリ** が有効化されていること

---

## Step 1: AWS 環境の初期設定

### 1.1 CDK Bootstrap

CDK を使うリージョンで初回のみ実行が必要。CDK が使用する S3 バケットや IAM ロールを作成する。

```bash
npx cdk bootstrap aws://<ACCOUNT_ID>/ap-northeast-1
```

`<ACCOUNT_ID>` は以下で確認:

```bash
aws sts get-caller-identity --query Account --output text
```

### 1.2 CDK 依存パッケージのインストール

```bash
cd infrastructure/cdk
npm install
```

### 1.3 CDK のビルドとスタック確認

```bash
npm run build
npx cdk ls
```

以下の 3 スタックが表示される（dev 環境）:

```
MemoruCognitoDev
MemoruKeycloakDev      ← 今回は使用しない
MemoruLiffHostingDev
```

---

## Step 2: CDK — Cognito スタックのデプロイ

### 2.1 設定の確認

`infrastructure/cdk/bin/app.ts` の dev 設定を確認:

```typescript
new CognitoStack(app, 'MemoruCognitoDev', {
  environment: 'dev',
  cognitoDomainPrefix: 'memoru-dev',  // ← 重複する場合は変更
  callbackUrls: ['http://localhost:3000/callback', 'https://localhost:3000/callback'],
  logoutUrls: ['http://localhost:3000/', 'https://localhost:3000/'],
});
```

> **注意**: `cognitoDomainPrefix` はグローバルで一意である必要がある。`memoru-dev` が既に使用されている場合は `memoru-dev-<任意の識別子>` に変更すること。

### 2.2 デプロイの実行

```bash
cd infrastructure/cdk
npx cdk deploy MemoruCognitoDev
```

### 2.3 出力値の記録

デプロイ完了後、CloudFormation Outputs に以下が表示される。**すべてメモしておくこと**:

| Output Key | 説明 | 例 |
|-----------|------|-----|
| `UserPoolId` | Cognito User Pool ID | `ap-northeast-1_XXXXXXXXX` |
| `UserPoolClientId` | クライアント ID | `1abc2defghijk3lmnopq4rst5u` |
| `OidcIssuerUrl` | OIDC Issuer URL | `https://cognito-idp.ap-northeast-1.amazonaws.com/ap-northeast-1_XXXXXXXXX` |
| `CognitoDomainUrl` | Hosted UI URL | `https://memoru-dev.auth.ap-northeast-1.amazoncognito.com` |

出力値は後からでも確認可能:

```bash
aws cloudformation describe-stacks \
  --stack-name MemoruCognitoDev \
  --query "Stacks[0].Outputs" \
  --output table
```

---

## Step 3: Cognito LINE Login 外部 IdP 設定

Cognito に LINE Login を外部 OIDC IdP として登録し、LINE アカウントで Cognito にサインインできるようにする。

> **方式A の認証フロー**:
> ```
> ユーザー → Cognito Hosted UI → 「LINE でログイン」ボタン
>   → LINE Login 認証画面 → 認可コード発行
>   → Cognito が LINE からトークン取得 → Cognito JWT 発行
>   → フロントエンド (oidc-client-ts) がトークン受領
>   → API Gateway JWT Authorizer で検証
> ```

### 3.1 LINE Login チャネル情報の確認

LINE Developers Console から以下を控える:

| 項目 | 取得場所 |
|------|---------|
| **Channel ID** | LINE Login チャネル →「Basic settings」→「Channel ID」 |
| **Channel Secret** | LINE Login チャネル →「Basic settings」→「Channel secret」 |

### 3.2 LINE Login チャネルにコールバック URL を登録

LINE Developers Console → LINE Login チャネル →「LINE Login」タブ:

1. 「ウェブアプリ」が有効になっていることを確認
2. 「Callback URL」に Cognito の IdP レスポンスエンドポイントを追加:

```
https://<cognitoDomainPrefix>.auth.ap-northeast-1.amazoncognito.com/oauth2/idpresponse
```

例（`cognitoDomainPrefix` が `memoru-dev` の場合）:

```
https://memoru-dev.auth.ap-northeast-1.amazoncognito.com/oauth2/idpresponse
```

> **注意**: この URL は Step 2 の `CognitoDomainUrl` 出力値のドメイン部分 + `/oauth2/idpresponse`。

### 3.3 Cognito に LINE を OIDC プロバイダとして登録

> **CDK 実装が完了している場合**: `npx cdk deploy MemoruCognitoDev` で自動設定される。以下の手動手順は不要。
>
> **CDK 実装が未完了の場合**: AWS Management Console から手動設定する。

#### AWS Console での手動設定手順

1. AWS Console → **Amazon Cognito** → User pools → `memoru-dev-user-pool`
2. 「**Sign-in experience**」タブ → 「Federated identity provider sign-in」セクション
3. 「**Add identity provider**」→「**OpenID Connect (OIDC)**」を選択
4. 以下を設定:

| 設定項目 | 値 |
|---------|-----|
| Provider name | `LINE` |
| Client ID | `<LINE Login Channel ID>` |
| Client secret | `<LINE Login Channel Secret>` |
| Authorized scopes | `openid profile` |
| Attribute request method | `GET` |

5. 「**Issuer URL**」に `https://access.line.me` を入力し、自動検出を試みる

> **自動検出が失敗する場合**: LINE は標準の `.well-known/openid-configuration` を提供しない可能性がある。その場合は「手動入力」に切り替え、以下のエンドポイントを入力:
>
> | エンドポイント | URL |
> |--------------|-----|
> | Authorization endpoint | `https://access.line.me/oauth2/v2.1/authorize` |
> | Token endpoint | `https://api.line.me/oauth2/v2.1/token` |
> | Userinfo endpoint | `https://api.line.me/v2/profile` |
> | JWKS URI | `https://api.line.me/oauth2/v2.1/certs` |

6. 「**Create identity provider**」をクリック

### 3.4 属性マッピングの設定

LINE から取得した属性を Cognito ユーザー属性にマッピングする。

1. 作成した LINE IdP の詳細画面 → 「**Attribute mapping**」セクション
2. 以下をマッピング:

| LINE 属性 (OIDC claim) | Cognito 属性 | 説明 |
|------------------------|-------------|------|
| `sub` | `Username` | LINE ユーザー ID（自動マッピング） |
| `name` | `name` | 表示名 |
| `picture` | `picture` | プロフィール画像 URL |
| `email` | `email` | メールアドレス（LINE 側で許可が必要） |

> **注意**: LINE の `sub` は `U` で始まる LINE ユーザー ID（例: `U1234567890abcdef...`）。Cognito はこれをフェデレーテッドユーザーの識別子として使用するが、Cognito 側の `sub` クレームは別途 Cognito が生成する UUID になる。

### 3.5 User Pool Client に LINE IdP を追加

1. 「**App integration**」タブ → 「App clients and analytics」セクション
2. `memoru-dev-liff-client` をクリック
3. 「**Edit**」→「Hosted UI settings」セクション
4. 「**Identity providers**」で以下を両方選択:
   - `Cognito user pool`（メール+パスワード認証を維持）
   - `LINE`（追加）
5. 「**Save changes**」

### 3.6 設定の確認

Cognito Hosted UI にアクセスし、LINE ログインボタンが表示されることを確認:

```
https://<cognitoDomainPrefix>.auth.ap-northeast-1.amazoncognito.com/login?client_id=<UserPoolClientId>&response_type=code&scope=openid+profile+email&redirect_uri=http://localhost:3000/callback
```

> この時点ではリダイレクト先（localhost）にアプリが動いていなくてもよい。LINE ログインボタンが表示され、LINE 認証画面に遷移することだけ確認する。

---

## Step 4: CDK — LIFF Hosting スタックのデプロイ

### 4.1 デプロイの実行

dev 環境はカスタムドメインなしの CloudFront ドメインで動作する。

```bash
cd infrastructure/cdk
npx cdk deploy MemoruLiffHostingDev
```

### 4.2 出力値の記録

| Output Key | 説明 | 例 |
|-----------|------|-----|
| `BucketName` | S3 バケット名 | `memoru-liff-dev-123456789012` |
| `DistributionId` | CloudFront Distribution ID | `E1A2B3C4D5E6F7` |
| `DistributionDomainName` | CloudFront ドメイン | `d1234567890abc.cloudfront.net` |
| `LiffUrl` | LIFF アプリ URL | `https://d1234567890abc.cloudfront.net` |
| `DeployCommand` | デプロイ用コマンド | `aws s3 sync ...` |

確認コマンド:

```bash
aws cloudformation describe-stacks \
  --stack-name MemoruLiffHostingDev \
  --query "Stacks[0].Outputs" \
  --output table
```

---

## Step 5: LINE Secrets の登録

Lambda 関数（Webhook, DuePush）が LINE API を呼び出すために、Secrets Manager にクレデンシャルを登録する。

### 5.1 LINE Developer Console から値を取得

- **Channel Secret**: Messaging API チャネルの「Basic settings」→「Channel secret」
- **Channel Access Token**: Messaging API チャネルの「Messaging API」→「Channel access token（long-lived）」を発行

### 5.2 Secrets Manager に登録

```bash
aws secretsmanager create-secret \
  --name memoru-dev-line-credentials \
  --description "LINE Messaging API credentials for Memoru dev environment" \
  --secret-string '{
    "channelSecret": "<LINE_CHANNEL_SECRET>",
    "channelAccessToken": "<LINE_CHANNEL_ACCESS_TOKEN>"
  }' \
  --region ap-northeast-1
```

### 5.3 登録確認

```bash
aws secretsmanager describe-secret \
  --secret-id memoru-dev-line-credentials \
  --region ap-northeast-1
```

---

## Step 6: バックエンドのデプロイ（SAM）

### 6.1 samconfig.toml の更新

`backend/samconfig.toml` の `[dev.deploy.parameters]` セクションを、Step 2 で取得した Cognito の値に更新する。

```toml
[dev.deploy.parameters]
stack_name = "memoru-backend-dev"
capabilities = "CAPABILITY_IAM CAPABILITY_AUTO_EXPAND"
confirm_changeset = false
resolve_s3 = true
region = "ap-northeast-1"
parameter_overrides = "Environment=dev OidcIssuer=https://cognito-idp.ap-northeast-1.amazonaws.com/<UserPoolId> OidcAudience=<UserPoolClientId>"
```

- `<UserPoolId>`: Step 2 の `UserPoolId`（例: `ap-northeast-1_XXXXXXXXX`）
- `<UserPoolClientId>`: Step 2 の `UserPoolClientId`

> **重要**: Cognito の場合、API Gateway JWT Authorizer の `audience` は **Client ID** と一致させる必要がある。`OidcAudience` パラメータにも `UserPoolClientId` を指定すること。`template.yaml` のデフォルト値は `liff-client`（Keycloak 用）なので、上書きが必要。

#### オプション: AgentCore Memory を使用する場合

チューターセッションの会話履歴管理に Bedrock AgentCore Memory を使用する場合は、`parameter_overrides` に以下を追加する:

```toml
parameter_overrides = "Environment=dev OidcIssuer=... OidcAudience=... TutorSessionBackend=agentcore AgentCoreMemoryId=<AgentCore Memory ID>"
```

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| `TutorSessionBackend` | `dynamodb` | チューターセッション履歴のバックエンド。`dynamodb`（デフォルト）または `agentcore` |
| `AgentCoreMemoryId` | （空文字列） | AgentCore Memory ID。`TutorSessionBackend=agentcore` の場合に必須 |

> **注意**: AgentCore Memory を使用するには、事前に Step 10b で Memory を作成し、Memory ID を取得しておく必要がある。デフォルトの `dynamodb` バックエンドであればこれらのパラメータは不要。

### 6.2 ビルドとデプロイ

```bash
cd backend
make deploy-dev
```

内部的に以下が実行される:

```bash
sam build --use-container
sam deploy --config-env dev
```

> **注意**: 初回デプロイ時、Docker で `python:3.12` ベースイメージのダウンロードに時間がかかる場合がある。

### 6.3 出力値の記録

| Output Key | 説明 | 例 |
|-----------|------|-----|
| `ApiEndpoint` | API Gateway URL | `https://abc123def4.execute-api.ap-northeast-1.amazonaws.com/dev` |

確認コマンド:

```bash
aws cloudformation describe-stacks \
  --stack-name memoru-backend-dev \
  --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
  --output text
```

---

## Step 7: Cognito コールバック URL の更新

CloudFront ドメインを Cognito のコールバック URL に追加する必要がある。

### 7.1 app.ts の編集

`infrastructure/cdk/bin/app.ts` を編集:

```typescript
new CognitoStack(app, 'MemoruCognitoDev', {
  environment: 'dev',
  cognitoDomainPrefix: 'memoru-dev',
  callbackUrls: [
    'http://localhost:3000/callback',
    'https://localhost:3000/callback',
    'https://<CloudFront Domain>/callback',  // ← Step 4 の DistributionDomainName
  ],
  logoutUrls: [
    'http://localhost:3000/',
    'https://localhost:3000/',
    'https://<CloudFront Domain>/',           // ← Step 4 の DistributionDomainName
  ],
});
```

### 7.2 再デプロイ

```bash
cd infrastructure/cdk
npm run build
npx cdk deploy MemoruCognitoDev
```

---

## Step 8: フロントエンドのビルドとデプロイ

### 8.1 環境変数ファイルの作成

```bash
cd frontend
cat > .env.production.local << 'EOF'
VITE_API_BASE_URL=<API Gateway エンドポイント URL>
VITE_LIFF_ID=<LIFF ID>
VITE_OIDC_AUTHORITY=<Cognito OIDC Issuer URL>
VITE_OIDC_CLIENT_ID=<Cognito UserPool Client ID>
EOF
```

各値の例:

```
VITE_API_BASE_URL=https://abc123def4.execute-api.ap-northeast-1.amazonaws.com/dev
VITE_LIFF_ID=1234567890-abcdefgh
VITE_OIDC_AUTHORITY=https://cognito-idp.ap-northeast-1.amazonaws.com/ap-northeast-1_XXXXXXXXX
VITE_OIDC_CLIENT_ID=1abc2defghijk3lmnopq4rst5u
```

> **注意**: `VITE_LIFF_ID` は Step 9 で LIFF アプリ作成後に取得する値。先にダミー値を入れて後から更新するか、Step 9 を先に実施してもよい。

### 8.2 ビルド

```bash
cd frontend
npm install
npm run build
```

### 8.3 S3 にアップロード & CloudFront キャッシュ無効化

Step 4 のデプロイ出力 `DeployCommand` をそのまま実行するか、手動で:

```bash
aws s3 sync dist s3://<BucketName> --delete
aws cloudfront create-invalidation \
  --distribution-id <DistributionId> \
  --paths "/*"
```

### 8.4 デプロイ確認

ブラウザで CloudFront URL（`https://<DistributionDomainName>`）にアクセスし、アプリが表示されることを確認。

---

## Step 9: LINE Developer Console の設定

### 9.1 LIFF アプリの作成

1. [LINE Developers Console](https://developers.line.biz/console/) にアクセス
2. 対象の LINE Login チャネルを選択
3. 「LIFF」タブ → 「追加」
4. 以下を設定:

| 設定項目 | 値 |
|---------|-----|
| LIFF アプリ名 | `Memoru Dev` |
| サイズ | `Full`（推奨） |
| エンドポイント URL | `https://<CloudFront Domain>` |
| Scope | `openid`, `profile` |
| ボットリンク機能 | `On (aggressive)` |

5. 「追加」をクリック
6. 発行された **LIFF ID** をメモ

### 9.2 Messaging API Webhook の設定

1. Messaging API チャネルを選択
2. 「Messaging API」タブ
3. Webhook URL を設定:

```
https://<API Gateway エンドポイント>/webhook/line
```

4. 「Webhookの利用」をオンにする
5. 「検証」ボタンでエンドポイントの疎通を確認

### 9.3 LIFF ID の反映

Step 8 の `.env.production.local` に正しい LIFF ID を設定し、フロントエンドを再ビルド・再デプロイ:

```bash
cd frontend
# .env.production.local の VITE_LIFF_ID を更新
npm run build
aws s3 sync dist s3://<BucketName> --delete
aws cloudfront create-invalidation --distribution-id <DistributionId> --paths "/*"
```

---

## Step 10: Amazon Bedrock モデルアクセスの有効化

AI カード生成・AI 採点機能は Amazon Bedrock の Claude モデルを使用する。

### 10.1 モデルアクセスのリクエスト

1. AWS Management Console → Amazon Bedrock → 「Model access」
2. 「Manage model access」をクリック
3. **Anthropic** → **Claude Haiku** にチェックを入れる
   - 使用モデル: `anthropic.claude-haiku-4-5-20251001-v1:0`
4. 「Request model access」をクリック
5. アクセスが「Access granted」になるのを確認（通常即時）

### 10.2 クロスリージョン推論プロファイルの確認

`template.yaml` のデフォルト `BedrockModelId` は `global.anthropic.claude-haiku-4-5-20251001-v1:0`（クロスリージョン推論プロファイル）を使用している。追加設定は不要だが、もしリージョン固定にしたい場合は `samconfig.toml` の `parameter_overrides` に `BedrockModelId=anthropic.claude-haiku-4-5-20251001-v1:0` を追加する。

---

## Step 10b: （オプション）AgentCore Memory のセットアップ

> **この手順はオプションです。** チューターセッションの会話履歴管理に Bedrock AgentCore Memory を使用する場合のみ実施してください。デフォルトの DynamoDB バックエンドを使う場合はスキップしてください。

### 10b.1 AgentCore Memory の作成

AWS CLI または AWS Management Console から AgentCore Memory を作成する。

```bash
aws bedrock-agentcore create-memory \
  --name "memoru-tutor-dev" \
  --description "Memoru tutor session memory for dev environment" \
  --region ap-northeast-1
```

レスポンスの `memoryId` をメモしておく。

### 10b.2 バックエンドの再デプロイ

`samconfig.toml` の `parameter_overrides` に AgentCore パラメータを追加し、再デプロイする:

```bash
cd backend
# samconfig.toml を編集して TutorSessionBackend=agentcore AgentCoreMemoryId=<memoryId> を追加
make deploy-dev
```

詳細は [Step 6 のオプション: AgentCore Memory を使用する場合](#オプション-agentcore-memory-を使用する場合) を参照。

---

## Step 11: 動作確認

### 11.1 API ヘルスチェック

```bash
# 認証なしエンドポイント（Webhook）が応答するか確認
curl -s -o /dev/null -w "%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{}' \
  <API Gateway エンドポイント>/webhook/line
```

> 400 や 403 が返れば Lambda は動作している（署名検証でリクエストが拒否される）。

### 11.2 Cognito メール認証の確認（テスト用）

```bash
# ユーザー作成
aws cognito-idp admin-create-user \
  --user-pool-id <UserPoolId> \
  --username test@example.com \
  --user-attributes Name=email,Value=test@example.com Name=email_verified,Value=true \
  --temporary-password 'TempPass123!'

# パスワード確定（初回変更を省略）
aws cognito-idp admin-set-user-password \
  --user-pool-id <UserPoolId> \
  --username test@example.com \
  --password 'TestPass123!' \
  --permanent
```

### 11.3 LINE Login 経由の Cognito 認証確認

Step 3 で LINE Login を外部 IdP として設定済みの場合、以下を確認:

1. Cognito Hosted UI にアクセス:
   ```
   https://<cognitoDomainPrefix>.auth.ap-northeast-1.amazoncognito.com/login?client_id=<UserPoolClientId>&response_type=code&scope=openid+profile+email&redirect_uri=https://<CloudFront Domain>/callback
   ```
2. 「LINE でログイン」ボタンが表示されること
3. ボタンをクリック → LINE 認証画面に遷移すること
4. LINE 認証完了後、Cognito がトークンを発行しアプリにリダイレクトされること

> **確認ポイント**: 認証後に Cognito コンソール → 「Users」タブで、LINE IdP 経由のフェデレーテッドユーザーが作成されているか確認する。ユーザー名は `LINE_<LINE ユーザー ID>` のような形式になる。

### 11.4 LIFF アプリの動作確認

1. LINE アプリまたはブラウザで LIFF URL にアクセス:
   ```
   https://liff.line.me/<LIFF ID>
   ```
2. 認証画面が表示され、ログインできることを確認
3. カード一覧画面が表示されることを確認

### 11.5 CloudWatch ログの確認

```bash
# API Function のログ
sam logs -n ApiFunction --stack-name memoru-backend-dev --tail

# Webhook のログ
sam logs -n LineWebhookFunction --stack-name memoru-backend-dev --tail
```

---

## 付録: デプロイ後の値一覧

デプロイ完了後、以下の値を一覧で管理しておくと便利。

| 項目 | 値 | 取得元 |
|------|-----|-------|
| AWS Account ID | | `aws sts get-caller-identity` |
| Cognito User Pool ID | | Step 2 Output |
| Cognito Client ID | | Step 2 Output |
| Cognito OIDC Issuer | | Step 2 Output |
| Cognito Domain URL | | Step 2 Output |
| LINE Login Channel ID | | LINE Developer Console（Step 3 で使用） |
| LINE Login Channel Secret | | LINE Developer Console（Step 3 で使用） |
| S3 Bucket Name | | Step 4 Output |
| CloudFront Distribution ID | | Step 4 Output |
| CloudFront Domain | | Step 4 Output |
| API Gateway Endpoint | | Step 6 Output |
| LINE Messaging Channel Secret | | LINE Developer Console（Step 5 で使用） |
| LINE Channel Access Token | | LINE Developer Console（Step 5 で使用） |
| LIFF ID | | LINE Developer Console（Step 9 で使用） |
| AgentCore Memory ID | | Step 10b（オプション） |

一括確認スクリプト:

```bash
echo "=== Cognito ==="
aws cloudformation describe-stacks --stack-name MemoruCognitoDev \
  --query "Stacks[0].Outputs" --output table

echo "=== LIFF Hosting ==="
aws cloudformation describe-stacks --stack-name MemoruLiffHostingDev \
  --query "Stacks[0].Outputs" --output table

echo "=== Backend ==="
aws cloudformation describe-stacks --stack-name memoru-backend-dev \
  --query "Stacks[0].Outputs" --output table
```

---

## 付録: トラブルシューティング

### CDK Bootstrap が失敗する

```
Error: This stack uses assets, so the toolkit stack must be deployed
```

→ CDK Bootstrap を実行:
```bash
npx cdk bootstrap aws://<ACCOUNT_ID>/ap-northeast-1
```

### Cognito ドメインプレフィックスが重複する

```
Error: Domain already associated with another user pool
```

→ `cognitoDomainPrefix` を一意な値に変更（例: `memoru-dev-<あなたの名前>`）

### SAM build が Docker エラーで失敗する

```
Error: Docker is not reachable
```

→ Docker Desktop が起動しているか確認。起動していれば `docker ps` が動くはず。

### API Gateway が 401 Unauthorized を返す

- Cognito の OIDC Issuer URL が正しいか確認
- `OidcAudience` が Cognito Client ID と一致しているか確認
- JWT トークンの `aud` クレームが API Gateway Authorizer の audience 設定と合っているか確認

### CloudFront が 403 を返す

- S3 バケットにファイルがアップロードされているか確認:
  ```bash
  aws s3 ls s3://<BucketName>/
  ```
- OAC（Origin Access Control）が正しく設定されているか CloudFront コンソールで確認

### Bedrock InvokeModel が AccessDeniedException を返す

- Bedrock コンソールでモデルアクセスが「Access granted」になっているか確認
- Lambda の IAM ポリシーに `bedrock:InvokeModel` が含まれているか確認（SAM template で自動設定済み）

### AgentCore Memory が AccessDeniedException を返す

- `TutorSessionBackend=agentcore` が設定されている場合、SAM テンプレートが自動的に `bedrock-agentcore:*` 系の IAM ポリシーを追加する（`UseAgentCore` Condition による条件付き）
- `AgentCoreMemoryId` が正しい Memory ID であるか確認
- AgentCore Memory が同じリージョン（`ap-northeast-1`）に作成されているか確認

### Cognito Hosted UI に LINE ログインボタンが表示されない

- User Pool Client の「Identity providers」に `LINE` が追加されているか確認（Step 3.5）
- LINE IdP が正しく作成されているか Cognito コンソールの「Sign-in experience」→「Federated identity provider sign-in」で確認
- User Pool Client の Hosted UI 設定が有効になっているか確認

### LINE Login → Cognito 認証後にエラーになる

- LINE Login チャネルのコールバック URL に Cognito の `/oauth2/idpresponse` が登録されているか確認（Step 3.2）
- LINE Login チャネルの Channel ID / Secret が Cognito IdP 設定と一致しているか確認
- LINE Login チャネルで「ウェブアプリ」が有効になっているか確認
- エンドポイント URL が正しいか確認（特に手動入力した場合）

### Cognito が LINE の OIDC Discovery を自動検出できない

LINE は標準の `.well-known/openid-configuration` を提供しない場合がある。Step 3.3 の手動エンドポイント入力で対応すること。

### LINE Login 経由ユーザーの `sub` が想定と異なる

Cognito は LINE からのフェデレーテッドユーザーに対して独自の `sub`（UUID）を生成する。LINE の `sub`（`U` で始まる LINE ユーザー ID）は Cognito のカスタム属性にマッピングされる。バックエンドで `line_user_id` を取得するには、JWT のカスタムクレームまたは `/users/link-line` API の仕組みを確認すること。

> **実装タスクとの関連**: `sub` クレームの扱いとLINEユーザーID自動連携については、別途実装タスクで対応が必要。

### LINE Webhook が検証に失敗する

- Webhook URL が正しいか確認: `https://<API Endpoint>/webhook/line`
- Secrets Manager の `memoru-dev-line-credentials` に正しい `channelSecret` が設定されているか確認
- Lambda がインターネットにアクセスできるか確認（VPC 外で動作するため通常は問題なし）

---

## 付録: コスト概算（dev 環境・月額）

| リソース | 概算 | 備考 |
|----------|------|------|
| Cognito | $0 | MAU 50,000 まで無料 |
| Lambda | $0 | 月 100 万リクエスト + 40 万 GB-秒まで無料 |
| API Gateway | $0 | 月 100 万 API コールまで無料（最初の 12 ヶ月） |
| DynamoDB | $0 | 25 GB ストレージ + 25 WCU/RCU まで無料 |
| S3 | ~$0.03 | 5 GB まで無料（最初の 12 ヶ月） |
| CloudFront | ~$0-1 | 1 TB/月まで無料（最初の 12 ヶ月） |
| Bedrock (Claude Haiku) | ~$0-5 | 従量課金（入力 $0.80/M tokens, 出力 $4/M tokens） |
| Secrets Manager | ~$0.40 | $0.40/シークレット/月 |
| CloudWatch Logs | ~$0-1 | 5 GB まで無料 |
| AgentCore Memory | ~$0 | オプション。使用時は従量課金 |
| **合計** | **~$1-7/月** | 開発用途の軽負荷時 |
