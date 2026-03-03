# TASK-0146 TDD 要件定義書: CognitoStack LINE Login 外部 IdP 実装

**タスクID**: TASK-0146
**機能名**: cognito-line-login
**要件名**: cognito-stack.ts に LINE Login を外部 OIDC IdP として登録する機能を追加する
**作成日**: 2026-03-04

---

## 1. 機能の概要

### 何をする機能か 🔵

**信頼性**: 🔵 *要件定義書 REQ-001・architecture.md「システム概要」セクションより*

`infrastructure/cdk/lib/cognito-stack.ts` の `CognitoStack` を拡張し、LINE Login を Cognito UserPool の外部 OIDC Identity Provider（`UserPoolIdentityProviderOidc`）として CDK で登録する機能を追加する。Props にオプショナルな LINE Login チャネル情報が指定された場合のみ LINE IdP を条件付きで作成し、`UserPoolClient` の `supportedIdentityProviders` に LINE を追加する。

### どのような問題を解決するか 🔵

**信頼性**: 🔵 *要件定義書「背景・動機」セクション・ストーリー1, 3 より*

- 現在の Cognito にはメール+パスワード認証のみが登録されており、LINE ユーザーが LINE アカウントでシームレスにログインできない
- 手動リンク方式（`/users/link-line`）では OIDC ログインと LINE リンクを別々に行う必要があり UX が悪い
- AWS Console での手動設定ではなく、CDK による IaC（Infrastructure as Code）で再現可能な環境構築を実現する

### 想定されるユーザー 🔵

**信頼性**: 🔵 *要件定義書ストーリー3 より*

- **インフラ管理者 / 開発者**: `npx cdk deploy` のみで LINE Login 統合を含む Cognito 環境を構築したい
- **間接的な利用者**: LINE ユーザー（Hosted UI 経由で LINE ログインを利用）

### システム内での位置づけ 🔵

**信頼性**: 🔵 *architecture.md「コンポーネント構成」セクション・既存 cognito-stack.ts より*

- **変更対象**: `infrastructure/cdk/lib/cognito-stack.ts`（CognitoStack 本体）
- **テスト対象**: `infrastructure/cdk/test/cognito-stack.test.ts`（既存テストの拡張）
- **変更不要**: フロントエンド、バックエンド、`app.ts`（TASK-0147 で対応）
- CDK スタックの 1 レイヤーとして、既存の UserPool → Domain → Client の構成に LINE IdP を条件付きで挿入する

**参照したEARS要件**: REQ-001, REQ-004, REQ-005, REQ-006
**参照した設計文書**: architecture.md「システム概要」「コンポーネント構成」セクション

---

## 2. 入力・出力の仕様

### 入力パラメータ 🔵

**信頼性**: 🔵 *architecture.md「CognitoStackProps の拡張」セクション・REQ-006 より*

`CognitoStackProps` インターフェースに追加するオプショナルプロパティ:

| プロパティ名 | 型 | 必須 | 説明 | 制約 |
|---|---|---|---|---|
| `lineLoginChannelId` | `string \| undefined` | No | LINE Login Channel ID | LINE Developers Console で発行される Channel ID |
| `lineLoginChannelSecret` | `string \| undefined` | No | LINE Login Channel Secret | LINE Developers Console で発行される Channel Secret |

**条件分岐ロジック**:
- `lineLoginChannelId` **かつ** `lineLoginChannelSecret` の**両方**が指定された場合: LINE IdP を作成する
- どちらか一方でも未指定（`undefined`）の場合: LINE IdP を作成しない（既存動作を維持）

### 出力（生成される AWS リソース） 🔵

**信頼性**: 🔵 *architecture.md「UserPoolIdentityProviderOidc の追加」セクション・REQ-001, REQ-002, REQ-003 より*

#### LINE IdP が作成される場合

| リソース | CloudFormation タイプ | 主要プロパティ |
|---|---|---|
| LINE Login IdP | `AWS::Cognito::UserPoolIdentityProvider` | `ProviderType: OIDC`, `ProviderName: LINE` |
| UserPoolClient 更新 | `AWS::Cognito::UserPoolClient` | `SupportedIdentityProviders: [COGNITO, LINE]` |

#### LINE IdP が作成されない場合

| リソース | CloudFormation タイプ | 主要プロパティ |
|---|---|---|
| UserPoolClient（変更なし） | `AWS::Cognito::UserPoolClient` | `SupportedIdentityProviders: [COGNITO]` |

### LINE OIDC エンドポイント構成 🟡

**信頼性**: 🟡 *LINE Developers 公式ドキュメントから妥当な推測。デプロイ時に実動作確認が必要*

| エンドポイント | URL | CDK プロパティ |
|---|---|---|
| Issuer URL | `https://access.line.me` | `issuerUrl` |
| Authorization | `https://access.line.me/oauth2/v2.1/authorize` | `endpoints.authorization` |
| Token | `https://api.line.me/oauth2/v2.1/token` | `endpoints.token` |
| UserInfo | `https://api.line.me/v2/profile` | `endpoints.userInfo` |
| JWKS URI | `https://api.line.me/oauth2/v2.1/certs` | `endpoints.jwksUri` |

### 属性マッピング仕様 🔵

**信頼性**: 🔵 *architecture.md「属性マッピング」セクション・REQ-003 より*

| LINE 属性 | Cognito 属性 | マッピング方法 | 説明 |
|---|---|---|---|
| `sub` | `username`（自動） | `ProviderAttribute.other('sub')` | LINE ユーザー ID |
| `name` | `name` | `ProviderAttribute.other('name')` | 表示名 |
| `picture` | `picture` | `ProviderAttribute.other('picture')` | プロフィール画像 URL |

### データフロー 🔵

**信頼性**: 🔵 *dataflow.md「フロー3: CDK デプロイフロー」より*

```
開発者 → CognitoStackProps(lineLoginChannelId, lineLoginChannelSecret)
  → CognitoStack コンストラクタ
    → 条件判定: 両方指定?
      → Yes: UserPoolIdentityProviderOidc 作成 → UserPoolClient 更新(COGNITO + LINE)
      → No: 既存の UserPoolClient のみ(COGNITO)
    → CloudFormation テンプレート出力
```

**参照したEARS要件**: REQ-001, REQ-002, REQ-003, REQ-006
**参照した設計文書**: architecture.md「CognitoStackProps の拡張」「UserPoolIdentityProviderOidc の追加」「属性マッピング」セクション

---

## 3. 制約条件

### 後方互換性制約 🔵

**信頼性**: 🔵 *REQ-401, REQ-402, REQ-403, REQ-404 より*

- `lineLoginChannelId` / `lineLoginChannelSecret` が未指定の場合、生成される CloudFormation テンプレートは**既存と完全に同一**でなければならない
- 既存の `devProps` / `prodProps` によるスナップショットテストが変更なしで通過すること
- 既存の OIDC 汎用化（`OidcIssuer`/`OidcAudience`）を変更しないこと
- 既存の手動 LINE リンク機能（`/users/link-line`）を変更・削除しないこと

### アーキテクチャ制約 🔵

**信頼性**: 🔵 *architecture.md「技術的制約」セクション・既存 cognito-stack.ts より*

- **変数宣言順序**: `lineProvider` 変数は `UserPoolClient` の `supportedIdentityProviders` で参照するため、`this.userPool.addClient(...)` 呼び出しの**前に**定義する必要がある
  - 現在の `addClient` は L61（cognito-stack.ts）にある
  - `lineProvider` の条件付き作成コードを L60 以前（UserPool Domain 後、UserPoolClient 前）に挿入する
- **IdP 名**: `name: 'LINE'` を使用する（Cognito のプロバイダ名制約に準拠）
- **スコープ**: `['openid', 'profile']` を指定する（LINE Login が対応するスコープ）
- **OIDC Discovery 非対応**: LINE は `.well-known/openid-configuration` に対応していない可能性があるため、`endpoints` の手動指定が必須

### ビルド・テスト制約 🔵

**信頼性**: 🔵 *既存テストパターン・CLAUDE.md 開発ルールより*

- `npm run build`（TypeScript コンパイル）が成功すること
- `npm test`（Jest）が全件パスすること
- 既存のスナップショットテストを LINE Props なし状態で更新すること
- LINE IdP 登録の新規テストを追加すること

### セキュリティ制約 🟡

**信頼性**: 🟡 *セキュリティベストプラクティスから妥当な推測*

- LINE Login Channel Secret は CDK コード内にハードコードしない（Props 経由で注入）
- `app.ts` での環境変数注入は TASK-0147 のスコープ

### スコープ制約 🔵

**信頼性**: 🔵 *TASK-0146 タスク定義・overview.md 依存関係より*

- **本タスクのスコープ**: `cognito-stack.ts` と `cognito-stack.test.ts` のみ
- **スコープ外**: `app.ts` の変更（TASK-0147）、フロントエンド変更、バックエンド変更
- **スコープ外**: LINE ユーザー ID の自動連携（Cognito → DynamoDB）

**参照したEARS要件**: REQ-401, REQ-402, REQ-403, REQ-404, REQ-405
**参照した設計文書**: architecture.md「技術的制約」セクション

---

## 4. 想定される使用例

### 基本的な使用パターン

#### パターン1: LINE IdP あり（Props 指定時）🔵

**信頼性**: 🔵 *REQ-001 受け入れ基準・architecture.md コード例より*

```typescript
const stack = new CognitoStack(app, 'MemoruCognitoDev', {
  environment: 'dev',
  cognitoDomainPrefix: 'memoru-dev',
  callbackUrls: ['http://localhost:3000/callback'],
  logoutUrls: ['http://localhost:3000/'],
  lineLoginChannelId: '1234567890',
  lineLoginChannelSecret: 'abcdef1234567890',
});
```

**期待結果**:
- `AWS::Cognito::UserPoolIdentityProvider` リソースが CloudFormation テンプレートに含まれる
- `ProviderType` が `OIDC`
- `ProviderName` が `LINE`
- OIDC エンドポイントが正しく設定されている
- 属性マッピング（sub, name, picture）が設定されている
- `UserPoolClient` の `SupportedIdentityProviders` が `[COGNITO, LINE]`

#### パターン2: LINE IdP なし（Props 未指定時 - 既存動作）🔵

**信頼性**: 🔵 *REQ-001 受け入れ基準「未指定の場合 LINE IdP が登録されない」より*

```typescript
const stack = new CognitoStack(app, 'MemoruCognitoDev', {
  environment: 'dev',
  cognitoDomainPrefix: 'memoru-dev',
  callbackUrls: ['http://localhost:3000/callback'],
  logoutUrls: ['http://localhost:3000/'],
  // lineLoginChannelId, lineLoginChannelSecret は未指定
});
```

**期待結果**:
- `AWS::Cognito::UserPoolIdentityProvider` リソースが CloudFormation テンプレートに**含まれない**
- `UserPoolClient` の `SupportedIdentityProviders` が `[COGNITO]` のみ
- 生成されるテンプレートが既存テンプレートと同一

### エッジケース

#### エッジケース1: Channel ID のみ指定（Secret 未指定）🟡

**信頼性**: 🟡 *条件分岐ロジック（両方指定時のみ作成）から妥当な推測*

```typescript
const stack = new CognitoStack(app, 'Test', {
  ...baseProps,
  lineLoginChannelId: '1234567890',
  // lineLoginChannelSecret は未指定
});
```

**期待結果**:
- LINE IdP は作成**されない**（既存動作と同一）
- エラーは発生しない

#### エッジケース2: Channel Secret のみ指定（ID 未指定）🟡

**信頼性**: 🟡 *条件分岐ロジック（両方指定時のみ作成）から妥当な推測*

```typescript
const stack = new CognitoStack(app, 'Test', {
  ...baseProps,
  lineLoginChannelSecret: 'abcdef1234567890',
  // lineLoginChannelId は未指定
});
```

**期待結果**:
- LINE IdP は作成**されない**（既存動作と同一）
- エラーは発生しない

#### エッジケース3: 空文字列の指定 🟡

**信頼性**: 🟡 *TypeScript の truthy/falsy 評価から妥当な推測*

```typescript
const stack = new CognitoStack(app, 'Test', {
  ...baseProps,
  lineLoginChannelId: '',
  lineLoginChannelSecret: '',
});
```

**期待結果**:
- `if (props.lineLoginChannelId && props.lineLoginChannelSecret)` の条件で falsy となり、LINE IdP は作成**されない**

#### エッジケース4: prod 環境 + LINE IdP あり 🔵

**信頼性**: 🔵 *既存 dev/prod 環境分岐テストパターンより*

```typescript
const stack = new CognitoStack(app, 'MemoruCognitoProd', {
  environment: 'prod',
  cognitoDomainPrefix: 'memoru-prod',
  callbackUrls: ['https://app.example.com/callback'],
  logoutUrls: ['https://app.example.com/'],
  lineLoginChannelId: '1234567890',
  lineLoginChannelSecret: 'abcdef1234567890',
});
```

**期待結果**:
- LINE IdP が作成される
- prod 固有の設定（DeletionProtection: ACTIVE, RemovalPolicy: RETAIN）は維持される

### エラーケース

#### エラーケース1: CDK Synth/Deploy 失敗 🟡

**信頼性**: 🟡 *CloudFormation 一般的な動作から妥当な推測*

- 不正な OIDC エンドポイント URL を指定した場合 → CDK deploy 時に CloudFormation エラー → ロールバック
- 本タスク（CDK テスト）のスコープでは CloudFormation の実デプロイエラーはテスト対象外

**参照したEARS要件**: REQ-001 受け入れ基準
**参照した設計文書**: dataflow.md「フロー3: CDK デプロイフロー」

---

## 5. EARS要件・設計文書との対応関係

### 参照したユーザーストーリー
- ストーリー1: LINE アカウントでログイン（REQ-001, REQ-004, REQ-005）
- ストーリー3: インフラ管理者による環境構築（REQ-001, REQ-006, REQ-007）

### 参照した機能要件
- **REQ-001**: CDK で Cognito UserPool に LINE Login を `UserPoolIdentityProviderOidc` として登録
- **REQ-002**: LINE Login の OIDC エンドポイントを手動指定
- **REQ-003**: LINE 属性（sub, name, picture）を Cognito ユーザー属性にマッピング
- **REQ-004**: `supportedIdentityProviders` に LINE を追加
- **REQ-005**: LINE Login とメール+パスワード認証の両方が利用可能
- **REQ-006**: `CognitoStackProps` に LINE Login チャネル情報 Props を追加

### 参照した制約要件
- **REQ-401**: 既存の OIDC 汎用化を変更しない
- **REQ-402**: 既存の手動 LINE リンク機能を変更・削除しない
- **REQ-403**: フロントエンド変更不要
- **REQ-404**: バックエンド変更不要
- **REQ-405**: LINE ユーザー ID 自動連携はスコープ外

### 参照した受け入れ基準
- REQ-001: LINE Channel ID/Secret 指定時に CDK デプロイ成功、未指定時に影響なし
- REQ-005: LINE ログインボタンとメール認証フォームの両方が表示

### 参照した設計文書
- **アーキテクチャ**: architecture.md「コンポーネント構成」セクション全体
  - CognitoStackProps の拡張
  - UserPoolIdentityProviderOidc の追加
  - 属性マッピング
  - UserPoolClient の更新
  - 技術的制約
- **データフロー**: dataflow.md「フロー3: CDK デプロイフロー」
- **既存実装**: `infrastructure/cdk/lib/cognito-stack.ts`（L7-12 Props, L61-85 UserPoolClient）
- **既存テスト**: `infrastructure/cdk/test/cognito-stack.test.ts`（スナップショット、リソース確認パターン）

---

## 6. テスト観点（TDD Red フェーズ用）

### 必須テストケース

#### A. LINE IdP 登録テスト（LINE Props 指定時）🔵

**信頼性**: 🔵 *REQ-001 受け入れ基準・既存テストパターンより*

1. `AWS::Cognito::UserPoolIdentityProvider` リソースが CloudFormation テンプレートに含まれること
2. IdP の `ProviderType` が `OIDC` であること
3. IdP の `ProviderName` が `LINE` であること
4. OIDC エンドポイント（Authorization, Token, UserInfo, JWKS）が正しく設定されていること
5. 属性マッピング（sub, name, picture）が正しく設定されていること
6. `UserPoolClient` の `SupportedIdentityProviders` に `COGNITO` と `LINE` が含まれること

#### B. 後方互換性テスト（LINE Props 未指定時）🔵

**信頼性**: 🔵 *REQ-001 受け入れ基準・既存テストパターンより*

7. `AWS::Cognito::UserPoolIdentityProvider` リソースが CloudFormation テンプレートに**含まれない**こと
8. `UserPoolClient` の `SupportedIdentityProviders` が `COGNITO` のみであること

#### C. スナップショットテスト 🔵

**信頼性**: 🔵 *既存テストパターンより*

9. 既存の dev/prod スナップショット（LINE Props なし）が正常に更新されること
10. LINE Props あり用の新規スナップショットテストが追加されること

### テスト用 Props 定義 🔵

**信頼性**: 🔵 *既存テストの devProps/prodProps パターンより*

```typescript
// 既存の Props（変更なし）
const devProps: CognitoStackProps = {
  environment: 'dev',
  cognitoDomainPrefix: 'memoru-dev-test',
  callbackUrls: ['http://localhost:3000/callback'],
  logoutUrls: ['http://localhost:3000/'],
};

// LINE Props あり（新規追加）
const devPropsWithLine: CognitoStackProps = {
  ...devProps,
  lineLoginChannelId: 'test-channel-id',
  lineLoginChannelSecret: 'test-channel-secret',
};
```

---

## 7. 実装ガイドライン

### 変更すべきファイル 🔵

**信頼性**: 🔵 *タスク定義・architecture.md より*

| ファイル | 変更内容 |
|---|---|
| `infrastructure/cdk/lib/cognito-stack.ts` | CognitoStackProps 拡張、LINE IdP 条件付き作成、UserPoolClient 更新 |
| `infrastructure/cdk/test/cognito-stack.test.ts` | LINE IdP テスト追加、スナップショット更新 |
| `infrastructure/cdk/test/__snapshots__/cognito-stack.test.ts.snap` | スナップショット自動更新 |

### 変更しないファイル 🔵

**信頼性**: 🔵 *REQ-401〜404・スコープ定義より*

- `infrastructure/cdk/bin/app.ts`（TASK-0147 のスコープ）
- フロントエンドコード全般
- バックエンドコード全般

### コード挿入位置 🔵

**信頼性**: 🔵 *既存 cognito-stack.ts のコード構造分析より*

```
cognito-stack.ts の構造:
  L7-12:   CognitoStackProps インターフェース ← ★ 拡張
  L26-47:  UserPool 作成
  L52-56:  UserPool Domain 作成
  ★ L57-59: LINE IdP 条件付き作成（新規挿入）
  L61-85:  UserPoolClient 作成 ← ★ supportedIdentityProviders 更新
  L90-118: CfnOutput
```

---

## 信頼性レベルサマリー

| カテゴリ | 項目数 | 🔵 青 | 🟡 黄 | 🔴 赤 |
|---|---|---|---|---|
| 機能概要 | 4 | 4 | 0 | 0 |
| 入出力仕様 | 6 | 5 | 1 | 0 |
| 制約条件 | 5 | 4 | 1 | 0 |
| 使用例 | 7 | 3 | 4 | 0 |
| テスト観点 | 4 | 4 | 0 | 0 |
| **合計** | **26** | **20 (77%)** | **6 (23%)** | **0 (0%)** |

**品質評価**: ✅ 高品質

- 要件の曖昧さ: なし（全項目が具体的なコード・リソース名・条件で定義されている）
- 入出力定義: 完全（Props インターフェース、CloudFormation リソース、属性マッピングが明確）
- 制約条件: 明確（後方互換性、変数宣言順序、スコープ制約が明示）
- 実装可能性: 確実（既存コードの構造分析に基づき挿入位置が特定されている）
- 🔴 赤信号: 0件（設計文書・要件定義に基づかない推測なし）
