# infra-cdk-tests コンテキストノート

## 技術スタック

### テストフレームワーク
- **Jest** 29.x + **ts-jest** 29.x (既に package.json に設定済み)
- **CDK assertions**: `aws-cdk-lib/assertions` (`Template`, `Match`)
- テストディレクトリ: `infrastructure/cdk/test/` (`jest.config.js` で `<rootDir>/test` 指定)
- テストパターン: `**/*.test.ts`

### CDK プロジェクト構成
- CDK v2 (`aws-cdk-lib` ^2.240.0)
- TypeScript 5.6
- `module: "NodeNext"` / `moduleResolution: "NodeNext"`

## テスト対象スタック

| スタック | ファイル | 主要リソース | 環境差異 |
|---------|---------|-------------|---------|
| CognitoStack | `lib/cognito-stack.ts` | UserPool, UserPoolClient, UserPoolDomain | deletionProtection, removalPolicy |
| KeycloakStack | `lib/keycloak-stack.ts` | VPC, RDS, ECS/Fargate, ALB, SecretsManager, LogGroup | NAT, SubnetType, multiAz, prod証明書必須 |
| LiffHostingStack | `lib/liff-hosting-stack.ts` | S3, CloudFront, CachePolicy, SecurityHeaders | LogBucket(prodのみ), カスタムドメイン |

### 環境差異パターン (`isProd`)
各スタックで `props.environment === 'prod'` による分岐があり、テストで dev/prod 両方を検証する必要がある。

## app.ts の環境フィルタリング
- `-c stage=dev|prod` context で synth 対象を制御
- 未指定時は dev のみ

## バリデーションロジック
- **KeycloakStack**: prod 環境で `certificateArn` 未指定時に `throw new Error`
- **LiffHostingStack**: `domainName` 指定時に `certificateArn` 未指定で `throw new Error`

## 関連ファイル
- `infrastructure/cdk/jest.config.js`: Jest 設定
- `infrastructure/cdk/package.json`: 依存関係
- `infrastructure/cdk/tsconfig.json`: TypeScript 設定
