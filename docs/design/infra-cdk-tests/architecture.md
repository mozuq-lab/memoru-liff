# infra-cdk-tests アーキテクチャ設計

**作成日**: 2026-03-03
**関連要件定義**: [requirements.md](../../spec/infra-cdk-tests/requirements.md)
**ヒアリング記録**: [design-interview.md](design-interview.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: 要件定義書・既存コード・ユーザヒアリングを参考にした確実な設計
- 🟡 **黄信号**: 要件定義書・既存コード・ユーザヒアリングから妥当な推測による設計

---

## システム概要 🔵

**信頼性**: 🔵 *要件定義 REQ-001〜REQ-005 より*

CDK スタック (CognitoStack, KeycloakStack, LiffHostingStack) のユニットテストを、Jest + CDK assertions (`aws-cdk-lib/assertions`) で実装する。Snapshot テストで全体の回帰を検知し、Fine-grained assertions でセキュリティ・環境差異・バリデーションを個別検証する。

## テスト戦略 🔵

**信頼性**: 🔵 *ユーザヒアリング「Snapshot + 重要 assertions」方針より*

| 層 | テスト種別 | 目的 | ツール |
|---|---|---|---|
| Snapshot | `toMatchSnapshot()` | 意図しないテンプレート変更の検知 | Jest snapshot |
| Fine-grained | `hasResourceProperties()` | セキュリティ・環境差異の保証 | CDK assertions |
| Validation | `expect(() => ...).toThrow()` | 不正 Props の検知 | Jest |

## テストフレームワーク構成 🔵

**信頼性**: 🔵 *jest.config.js・package.json の既存設定より*

```
infrastructure/cdk/
├── jest.config.js          # Jest 設定 (ts-jest, testMatch: **/*.test.ts)
├── package.json            # jest, ts-jest, @types/jest
├── lib/
│   ├── cognito-stack.ts
│   ├── keycloak-stack.ts
│   └── liff-hosting-stack.ts
└── test/                   # テストディレクトリ (新規作成)
    ├── cognito-stack.test.ts
    ├── keycloak-stack.test.ts
    └── liff-hosting-stack.test.ts
```

## テストファイル設計

### cognito-stack.test.ts 🔵

**信頼性**: 🔵 *REQ-001〜REQ-005、既存 cognito-stack.ts より*

| テストグループ | テスト内容 | 種別 |
|---|---|---|
| Snapshot (dev) | dev Props で synth → Snapshot 一致 | Snapshot |
| Snapshot (prod) | prod Props で synth → Snapshot 一致 | Snapshot |
| 環境差異 | dev: DeletionProtection=false / prod: true | Fine-grained |
| 環境差異 | dev: RemovalPolicy=DESTROY / prod: RETAIN | Fine-grained |
| セキュリティ | パスワードポリシー (minLength=8, 大小英数記号必須) | Fine-grained |
| セキュリティ | MFA OPTIONAL + TOTP | Fine-grained |
| OIDC | OAuth flows: authorizationCodeGrant, scopes | Fine-grained |

### keycloak-stack.test.ts 🔵

**信頼性**: 🔵 *REQ-001〜REQ-005、既存 keycloak-stack.ts より*

| テストグループ | テスト内容 | 種別 |
|---|---|---|
| Snapshot (dev) | dev Props で synth → Snapshot 一致 | Snapshot |
| Snapshot (prod) | prod Props で synth → Snapshot 一致 | Snapshot |
| Validation | prod + certificateArn なし → Error | Validation |
| 環境差異 (VPC) | dev: NatGateways=0 / prod: 1 | Fine-grained |
| 環境差異 (RDS) | dev: MultiAZ=false / prod: true | Fine-grained |
| 環境差異 (RDS) | dev: DeletionProtection=false / prod: true | Fine-grained |
| 環境差異 (ECS) | dev: AssignPublicIp=ENABLED / prod: DISABLED | Fine-grained |
| 環境差異 (Log) | dev: RemovalPolicy=Delete / prod: Retain | Fine-grained |
| セキュリティ | RDS: StorageEncrypted=true, PubliclyAccessible=false | Fine-grained |

### liff-hosting-stack.test.ts 🔵

**信頼性**: 🔵 *REQ-001〜REQ-005、既存 liff-hosting-stack.ts より*

| テストグループ | テスト内容 | 種別 |
|---|---|---|
| Snapshot (dev) | dev Props で synth → Snapshot 一致 | Snapshot |
| Snapshot (prod) | prod Props で synth → Snapshot 一致 | Snapshot |
| Validation | domainName あり + certificateArn なし → Error | Validation |
| Validation | domainName なし → エラーなし | Validation |
| 環境差異 | prod のみ LogBucket が存在 | Fine-grained |
| セキュリティ | S3: BlockPublicAccess=BLOCK_ALL | Fine-grained |
| セキュリティ | S3: BucketEncryption=S3_MANAGED | Fine-grained |
| セキュリティ | CloudFront: SecurityHeaders (HSTS, CSP) | Fine-grained |
| キャッシュ | /assets/* は長期キャッシュ、/index.html はキャッシュ無効 | Fine-grained |

## テスト用 Props 定義 🔵

**信頼性**: 🔵 *既存 app.ts・各 Stack Props インターフェースより*

各テストファイル内にヘルパー関数を定義し、dev/prod の Props を生成する。

```typescript
// 例: keycloak-stack.test.ts
const devProps: KeycloakStackProps = {
  environment: 'dev',
  domainName: 'keycloak-dev.example.com',
};

const prodProps: KeycloakStackProps = {
  environment: 'prod',
  domainName: 'keycloak.example.com',
  hostedZoneName: 'example.com',
  certificateArn: 'arn:aws:acm:ap-northeast-1:123456789012:certificate/test',
  hostedZoneId: 'Z0123456789ABCDEF',
};
```

## CDK assertions パターン 🔵

**信頼性**: 🔵 *CDK v2 公式テストガイドより*

```typescript
import { Template, Match } from 'aws-cdk-lib/assertions';
import * as cdk from 'aws-cdk-lib';

// Snapshot テスト
const template = Template.fromStack(stack);
expect(template.toJSON()).toMatchSnapshot();

// Fine-grained assertions
template.hasResourceProperties('AWS::RDS::DBInstance', {
  StorageEncrypted: true,
  PubliclyAccessible: false,
});

// リソース数カウント
template.resourceCountIs('AWS::S3::Bucket', 1);

// Validation テスト
expect(() => new KeycloakStack(app, 'Test', { environment: 'prod', domainName: 'x' }))
  .toThrow('CertificateArn is required');
```

## 技術的制約 🔵

**信頼性**: 🔵 *既存設定・CDK ドキュメントより*

- `module: "NodeNext"` のため `import` 構文を使用（`require` は非推奨）
- テスト実行コマンド: `cd infrastructure/cdk && npm test`
- Snapshot ファイルは `test/__snapshots__/` に自動生成される

## 関連文書

- **データフロー**: [dataflow.md](dataflow.md)
- **要件定義**: [requirements.md](../../spec/infra-cdk-tests/requirements.md)

## 信頼性レベルサマリー

- 🔵 青信号: 12件 (100%)
- 🟡 黄信号: 0件 (0%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質
