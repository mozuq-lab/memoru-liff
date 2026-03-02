# infra-cdk-migration 設計ヒアリング記録

**作成日**: 2026-03-02
**ヒアリング実施**: step4 既存情報ベースの差分ヒアリング

## ヒアリング目的

CDK 移行の技術設計にあたり、CDK 固有の設計方針（環境管理方法、Construct レベル）を明確化するためのヒアリングを実施しました。

## 質問と回答

### Q1: 環境別設定の管理方法

**カテゴリ**: アーキテクチャ
**背景**: CDK では環境差異の制御に Stack Props（TypeScript の型付きプロパティ）と CDK Context（cdk.json / -c フラグ）の2つのアプローチがある。既存テンプレートは CloudFormation Parameters で制御しているため、CDK でどちらに移行するか確認が必要。

**回答**: Stack Props

**信頼性への影響**:
- アーキテクチャ設計の環境管理方式が 🔵 に確定
- bin/app.ts で環境ごとにスタックをインスタンス化する設計が確定

---

### Q2: Keycloak スタックの ECS+ALB 構成の Construct レベル

**カテゴリ**: 技術選択
**背景**: CDK の `ecs-patterns` モジュールには `ApplicationLoadBalancedFargateService` という高レベル Construct があり、ALB + ECS + SecurityGroup + LogGroup をまとめて作成できる。一方、個別の L2 Construct を組み合わせる方法もある。

**回答**: 高レベル Construct（ApplicationLoadBalancedFargateService）

**信頼性への影響**:
- Keycloak スタックの ECS 構成設計が 🔵 に確定
- 記述量が大幅に削減される見込み

---

## ヒアリング結果サマリー

### 確認できた事項

- 環境管理: Stack Props パターン（bin/app.ts で環境ごとにインスタンス化）
- ECS 構成: `ApplicationLoadBalancedFargateService` を使用
- 両方とも CDK のベストプラクティスに沿った選択

### 設計方針の決定事項

- 環境差異は TypeScript の型システムで管理（CloudFormation Parameters → Stack Props）
- Keycloak の ALB+ECS は `ecs-patterns` の高レベル Construct で簡潔に記述
- LIFF Hosting は `aws-cdk-lib/aws-cloudfront` + `aws-s3` の L2 Construct を使用
- Cognito は `aws-cdk-lib/aws-cognito` の L2 Construct を使用

### 残課題

- なし（主要な設計方針はすべて確定）

### 信頼性レベル分布

**ヒアリング前**:
- 🔵 青信号: 0件
- 🟡 黄信号: 2件
- 🔴 赤信号: 0件

**ヒアリング後**:
- 🔵 青信号: 2件 (+2)
- 🟡 黄信号: 0件 (-2)
- 🔴 赤信号: 0件

## 関連文書

- **アーキテクチャ設計**: [architecture.md](architecture.md)
- **データフロー**: [dataflow.md](dataflow.md)
- **要件定義**: [../../spec/infra-cdk-migration/requirements.md](../../spec/infra-cdk-migration/requirements.md)
