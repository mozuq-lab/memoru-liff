# feature/infra-cdk-migration-spec ブランチ コードレビュー

**レビュー日**: 2026-03-03
**レビュアー**: Claude Opus 4.6 + OpenAI Codex (MCP)
**対象ブランチ**: `feature/infra-cdk-migration-spec` (12 commits, 52 files changed)
**ベースブランチ**: `main`

---

## 概要

既存の CloudFormation テンプレート（Keycloak, LIFF Hosting, Cognito）を AWS CDK v2 (TypeScript) に移行し、旧テンプレートを削除するブランチ。加えて Backend の Bedrock モデル ID を `anthropic.claude-3-haiku-20240307-v1:0` → `global.anthropic.claude-haiku-4-5-20251001-v1:0` に更新。

### 変更の全体像

| カテゴリ | 追加行 | 削除行 | 主要ファイル |
|----------|--------|--------|-------------|
| CDK コード | ~870 | — | `infrastructure/cdk/` 配下 |
| 旧 CFn テンプレート削除 | — | ~2,500 | `infrastructure/{cognito,keycloak,liff-hosting}/` |
| Backend モデル ID 更新 | 5 | 5 | `bedrock.py`, `strands_service.py`, `template.yaml`, テスト |
| ドキュメント | ~1,600 | ~200 | `docs/`, `README.md`, `CLAUDE.md` |

---

## 総合評価

全体として**良い移行**が行われている。CDK の L2 Construct を適切に活用しており、既存の CloudFormation テンプレート (約2,500行) が CDK コード (約870行) に大幅に圧縮されている。環境差異の制御は `isProd` パターンで明確に管理されており、Stack Props による型安全なパラメータ管理も適切。

ただし、いくつかの重要な問題が発見された。

---

## 指摘事項

### P0: マージ前に修正を推奨

#### 1. Bedrock IAM ポリシーが推論プロファイル ID に対応していない

**ファイル**: `backend/template.yaml:298`, `:524`, `:563`
**重大度**: P0 (実行時に AccessDenied の可能性)

現在の IAM ポリシー:
```yaml
Resource: !Sub arn:aws:bedrock:${AWS::Region}::foundation-model/${BedrockModelId}
```

`global.anthropic.claude-haiku-4-5-20251001-v1:0` は **推論プロファイル ID** であり、`foundation-model/` パス配下の ARN では権限が不足する可能性がある。

**推奨修正**: `inference-profile` ARN を許可対象に追加する。

```yaml
Resource:
  - !Sub arn:aws:bedrock:${AWS::Region}:${AWS::AccountId}:inference-profile/${BedrockModelId}
  - !Sub arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0
```

> **Codex 所見**: AWS 公式ドキュメント ([Cross-region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/global-cross-region-inference.html), [Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonbedrock.html)) を根拠に、`inference-profile` + 対応 `foundation-model` ARN の組み合わせが必要と判断。

---

### P1: リリース前に修正を推奨

#### 2. Route53 の zoneName / recordName 設計が誤りやすい

**ファイル**: `keycloak-stack.ts:227-233`, `liff-hosting-stack.ts:221-227`
**重大度**: P1

```typescript
// keycloak-stack.ts:227-229
const zone = route53.HostedZone.fromHostedZoneAttributes(this, 'Zone', {
  hostedZoneId: props.hostedZoneId,
  zoneName: props.domainName, // ← "keycloak.example.com" がゾーン名になる
});
new route53.ARecord(this, 'DNSRecord', {
  zone,
  recordName: props.domainName, // ← FQDN が recordName に
});
```

`zoneName` に `keycloak.example.com` のようなホスト名を入れているが、通常は apex ドメイン（`example.com`）を渡す。`domainName` 1つに「ホスト名」と「Hosted Zone 名」の2つの意味を持たせているため、実運用で値を差し替えても片方を正すと片方が壊れる。

**推奨修正**: Props を分離する。

```typescript
export interface KeycloakStackProps extends cdk.StackProps {
  // ...
  domainName: string;        // e.g. "keycloak.example.com"
  hostedZoneName?: string;   // e.g. "example.com" (新規追加)
  hostedZoneId?: string;
}
```

> **Codex 所見**: プレースホルダ値の問題ではなく構造設計の問題。`domainName` が2つの役割を持つ限り、実運用時に DNS レコードの誤作成リスクがある。

#### 3. Keycloak の KC_HOSTNAME が環境実態とズレる

**ファイル**: `keycloak-stack.ts:186`
**重大度**: P1

```typescript
KC_HOSTNAME: props.domainName,  // dev でも "keycloak-dev.example.com"
```

dev 環境では証明書なし (HTTP) で ALB の DNS 名でアクセスするが、`KC_HOSTNAME` に固定ドメインを設定している。Keycloak はこの値をベース URL として使うため、ALB DNS 名でアクセスした際に OIDC リダイレクト URL 不整合が発生する。

**推奨修正**: 証明書有無で hostname を切り替える。

```typescript
KC_HOSTNAME: certificate ? props.domainName : '',
KC_HOSTNAME_STRICT: isProd ? 'true' : 'false',
```

#### 4. app.ts で dev/prod が同時 synth され、プレースホルダ値がそのまま使用される

**ファイル**: `bin/app.ts:12-53`
**重大度**: P1

dev/prod の全スタックが常に synth 対象になり、`example.com` や `123456789012` などのプレースホルダ値が含まれる。誤って prod スタックをデプロイするリスクがある。

**推奨修正**: context による環境フィルタリングを導入する。

```typescript
const stage = app.node.tryGetContext('stage') as string | undefined;
if (!stage || stage === 'dev') {
  new CognitoStack(app, 'MemoruCognitoDev', { ... });
  // ...
}
if (stage === 'prod') {
  new CognitoStack(app, 'MemoruCognitoProd', { ... });
  // ...
}
```

---

### P2: 改善を推奨

#### 5. セキュリティヘッダーの CSP に `unsafe-inline` が含まれる

**ファイル**: `liff-hosting-stack.ts:117-118`
**重大度**: P2

```typescript
"script-src 'self' 'unsafe-inline' https://static.line-scdn.net",
"style-src 'self' 'unsafe-inline'",
```

`unsafe-inline` は XSS 耐性を下げる。LIFF SDK や React の要件で必要な場合は理解できるが、可能であれば nonce ベースまたは hash ベースの CSP への移行を検討すべき。

> **Claude 所見**: LIFF SDK が `unsafe-inline` を要求するケースがあるため、現時点では許容可能。ただし将来的に `strict-dynamic` への移行を検討すべき。

#### 6. Keycloak LogGroup の本番 RemovalPolicy が DESTROY

**ファイル**: `keycloak-stack.ts:146`
**重大度**: P2

```typescript
removalPolicy: cdk.RemovalPolicy.DESTROY,  // prod でも DESTROY
```

認証基盤のログが CloudFormation スタック削除時に消失する。監査要件がある場合は問題になる。

**推奨修正**:

```typescript
removalPolicy: isProd ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
```

#### 7. Keycloak コンテナイメージがタグ固定のみ（digest 非固定）

**ファイル**: `keycloak-stack.ts:36`
**重大度**: P2

```typescript
const keycloakImage = props.keycloakImage ?? 'quay.io/keycloak/keycloak:24.0';
```

タグは可変であり、同じタグでも異なるイメージが pull される可能性がある。再現性とサプライチェーンセキュリティの観点から、digest 固定が望ましい。

#### 8. Secrets Manager のローテーション未設定

**ファイル**: `keycloak-stack.ts:72-92`
**重大度**: P2

DB パスワードと Keycloak admin パスワードのシークレットにローテーション設定がない。長期運用ではセキュリティリスクになる。

#### 9. bedrock.py の docstring が旧モデル名のまま

**ファイル**: `backend/src/services/bedrock.py:75`
**重大度**: P2

```python
model_id: Bedrock model ID. Defaults to Claude 3 Haiku.
```

実際は Claude Haiku 4.5 であり、運用時の誤解を招く。

#### 10. `X-Frame-Options` と `frame-ancestors` の競合

**ファイル**: `liff-hosting-stack.ts:102`, `:122`
**重大度**: P2

`X-Frame-Options: SAMEORIGIN` と CSP の `frame-ancestors 'self' https://liff.line.me` が同時に設定されている。`X-Frame-Options` は CSP の `frame-ancestors` が存在する場合無視されるが、意図の不明確さが残る。LIFF は `liff.line.me` 内の iframe で動作するため、`X-Frame-Options: SAMEORIGIN` は LIFF の動作をブロックしうる（古いブラウザ）。

**推奨**: `X-Frame-Options` を `DENY` ではなく削除するか、CSP `frame-ancestors` のみに統一する。

---

### P3: 軽微 / 既存課題

#### 11. Keycloak の可用性（desiredCount=1, NAT=1）

**ファイル**: `keycloak-stack.ts:52`, `:164`
**重大度**: P3

個人プロジェクトのコスト最適化として妥当。ただし、認証基盤の停止は全機能停止に直結するため、運用方針として許容停止時間（RTO）を明文化することを推奨。

> **Codex 所見**: 「必ず修正」ではなく受容可能なリスクとして扱える。

#### 12. RDS PostgreSQL バージョンの要件不一致

**ファイル**: `keycloak-stack.ts:106`
**重大度**: P3（要確認）

要件定義 (REQ-003) では「PostgreSQL 18」と記載されているが、実装は `VER_17`。CDK/RDS で PostgreSQL 18 が利用可能かどうかの確認が必要。利用不可の場合は要件定義側を VER_17 に修正すべき。

```typescript
engine: rds.DatabaseInstanceEngine.postgres({
  version: rds.PostgresEngineVersion.VER_17,  // 要件は 18
}),
```

#### 13. strands_service.py の OllamaModel 未導入時エラー（既存課題）

**ファイル**: `backend/src/services/strands_service.py:21-24`
**重大度**: P3

`OllamaModel = None` の状態で `OllamaModel(...)` を呼ぶ経路があり `TypeError` になる。ただしこれは今回のブランチの変更範囲外（既存課題）のため、別タスクで対応が妥当。

#### 14. CloudFront キャッシュ戦略が手動 invalidation 依存

**ファイル**: `liff-hosting-stack.ts:166`, `:270`
**重大度**: P3

`defaultBehavior` に `CACHING_OPTIMIZED` を使用し、`DeployCommand` 出力で手動 invalidation を前提としている。CI/CD 導入時には自動化が必要。現時点では許容可能。

---

## 良い点

1. **L2 Construct の適切な活用**: `ApplicationLoadBalancedFargateService` により、既存テンプレートの約300行が数十行に集約されている
2. **S3BucketOrigin.withOriginAccessControl()**: OAC + バケットポリシーの自動設定が適切に利用されている
3. **環境差異の制御**: `isProd` パターンによる一貫した条件分岐が実現できている
4. **型安全な Props**: TypeScript の型システムを活用した環境パラメータ管理
5. **セキュリティ設定の包括性**: 暗号化、パブリックアクセスブロック、セキュリティヘッダー、deletionProtection が適切に設定されている
6. **CloudFront のキャッシュ戦略**: `/assets/*` の長期キャッシュと `/index.html` のキャッシュ無効化が SPA に適切
7. **Bedrock モデル ID の一貫した更新**: 3ファイル + テスト2ファイルで漏れなく更新されている
8. **ドキュメントの充実**: 要件定義、設計文書、タスクファイルが信頼性レベル付きで管理されている

---

## 推奨アクション（優先順）

| 優先度 | アクション | 指摘# |
|--------|-----------|-------|
| P0 | `template.yaml` の Bedrock IAM を `inference-profile` ARN 対応に修正 | 1 |
| P1 | Route53 の `zoneName` / `domainName` Props を分離 | 2 |
| P1 | Keycloak の `KC_HOSTNAME` を証明書有無で切り替え | 3 |
| P1 | `app.ts` に context ベースの環境フィルタリング導入 | 4 |
| P2 | Keycloak LogGroup の prod RemovalPolicy を RETAIN に | 6 |
| P2 | bedrock.py の docstring 更新 | 9 |
| P2 | `X-Frame-Options` と `frame-ancestors` の整理 | 10 |
| P3 | PostgreSQL バージョンの要件と実装の整合確認 | 12 |

---

## レビュー方法

- **Claude Opus 4.6**: CDK コード、設計文書、バックエンド変更の直接レビュー
- **OpenAI Codex (via MCP)**: 独立した視点からのセキュリティ、ベストプラクティス、アーキテクチャレビュー
- 両者の意見を統合し、議論を経て重大度を再評価
