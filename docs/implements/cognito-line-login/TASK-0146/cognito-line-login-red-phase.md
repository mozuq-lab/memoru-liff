# Red フェーズ記録: cognito-line-login TASK-0146

**タスクID**: TASK-0146
**フェーズ**: Red（失敗テスト作成）
**作成日**: 2026-03-04

---

## 作成したテストケース一覧

| テストID | テスト名 | 信頼性 | 状態 |
|---|---|---|---|
| TC-001 | UserPoolIdentityProvider リソースが作成される | 🔵 | 失敗（Red） |
| TC-002 | LINE IdP の ProviderName が LINE であること | 🔵 | 失敗（Red） |
| TC-003 | LINE OIDC エンドポイントが正しく設定されていること | 🟡 | 失敗（Red） |
| TC-004 | LINE 属性マッピング（sub, name, picture）が設定されていること | 🔵 | 失敗（Red） |
| TC-005 | UserPoolClient の SupportedIdentityProviders に COGNITO と LINE が含まれること | 🔵 | 失敗（Red） |
| TC-006 | LINE IdP の clientId と clientSecret が Props から正しく設定されること | 🟡 | 失敗（Red） |
| TC-007 | LINE IdP の OIDC スコープが openid, profile であること | 🟡 | 失敗（Red） |
| TC-008 | dev + LINE IdP のスナップショットが一致すること | 🔵 | PASS（スナップショット初回生成） |
| TC-009 | prod + LINE IdP のスナップショットが一致すること | 🔵 | PASS（スナップショット初回生成） |
| TC-010 | Channel ID のみ指定で IdP が作成されないこと | 🟡 | PASS（後方互換性） |
| TC-011 | Channel Secret のみ指定で IdP が作成されないこと | 🟡 | PASS（後方互換性） |
| TC-012 | LINE Props 未指定時に UserPoolIdentityProvider リソースが存在しないこと | 🔵 | PASS（後方互換性） |
| TC-013 | LINE Props 両方空文字列で LINE IdP が作成されないこと | 🟡 | PASS（後方互換性） |
| TC-016 | LINE Props 未指定時に UserPoolClient の SupportedIdentityProviders が COGNITO のみ | 🔵 | PASS（後方互換性） |

---

## 期待される失敗内容

### TC-001〜TC-007 の失敗メッセージ（共通）

```
Template has 0 resources with type AWS::Cognito::UserPoolIdentityProvider.
No matches found
```

- `cognito-stack.ts` に `lineLoginChannelId`/`lineLoginChannelSecret` の処理がまだ実装されていないため、LINE IdP リソースが作成されない
- TC-005 では SupportedIdentityProviders が `['COGNITO']` のみで `['COGNITO', 'LINE']` にならない

### TC-008〜TC-009 の状態

- スナップショット初回実行のため PASS（新規スナップショット生成）
- Green フェーズで実装後に再実行すると、スナップショットが更新される

### TC-010〜TC-013, TC-016 の状態

- 実装前なので条件分岐自体が存在せず、結果的に後方互換性テストは PASS
- Green フェーズ実装後も PASS が維持される（条件分岐が正しく動作する場合）

---

## テストファイル

**ファイル**: `infrastructure/cdk/test/cognito-stack.test.ts`

テストは既存の `describe('CognitoStack', () => {})` ブロックに追加。新規追加した `describe('LINE Login IdP', () => {})` ブロックに TC-001〜TC-016 が含まれる。

---

## テスト実行コマンドと結果

```bash
cd infrastructure/cdk && npm test
```

**結果**:
- 失敗: 7件（TC-001〜TC-007）
- 通過: 67件（既存テスト + 後方互換性テスト）
- スナップショット: 2件新規生成
- 合計: 74テスト

---

## Green フェーズで実装すべき内容

### `infrastructure/cdk/lib/cognito-stack.ts` の変更

1. **`CognitoStackProps` の拡張**（L7-12）:
   ```typescript
   export interface CognitoStackProps extends cdk.StackProps {
     environment: Environment;
     cognitoDomainPrefix: string;
     callbackUrls: string[];
     logoutUrls: string[];
     lineLoginChannelId?: string;     // 追加
     lineLoginChannelSecret?: string; // 追加
   }
   ```

2. **`UserPoolIdentityProviderOidc` の条件付き作成**（UserPool Domain 後、UserPoolClient 前）:
   ```typescript
   let lineProvider: cognito.UserPoolIdentityProviderOidc | undefined;
   if (props.lineLoginChannelId && props.lineLoginChannelSecret) {
     lineProvider = new cognito.UserPoolIdentityProviderOidc(this, 'LineLoginProvider', {
       userPool: this.userPool,
       name: 'LINE',
       clientId: props.lineLoginChannelId,
       clientSecret: props.lineLoginChannelSecret,
       issuerUrl: 'https://access.line.me',
       endpoints: {
         authorization: 'https://access.line.me/oauth2/v2.1/authorize',
         token: 'https://api.line.me/oauth2/v2.1/token',
         userInfo: 'https://api.line.me/v2/profile',
         jwksUri: 'https://api.line.me/oauth2/v2.1/certs',
       },
       scopes: ['openid', 'profile'],
       attributeMapping: {
         custom: {
           username: cognito.ProviderAttribute.other('sub'),
           name: cognito.ProviderAttribute.other('name'),
           picture: cognito.ProviderAttribute.other('picture'),
         },
       },
     });
   }
   ```

3. **`UserPoolClient` の `supportedIdentityProviders` 更新**:
   ```typescript
   supportedIdentityProviders: [
     cognito.UserPoolClientIdentityProvider.COGNITO,
     ...(lineProvider ? [cognito.UserPoolClientIdentityProvider.custom('LINE')] : []),
   ],
   ```

4. **既存スナップショットの更新**:
   - `npm test -- --updateSnapshot` で既存スナップショットを更新
