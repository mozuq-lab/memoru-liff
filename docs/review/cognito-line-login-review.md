# feature/cognito-line-login-spec ブランチレビュー

> レビュー日: 2026-03-04
> レビュアー: Claude Code (Opus 4.6) + OpenAI Codex
> 対象コミット: `03a9d51`..`e4adab0`（3 commits）

## レビュー対象

| ファイル | 変更内容 |
|----------|----------|
| `infrastructure/cdk/lib/cognito-stack.ts` | LINE Login 外部 OIDC IdP の条件付き作成 |
| `infrastructure/cdk/bin/app.ts` | LINE Login 環境変数の注入 |
| `infrastructure/cdk/test/cognito-stack.test.ts` | 14 テストケース追加 |
| `infrastructure/cdk/test/__snapshots__/cognito-stack.test.ts.snap` | スナップショット追加 |
| `docs/**` | 要件定義・設計・タスク・デプロイガイド（19 ファイル） |

---

## Must Fix（対応必須）

### MF-1: userInfo エンドポイントが OIDC 標準と不一致

**重大度: High** | **影響: デプロイ後のログイン失敗**

`cognito-stack.ts:85` で設定されている userInfo エンドポイントが間違っている。

| 項目 | 現在の値 | 正しい値 |
|------|---------|----------|
| userInfo | `https://api.line.me/v2/profile` | `https://api.line.me/oauth2/v2.1/userinfo` |

**根拠**: LINE の `.well-known/openid-configuration`（`https://access.line.me/.well-known/openid-configuration`）を実際に取得して確認済み。

**レスポンス形式の違い**:
- `/v2/profile`（LINE Profile API）: `{ userId, displayName, pictureUrl, statusMessage }`
- `/oauth2/v2.1/userinfo`（OIDC 標準）: `{ sub, name, picture }`

現在の属性マッピングは `sub`, `name`, `picture` を期待しているため、`/v2/profile` では属性取得が失敗する。

**追加**: 設計文書とコード内コメントに「LINE は `.well-known/openid-configuration` に非対応のため」とあるが、**実際には LINE は `.well-known` を提供している**。この誤認識もコメントから修正すべき。

**修正案**:
```typescript
endpoints: {
  authorization: 'https://access.line.me/oauth2/v2.1/authorize',
  token: 'https://api.line.me/oauth2/v2.1/token',
  userInfo: 'https://api.line.me/oauth2/v2.1/userinfo', // 修正
  jwksUri: 'https://api.line.me/oauth2/v2.1/certs',
},
```

### MF-2: UserPoolClient と LINE IdP の CloudFormation 依存関係が未設定

**重大度: High** | **影響: 初回デプロイ失敗のリスク**

`cognito-stack.ts:120-124` で `supportedIdentityProviders` に文字列 `'LINE'` を指定しているが、`UserPoolClient` から `LineLoginProvider` への CloudFormation `DependsOn` が張られていない。

CloudFormation が `UserPoolClient` を先に作成すると「指定された IdP が存在しない」エラーが発生する可能性がある。

**根拠**: [AWS CDK Cognito README](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_cognito-readme.html) に `client.node.addDependency(provider)` が明示的に推奨されている。

**修正案**:
```typescript
// UserPoolClient 定義の後に追加
if (lineProvider) {
  this.userPoolClient.node.addDependency(lineProvider);
}
```

### MF-3: テストの更新（MF-1, MF-2 連動）

MF-1 の修正に伴い以下を更新する必要がある:
- **TC-003**: `attributes_url` のアサーション値を `/oauth2/v2.1/userinfo` に変更
- **TC-008, TC-009**: スナップショットの更新（`--updateSnapshot`）
- **新規テスト追加**: `UserPoolClient` が `LineLoginProvider` に依存していることを検証するテスト

---

## Should Fix（推奨）

### SF-1: Channel Secret の取り扱いに TODO を明示

**重大度: Medium** | `app.ts:22-23, 48-49`

`process.env` 経由で Channel Secret を渡している。dev 環境のプロトタイプ段階では許容範囲だが、以下のリスクがある:
- `cdk synth` 成果物に平文で出力される
- CI/CD パイプライン構築時にログ経由で漏洩する可能性

**修正案**: コードに TODO コメントを追加し、prod 環境では Secrets Manager / SSM Parameter Store の Dynamic Reference に移行する方針を明示する。

```typescript
// TODO: prod 環境では AWS Secrets Manager の Dynamic Reference に移行する
lineLoginChannelId: process.env.LINE_LOGIN_CHANNEL_ID,
lineLoginChannelSecret: process.env.LINE_LOGIN_CHANNEL_SECRET,
```

### SF-2: username 属性マッピングの再検討

**重大度: Medium** | `cognito-stack.ts:92`

`custom.username = sub` のマッピングについて:
- CDK の標準マッピングキーに `username` は存在しない
- Cognito は federated user の `username` を OIDC の `sub` から自動導出する（形式: `LINE_<sub>`）
- このマッピングは不要/効果不明であり、将来の保守性を下げる

**修正案**: `username` マッピングを削除し、LINE の `sub` を保持したい場合は `custom:line_user_id` 等のカスタム属性へマッピングすることを検討する。

```typescript
attributeMapping: {
  custom: {
    // username マッピングは削除（Cognito が自動で LINE_<sub> を設定）
    name: cognito.ProviderAttribute.other('name'),
    picture: cognito.ProviderAttribute.other('picture'),
  },
},
```

### SF-3: コメント過多の整理

**重大度: Low** | `cognito-stack.ts` 全体

各行に詳細なコメント（色付き絵文字 🔵🟡 付き）があり、コードの可読性を下げている。TDD プロセスのメモ的コメントが本番コードに残っている。

**修正案**: 設計意図が重要なもの（条件分岐の理由、LINE 固有の注意点）のみ残し、自明なもの（「プロバイダ名」「スコープ」等の説明）は削除する。

---

## Nice to Have（検討）

### NH-1: テストケース番号の欠番整理

TC-014, TC-015 が欠番。設計段階で削除されたテストケースだが、番号の飛びは混乱を招く可能性がある。

### NH-2: `.well-known` ディスカバリの活用検討

LINE が `.well-known/openid-configuration` を提供していることが確認されたため、エンドポイントの手動管理を減らし、LINE 側の変更へのドリフト耐性を向上させることを検討してもよい（ただし CDK の `UserPoolIdentityProviderOidc` が自動ディスカバリをサポートしているかの確認が必要）。

---

## 良い点

1. **後方互換性の設計**: `lineLoginChannelId` / `lineLoginChannelSecret` をオプショナルにし、未指定時は既存動作を維持する設計は適切
2. **テストカバレッジ**: 14 テストケースで正常系・異常系（片方のみ指定、空文字列）を網羅。TDD プロセスが機能している
3. **条件分岐のパターン**: `let lineProvider` + `if` + spread 演算子による条件付き IdP 追加は CDK のイディオムとして自然
4. **ドキュメント**: 要件定義 → 設計 → タスク → デプロイガイドまで一貫した文書化がされている

---

## 総合評価

**Approve with Required Changes**

全体的な設計方針と実装アプローチは良好だが、**MF-1（userInfo エンドポイント誤り）** と **MF-2（CloudFormation 依存関係）** はデプロイ時に実際に問題を引き起こす可能性が高く、マージ前に修正が必須。

特に MF-1 は設計文書の誤認識（「LINE は `.well-known` 非対応」）に起因しており、設計文書・コードコメント・テストの3箇所を修正する必要がある。

---

## 参考リンク

- [LINE OIDC Discovery](https://access.line.me/.well-known/openid-configuration)
- [LINE Login v2.1 API Reference](https://developers.line.biz/en/reference/line-login/)
- [AWS CDK Cognito README - Identity Providers](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_cognito-readme.html)
- [Cognito 属性マッピング仕様](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-specifying-attribute-mapping.html)
- [CloudFormation UserPoolIdentityProvider](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-cognito-userpoolidentityprovider.html)
