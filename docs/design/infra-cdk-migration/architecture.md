# infra-cdk-migration アーキテクチャ設計

**作成日**: 2026-03-02
**関連要件定義**: [requirements.md](../../spec/infra-cdk-migration/requirements.md)
**ヒアリング記録**: [design-interview.md](design-interview.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: 要件定義書・既存テンプレート・ユーザヒアリングを参考にした確実な設計
- 🟡 **黄信号**: 要件定義書・既存テンプレート・CDK ベストプラクティスから妥当な推測による設計
- 🔴 **赤信号**: 推測による設計

---

## システム概要 🔵

**信頼性**: 🔵 *要件定義 REQ-001〜REQ-009、ヒアリングより*

既存の3つの CloudFormation テンプレートを AWS CDK (TypeScript) に移行する。各テンプレートは独立した CDK スタックとして実装し、環境差異は Stack Props パターンで制御する。

## CDK プロジェクト構成 🔵

**信頼性**: 🔵 *要件定義 REQ-001, REQ-002、ヒアリング Q1, Q2 より*

### ディレクトリ構造

```
infrastructure/cdk/
├── bin/
│   └── app.ts                    # CDK App エントリポイント
├── lib/
│   ├── keycloak-stack.ts         # Keycloak スタック (VPC+ECS+RDS+ALB)
│   ├── liff-hosting-stack.ts     # LIFF Hosting スタック (CloudFront+S3)
│   └── cognito-stack.ts          # Cognito スタック (UserPool)
├── test/                         # CDK テスト (任意)
├── cdk.json                      # CDK 設定
├── tsconfig.json                 # TypeScript 設定
└── package.json                  # 依存関係
```

### 依存パッケージ 🔵

**信頼性**: 🔵 *CDK v2 標準構成*

```json
{
  "dependencies": {
    "aws-cdk-lib": "^2",
    "constructs": "^10"
  },
  "devDependencies": {
    "aws-cdk": "^2",
    "typescript": "~5.x"
  }
}
```

`aws-cdk-lib` に必要なモジュールがすべて含まれる（`aws-ec2`, `aws-ecs`, `aws-ecs-patterns`, `aws-rds`, `aws-s3`, `aws-cloudfront`, `aws-cognito` 等）。追加パッケージは不要。

## 環境管理パターン 🔵

**信頼性**: 🔵 *ヒアリング Q1 より確定*

### Stack Props パターン

環境差異は TypeScript の Props インターフェースで型安全に管理する。

```typescript
// 共通の環境型定義
type Environment = 'dev' | 'staging' | 'prod';

// 各スタックの Props に environment を含める
interface KeycloakStackProps extends cdk.StackProps {
  environment: Environment;
  domainName: string;
  certificateArn?: string;  // prod は必須
  hostedZoneId?: string;
  // ... 他のパラメータ
}
```

### bin/app.ts でのインスタンス化

```typescript
const app = new cdk.App();

// dev 環境
new KeycloakStack(app, 'MemoruKeycloakDev', {
  environment: 'dev',
  domainName: 'keycloak-dev.example.com',
});

// prod 環境
new KeycloakStack(app, 'MemoruKeycloakProd', {
  environment: 'prod',
  domainName: 'keycloak.example.com',
  certificateArn: 'arn:aws:acm:...',
  hostedZoneId: 'Z...',
});
```

### CloudFormation Parameters → Stack Props 移行マッピング

| CloudFormation Parameter | CDK Stack Prop | 型 |
|---|---|---|
| `Environment` | `environment` | `'dev' \| 'staging' \| 'prod'` |
| `DomainName` | `domainName` | `string` |
| `CertificateArn` | `certificateArn?` | `string \| undefined` |
| `HostedZoneId` | `hostedZoneId?` | `string \| undefined` |
| `VpcCidr` | `vpcCidr?` | `string` (default: `'10.0.0.0/16'`) |
| `KeycloakImage` | `keycloakImage?` | `string` (default: `'quay.io/keycloak/keycloak:24.0'`) |
| `DBInstanceClass` | `dbInstanceClass?` | `ec2.InstanceType` |
| `CognitoDomainPrefix` | `cognitoDomainPrefix` | `string` |
| `CallbackUrls` | `callbackUrls` | `string[]` |
| `LogoutUrls` | `logoutUrls` | `string[]` |
| `ApiEndpoint` | `apiEndpoint?` | `string` |

## スタック設計

### 1. Keycloak スタック (`keycloak-stack.ts`) 🔵

**信頼性**: 🔵 *既存テンプレート `infrastructure/keycloak/template.yaml` + ヒアリング Q2 より*

**使用する主要 Construct**:

| Construct | 用途 | レベル |
|---|---|---|
| `ec2.Vpc` | VPC + Subnet + NAT Gateway + IGW | L2 |
| `ecs_patterns.ApplicationLoadBalancedFargateService` | ECS Fargate + ALB + SG + LogGroup | L2 (Pattern) |
| `rds.DatabaseInstance` | RDS PostgreSQL 18 | L2 |
| `secretsmanager.Secret` | DB パスワード・Keycloak admin | L2 |
| `route53.ARecord` | DNS レコード | L2 |

**環境差異の制御** (既存 Conditions/Rules → CDK の if 文):

```typescript
// prod: NAT Gateway あり、MultiAZ、証明書必須
const isProd = props.environment === 'prod';

// VPC の NAT Gateway 制御
const vpc = new ec2.Vpc(this, 'Vpc', {
  natGateways: isProd ? 1 : 0,
});

// RDS の MultiAZ 制御
const db = new rds.DatabaseInstance(this, 'Database', {
  engine: rds.DatabaseInstanceEngine.postgres({
    version: rds.PostgresEngineVersion.VER_18,
  }),
  multiAz: isProd,
  deletionProtection: isProd,
});

// prod は証明書必須（TypeScript の型で強制も可能）
if (isProd && !props.certificateArn) {
  throw new Error('CertificateArn is required for prod environment');
}
```

**ApplicationLoadBalancedFargateService の活用**:

```typescript
const service = new ecs_patterns.ApplicationLoadBalancedFargateService(
  this, 'KeycloakService', {
    vpc,
    cluster,
    cpu: 512,
    memoryLimitMiB: 1024,
    desiredCount: 1,
    taskImageOptions: {
      image: ecs.ContainerImage.fromRegistry(props.keycloakImage),
      containerPort: 8080,
      environment: {
        KC_DB: 'postgres',
        KC_DB_URL: `jdbc:postgresql://${db.instanceEndpoint.hostname}:5432/keycloak`,
        KC_PROXY_HEADERS: 'xforwarded',
        KC_HOSTNAME: props.domainName,
        // ...
      },
      secrets: {
        KC_DB_USERNAME: ecs.Secret.fromSecretsManager(dbSecret, 'username'),
        KC_DB_PASSWORD: ecs.Secret.fromSecretsManager(dbSecret, 'password'),
        // ...
      },
    },
    // HTTPS 設定（証明書がある場合）
    certificate: props.certificateArn
      ? acm.Certificate.fromCertificateArn(this, 'Cert', props.certificateArn)
      : undefined,
    protocol: props.certificateArn
      ? elbv2.ApplicationProtocol.HTTPS
      : elbv2.ApplicationProtocol.HTTP,
    redirectHTTP: !!props.certificateArn,
    // ヘルスチェック
    healthCheck: { path: '/health/ready' },
  }
);
```

> この Construct 1つで ALB, TargetGroup, Listener, ECS Service, SecurityGroup, LogGroup が自動生成される。既存テンプレートの約300行が数十行に集約。

### 2. LIFF Hosting スタック (`liff-hosting-stack.ts`) 🔵

**信頼性**: 🔵 *既存テンプレート `infrastructure/liff-hosting/template.yaml` より*

**使用する主要 Construct**:

| Construct | 用途 | レベル |
|---|---|---|
| `s3.Bucket` | 静的ファイル格納 | L2 |
| `cloudfront.Distribution` | CDN 配信 | L2 |
| `cloudfront.S3BucketOrigin` | OAC 付き S3 オリジン | L2 |
| `cloudfront.ResponseHeadersPolicy` | セキュリティヘッダー | L2 |
| `route53.ARecord` | DNS レコード | L2 |

**主要な設計ポイント**:

```typescript
// S3 バケット（L2 Construct のデフォルトで暗号化・パブリックアクセスブロック済み）
const bucket = new s3.Bucket(this, 'LiffBucket', {
  bucketName: `memoru-liff-${props.environment}-${cdk.Aws.ACCOUNT_ID}`,
  removalPolicy: cdk.RemovalPolicy.RETAIN,
  versioned: true,
});

// CloudFront Distribution（S3BucketOrigin で OAC 自動設定）
const distribution = new cloudfront.Distribution(this, 'Distribution', {
  defaultBehavior: {
    origin: origins.S3BucketOrigin.withOriginAccessControl(bucket),
    viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
  },
  // SPA ルーティング
  errorResponses: [
    { httpStatus: 403, responseHttpStatus: 200, responsePagePath: '/index.html' },
    { httpStatus: 404, responseHttpStatus: 200, responsePagePath: '/index.html' },
  ],
  // カスタムドメイン（オプション）
  domainNames: props.domainName ? [props.domainName] : undefined,
  certificate: props.certificateArn
    ? acm.Certificate.fromCertificateArn(this, 'Cert', props.certificateArn)
    : undefined,
});
```

> `S3BucketOrigin.withOriginAccessControl()` により、OAC + バケットポリシーが自動設定される。既存テンプレートで手動定義していた OAC リソースとバケットポリシーが不要に。

### 3. Cognito スタック (`cognito-stack.ts`) 🔵

**信頼性**: 🔵 *既存テンプレート `infrastructure/cognito/template.yaml` より*

**使用する主要 Construct**:

| Construct | 用途 | レベル |
|---|---|---|
| `cognito.UserPool` | ユーザープール | L2 |
| `cognito.UserPoolClient` | アプリクライアント (PKCE) | L2 |
| `cognito.UserPoolDomain` | Cognito ドメイン | L2 |

**主要な設計ポイント**:

```typescript
const userPool = new cognito.UserPool(this, 'UserPool', {
  userPoolName: `memoru-${props.environment}-user-pool`,
  selfSignUpEnabled: true,
  signInAliases: { email: true },
  signInCaseSensitive: false,
  autoVerify: { email: true },
  mfa: cognito.Mfa.OPTIONAL,
  mfaSecondFactor: { sms: false, otp: true },
  passwordPolicy: {
    minLength: 8,
    requireLowercase: true,
    requireUppercase: true,
    requireDigits: true,
    requireSymbols: true,
    tempPasswordValidity: cdk.Duration.days(7),
  },
  accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
  deletionProtection: isProd,
});

const client = userPool.addClient('LiffClient', {
  generateSecret: false,  // Public client (SPA + PKCE)
  oAuth: {
    flows: { authorizationCodeGrant: true },
    scopes: [
      cognito.OAuthScope.OPENID,
      cognito.OAuthScope.PROFILE,
      cognito.OAuthScope.EMAIL,
    ],
    callbackUrls: props.callbackUrls,
    logoutUrls: props.logoutUrls,
  },
  authFlows: { custom: false, userSrp: false },
  accessTokenValidity: cdk.Duration.hours(1),
  idTokenValidity: cdk.Duration.hours(1),
  refreshTokenValidity: cdk.Duration.days(30),
  preventUserExistenceErrors: true,
});
```

## Outputs / Exports 🔵

**信頼性**: 🔵 *既存テンプレートの Outputs セクション・REQ-009 より*

各スタックは既存テンプレートと同等の CloudFormation Outputs を `CfnOutput` で出力する。

### Keycloak スタック

| Output | Export 名 | 値 |
|---|---|---|
| VpcId | `memoru-{env}-vpc-id` | VPC ID |
| KeycloakURL | — | `https://{domain}` or `http://{alb-dns}` |
| ALBDNSName | `memoru-{env}-keycloak-alb-dns` | ALB DNS 名 |
| RDSEndpoint | `memoru-{env}-keycloak-db-endpoint` | RDS エンドポイント |
| ECSClusterArn | `memoru-{env}-keycloak-cluster-arn` | ECS クラスター ARN |

### LIFF Hosting スタック

| Output | Export 名 | 値 |
|---|---|---|
| BucketName | `memoru-{env}-liff-bucket` | S3 バケット名 |
| DistributionId | `memoru-{env}-liff-distribution-id` | CloudFront Distribution ID |
| LiffUrl | `memoru-{env}-liff-url` | LIFF アプリ URL |
| DeployCommand | — | S3 sync + CloudFront invalidation コマンド |

### Cognito スタック

| Output | Export 名 | 値 |
|---|---|---|
| UserPoolId | `memoru-{env}-cognito-user-pool-id` | User Pool ID |
| UserPoolClientId | `memoru-{env}-cognito-client-id` | Client ID |
| OidcIssuerUrl | `memoru-{env}-cognito-oidc-issuer` | OIDC Issuer URL |
| CognitoDomainUrl | `memoru-{env}-cognito-domain-url` | Cognito ドメイン URL |

## backend 変更（CDK 移行対象外）🔵

**信頼性**: 🔵 *ユーザ指示 REQ-010, REQ-011 より*

CDK 移行とあわせて以下のバージョン更新を行う:

| ファイル | 変更箇所 | 変更前 | 変更後 |
|---|---|---|---|
| `backend/template.yaml` | `BedrockModelId` Default | `anthropic.claude-3-haiku-20240307-v1:0` | `global.anthropic.claude-haiku-4-5-20251001-v1:0` |
| `backend/src/services/bedrock.py` | `DEFAULT_MODEL_ID` | `anthropic.claude-3-haiku-20240307-v1:0` | `global.anthropic.claude-haiku-4-5-20251001-v1:0` |

## 技術的制約 🔵

**信頼性**: 🔵 *CDK 公式ドキュメント・プロジェクト構成より*

- CDK Bootstrap が各 AWS アカウント/リージョンで事前に必要
- `backend/template.yaml` は SAM のまま維持（CDK 移行対象外）
- CloudFront 用 ACM 証明書は `us-east-1` リージョンで作成が必要（CDK でも変わらない）
- `ApplicationLoadBalancedFargateService` は `--optimized` フラグをコマンドに含める場合 `command` プロパティで指定

## 関連文書

- **データフロー**: [dataflow.md](dataflow.md)
- **ヒアリング記録**: [design-interview.md](design-interview.md)
- **要件定義**: [../../spec/infra-cdk-migration/requirements.md](../../spec/infra-cdk-migration/requirements.md)
- **コンテキストノート**: [../../spec/infra-cdk-migration/note.md](../../spec/infra-cdk-migration/note.md)

## 信頼性レベルサマリー

- 🔵 青信号: 14件 (93%)
- 🟡 黄信号: 1件 (7%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質
