# TASK-0146 TDD開発コンテキストノート

**タスク**: cognito-stack.ts に LINE Login を外部 OIDC IdP として登録する機能を追加する
**タスクID**: TASK-0146
**作成日**: 2026-03-04

---

## 1. 技術スタック

### インフラストラクチャ・CDK

- **AWS CDK**: v2.240.0（TypeScript）
- **aws-cdk-lib**: ^2.240.0
- **constructs**: ^10.0.0
- **Cognito AWS SDK**: `aws-cdk-lib/aws-cognito`
  - `UserPool` - ユーザープール管理
  - `UserPoolIdentityProviderOidc` - 外部 OIDC IdP 登録
  - `UserPoolClient` - クライアント設定
  - `UserPoolClientIdentityProvider` - サポート IdP 指定

### テスト・ビルド

- **テストフレームワーク**: Jest ^29.7.0
- **TypeScript 拡張**: ts-jest ^29.2.5, ts-node ^10.9.2
- **型定義**: TypeScript ~5.6.3, @types/jest ^29.5.14, @types/node 22.7.9
- **ビルド**: TypeScript コンパイラ（`tsc`）
- **スナップショットテスト**: aws-cdk-lib/assertions の `Template` + Jest スナップショット

### 認証・OIDC

- **LINE Login OIDC エンドポイント**:
  - Authorization: `https://access.line.me/oauth2/v2.1/authorize`
  - Token: `https://api.line.me/oauth2/v2.1/token`
  - UserInfo: `https://api.line.me/v2/profile`
  - JWKS URI: `https://api.line.me/oauth2/v2.1/certs`
  - Issuer URL: `https://access.line.me`
- **PKCE フロー**: 既存実装で `authorizationCodeGrant: true`, `generateSecret: false`
- **スコープ**: `openid`, `profile`（LINE ユーザー属性取得用）

参照元: `docs/design/cognito-line-login/architecture.md`

---

## 2. 開発ルール

### コミット規則

- **タスク完了時**: 1コミット＝1タスク
- **コミットメッセージ形式**:
  ```
  TASK-0146: cognito-stack.ts に LINE Login OIDC IdP 機能を追加

  - CognitoStackProps に lineLoginChannelId? / lineLoginChannelSecret? を追加
  - UserPoolIdentityProviderOidc の条件付き作成を実装
  - LINE 属性マッピング（sub, name, picture）を設定
  - UserPoolClient の supportedIdentityProviders を更新
  - 既存スナップショットテストを更新

  Co-Authored-By: Claude <noreply@anthropic.com>
  ```

### TDD プロセス

1. `/tsumiki:tdd-red` - テスト実装（失敗状態）
2. `/tsumiki:tdd-green` - 最小実装
3. `/tsumiki:tdd-refactor` - リファクタリング
4. コミット作成

### テストファイル構成

- **テストファイル**: `infrastructure/cdk/test/cognito-stack.test.ts`
- **スナップショット**: `infrastructure/cdk/test/__snapshots__/cognito-stack.test.ts.snap`
- **実装ファイル**: `infrastructure/cdk/lib/cognito-stack.ts`
- **アプリケーション**: `infrastructure/cdk/bin/app.ts`

### コード品質

- **テストカバレッジ**: 80% 以上を目標
- **ビルド**: `npm run build` で TypeScript チェック
- **テスト実行**: `npm test` で全テストをパス

参照元: `AGENTS.md`, `CLAUDE.md`

---

## 3. 関連実装・参考パターン

### 既存 CognitoStackProps 構造

```typescript
export interface CognitoStackProps extends cdk.StackProps {
  environment: Environment;
  cognitoDomainPrefix: string;
  callbackUrls: string[];
  logoutUrls: string[];
}
```

**拡張ポイント**: `lineLoginChannelId?` と `lineLoginChannelSecret?` を追加

参照元: `infrastructure/cdk/lib/cognito-stack.ts` (L7-12)

### 既存 UserPoolClient 設定パターン

```typescript
this.userPoolClient = this.userPool.addClient('LiffClient', {
  userPoolClientName: `memoru-${props.environment}-liff-client`,
  generateSecret: false, // Public client
  oAuth: {
    flows: { authorizationCodeGrant: true },
    scopes: [
      cognito.OAuthScope.OPENID,
      cognito.OAuthScope.PROFILE,
      cognito.OAuthScope.EMAIL,
    ],
    callbackUrls: props.callbackUrls,
    logoutUrls: props.logoutUrls,
  },
  supportedIdentityProviders: [
    cognito.UserPoolClientIdentityProvider.COGNITO,
  ],
  // ... その他の設定
});
```

**更新ポイント**: `supportedIdentityProviders` に LINE を条件付きで追加

参照元: `infrastructure/cdk/lib/cognito-stack.ts` (L61-85)

### 既存テストパターン

**スナップショットテスト**:
```typescript
test('dev environment matches snapshot', () => {
  const template = Template.fromStack(createStack(devProps));
  expect(template.toJSON()).toMatchSnapshot();
});
```

**リソース存在確認テスト**:
```typescript
test('password policy meets requirements', () => {
  const template = Template.fromStack(createStack(devProps));
  template.hasResourceProperties('AWS::Cognito::UserPool', {
    Policies: { PasswordPolicy: { /* ... */ } },
  });
});
```

**条件付きリソーステスト**: Cognito には `AWS::Cognito::UserPoolIdentityProvider` の存在確認パターンを参照

参照元: `infrastructure/cdk/test/cognito-stack.test.ts`

### 既存 app.ts 環境変数パターン

```typescript
const stage = app.node.tryGetContext('stage') as string | undefined;

if (!stage || stage === 'dev') {
  new CognitoStack(app, 'MemoruCognitoDev', {
    environment: 'dev',
    cognitoDomainPrefix: 'memoru-dev',
    callbackUrls: ['http://localhost:3000/callback'],
    logoutUrls: ['http://localhost:3000/'],
    // LINE Login Props を追加予定（TASK-0147）
  });
}
```

**参考**: 環境ごとの Props 注入パターン。TASK-0146 では実装不要（TASK-0147 で実施）

参照元: `infrastructure/cdk/bin/app.ts`

---

## 4. 設計文書・要件

### 要件定義書

**ファイル**: `docs/spec/cognito-line-login/requirements.md`

**主要要件**:
- **REQ-001**: CDK で Cognito UserPool に LINE Login を `UserPoolIdentityProviderOidc` として登録できること
- **REQ-002**: LINE OIDC エンドポイント（Authorization, Token, UserInfo, JWKS）を手動指定できること
- **REQ-003**: LINE 属性（sub, name, picture）を Cognito ユーザー属性にマッピングできること
- **REQ-004**: `supportedIdentityProviders` に LINE を追加し、Hosted UI に LINE ログインボタンを表示すること
- **REQ-006**: `CognitoStackProps` に LINE Login チャネル情報を受け取る Props を追加すること
- **REQ-401**: 既存の OIDC 汎用化を変更しないこと
- **REQ-402**: 既存の手動 LINE リンク機能を変更・削除しないこと

**制約条件**:
- LINE Props 未指定時、既存のテンプレートと変わらない（後方互換性）
- フロントエンド・バックエンドのコード変更は不要

参照元: `docs/spec/cognito-line-login/requirements.md`

### アーキテクチャ設計

**ファイル**: `docs/design/cognito-line-login/architecture.md`

**実装パターン**: Cognito Federated Identity Provider（外部 OIDC IdP）

**主要コンポーネント**:
1. `CognitoStackProps` 拡張
2. `UserPoolIdentityProviderOidc` の条件付き作成
3. 属性マッピング（LINE sub, name, picture → Cognito）
4. `UserPoolClient` の更新

**変更箇所**:
- `infrastructure/cdk/lib/cognito-stack.ts` - LINE IdP 追加、Client 更新
- `infrastructure/cdk/bin/app.ts` - LINE Login Props 追加（TASK-0147）

**変更不要**:
- フロントエンド（OIDC 汎用化済み）
- バックエンド（JWT クレーム非依存）

参照元: `docs/design/cognito-line-login/architecture.md`

### データフロー設計

**ファイル**: `docs/design/cognito-line-login/dataflow.md`

**主要フロー**:

**フロー1: LINE Login 経由の認証**
1. ユーザーが LIFF アプリ起動 → oidc-client-ts が Cognito Hosted UI へリダイレクト
2. Hosted UI に LINE ログインボタン + メール認証フォームが表示
3. ユーザーが「LINE でログイン」をクリック → LINE 認証画面へ遷移
4. LINE 認証完了 → Cognito が LINE トークンを受け取り属性マッピング
5. Cognito が JWT を発行 → フロントエンドが API 呼び出し

**フロー3: CDK デプロイフロー**
1. 開発者が `LINE_LOGIN_CHANNEL_ID` / `LINE_LOGIN_CHANNEL_SECRET` 環境変数を設定
2. `npx cdk deploy` 実行 → `app.ts` が `process.env` から Props を取得
3. `cognito-stack.ts` が Props を判定し、LINE IdP を条件付きで作成

参照元: `docs/design/cognito-line-login/dataflow.md`

### タスク関連文書

**タスク定義**: `docs/tasks/cognito-line-login/TASK-0146.md`

**完了条件** (10項目):
- [ ] `CognitoStackProps` に `lineLoginChannelId?` と `lineLoginChannelSecret?` が追加
- [ ] LINE Props 指定時に `UserPoolIdentityProviderOidc` が作成
- [ ] LINE Props 未指定時、既存動作に影響なし
- [ ] LINE 属性（sub, name, picture）が Cognito にマッピング
- [ ] `supportedIdentityProviders` に LINE が条件付きで追加
- [ ] 既存スナップショットテストが更新
- [ ] LINE IdP 登録テストが追加
- [ ] LINE Props 未指定時の後方互換性テストが追加
- [ ] `npm run build` が成功
- [ ] `npm test` が全件パス

**信頼性レベル**: 🔵 青信号 88%、🟡 黄信号 12%（LINE OIDC エンドポイントの実動作確認がデプロイ時に必要）

参照元: `docs/tasks/cognito-line-login/TASK-0146.md`

---

## 5. 注意事項・技術的制約

### 実装上の注意

1. **変数宣言位置**: `lineProvider` を `UserPoolClient` の `supportedIdentityProviders` で参照するため、IdP 作成を **先に行う必要がある**
   - 現在の `addClient` 呼び出し位置（L61）より前に `lineProvider` を定義

2. **条件分岐パターン**: LINE Props が未指定（undefined）の場合、既存の動作を維持
   ```typescript
   if (props.lineLoginChannelId && props.lineLoginChannelSecret) {
     // LINE IdP を作成
   }
   ```

3. **属性マッピング**: Cognito が LINE の `sub`（ユーザー ID）を自動マッピング。Cognito 発行の JWT `sub` とは別（LINE ユーザー ID の自動連携はスコープ外）

4. **OIDC エンドポイント URL**: LINE が `.well-known/openid-configuration` に対応していない可能性があるため、**手動指定（`endpoints` オブジェクト）が必須**

### セキュリティ・ベストプラクティス

- **Channel Secret**: `app.ts` では環境変数経由で注入。CDK コードにハードコードしない
- **PKCE**: 既存の `generateSecret: false` で SPA はクライアント側 PKCE を使用
- **JWT 検証**: API Gateway JWT Authorizer が Cognito 発行の JWT を検証（既存動作維持）

### テスト時の注意

1. **スナップショットテスト**: LINE Props なし（既存）のテストと LINE Props あり（新規）のテストを分ける
   - 既存の `devProps` / `prodProps` は LINE Props を持たない状態で更新
   - LINE Props 付きの新規テスト Props を作成

2. **リソース存在確認**: `hasResourceProperties` で `AWS::Cognito::UserPoolIdentityProvider` の存在を確認

3. **条件付きリソーステスト**: LINE Props なし時は IdP リソースが **存在しない** ことを確認

### 後方互換性

- LINE Props 未指定時、既存スナップショットと変わらない
- `supportedIdentityProviders` で条件分岐（LINE ありなしで配列構成が異なる）
- 既存の手動リンク機能（`/users/link-line`）は変更しない

参照元: `docs/design/cognito-line-login/architecture.md` 🔵 青信号, `docs/tasks/cognito-line-login/TASK-0146.md`

---

## 6. ファイル・ディレクトリ一覧

### 実装対象

- `infrastructure/cdk/lib/cognito-stack.ts` - 主実装ファイル
  - CognitoStackProps インタフェース拡張
  - UserPoolIdentityProviderOidc 条件付き作成
  - UserPoolClient supportedIdentityProviders 更新

### テスト対象

- `infrastructure/cdk/test/cognito-stack.test.ts` - テストファイル
- `infrastructure/cdk/test/__snapshots__/cognito-stack.test.ts.snap` - スナップショット

### 参考・設定ファイル

- `infrastructure/cdk/bin/app.ts` - 環境変数参考パターン
- `infrastructure/cdk/package.json` - Jest / TypeScript 設定
- `docs/design/cognito-line-login/architecture.md` - アーキテクチャ設計
- `docs/spec/cognito-line-login/requirements.md` - 要件定義

---

## 7. 実装ステップサマリー

### Phase 1: テスト実装（Red）
- LINE Props 指定時の IdP 作成テスト
- LINE Props 未指定時の後方互換性テスト
- 属性マッピング確認テスト
- supportedIdentityProviders の条件付き追加テスト

### Phase 2: 最小実装（Green）
- CognitoStackProps に lineLoginChannelId?, lineLoginChannelSecret? を追加
- UserPoolIdentityProviderOidc の条件付き作成を実装
- 属性マッピングを設定
- supportedIdentityProviders を更新
- スナップショット更新

### Phase 3: リファクタリング（Refactor）
- コード整理・コメント追加
- テスト可読性向上
- スナップショット最終確認

### Phase 4: 品質確認
- `npm run build` で TypeScript チェック
- `npm test` で全テストパス確認
- テストカバレッジ確認

---

## 参考資料

- AWS CDK Cognito: https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cognito-readme.html
- Cognito UserPoolIdentityProviderOidc: https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cognito.UserPoolIdentityProviderOidc.html
- Jest Testing: https://jestjs.io/docs/getting-started
- AWS CDK Assertions Template: https://docs.aws.amazon.com/cdk/api/v2/docs/assertions-readme.html

