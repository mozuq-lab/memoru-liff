# Green フェーズ記録: cognito-line-login TASK-0146

**タスクID**: TASK-0146
**フェーズ**: Green（最小実装）
**作成日**: 2026-03-04

---

## 実装方針

TC-001〜TC-007 の失敗テストを通すために、以下の最小限の実装を `infrastructure/cdk/lib/cognito-stack.ts` に行った。

1. `CognitoStackProps` に `lineLoginChannelId?` / `lineLoginChannelSecret?` を追加
2. `UserPoolIdentityProviderOidc` の条件付き作成（UserPool Domain 後、UserPoolClient 前）
3. LINE OIDC エンドポイントの手動指定
4. 属性マッピング（`attributeMapping.custom` を使用）
5. `supportedIdentityProviders` への LINE 条件付き追加
6. スナップショット更新（`npx jest --updateSnapshot`）

---

## 実装コード全文

```typescript
import * as cdk from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import type { Construct } from 'constructs';

type Environment = 'dev' | 'staging' | 'prod';

export interface CognitoStackProps extends cdk.StackProps {
  environment: Environment;
  cognitoDomainPrefix: string;
  callbackUrls: string[];
  logoutUrls: string[];
  // 【LINE Login 追加 Props】: LINE Login 外部 OIDC IdP 登録用のオプショナルプロパティ 🔵
  // 【設計方針】: 両方が指定された場合のみ LINE IdP を登録し、後方互換性を維持 (REQ-006)
  lineLoginChannelId?: string;     // LINE Login Channel ID（省略時は LINE IdP 未登録）
  lineLoginChannelSecret?: string; // LINE Login Channel Secret
}

export class CognitoStack extends cdk.Stack {
  // ... （UserPool, UserPoolDomain は変更なし）

  // ============================================================
  // LINE Login 外部 OIDC IdP（条件付き作成）
  // ============================================================
  // 【機能概要】: LINE Login を外部 OIDC IdP として Cognito UserPool に登録する 🔵
  // 【実装方針】: lineLoginChannelId と lineLoginChannelSecret の両方が指定された場合のみ作成 (REQ-001)
  // 【テスト対応】: TC-001〜TC-007 の失敗テストを通すための最小限の実装
  // 【変数宣言位置の注意】: UserPoolClient の supportedIdentityProviders で参照するため、
  //   addClient 呼び出し前に lineProvider を定義する必要がある
  let lineProvider: cognito.UserPoolIdentityProviderOidc | undefined;
  if (props.lineLoginChannelId && props.lineLoginChannelSecret) {
    // 【LINE IdP 作成】: LINE Login の OIDC エンドポイントを手動指定して登録 (REQ-002) 🔵
    // 【エンドポイント設定】: LINE が .well-known/openid-configuration に対応していない可能性があるため手動指定
    lineProvider = new cognito.UserPoolIdentityProviderOidc(this, 'LineLoginProvider', {
      userPool: this.userPool,
      name: 'LINE', // 【プロバイダ名】: Cognito Hosted UI の LINE ログインボタン識別子
      clientId: props.lineLoginChannelId,
      clientSecret: props.lineLoginChannelSecret,
      issuerUrl: 'https://access.line.me', // 🟡 LINE OIDC Issuer URL
      scopes: ['openid', 'profile'], // 【スコープ】: LINE ユーザー属性取得に必要な最小スコープ
      endpoints: {
        // 【LINE OIDC エンドポイント手動指定】: 各エンドポイントを手動設定 (REQ-002) 🟡
        authorization: 'https://access.line.me/oauth2/v2.1/authorize',
        token: 'https://api.line.me/oauth2/v2.1/token',
        userInfo: 'https://api.line.me/v2/profile',
        jwksUri: 'https://api.line.me/oauth2/v2.1/certs',
      },
      attributeMapping: {
        // 【属性マッピング】: LINE 属性を Cognito ユーザー属性にマッピング (REQ-003) 🔵
        // 【custom 使用】: 標準マッピングキーでは username が undefined になるため custom を使用
        custom: {
          username: cognito.ProviderAttribute.other('sub'),     // LINE ユーザー ID → Cognito username
          name: cognito.ProviderAttribute.other('name'),        // LINE 表示名 → Cognito name
          picture: cognito.ProviderAttribute.other('picture'),  // LINE プロフィール画像 → Cognito picture
        },
      },
    });
  }

  // UserPoolClient の supportedIdentityProviders
  supportedIdentityProviders: [
    // 【supportedIdentityProviders】: LINE IdP が登録されている場合のみ追加 (REQ-004, REQ-005) 🔵
    // 【条件付き追加】: lineProvider が存在する場合のみ LINE を配列に追加
    cognito.UserPoolClientIdentityProvider.COGNITO,
    ...(lineProvider ? [cognito.UserPoolClientIdentityProvider.custom('LINE')] : []),
  ],
}
```

---

## 技術的判断

### `attributeMapping.custom` を使用した理由

CDK の `attributeMapping` で `username` プロパティを標準マッピングとして指定すると、CloudFormation テンプレートで `"undefined": "sub"` という不正な出力になる CDK の挙動があることを実際に確認した。

`attributeMapping.custom` に `username` をキーとして指定することで、CloudFormation テンプレートで正しく `"username": "sub"` が出力される。

これは TC-004 のテスト（`AttributeMapping: { username: 'sub', name: 'name', picture: 'picture' }`）を通すために必要な判断。

### スナップショット更新の理由

TC-008（dev + LINE IdP スナップショット）と TC-009（prod + LINE IdP スナップショット）は Red フェーズで LINE IdP なしの状態でスナップショットが生成されていた。実装後の LINE IdP あり状態に合わせて `npx jest --updateSnapshot` で更新した。

---

## テスト実行結果

```bash
cd infrastructure/cdk && npm test

Test Suites: 3 passed, 3 total
Tests:       74 passed, 74 total
Snapshots:   8 passed, 8 total
Time:        1.212 s
```

全74件パス。既存テスト60件も全件維持。

---

## 品質評価

- テスト結果: 全74件 PASS ✅
- 実装品質: シンプルかつ動作する ✅
- ファイルサイズ: 165行（800行制限以下） ✅
- モック使用: 実装コードにモック・スタブなし ✅
- コンパイルエラー: なし（`npm run build` 成功） ✅
- 後方互換性: LINE Props 未指定時の既存テスト全件維持 ✅

---

## 課題・改善点（Refactorフェーズで対応）

- コメントの整理・統一（信頼性レベル記号の一貫性）
- `lineProvider` 変数のスコープをより明確に表現する方法の検討
- Red フェーズの `as any` 型アサーションが不要になった（`CognitoStackProps` に型が追加されたため）
