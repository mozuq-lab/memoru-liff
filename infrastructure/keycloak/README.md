# Keycloak ECS/Fargate Infrastructure

Memoru LIFF アプリケーション用の Keycloak 認証基盤インフラストラクチャ。

## アーキテクチャ概要

```
┌─────────────────────────────────────────────────────────────┐
│                          VPC                                 │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Public Subnets (2 AZs)                   │  │
│  │  ┌─────────────┐              ┌─────────────┐         │  │
│  │  │     ALB     │◄────HTTPS───►│  Internet   │         │  │
│  │  │   (HTTPS)   │              │   Gateway   │         │  │
│  │  └──────┬──────┘              └─────────────┘         │  │
│  │         │                           ▲                 │  │
│  │         │                     NAT Gateway             │  │
│  └─────────┼─────────────────────────────────────────────┘  │
│            │                                                 │
│  ┌─────────┼─────────────────────────────────────────────┐  │
│  │         ▼         Private Subnets (2 AZs)             │  │
│  │  ┌─────────────┐              ┌─────────────┐         │  │
│  │  │ ECS Fargate │─────────────►│     RDS     │         │  │
│  │  │  Keycloak   │              │  PostgreSQL │         │  │
│  │  └─────────────┘              └─────────────┘         │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## ローカル開発環境（Docker）

LINE 環境なしでも認証フローの動作確認ができるよう、Keycloak を Docker で起動できます。

### 構成ファイル

| ファイル | 用途 |
|---------|------|
| `realm-export.json` | 本番/ステージング用 realm 設定（LINE IdP あり） |
| `realm-local.json` | ローカル開発用 realm 設定（LINE IdP なし、テストユーザー付き） |
| `test-users.json` | テストユーザー定義（realm-local.json に統合済み） |

### ローカル Keycloak 起動

```bash
cd backend

# Keycloak のみ起動
make local-keycloak

# DynamoDB + Keycloak をまとめて起動
make local-all
```

- Keycloak: http://localhost:8180
- 管理コンソール: http://localhost:8180/admin（admin / admin）
- OIDC ディスカバリ: http://localhost:8180/realms/memoru/.well-known/openid-configuration

### realm-local.json の主な変更点（realm-export.json との差分）

- `sslRequired`: `"external"` → `"none"`（localhost は HTTP）
- `loginWithEmailAllowed`: `true`（メールでもログイン可能）
- `directAccessGrantsEnabled`: `true`（Resource Owner Password Grant 有効）
- `identityProviders`: LINE IdP を削除
- `users`: テストユーザーを組み込み（Keycloak 起動時に自動作成）
- `clientScopes`: `profile`、`email` スコープを明示的に定義（realm インポート時に組み込みスコープが自動作成されないため）
- `components`: 空（Keycloak 24.0 のデフォルトに任せる）

---

## AWS デプロイ

### 前提条件

- AWS CLI v2 がインストールされていること
- 適切な AWS 認証情報が設定されていること
- (本番環境) ACM 証明書が事前に作成されていること
- (本番環境) Route53 ホストゾーンが存在すること

## クイックスタート（開発環境）

### 1. パラメータファイルの編集

```bash
# 開発環境用パラメータを編集
vi parameters-dev.json
```

### 2. スタックのデプロイ

```bash
# 開発環境へデプロイ
aws cloudformation deploy \
  --stack-name memoru-dev-keycloak \
  --template-file template.yaml \
  --parameter-overrides file://parameters-dev.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-northeast-1

# デプロイ状況の確認
aws cloudformation describe-stacks \
  --stack-name memoru-dev-keycloak \
  --query 'Stacks[0].StackStatus' \
  --region ap-northeast-1
```

### 3. 出力値の確認

```bash
# スタック出力の確認
aws cloudformation describe-stacks \
  --stack-name memoru-dev-keycloak \
  --query 'Stacks[0].Outputs' \
  --region ap-northeast-1
```

## 本番環境デプロイ

### 1. ACM 証明書の作成（事前準備）

```bash
# ACM 証明書のリクエスト
aws acm request-certificate \
  --domain-name keycloak.your-domain.com \
  --validation-method DNS \
  --region ap-northeast-1

# DNS 検証レコードを Route53 に追加後、証明書 ARN を取得
aws acm list-certificates \
  --query 'CertificateSummaryList[?DomainName==`keycloak.your-domain.com`].CertificateArn' \
  --region ap-northeast-1
```

### 2. パラメータファイルの更新

```bash
# parameters-prod.json を編集
# - DomainName: 実際のドメイン名
# - HostedZoneId: Route53 ホストゾーン ID
# - CertificateArn: 上記で取得した証明書 ARN
```

### 3. 本番デプロイ

```bash
aws cloudformation deploy \
  --stack-name memoru-prod-keycloak \
  --template-file template.yaml \
  --parameter-overrides file://parameters-prod.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-northeast-1
```

## Keycloak 初期設定

### 管理者パスワードの取得

```bash
# Secrets Manager から管理者パスワードを取得
aws secretsmanager get-secret-value \
  --secret-id memoru-dev-keycloak-admin-secret \
  --query 'SecretString' \
  --output text \
  --region ap-northeast-1 | jq -r '.password'
```

### 管理コンソールへのアクセス

1. ALB DNS 名または設定したドメインにアクセス
2. 管理者ユーザー名: `admin`（または設定した値）
3. 上記で取得したパスワードでログイン
4. `/admin` パスで管理コンソールにアクセス

## リソース一覧

| リソース | 説明 | 開発環境 | 本番環境 |
|---------|------|---------|---------|
| VPC | 仮想ネットワーク | 10.0.0.0/16 | 10.0.0.0/16 |
| Subnets | パブリック2 + プライベート2 | 2 AZ | 2 AZ |
| NAT Gateway | プライベートサブネット用 | 1 | 1 |
| ALB | ロードバランサー | HTTP | HTTPS |
| ECS Cluster | コンテナ実行環境 | Fargate | Fargate |
| ECS Task | Keycloak コンテナ | 0.5 vCPU / 1GB | 0.5 vCPU / 1GB |
| RDS | PostgreSQL 15 | db.t3.micro / 20GB | db.t3.small / 50GB |
| Security Groups | ネットワークセキュリティ | 3 | 3 |
| Secrets Manager | 認証情報管理 | 2 | 2 |

## コスト見積もり（東京リージョン）

### 開発環境（月額概算）
- NAT Gateway: ~$35
- ALB: ~$18
- ECS Fargate (0.5 vCPU, 1GB): ~$15
- RDS db.t3.micro: ~$15
- その他（Secrets Manager, CloudWatch）: ~$5
- **合計: 約 $90/月**

### 本番環境（月額概算）
- NAT Gateway: ~$35
- ALB: ~$18
- ECS Fargate: ~$15
- RDS db.t3.small (Multi-AZ): ~$50
- その他: ~$10
- **合計: 約 $130/月**

## トラブルシューティング

### ECS タスクが起動しない

```bash
# タスクの状態を確認
aws ecs describe-services \
  --cluster memoru-dev-keycloak-cluster \
  --services memoru-dev-keycloak-service \
  --region ap-northeast-1

# 停止したタスクの理由を確認
aws ecs describe-tasks \
  --cluster memoru-dev-keycloak-cluster \
  --tasks $(aws ecs list-tasks --cluster memoru-dev-keycloak-cluster --desired-status STOPPED --query 'taskArns[0]' --output text) \
  --region ap-northeast-1
```

### RDS 接続エラー

```bash
# セキュリティグループの確認
aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=memoru-dev-keycloak-*" \
  --query 'SecurityGroups[*].[GroupName,GroupId]' \
  --region ap-northeast-1
```

### CloudWatch ログの確認

```bash
# Keycloak のログを確認
aws logs tail /ecs/memoru-dev-keycloak \
  --follow \
  --region ap-northeast-1
```

## スタックの削除

```bash
# 開発環境の削除
aws cloudformation delete-stack \
  --stack-name memoru-dev-keycloak \
  --region ap-northeast-1

# 削除完了まで待機
aws cloudformation wait stack-delete-complete \
  --stack-name memoru-dev-keycloak \
  --region ap-northeast-1
```

**注意**: RDS は削除保護が有効な場合、手動で無効化が必要です。また、スナップショットが自動作成されます。

## Realm/Client 設定（TASK-0002）

### Realm インポート

Keycloak が起動したら、管理コンソールから Realm をインポートします。

```bash
# 1. 管理コンソールにログイン
# URL: https://<keycloak-domain>/admin

# 2. 左上のドロップダウンから "Create realm" を選択

# 3. "Browse..." をクリックして realm-export.json を選択

# 4. "Create" をクリック
```

### LINE Login 設定

LINE Identity Provider を有効にするには、LINE Developers Console での設定が必要です。

1. [LINE Developers Console](https://developers.line.biz/) にアクセス
2. Provider を作成または選択
3. LINE Login Channel を作成
4. Callback URL を設定:
   ```
   https://<keycloak-domain>/realms/memoru/broker/line/endpoint
   ```
5. Channel ID と Channel Secret を取得

### 環境変数の設定

LINE Identity Provider の認証情報を Secrets Manager に登録：

```bash
# LINE Channel 認証情報を登録
aws secretsmanager create-secret \
  --name memoru-dev-line-credentials \
  --secret-string '{"channelId":"YOUR_CHANNEL_ID","channelSecret":"YOUR_CHANNEL_SECRET"}' \
  --region ap-northeast-1
```

### Keycloak CLI でのインポート（代替方法）

```bash
# Keycloak Admin CLI を使用してインポート
docker run --rm \
  -v $(pwd)/realm-export.json:/tmp/realm-export.json \
  quay.io/keycloak/keycloak:24.0 \
  /opt/keycloak/bin/kc.sh import \
  --file /tmp/realm-export.json \
  --override false
```

### 設定確認チェックリスト

- [ ] memoru Realm が作成されている
- [ ] liff-client (Public Client) が作成されている
- [ ] PKCE (S256) が有効になっている
- [ ] LINE Identity Provider が設定されている
- [ ] memoru-scope にカスタムマッパーが設定されている
- [ ] テストユーザーでログインできる

### テストユーザー

開発環境では `test-users.json` を参照してテストユーザーを作成できます：

| ユーザー名 | メール | パスワード | ロール |
|-----------|--------|-----------|-------|
| test-user | test@example.com | test-password-123 | user |
| test-admin | admin@example.com | admin-password-123 | user, admin |

**注意**: 本番環境ではこれらのテストユーザーを削除してください。

## 関連ドキュメント

- [Keycloak 公式ドキュメント](https://www.keycloak.org/documentation)
- [AWS ECS on Fargate](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)
- [設計文書: architecture.md](../../docs/design/memoru-liff/architecture.md)
