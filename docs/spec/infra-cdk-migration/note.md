# infra-cdk-migration コンテキストノート

## 技術スタック

### CDK プロジェクト
- **言語**: TypeScript
- **CDK バージョン**: aws-cdk-lib v2 (最新)
- **配置**: `infrastructure/cdk/`
- **ノードランタイム**: フロントエンドと同じ Node.js 環境を使用

### 移行対象テンプレート
| テンプレート | リソース数 | 行数 | 複雑度 |
|---|---|---|---|
| `infrastructure/keycloak/template.yaml` | VPC, Subnet×4, NAT, IGW, SG×3, SecretsManager×2, RDS PostgreSQL 18 (16から更新), ECS/Fargate, ALB, Route53 | 672行 | 高 |
| `infrastructure/liff-hosting/template.yaml` | S3×2, CloudFront, OAC, CachePolicy, ResponseHeadersPolicy, Route53 | 358行 | 中 |
| `infrastructure/cognito/template.yaml` | UserPool, UserPoolDomain, UserPoolClient | 183行 | 低 |

### 移行対象外
- `backend/template.yaml` — SAM テンプレートとして維持

## プロジェクト構成

### 現在のインフラ構成
```
infrastructure/
├── keycloak/
│   ├── template.yaml          # → CDK 化対象
│   ├── realm-local.json       # ローカル用 (変更なし)
│   └── test-users.json        # ローカル用 (変更なし)
├── liff-hosting/
│   └── template.yaml          # → CDK 化対象
└── cognito/
    └── template.yaml          # → CDK 化対象
```

### CDK 化後の構成 (予定)
```
infrastructure/
├── cdk/
│   ├── bin/app.ts             # CDK App エントリポイント
│   ├── lib/
│   │   ├── keycloak-stack.ts
│   │   ├── liff-hosting-stack.ts
│   │   └── cognito-stack.ts
│   ├── cdk.json
│   ├── tsconfig.json
│   └── package.json
├── keycloak/
│   ├── realm-local.json       # 残す
│   └── test-users.json        # 残す
```

## クロスリファレンス

### backend/template.yaml が参照するパラメータ
- `OidcIssuer` — Cognito の OIDC Issuer URL (手動設定)
- `OidcAudience` — Cognito の Client ID (手動設定)

### スタック間の Export/Import
現在のテンプレートでは CloudFormation Export を定義しているが、スタック間で Import している箇所はない。各スタックは独立しており、パラメータ値はデプロイ時に手動で指定。

## バージョン更新事項

### Bedrock モデル ID
- **現在のテンプレートデフォルト**: `anthropic.claude-3-haiku-20240307-v1:0` (Claude 3 Haiku)
- **更新後**: `global.anthropic.claude-haiku-4-5-20251001-v1:0` (Claude Haiku 4.5, Global 推論プロファイル)
- **対象ファイル**: `backend/template.yaml` (BedrockModelId パラメータ), `backend/src/services/bedrock.py` (DEFAULT_MODEL_ID)
- **env.json**: 既に `global.anthropic.claude-haiku-4-5-20251001-v1:0` に更新済み（変更不要）

### PostgreSQL バージョン
- **現在**: PostgreSQL 16 (`EngineVersion: '16'`, `Family: postgres16`)
- **更新後**: PostgreSQL 18 (`EngineVersion: '18'`, `Family: postgres18`)
- **RDS 対応状況**: 2025年11月にサポート開始、最新マイナーバージョン 18.3 (2026年2月)

## 注意事項

- **既存リソースなし**: AWS にデプロイ済みのリソースがないため、`cdk import` は不要。新規 `cdk deploy` で対応可能
- **SAM との併用**: backend は SAM のまま。CDK スタックの Output を SAM のパラメータに手動で渡す運用は変わらない
- **旧テンプレート**: CDK 完成・動作確認後に削除
