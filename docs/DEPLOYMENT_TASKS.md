# Memoru LIFF デプロイ作業リスト

**作成日**: 2026-01-05
**対象者**: プロジェクトオーナー（手動作業担当）

---

## 概要

コード実装は完了しています。本番稼働に向けて以下の手動作業が必要です。

### 作業フロー

```
[1. AWS基盤構築] → [2. Keycloak設定] → [3. LINE設定] → [4. GitHub設定] → [5. 動作確認]
                                                                              ↓
                                                              [Claude Codeに依頼: 最終調整]
```

---

## 1. AWS基盤構築

### 1.1 Keycloak ECS/Fargate デプロイ

**場所**: `infrastructure/keycloak/`

```bash
cd infrastructure/keycloak
make deploy-dev  # 開発環境
# または
make deploy-prod  # 本番環境
```

**確認事項**:
- [ ] ECSクラスターが作成されている
- [ ] Fargateタスクが起動している
- [ ] ALBエンドポイントにアクセスできる
- [ ] Keycloak管理画面が表示される

### 1.2 CloudFront + S3 デプロイ

**場所**: `infrastructure/liff-hosting/`

```bash
cd infrastructure/liff-hosting
make deploy-dev  # 開発環境
```

**確認事項**:
- [ ] S3バケットが作成されている
- [ ] CloudFrontディストリビューションが作成されている
- [ ] CloudFront URLにアクセスできる

### 1.3 バックエンド SAM デプロイ

**場所**: `backend/`

```bash
cd backend
sam build
sam deploy --config-env dev
```

**確認事項**:
- [ ] Lambda関数が3つ作成されている（API, Webhook, DuePush）
- [ ] API Gatewayエンドポイントが作成されている
- [ ] DynamoDBテーブルが3つ作成されている

**出力値をメモ**:
- API Gateway URL: `https://xxxxxx.execute-api.ap-northeast-1.amazonaws.com/dev`

---

## 2. Keycloak 設定

### 2.1 Realm 作成

1. Keycloak管理画面にログイン
2. 新規Realm「memoru」を作成

### 2.2 Client 設定

1. Clients → Create client
2. 設定値:
   - Client ID: `memoru-liff`
   - Client Protocol: `openid-connect`
   - Access Type: `public`
   - Valid Redirect URIs:
     - `https://liff.line.me/*`
     - `http://localhost:5173/*`
     - `http://localhost:3000/*`
   - Web Origins:
     - `https://liff.line.me`
     - `http://localhost:5173`
     - `http://localhost:3000`
   - Standard Flow Enabled: `ON`
   - Direct Access Grants Enabled: `OFF`

### 2.3 LINE Identity Provider 設定

1. Identity Providers → Add provider → LINE
2. LINE Developer Consoleから取得した値を設定:
   - Client ID: (LINE Channel ID)
   - Client Secret: (LINE Channel Secret)
   - Default Scopes: `profile openid`

**確認事項**:
- [ ] Realm「memoru」が存在する
- [ ] Client「memoru-liff」が設定されている
- [ ] LINE Identity Providerが設定されている

**出力値をメモ**:
- Keycloak Issuer URL: `https://your-keycloak-domain/realms/memoru`

---

## 3. LINE Developer Console 設定

### 3.1 LINE Login チャネル

1. LINE Developers (https://developers.line.biz/) にログイン
2. プロバイダー作成（未作成の場合）
3. LINE Loginチャネル作成
   - チャネル名: `Memoru`
   - チャネル説明: 暗記カードアプリ

4. 設定:
   - Callback URL: Keycloakの callback URL
     - `https://your-keycloak-domain/realms/memoru/broker/line/endpoint`

**出力値をメモ**:
- Channel ID: `xxxxxxxxxx`
- Channel Secret: `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### 3.2 Messaging API チャネル

1. Messaging APIチャネル作成
   - チャネル名: `Memoru Bot`

2. Webhook設定:
   - Webhook URL: `https://your-api-gateway-url/webhook/line`
   - Webhook有効化: ON
   - 応答メッセージ: OFF
   - あいさつメッセージ: OFF

**出力値をメモ**:
- Channel Access Token: (長いトークン)
- Channel Secret: `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### 3.3 LIFF アプリ作成

1. LINE Login チャネル内でLIFFアプリ追加
2. 設定:
   - LIFF app name: `Memoru`
   - Size: `Full`
   - Endpoint URL: `https://your-cloudfront-url`
   - Scopes: `profile`, `openid`
   - Bot link feature: `On (Aggressive)`

**出力値をメモ**:
- LIFF ID: `0000000000-xxxxxxxx`
- LIFF URL: `https://liff.line.me/0000000000-xxxxxxxx`

---

## 4. Secrets Manager 設定

AWS Secrets Managerに以下のシークレットを作成:

### 4.1 LINE認証情報

**シークレット名**: `memoru-dev-line-credentials`

```json
{
  "channel_secret": "LINE Messaging API Channel Secret",
  "channel_access_token": "LINE Messaging API Channel Access Token"
}
```

**作成コマンド**:
```bash
aws secretsmanager create-secret \
  --name memoru-dev-line-credentials \
  --secret-string '{"channel_secret":"xxx","channel_access_token":"xxx"}'
```

**確認事項**:
- [ ] シークレットが作成されている
- [ ] Lambda関数がシークレットにアクセスできる

---

## 5. GitHub リポジトリ設定

### 5.1 OIDC認証用IAMロール作成

GitHub ActionsがAWSにデプロイするためのIAMロールを作成:

```bash
# CloudFormationまたはコンソールで作成
# 信頼ポリシー例:
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR_ORG/memoru-liff:*"
        }
      }
    }
  ]
}
```

### 5.2 GitHub Secrets 設定

Repository Settings → Secrets and variables → Actions

**Secrets**:
| Name | Value |
|------|-------|
| `AWS_DEPLOY_ROLE_ARN` | IAMロールのARN |

### 5.3 GitHub Variables 設定 (環境別)

Environments → `dev` を作成 → Variables

| Name | Value |
|------|-------|
| `API_URL` | API Gateway URL |
| `LIFF_ID` | LIFF ID |
| `KEYCLOAK_URL` | Keycloak URL |
| `KEYCLOAK_REALM` | `memoru` |
| `KEYCLOAK_CLIENT_ID` | `memoru-liff` |
| `FRONTEND_BUCKET` | S3バケット名 |
| `CLOUDFRONT_DISTRIBUTION_ID` | CloudFront ID |

**確認事項**:
- [ ] IAMロールが作成されている
- [ ] GitHub Secretsが設定されている
- [ ] GitHub Variablesが環境別に設定されている

---

## 6. フロントエンド環境変数設定

### 6.1 ローカル開発用

`frontend/.env.local` を作成:

```env
VITE_API_URL=https://your-api-gateway-url
VITE_LIFF_ID=0000000000-xxxxxxxx
VITE_KEYCLOAK_URL=https://your-keycloak-domain
VITE_KEYCLOAK_REALM=memoru
VITE_KEYCLOAK_CLIENT_ID=memoru-liff
```

---

## 7. 動作確認

### 7.1 バックエンド確認

```bash
# API Gateway エンドポイントにアクセス
curl https://your-api-gateway-url/users/me \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 7.2 フロントエンド確認

```bash
cd frontend
npm run dev
# ブラウザで http://localhost:5173 にアクセス
```

### 7.3 LINE連携確認

1. LIFFアプリURL（`https://liff.line.me/xxxx`）をLINEで開く
2. ログインフローが動作することを確認
3. カード作成・復習が動作することを確認

**確認事項**:
- [ ] LIFF内でアプリが表示される
- [ ] LINE Loginでログインできる
- [ ] APIが正常に動作する
- [ ] カード作成・復習が動作する

---

## 8. Claude Code への依頼タイミング

以下の状況で Claude Code に依頼してください：

### 8.1 設定値の反映が必要な場合

**タイミング**: 上記手順完了後

**依頼内容**:
```
以下の設定値でフロントエンドの環境変数を更新してください：
- API_URL: https://xxxxx.execute-api.ap-northeast-1.amazonaws.com/dev
- LIFF_ID: 0000000000-xxxxxxxx
- KEYCLOAK_URL: https://your-keycloak-domain
```

### 8.2 エラーが発生した場合

**タイミング**: 動作確認でエラーが発生した場合

**依頼内容**:
```
以下のエラーが発生しています。修正をお願いします：
[エラー内容をコピー]
```

### 8.3 追加機能が必要な場合

**タイミング**: MVP完成後

**依頼例**:
- 「カードのタグ機能を追加してください」
- 「復習履歴のグラフを表示したい」
- 「複数言語対応をお願いします」

---

## チェックリストサマリー

### AWS
- [ ] Keycloak ECS/Fargate デプロイ完了
- [ ] CloudFront + S3 デプロイ完了
- [ ] SAM バックエンドデプロイ完了
- [ ] Secrets Manager シークレット作成完了

### 外部サービス
- [ ] Keycloak Realm/Client 設定完了
- [ ] LINE Login チャネル作成完了
- [ ] LINE Messaging API チャネル作成完了
- [ ] LIFF アプリ作成完了

### GitHub
- [ ] OIDC認証用IAMロール作成完了
- [ ] GitHub Secrets 設定完了
- [ ] GitHub Variables 設定完了

### 動作確認
- [ ] バックエンドAPI動作確認
- [ ] フロントエンド動作確認
- [ ] LINE連携動作確認

---

## トラブルシューティング

### よくある問題

1. **CORS エラー**
   - API Gateway の CORS 設定を確認
   - CloudFront のオリジン設定を確認

2. **認証エラー**
   - Keycloak の Client 設定を確認
   - JWT Issuer URL が正しいか確認

3. **LINE Webhook エラー**
   - Webhook URL が正しいか確認
   - Channel Secret が Secrets Manager に設定されているか確認

4. **LIFF エラー**
   - LIFF ID が正しいか確認
   - Endpoint URL が正しいか確認

---

**作業完了後、Claude Code に「動作確認が完了しました」とお知らせください。**
