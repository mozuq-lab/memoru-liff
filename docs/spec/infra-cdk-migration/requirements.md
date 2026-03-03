# infra-cdk-migration 要件定義書（軽量版）

## 概要

既存の CloudFormation テンプレート（Keycloak, LIFF Hosting, Cognito）を AWS CDK (TypeScript) に移行する。`backend/template.yaml` は SAM のまま維持する。既存の AWS リソースがデプロイされていないため、移行リスクなく新規構築として対応可能。

## 関連文書

- **ヒアリング記録**: [interview-record.md](interview-record.md)
- **コンテキストノート**: [note.md](note.md)

## 主要機能要件

**【信頼性レベル凡例】**:
- 🔵 **青信号**: ユーザヒアリング・既存テンプレートから確定した要件
- 🟡 **黄信号**: 既存テンプレート・CDK ベストプラクティスから妥当な推測による要件
- 🔴 **赤信号**: 推測による要件

### 必須機能（Must Have）

- REQ-001: CDK プロジェクトを TypeScript で `infrastructure/cdk/` に作成しなければならない 🔵 *ヒアリング Q1, Q2 より*

- REQ-002: 3つの独立した CDK スタック（Keycloak, LIFF Hosting, Cognito）を作成しなければならない 🔵 *ヒアリング Q3, Q5 より*

- REQ-003: Keycloak スタックは既存テンプレートと同等のリソース（VPC, Subnet, NAT Gateway, IGW, SecurityGroup, SecretsManager, RDS PostgreSQL 17, ECS/Fargate, ALB, Route53）を作成しなければならない 🔵 *`infrastructure/keycloak/template.yaml` より。PostgreSQL 17 はユーザ指示により 16 からアップグレード*

- REQ-004: LIFF Hosting スタックは既存テンプレートと同等のリソース（S3, CloudFront + OAC, CachePolicy, SecurityHeaders, Route53）を作成しなければならない 🔵 *`infrastructure/liff-hosting/template.yaml` より*

- REQ-005: Cognito スタックは既存テンプレートと同等のリソース（UserPool, UserPoolDomain, UserPoolClient）を作成しなければならない 🔵 *`infrastructure/cognito/template.yaml` より*

- REQ-006: CDK 完成・動作確認後に旧 CloudFormation テンプレート（`infrastructure/keycloak/template.yaml`, `infrastructure/liff-hosting/template.yaml`, `infrastructure/cognito/template.yaml`）を削除しなければならない 🔵 *ヒアリング Q4 より*

- REQ-007: 各スタックは Environment パラメータ（dev/staging/prod）による環境差異制御を維持しなければならない 🔵 *既存テンプレート共通パラメータより*

- REQ-008: 既存テンプレートの Conditions/Rules（prod 環境での証明書必須、NAT Gateway の prod 限定作成等）と同等の条件分岐を CDK で実装しなければならない 🔵 *既存テンプレートの Conditions/Rules セクションより*

- REQ-009: 各スタックは既存テンプレートと同等の CloudFormation Outputs / Export を出力しなければならない 🔵 *既存テンプレートの Outputs セクションより*

### 基本的な制約

- REQ-010: `backend/template.yaml` の BedrockModelId パラメータのデフォルト値を `global.anthropic.claude-haiku-4-5-20251001-v1:0` に更新しなければならない 🔵 *ユーザ指示より。現在のデフォルト `anthropic.claude-3-haiku-20240307-v1:0` は旧モデル。Global 推論プロファイルを使用*

- REQ-011: `backend/src/services/bedrock.py` の DEFAULT_MODEL_ID を `global.anthropic.claude-haiku-4-5-20251001-v1:0` に更新しなければならない 🔵 *ユーザ指示より。テンプレート・env.json と統一*

### 基本的な制約

- REQ-401: `backend/template.yaml` (SAM) は CDK 移行対象外（BedrockModelId のデフォルト値更新のみ行う） 🔵 *プロジェクト方針・ユーザ指示より*
- REQ-402: CDK は L2 Construct を優先的に使用し、L1 (Cfn*) は必要な場合のみ使用する 🟡 *CDK ベストプラクティスから妥当な推測*
- REQ-403: `infrastructure/keycloak/realm-local.json` と `test-users.json` は移行対象外（ローカル開発用設定ファイル）として残す 🔵 *ヒアリング・ファイル内容より*
- REQ-404: CDK Bootstrap (`cdk bootstrap`) が各 AWS アカウント/リージョンで事前に必要であることをドキュメントに記載する 🟡 *CDK 運用要件から妥当な推測*

## 簡易ユーザーストーリー

### ストーリー1: Keycloak インフラの CDK 化

**私は** インフラ管理者 **として**
**Keycloak の ECS/Fargate + RDS + VPC 構成を CDK で管理したい**
**そうすることで** 型安全な IaC コードで保守・変更がしやすくなる

**関連要件**: REQ-001, REQ-002, REQ-003, REQ-007, REQ-008, REQ-009

### ストーリー2: LIFF ホスティングの CDK 化

**私は** インフラ管理者 **として**
**CloudFront + S3 の静的ホスティングを CDK で管理したい**
**そうすることで** セキュリティヘッダーやキャッシュポリシーの変更が容易になる

**関連要件**: REQ-001, REQ-002, REQ-004, REQ-007, REQ-008, REQ-009

### ストーリー3: Cognito の CDK 化

**私は** インフラ管理者 **として**
**Cognito User Pool を CDK で管理したい**
**そうすることで** User Pool の設定変更が型安全に行える

**関連要件**: REQ-001, REQ-002, REQ-005, REQ-007, REQ-009

## 基本的な受け入れ基準

### REQ-003: Keycloak スタック

**Given（前提条件）**: CDK プロジェクトが初期化されている
**When（実行条件）**: `cdk synth MemoruKeycloakStack` を実行する
**Then（期待結果）**: 既存テンプレートと同等のリソースが CloudFormation テンプレートとして生成される

**テストケース**:
- [ ] 正常系: `cdk synth` でエラーなくテンプレートが生成される
- [ ] 正常系: 生成テンプレートに VPC, Subnet×4, SecurityGroup×3, RDS, ECS/Fargate, ALB が含まれる
- [ ] 正常系: Environment=prod で NAT Gateway, MultiAZ RDS, 証明書必須が有効になる
- [ ] 正常系: Environment=dev で NAT Gateway なし, SingleAZ, HTTP のみが有効になる

### REQ-004: LIFF Hosting スタック

**Given（前提条件）**: CDK プロジェクトが初期化されている
**When（実行条件）**: `cdk synth MemoruLiffHostingStack` を実行する
**Then（期待結果）**: S3 + CloudFront + OAC + セキュリティヘッダーが定義される

**テストケース**:
- [ ] 正常系: S3 バケットに暗号化・パブリックアクセスブロックが設定される
- [ ] 正常系: CloudFront に SPA ルーティング用のエラーレスポンス（403→200, 404→200）が設定される
- [ ] 正常系: カスタムドメインありの場合、Aliases と ACM 証明書が設定される

### REQ-005: Cognito スタック

**Given（前提条件）**: CDK プロジェクトが初期化されている
**When（実行条件）**: `cdk synth MemoruCognitoStack` を実行する
**Then（期待結果）**: UserPool, UserPoolDomain, UserPoolClient が定義される

**テストケース**:
- [ ] 正常系: MFA OPTIONAL + TOTP が設定される
- [ ] 正常系: PKCE (code flow) + public client が設定される
- [ ] 正常系: Output に OIDC Issuer URL と Client ID が含まれる

## 最小限の非機能要件

- **保守性**: L2 Construct の活用で CloudFormation YAML より記述量を削減する 🟡
- **テスト**: `cdk synth` が正常に完了すること。CDK Assertions によるスナップショットテストは任意 🟡
- **セキュリティ**: 既存テンプレートのセキュリティ設定（暗号化、パブリックアクセスブロック、セキュリティグループ等）をすべて維持する 🔵
