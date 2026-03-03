# infra-cdk-migration データフロー図

**作成日**: 2026-03-02
**関連アーキテクチャ**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/infra-cdk-migration/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: 要件定義書・既存テンプレート・ユーザヒアリングを参考にした確実なフロー
- 🟡 **黄信号**: 要件定義書・既存テンプレート・CDK ベストプラクティスから妥当な推測によるフロー
- 🔴 **赤信号**: 推測によるフロー

---

## CDK デプロイフロー 🔵

**信頼性**: 🔵 *CDK 公式ドキュメント・要件定義より*

```mermaid
flowchart TD
    Dev[開発者] -->|cdk synth| Synth[CloudFormation テンプレート生成]
    Synth --> Validate{テンプレート検証}
    Validate -->|OK| Deploy[cdk deploy]
    Validate -->|エラー| Fix[TypeScript コード修正]
    Fix --> Synth

    Deploy --> CFn[CloudFormation]
    CFn --> KC[Keycloak スタック]
    CFn --> LH[LIFF Hosting スタック]
    CFn --> CG[Cognito スタック]

    KC --> VPC[VPC + Subnet]
    KC --> RDS[RDS PostgreSQL 17]
    KC --> ECS[ECS/Fargate + ALB]
    KC --> SM[Secrets Manager]

    LH --> S3[S3 Bucket]
    LH --> CF[CloudFront + OAC]

    CG --> UP[User Pool]
    CG --> UPC[User Pool Client]
```

## スタック間関係 🔵

**信頼性**: 🔵 *既存テンプレートの Export/Import 構成より*

```mermaid
flowchart LR
    subgraph CDK["CDK スタック（独立デプロイ）"]
        KC[Keycloak Stack]
        LH[LIFF Hosting Stack]
        CG[Cognito Stack]
    end

    subgraph SAM["SAM（変更なし）"]
        BE[Backend template.yaml]
    end

    CG -->|OidcIssuerUrl| BE
    CG -->|UserPoolClientId| BE
    LH -->|LiffUrl| BE
    KC -->|KeycloakURL| BE

    style BE fill:#FFE4B5
    style KC fill:#90EE90
    style LH fill:#90EE90
    style CG fill:#90EE90
```

**接続方法**: 各 CDK スタックの CfnOutput を確認し、backend の SAM テンプレートにパラメータとして手動で渡す（既存運用と同じ）。

## 移行前後のフロー比較 🔵

**信頼性**: 🔵 *既存テンプレート構成・CDK 設計より*

### 移行前（CloudFormation 直接）

```mermaid
flowchart LR
    YAML1[keycloak/template.yaml<br/>672行] -->|aws cloudformation deploy| CFn1[CloudFormation]
    YAML2[liff-hosting/template.yaml<br/>358行] -->|aws cloudformation deploy| CFn2[CloudFormation]
    YAML3[cognito/template.yaml<br/>183行] -->|aws cloudformation deploy| CFn3[CloudFormation]
```

### 移行後（CDK）

```mermaid
flowchart LR
    TS1[keycloak-stack.ts] --> App[bin/app.ts]
    TS2[liff-hosting-stack.ts] --> App
    TS3[cognito-stack.ts] --> App

    App -->|cdk synth| CFn[CloudFormation<br/>テンプレート自動生成]
    CFn -->|cdk deploy| AWS[AWS リソース]
```

## 各スタックの内部データフロー

### Keycloak スタック 🔵

**信頼性**: 🔵 *既存テンプレートのリソース依存関係より*

```mermaid
flowchart TD
    subgraph Network
        VPC[ec2.Vpc] --> PubSub[Public Subnet ×2]
        VPC --> PriSub[Private Subnet ×2]
        VPC -->|prod のみ| NAT[NAT Gateway]
    end

    subgraph Security
        SM1[Secret: DB Password]
        SM2[Secret: KC Admin]
    end

    subgraph Database
        PriSub --> RDS[rds.DatabaseInstance<br/>PostgreSQL 17]
        SM1 -->|credentials| RDS
    end

    subgraph Compute
        PubSub --> ALB_ECS[ApplicationLoadBalanced<br/>FargateService]
        RDS -->|JDBC URL| ALB_ECS
        SM1 -->|DB credentials| ALB_ECS
        SM2 -->|Admin credentials| ALB_ECS
    end

    subgraph DNS
        ALB_ECS -->|optional| R53[route53.ARecord]
    end
```

### LIFF Hosting スタック 🔵

**信頼性**: 🔵 *既存テンプレートのリソース依存関係より*

```mermaid
flowchart TD
    subgraph Storage
        S3[s3.Bucket<br/>暗号化・バージョニング有効]
        S3Log[s3.Bucket<br/>ログ用 prod のみ]
    end

    subgraph CDN
        OAC[OAC<br/>自動設定]
        S3 --> OAC --> CF[cloudfront.Distribution]

        CF --> Default[DefaultBehavior<br/>CachingOptimized]
        CF --> Assets[/assets/*<br/>長期キャッシュ]
        CF --> Index[/index.html<br/>キャッシュ無効]
        CF --> SPA[ErrorResponse<br/>403,404 → index.html]
        CF --> Headers[ResponseHeadersPolicy<br/>CSP, HSTS, X-Frame]
    end

    subgraph DNS
        CF -->|optional| R53[route53.ARecord]
    end

    CF -->|prod のみ| S3Log
```

### Cognito スタック 🔵

**信頼性**: 🔵 *既存テンプレートのリソース依存関係より*

```mermaid
flowchart TD
    UP[cognito.UserPool<br/>MFA OPTIONAL + TOTP<br/>email サインイン] --> Domain[UserPoolDomain<br/>Cognito prefix-based]
    UP --> Client[UserPoolClient<br/>Public PKCE<br/>code flow]

    subgraph Outputs
        UP -->|UserPoolId| O1[CfnOutput]
        UP -->|Arn| O2[CfnOutput]
        Client -->|ClientId| O3[CfnOutput]
        UP -->|OIDC Issuer URL| O4[CfnOutput]
        Domain -->|Domain URL| O5[CfnOutput]
    end
```

## デプロイ順序 🟡

**信頼性**: 🟡 *スタック間依存関係から妥当な推測*

各スタックは独立しているため順序に制約はないが、推奨デプロイ順:

1. **Cognito** — backend が OIDC 設定に必要な値を出力
2. **Keycloak** — 認証プロバイダとして先にデプロイ
3. **LIFF Hosting** — フロントエンド配信（API Endpoint を CSP に含めるため backend デプロイ後が望ましい）

```bash
# 推奨デプロイ順
cdk deploy MemoruCognitoDev
cdk deploy MemoruKeycloakDev
cdk deploy MemoruLiffHostingDev
```

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **ヒアリング記録**: [design-interview.md](design-interview.md)
- **要件定義**: [../../spec/infra-cdk-migration/requirements.md](../../spec/infra-cdk-migration/requirements.md)

## 信頼性レベルサマリー

- 🔵 青信号: 8件 (89%)
- 🟡 黄信号: 1件 (11%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質
