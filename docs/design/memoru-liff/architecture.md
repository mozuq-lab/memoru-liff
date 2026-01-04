# memoru-liff アーキテクチャ設計

**作成日**: 2026-01-05
**関連要件定義**: [requirements.md](../../spec/memoru-liff/requirements.md)

**【信頼性レベル凡例】**:

- 🔵 **青信号**: EARS要件定義書・設計文書・ユーザヒアリングを参考にした確実な設計
- 🟡 **黄信号**: EARS要件定義書・設計文書・ユーザヒアリングから妥当な推測による設計
- 🔴 **赤信号**: EARS要件定義書・設計文書・ユーザヒアリングにない推測による設計

---

## システム概要 🔵

**信頼性**: 🔵 *PRD・要件定義書より*

LINE内で動作する暗記アプリ（SRS: Spaced Repetition System）。以下の特徴を持つ：

- **LIFF（LINE内Web）** でカード入力・閲覧
- **LINE Messaging API** で復習通知・回答
- **Keycloak（OIDC）** を認証基盤として使用
- **Amazon Bedrock** を活用したAIカード生成
- **AWS サーバーレス** アーキテクチャで構築

---

## アーキテクチャパターン 🔵

**信頼性**: 🔵 *PRD技術選定より*

- **パターン**: サーバーレスアーキテクチャ（AWS Lambda + API Gateway + DynamoDB）
- **選択理由**:
  - スケーラビリティ（自動スケーリング）
  - コスト効率（従量課金）
  - 運用負荷軽減（インフラ管理不要）
  - AWS SAM による IaC

---

## コンポーネント構成

### フロントエンド 🔵

**信頼性**: 🔵 *PRD・要件定義より*

| 項目 | 選定技術 | 理由 |
|------|----------|------|
| フレームワーク | React + Vite | 軽量SPA、LIFF SDK との親和性 |
| 認証ライブラリ | oidc-client-ts | PKCE対応、Keycloak連携 |
| LINE SDK | LIFF SDK | LINE WebView内での動作必須 |
| ホスティング | CloudFront + S3 | HTTPS必須、低コスト |
| 状態管理 | React Context | 軽量、MVP向け |

### バックエンド 🔵

**信頼性**: 🔵 *PRD・要件定義より*

| 項目 | 選定技術 | 理由 |
|------|----------|------|
| 言語 | Python 3.12 | PRD指定、AI連携の親和性 |
| フレームワーク | AWS SAM | サーバーレス標準、IaC |
| API | API Gateway (REST) | JWT検証、レート制限対応 |
| ランタイム | Lambda | サーバーレス、自動スケール |
| AI連携 | Amazon Bedrock | PRD指定、Strands Agents |

### 認証基盤 🔵

**信頼性**: 🔵 *PRD・要件定義より*

| 項目 | 選定技術 | 理由 |
|------|----------|------|
| IdP | Keycloak | PRD指定、OIDC標準 |
| デプロイ | ECS/Fargate + ALB | スマホWebViewからのアクセス対応 |
| TLS終端 | ALB + ACM | HTTPS必須 |
| DB | RDS PostgreSQL | Keycloak標準対応 |
| 認証フロー | Authorization Code + PKCE | SPA向けセキュア認証 |

### データストア 🔵

**信頼性**: 🔵 *PRD・要件定義より*

| 項目 | 選定技術 | 理由 |
|------|----------|------|
| メインDB | DynamoDB | PRD指定、サーバーレス親和性 |
| Keycloak DB | RDS PostgreSQL | Keycloak標準 |

### 外部サービス連携 🔵

**信頼性**: 🔵 *PRD・要件定義より*

| サービス | 用途 |
|----------|------|
| LINE Messaging API | Webhook受信、Push通知、Flex Message |
| Amazon Bedrock | AIカード生成（Strands Agents） |
| EventBridge Scheduler | 定期通知ジョブ |

---

## システム構成図 🔵

**信頼性**: 🔵 *PRD・要件定義より*

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              AWS                                         │
│                                                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────────┐  │
│  │ CloudFront  │───▶│     S3      │    │        Keycloak             │  │
│  │   (LIFF)    │    │  (静的資産)  │    │      (ECS/Fargate)          │  │
│  │   HTTPS     │    │             │    │   ┌─────────────────────┐   │  │
│  └──────┬──────┘    └─────────────┘    │   │  ALB (HTTPS:443)    │   │  │
│         │                              │   └──────────┬──────────┘   │  │
│         │                              │              │              │  │
│         │                              │   ┌──────────▼──────────┐   │  │
│         │                              │   │ Keycloak Container  │   │  │
│         │                              │   └──────────┬──────────┘   │  │
│         │                              │              │              │  │
│         │                              │   ┌──────────▼──────────┐   │  │
│         │                              │   │  RDS PostgreSQL     │   │  │
│         │                              │   │  (Keycloak DB)      │   │  │
│         │                              │   └─────────────────────┘   │  │
│         │                              └─────────────────────────────┘  │
│         │                                                                │
│  ┌──────▼──────────────────────────────────────────────────────────┐    │
│  │                     API Gateway (REST)                           │    │
│  │                  JWT検証 (Keycloak Authorizer)                   │    │
│  │                     レート制限対応                                │    │
│  └──────────────────────────┬───────────────────────────────────────┘    │
│                             │                                            │
│  ┌──────────────────────────▼───────────────────────────────────────┐    │
│  │                        Lambda Functions                           │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │    │
│  │  │  api-main   │  │line-webhook │  │due-push-job │               │    │
│  │  │  (REST API) │  │ (Webhook)   │  │ (Scheduler) │               │    │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │    │
│  └─────────┼────────────────┼────────────────┼──────────────────────┘    │
│            │                │                │                           │
│  ┌─────────▼────────────────▼────────────────▼──────────────────────┐    │
│  │                        DynamoDB                                   │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐              │    │
│  │  │  users  │  │  cards  │  │ reviews │  │settings │              │    │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘              │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                     Amazon Bedrock                                │    │
│  │               (Claude 3 Sonnet / Strands Agents)                  │    │
│  │                   generate_cards / grade_answer                   │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                   EventBridge Scheduler                           │    │
│  │                  (定期実行: due-push-job)                         │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      LINE Platform                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                       │
│  │  Messaging  │  │    LIFF     │  │   Login     │                       │
│  │     API     │  │  Platform   │  │  Channel    │                       │
│  └─────────────┘  └─────────────┘  └─────────────┘                       │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## ディレクトリ構造 🟡

**信頼性**: 🟡 *AWS SAM標準構成から推測*

```
memoru-liff/
├── docs/
│   ├── spec/                    # 要件定義
│   │   └── memoru-liff/
│   └── design/                  # 設計文書
│       └── memoru-liff/
├── infrastructure/              # IaC (CDK/Terraform)
│   ├── keycloak/               # Keycloak ECS構成
│   └── liff-hosting/           # CloudFront + S3
├── backend/                     # AWS SAM
│   ├── template.yaml           # SAM テンプレート
│   ├── functions/
│   │   ├── api_main/           # REST API Lambda
│   │   ├── line_webhook/       # LINE Webhook Lambda
│   │   └── due_push_job/       # 定期通知 Lambda
│   ├── layers/
│   │   └── common/             # 共通ライブラリ
│   └── tests/
├── frontend/                    # LIFF (React + Vite)
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/
│   │   └── utils/
│   └── public/
└── README.md
```

---

## Lambda関数構成 🔵

**信頼性**: 🔵 *PRD・要件定義より*

| 関数名 | トリガー | 役割 |
|--------|----------|------|
| `api-main` | API Gateway | REST API（CRUD、AI生成） |
| `line-webhook` | API Gateway | LINE Webhook受信（署名検証、Postback処理） |
| `due-push-job` | EventBridge Scheduler | 復習通知送信（定期実行） |

---

## 非機能要件の実現方法

### パフォーマンス 🟡

**信頼性**: 🟡 *NFR要件から推測*

| 項目 | 目標 | 実現方法 |
|------|------|----------|
| APIレスポンス | 95%ile 3秒以内 | Lambda Provisioned Concurrency（必要時） |
| AI生成 | 30秒以内 | Bedrock タイムアウト設定 |
| 通知遅延 | due から5分以内 | EventBridge 5分間隔実行 |

### セキュリティ 🔵

**信頼性**: 🔵 *NFR要件・PRDより*

| 項目 | 実現方法 |
|------|----------|
| 通信暗号化 | HTTPS必須（CloudFront, ALB） |
| 認証 | Keycloak OIDC + JWT |
| 認可 | Lambda Authorizer (JWT検証) |
| シークレット管理 | Secrets Manager |
| LINE署名検証 | X-Line-Signature検証 |
| レート制限 | API Gateway Usage Plan |

### スケーラビリティ 🔵

**信頼性**: 🔵 *AWS サーバーレス特性より*

| 項目 | 実現方法 |
|------|----------|
| API | Lambda 自動スケール |
| DB | DynamoDB オンデマンドキャパシティ |
| 認証 | ECS Auto Scaling（必要時） |

### 可用性 🟡

**信頼性**: 🟡 *NFR要件から推測*

| 項目 | 目標 | 実現方法 |
|------|------|----------|
| 稼働率 | 99%以上 | マルチAZ構成（RDS, ECS） |
| 障害分離 | Keycloak障害時もWebhook継続 | 認証分離設計 |

---

## 技術的制約 🔵

**信頼性**: 🔵 *PRD・要件定義より*

### パフォーマンス制約

- Bedrock API呼び出しは30秒タイムアウト
- Lambda最大実行時間は15分（due-push-job用）
- DynamoDB 1アイテム最大400KB

### セキュリティ制約

- すべてのAPI呼び出しにJWT認証必須（LINE Webhook除く）
- LINE Webhookは署名検証必須
- ユーザーは自分のカードのみアクセス可能

### 互換性制約

- LIFF SDK バージョン 2.x 以上
- LINE アプリ内 WebView での動作必須
- Python 3.12 ランタイム

---

## 関連文書

- **データフロー**: [dataflow.md](dataflow.md)
- **API仕様**: [api-endpoints.md](api-endpoints.md)
- **DBスキーマ**: [database-schema.md](database-schema.md)
- **要件定義**: [requirements.md](../../spec/memoru-liff/requirements.md)

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 18件 | 82% |
| 🟡 黄信号 | 4件 | 18% |
| 🔴 赤信号 | 0件 | 0% |

**品質評価**: ✅ 高品質（青信号が80%以上）
