# infra-cdk-tests 要件定義書（軽量版）

## 概要

`infrastructure/cdk/` 配下の CDK スタック (Cognito, Keycloak, LIFF Hosting) にユニットテストを追加する。Snapshot テストで全体の回帰を検知しつつ、セキュリティ・環境差異・バリデーション等の重要プロパティを Fine-grained assertions で個別検証する。

## 関連文書

- **ヒアリング記録**: [interview-record.md](interview-record.md)
- **コンテキストノート**: [note.md](note.md)

## 主要機能要件

**【信頼性レベル凡例】**:
- 🔵 **青信号**: 既存コード・設計文書・ユーザヒアリングを参考にした確実な要件
- 🟡 **黄信号**: 既存コード・設計文書・ユーザヒアリングから妥当な推測による要件
- 🔴 **赤信号**: 推測による要件

### 必須機能（Must Have）

- REQ-001: 各スタック (CognitoStack, KeycloakStack, LiffHostingStack) について dev 環境の Snapshot テストを作成しなければならない 🔵 *ユーザヒアリング「Snapshot + 重要 assertions」方針より*

- REQ-002: 各スタックについて prod 環境の Snapshot テストを作成しなければならない 🔵 *dev/prod で `isProd` による条件分岐があり、両環境のテストが必要*

- REQ-003: 各スタックの dev/prod 環境差異を Fine-grained assertions で検証しなければならない 🔵 *既存コードの `isProd` パターンより。以下を含む:*
  - CognitoStack: `deletionProtection`, `removalPolicy`
  - KeycloakStack: NAT Gateway 数、SubnetType、`multiAz`、`deletionProtection`、`removalPolicy`、LogGroup `removalPolicy`、ECS TaskSubnets、`assignPublicIp`
  - LiffHostingStack: LogBucket 有無 (prod のみ)

- REQ-004: バリデーションロジックのテストを作成しなければならない 🔵 *既存コードの throw new Error パターンより:*
  - KeycloakStack: prod 環境で `certificateArn` 未指定時にエラー
  - LiffHostingStack: `domainName` 指定時に `certificateArn` 未指定でエラー

- REQ-005: セキュリティ関連の設定を Fine-grained assertions で検証しなければならない 🔵 *既存コードより:*
  - S3: `BlockPublicAccess.BLOCK_ALL`, `BucketEncryption.S3_MANAGED`
  - RDS: `storageEncrypted: true`, `publiclyAccessible: false`
  - CloudFront: セキュリティヘッダー (HSTS, CSP, X-Content-Type-Options)
  - Cognito: パスワードポリシー, MFA 設定

### 基本的な制約

- REQ-401: テストは `infrastructure/cdk/test/` ディレクトリに `*.test.ts` ファイルとして配置しなければならない 🔵 *jest.config.js の設定より*

- REQ-402: テストは `npm run test` (`jest`) で実行可能でなければならない 🔵 *package.json の scripts.test より*

- REQ-403: テストは CDK v2 の `assertions` モジュール (`Template`, `Match`) を使用しなければならない 🔵 *CDK v2 標準テストライブラリ*

## 簡易ユーザーストーリー

### ストーリー1: 回帰検知

**私は** CDK 開発者 **として**
**スタック定義の変更時に意図しない CloudFormation テンプレートの変化を検知したい**
**そうすることで** 安全にリファクタリングやプロパティ変更ができる

**関連要件**: REQ-001, REQ-002

### ストーリー2: 環境差異の保証

**私は** CDK 開発者 **として**
**dev/prod の環境差異が設計通りであることを保証したい**
**そうすることで** prod 環境のセキュリティ・可用性設定が dev 変更時に壊れないことを確認できる

**関連要件**: REQ-003, REQ-005

### ストーリー3: バリデーション保証

**私は** CDK 開発者 **として**
**不正な Props 組み合わせでスタック生成時にエラーが発生することを保証したい**
**そうすることで** 実行時の設定ミスを防止できる

**関連要件**: REQ-004

## 基本的な受け入れ基準

### REQ-001, REQ-002: Snapshot テスト

**Given**: 各スタックの Props が適切に設定されている
**When**: `Template.fromStack()` で CloudFormation テンプレートを取得
**Then**: `template.toJSON()` が保存済みスナップショットと一致する

**テストケース**:
- [ ] 正常系: CognitoStack (dev) の Snapshot が一致
- [ ] 正常系: CognitoStack (prod) の Snapshot が一致
- [ ] 正常系: KeycloakStack (dev) の Snapshot が一致
- [ ] 正常系: KeycloakStack (prod) の Snapshot が一致
- [ ] 正常系: LiffHostingStack (dev) の Snapshot が一致
- [ ] 正常系: LiffHostingStack (prod) の Snapshot が一致

### REQ-003: 環境差異の検証

**テストケース**:
- [ ] CognitoStack: dev は DeletionProtection=false, prod は true
- [ ] KeycloakStack: dev は NAT Gateway=0, prod は 1
- [ ] KeycloakStack: dev は multiAz=false, prod は true
- [ ] KeycloakStack: dev は assignPublicIp=true, prod は false
- [ ] LiffHostingStack: prod のみ LogBucket が存在

### REQ-004: バリデーション

**テストケース**:
- [ ] KeycloakStack: prod + certificateArn なしでエラー
- [ ] LiffHostingStack: domainName あり + certificateArn なしでエラー
- [ ] LiffHostingStack: domainName なしでエラーなし

### REQ-005: セキュリティ設定

**テストケース**:
- [ ] S3 バケットの PublicAccess がブロック
- [ ] RDS の暗号化が有効
- [ ] CloudFront にセキュリティヘッダーが設定
- [ ] Cognito のパスワードポリシーが要件を満たす

## 最小限の非機能要件

- **実行速度**: 全テスト 30 秒以内 🟡 *CDK synth ベースのため妥当な推測*
- **メンテナンス性**: Snapshot 更新は `jest --updateSnapshot` で実行可能 🔵 *Jest 標準機能*
