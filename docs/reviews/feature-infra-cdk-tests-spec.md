# コードレビュー: feature/infra-cdk-tests-spec

**レビュー日**: 2026-03-03
**レビュアー**: Claude Opus 4.6 + OpenAI Codex (MCP)
**ブランチ**: `feature/infra-cdk-tests-spec`
**ベースブランチ**: `main`

---

## 概要

CDK スタック (CognitoStack, KeycloakStack, LiffHostingStack) のユニットテストを追加するブランチ。4コミット、17ファイル、+5,220行の変更。

### コミット履歴

| コミット | 内容 |
|---------|------|
| `b92d587` | docs: CDK テストの要件定義・設計・タスク分割を追加 |
| `8ff3a1a` | TASK-0134: CognitoStack テスト作成 |
| `990a880` | TASK-0135: KeycloakStack テスト作成 |
| `9959fdd` | TASK-0136: LiffHostingStack テスト作成 |

### テスト実行結果

```
Test Suites: 3 passed, 3 total
Tests:       37 passed, 37 total
Snapshots:   6 passed, 6 total
Time:        5.312 s
```

---

## 判定: Approve with suggestions

**マージ可。ブロッカーなし。** 以下の改善提案は後続タスクとして対応可能。

---

## 評価サマリー

| 観点 | 評価 | コメント |
|------|------|---------|
| 要件充足 | **A** | 要件定義書 REQ-001〜REQ-005 を概ね網羅 |
| テスト網羅性 | **B+** | 基本的な dev/prod 差異・セキュリティ・バリデーションは押さえているが、一部条件分岐が未検証 |
| テスト品質 | **B** | assertion は動作するが、対象リソース特定が弱い箇所あり |
| Snapshot 戦略 | **B** | フルテンプレート snapshot は回帰検知に有効だが、ノイズ耐性に課題 |
| コード品質 | **B+** | 読みやすい構造だが、未使用 import やハードコード値の軽微な問題あり |
| 保守性 | **B** | CDK バージョン更新時の snapshot diff ノイズが運用課題になる可能性 |
| ドキュメント | **A** | 要件定義・設計・タスク管理が丁寧に整備されている |

---

## 良い点

### 1. 二層テスト戦略の適切な実装
Snapshot テストで全体回帰を検知しつつ、Fine-grained assertions でセキュリティ・環境差異を個別検証する方針が正しく実装されている。

### 2. dev/prod 環境差異の網羅
`isProd` による条件分岐のテストが各スタックで適切にカバーされている:
- CognitoStack: `DeletionProtection`, `RemovalPolicy`
- KeycloakStack: NAT Gateway, MultiAZ, DeletionProtection, AssignPublicIp, LogGroup RemovalPolicy
- LiffHostingStack: LogBucket 有無

### 3. バリデーションテスト
不正な Props でのエラー発生を検証:
- `keycloak-stack.test.ts:37-43`: prod で certificateArn なし → エラー
- `liff-hosting-stack.test.ts:36-48`: domainName あり + certificateArn なし → エラー、domainName なし → エラーなし

### 4. セキュリティ設定の明示検証
- Cognito: パスワードポリシー、MFA 設定
- RDS: StorageEncrypted, PubliclyAccessible
- S3: BlockPublicAccess, BucketEncryption
- CloudFront: HSTS, CSP (frame-ancestors), X-Content-Type-Options

### 5. テスト構造の統一感
3つのテストファイルすべてが同じパターン (Props 定義 → createStack ヘルパー → describe グループ) で統一されており、読みやすい。

---

## 指摘事項

### High: 本番環境の重要契約に対する assertion 不足

**対象**: `keycloak-stack.test.ts`, `liff-hosting-stack.test.ts`

本番環境で壊れるとサービス到達性・セキュリティに直結する以下の設定が、Snapshot にのみ依存しており明示 assertion がない:

| スタック | 不足している assertion | ソース位置 |
|---------|----------------------|-----------|
| KeycloakStack | HTTPS Listener (Port 443 + Certificate) | `keycloak-stack.ts:174-177` |
| KeycloakStack | HTTP→HTTPS リダイレクト | `keycloak-stack.ts:178` |
| KeycloakStack | Health check 設定 (`/health/ready`) | `keycloak-stack.ts:212-215` |
| KeycloakStack | Route53 DNS レコード (prod) | `keycloak-stack.ts:227-239` |
| LiffHostingStack | Custom domain + Certificate (prod) | `liff-hosting-stack.ts:208-209` |
| LiffHostingStack | CloudFront logging (prod) | `liff-hosting-stack.ts:211-212` |
| LiffHostingStack | Route53 DNS レコード (prod) | `liff-hosting-stack.ts:219-231` |

**推奨対応**: 後続タスクで以下の Fine-grained assertion を追加
- `AWS::ElasticLoadBalancingV2::Listener` に `Port: 443`, `Protocol: HTTPS`
- `Port: 80` Listener に redirect action
- CloudFront Distribution に `domainNames`, `certificate` (prod)

### High: Cognito 認証契約のテスト不足

**対象**: `cognito-stack.test.ts`

認証フローで壊れると影響が大きい設定の assertion が不足:

| 不足項目 | ソース位置 |
|---------|-----------|
| CallbackURLs / LogoutURLs が Props から正しく設定される | `cognito-stack.ts:71-72` |
| Token validity (access: 1h, id: 1h, refresh: 30d) | `cognito-stack.ts:81-83` |
| UserPool Domain 設定 | `cognito-stack.ts:52-56` |
| CfnOutput の値 (UserPoolId, ClientId, OIDC Issuer URL) | `cognito-stack.ts:90-118` |

### Medium: 条件分岐の網羅不足

以下の条件分岐パスが明示テストされていない:

| 分岐 | ソース位置 | 説明 |
|------|-----------|------|
| `hostedZoneId` なし時に Route53 レコードが作られない | `keycloak-stack.ts:227`, `liff-hosting-stack.ts:219` | 負のケースの検証 |
| `apiEndpoint` 指定時の CSP `connect-src` | `liff-hosting-stack.ts:87-89` | LIFF 固有の重要設定 |
| KeycloakStack optional props | `keycloak-stack.ts:22-27` | `vpcCidr`, `keycloakImage`, `dbAllocatedStorage` 等のデフォルト値 |

### Medium: assertion の特定性が弱い箇所

**対象**: `keycloak-stack.test.ts:106-120`

```typescript
// 現状: LogGroup の対象を特定していない
template.hasResource('AWS::Logs::LogGroup', {
  UpdateReplacePolicy: 'Delete',
  DeletionPolicy: 'Delete',
});
```

将来 LogGroup が増えた場合に誤検知のリスクがある。`resourceCountIs` や `LogGroupName` で対象を絞り込むことを推奨。

**推奨修正例**:
```typescript
template.resourceCountIs('AWS::Logs::LogGroup', 1);
template.hasResourceProperties('AWS::Logs::LogGroup', {
  LogGroupName: '/ecs/memoru-dev-keycloak',
  RetentionInDays: 14,
});
```

### Medium: Snapshot のノイズ耐性

フルテンプレート snapshot (`template.toJSON()`) は CDK バージョン更新時にノイズが大きくなりやすい。

**現状のリスク**:
- CDK バージョン更新で論理 ID やメタデータが変わると大量の diff が発生
- 意味のある変更とノイズの判別が困難

**推奨改善** (後続タスク):
1. フル snapshot は維持しつつ、`BootstrapVersion` 等のノイズ項目を正規化するヘルパーを検討
2. 重要リソース単位の部分 snapshot を補助的に追加
3. snapshot 更新ルールを文書化（「assertion 全通過 + diff 目視確認後のみ更新」）

### Low: 未使用 import

**対象**: `keycloak-stack.test.ts:2`

```typescript
import { Template, Match } from 'aws-cdk-lib/assertions';
//                  ^^^^^ 未使用
```

`Match` は使用されていないため削除すべき。

### Low: Deprecation Warning (ソースコード側の問題)

テスト実行時に `containerInsights` の deprecation warning が大量に出力される:

```
[WARNING] aws-cdk-lib.aws_ecs.ClusterProps#containerInsights is deprecated.
See {@link containerInsightsV2 }
```

**対象**: `keycloak-stack.ts:137`

テスト側の問題ではなくソースコード側の問題だが、以下の理由で対応を推奨:
- CI ログがノイジーになり、本当の警告/失敗が埋もれる
- 将来の CDK メジャー更新で破壊的変更につながる可能性

**推奨**: `containerInsights` → `containerInsightsV2` への移行を別タスクとして対応

---

## Codex との議論ログ

### 議論 1: Snapshot 戦略

**Claude の見解**: フルテンプレート Snapshot は要件定義書の方針に沿っており、廃止すべきではない。
**Codex の見解**: 同意。「snapshot = 変化検知レーダー」「important assertions = リリース判定」と役割分離し、ノイズ項目の正規化ヘルパーや部分 snapshot の追加で改善可能。
**合意**: フル snapshot は維持しつつ、補助的な改善を後続タスクで対応。

### 議論 2: L3 Construct の内部動作テスト粒度

**Claude の懸念**: `ApplicationLoadBalancedFargateService` の内部動作テストは CDK 内部実装への依存度が高くならないか。
**Codex の見解**: L3 内部実装には寄せず、CloudFormation 上の契約 (Listener/Protocol/CertificateArn) のみ検証するのが適切。論理 ID 固定や自動生成 SG ルール件数への依存は避けるべき。
**合意**: CloudFormation リソースレベルの assertion に留める。

### 議論 3: YAGNI vs 将来の誤検知防止

**Claude の懸念**: LogGroup が現在1つしかないのに対象特定を強化するのは YAGNI では。
**Codex の見解**: コストが低く効果が高いため、YAGNI より将来の誤検知防止を優先する価値がある。`resourceCountIs` + `LogGroupName` の最小強化で十分。
**合意**: 最小限の強化は後続タスクで対応。

### 議論 4: containerInsights deprecation warning

**Claude の質問**: テストレビューとして報告すべきか。
**Codex の見解**: 報告すべき（非ブロッカー扱い）。CI ログのノイズ化と将来の破壊的変更リスクがある。
**合意**: Low 扱いで報告し、ソースコード側の対応を別タスクとして推奨。

---

## 後続タスク提案（優先順）

| 優先度 | タスク | 対象ファイル |
|--------|-------|-------------|
| 1 | Keycloak 本番契約 assertion 追加 (HTTPS, redirect, health check, DNS) | `keycloak-stack.test.ts` |
| 2 | LIFF 本番契約 assertion 追加 (custom domain, logging, DNS, CSP connect-src) | `liff-hosting-stack.test.ts` |
| 3 | Cognito 認証契約 assertion 追加 (callback URLs, token validity, domain, outputs) | `cognito-stack.test.ts` |
| 4 | Snapshot ノイズ低減 (正規化ヘルパー + 部分 snapshot) | 全テストファイル |
| 5 | assertion 特定性強化 (LogGroup 等) | `keycloak-stack.test.ts` |
| 6 | テストコード軽微整理 (未使用 import 削除) | `keycloak-stack.test.ts` |
| 7 | `containerInsights` → `containerInsightsV2` 移行 | `keycloak-stack.ts` |
