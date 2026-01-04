# memoru-liff コンテキストノート

**作成日**: 2026-01-05
**PRD**: [requirement.md](../../../requirement.md)

## プロジェクト概要

LINE内で動作する暗記アプリ（SRS: Spaced Repetition System）。LIFF（LINE内Web）でカード入力・閲覧、LINE Messaging APIで復習通知・回答を行う。

## 技術スタック

### 認証基盤
- **Keycloak**: OIDC認証（ECS/Fargate + ALB + ACM構成）
- **LINE Login**: Keycloak Identity Provider経由
- **認証フロー**: Authorization Code + PKCE

### フロントエンド
- **LIFF SDK**: LINE内WebView
- **ホスティング**: CloudFront + S3（HTTPS配信）
- **SPA対応**: カスタムエラーレスポンスでindex.html返却

### バックエンド
- **言語**: Python
- **フレームワーク**: AWS SAM（Serverless Application Model）
- **API Gateway**: REST API with JWT検証（Keycloak issuer）
- **Lambda**: ビジネスロジック実行

### データストア
- **DynamoDB**: カード・学習状態管理
- **RDS PostgreSQL**: Keycloak用DB

### AI機能
- **AgentCore（Strands Agents）**
  - `generate_cards`: テキストからフラッシュカード生成
  - `grade_answer`: 回答採点（拡張機能）

### LINE連携
- **Messaging API**: Webhook、Flex Message、Postback
- **通知ジョブ**: EventBridge Scheduler → Lambda → LINE Push

## 主要データモデル

### users テーブル
- `keycloak_sub` (PK): Keycloak subject
- `line_user_id`: LINE通知先
- `created_at`, `updated_at`

### cards テーブル
- `card_id` (PK): ULID
- `user_id`: 所有者（keycloak_sub）
- `front`, `back`: カード内容
- `source_text`: 生成元テキスト
- `created_at`, `updated_at`

### reviews テーブル
- `review_id` (PK): ULID
- `card_id`: 対象カード
- `due`: 次回復習日（ISO8601）
- `interval`, `ease_factor`, `repetitions`: SRSパラメータ
- `last_review`, `updated_at`

## アーキテクチャ図

```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │ CloudFront  │───▶│     S3      │    │      Keycloak       │  │
│  │   (LIFF)    │    │  (静的資産)  │    │   (ECS/Fargate)     │  │
│  └─────────────┘    └─────────────┘    └─────────────────────┘  │
│                                                │                 │
│  ┌─────────────┐    ┌─────────────┐    ┌──────▼──────────────┐  │
│  │ API Gateway │───▶│   Lambda    │───▶│    DynamoDB         │  │
│  │ (JWT検証)   │    │  (Python)   │    │  (cards/reviews)    │  │
│  └─────────────┘    └─────────────┘    └─────────────────────┘  │
│         │                  │                                     │
│         │           ┌──────▼──────┐                             │
│         │           │  AgentCore  │                             │
│         │           │(Strands/AI) │                             │
│         │           └─────────────┘                             │
│  ┌──────▼──────┐                                                │
│  │  EventBridge│───▶ Lambda ───▶ LINE Messaging API            │
│  │  Scheduler  │    (Push通知)                                  │
│  └─────────────┘                                                │
└─────────────────────────────────────────────────────────────────┘
```

## 実装ステップ（PRDより）

1. **Keycloak ECS/Fargateデプロイ**
2. **Keycloak最小設定（Realm/Client/User）**
3. **LIFF（HTML）+ LIFF SDK + Keycloak OIDC連携**
4. **API Gateway + Lambda + JWT検証**
5. **LINE Identity Provider設定 + 紐づけ**
6. **LINE Webhook + Postback処理**
7. **DynamoDB + SRSロジック**
8. **AgentCore（AI）カード生成**

## 注意事項

- Keycloakは開発初期からAWS（ECS/Fargate）にデプロイ（スマホWebViewからのアクセスのため）
- LINE Webhookでは `line_user_id` からユーザー特定・認可が必要
- SRS日付計算はAIではなくアルゴリズムで実装（SM-2等）
- エラーハンドリング・リトライ戦略の詳細化が必要
