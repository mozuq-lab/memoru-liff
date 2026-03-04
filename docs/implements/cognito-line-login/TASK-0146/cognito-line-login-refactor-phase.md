# Refactor フェーズ記録: cognito-line-login TASK-0146

**タスクID**: TASK-0146
**フェーズ**: Refactor（品質改善）
**作成日**: 2026-03-04

---

## リファクタリング概要

Green フェーズで動作する実装を、以下の観点で品質改善した。

1. テストコードの `as any` 型アサーションの除去（型安全性向上）
2. テストコメントの簡潔化（DRY・可読性向上）
3. 実装ファイルのコメント整理（「最小限の実装」等の表現を適切な説明に変更）

---

## 改善内容

### 改善1: `as any` 型アサーションの除去 🔵

**対象ファイル**: `infrastructure/cdk/test/cognito-stack.test.ts`

**改善前**:
```typescript
// NOTE: CognitoStackProps にまだ lineLoginChannelId/lineLoginChannelSecret が存在しないため
//       Red フェーズでは型アサーション (as any) を一時的に使用する
const devPropsWithLine = {
  ...devProps,
  lineLoginChannelId: 'test-channel-id',
  lineLoginChannelSecret: 'test-channel-secret',
} as any;

const propsWithIdOnly = {
  ...devProps,
  lineLoginChannelId: 'test-channel-id',
} as any;
```

**改善後**:
```typescript
// 🔵 CognitoStackProps に lineLoginChannelId/lineLoginChannelSecret が追加されたため型安全
const devPropsWithLine: CognitoStackProps = {
  ...devProps,
  lineLoginChannelId: 'test-channel-id',
  lineLoginChannelSecret: 'test-channel-secret',
};

const propsWithIdOnly: CognitoStackProps = {
  ...devProps,
  lineLoginChannelId: 'test-channel-id',
  // lineLoginChannelSecret は未指定（undefined）
};
```

**除去箇所**: 計 5 箇所（`devPropsWithLine`, `prodPropsWithLine`, `propsWithIdOnly`, `propsWithSecretOnly`, `propsWithEmptyLine`）

**改善理由**: Green フェーズで `CognitoStackProps` に `lineLoginChannelId?` / `lineLoginChannelSecret?` が追加されたため、`as any` は不要になった。型安全性を維持するために明示的な型アノテーションに変更した。

---

### 改善2: テストコメントの簡潔化 🔵

**対象ファイル**: `infrastructure/cdk/test/cognito-stack.test.ts`

**改善前**: 各テストに `【テスト目的】`, `【テスト内容】`, `【期待される動作】`, `【テストデータ準備】`, `【初期条件設定】`, `【結果検証】`, `【期待値確認】`, `【確認内容】` といった多層コメントが存在し冗長だった。

**改善後**: 各テストに 1 行の信頼性レベル付きコメントで要点を記述。

```typescript
// 改善前
test('TC-001: UserPoolIdentityProvider リソースが作成される', () => {
  // 【テスト目的】: lineLoginChannelId と lineLoginChannelSecret の両方を指定した場合に
  //               CloudFormation テンプレートに AWS::Cognito::UserPoolIdentityProvider リソースが含まれることを確認
  // 【テスト内容】: devPropsWithLine で CognitoStack を作成し、IdP リソースの存在を検証
  // 【期待される動作】: CognitoStack が LINE OIDC IdP リソースを条件付きで生成する
  // 🔵 青信号: REQ-001 受け入れ基準・既存テストパターン hasResourceProperties より
  // 【テストデータ準備】: LINE Props を含む CognitoStack を作成し CloudFormation テンプレートを取得
  // 【初期条件設定】: devPropsWithLine を使用して LINE IdP が作成される条件を構築
  const template = Template.fromStack(createStack(devPropsWithLine));
  // 【結果検証】: CloudFormation テンプレートに UserPoolIdentityProvider リソースが含まれることを確認
  // 【期待値確認】: ProviderType が OIDC であること（LINE Login は OIDC プロトコルを使用）
  template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', {
    ProviderType: 'OIDC', // 【確認内容】: LINE Login は OIDC プロトコルを使用するため OIDC が設定される
  });
});

// 改善後
test('TC-001: UserPoolIdentityProvider リソースが作成される', () => {
  // 🔵 REQ-001: lineLoginChannelId/Secret 両方指定時に OIDC IdP リソースが生成されること
  const template = Template.fromStack(createStack(devPropsWithLine));
  template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', {
    ProviderType: 'OIDC',
  });
});
```

---

### 改善3: 実装ファイルのコメント整理 🔵

**対象ファイル**: `infrastructure/cdk/lib/cognito-stack.ts`

**改善前**:
```typescript
// 【機能概要】: LINE Login を外部 OIDC IdP として Cognito UserPool に登録する 🔵
// 【実装方針】: lineLoginChannelId と lineLoginChannelSecret の両方が指定された場合のみ作成 (REQ-001)
// 【テスト対応】: TC-001〜TC-007 の失敗テストを通すための最小限の実装
// 【変数宣言位置の注意】: UserPoolClient の supportedIdentityProviders で参照するため、
//   addClient 呼び出し前に lineProvider を定義する必要がある
```

**改善後**:
```typescript
// 【機能概要】: LINE Login を外部 OIDC IdP として Cognito UserPool に登録する 🔵
// 【実装方針】: lineLoginChannelId と lineLoginChannelSecret の両方が指定された場合のみ作成 (REQ-001)
// 【後方互換性】: Props 未指定時は既存動作（COGNITO のみ）を維持する (REQ-401)
// 【変数宣言位置】: UserPoolClient の supportedIdentityProviders で参照するため、
//   addClient 呼び出し前に lineProvider を定義する必要がある
```

**変更点**:
- 「TC-001〜TC-007 の失敗テストを通すための最小限の実装」という TDD Red→Green フェーズ特有の表現を削除
- 「後方互換性」の明示的な記述を追加（REQ-401 参照）
- 「変数宣言位置の注意」→「変数宣言位置」に簡潔化
- `【エンドポイント設定】` → `【エンドポイント手動指定】` に変更（より具体的な説明）

---

## セキュリティレビュー結果

| 観点 | 評価 | 詳細 |
|---|---|---|
| Channel Secret のハードコード | 問題なし | Props 経由で注入。テストコードは `'test-channel-secret'` というテスト値のみ使用 |
| 型安全性 | 改善済み | `as any` を除去し、`CognitoStackProps` 型を明示 |
| 入力値検証 | 問題なし | `if (props.lineLoginChannelId && props.lineLoginChannelSecret)` で truthy チェック |
| PKCE | 問題なし | 既存の `generateSecret: false` で SPA は PKCE を使用 |

---

## パフォーマンスレビュー結果

| 観点 | 評価 | 詳細 |
|---|---|---|
| テスト実行時間 | 問題なし | 全74件: 1.412秒（2秒未満） |
| ファイルサイズ | 問題なし | cognito-stack.ts: 166行、test.ts: 330行（500行制限以下） |
| CDK synth 処理 | 問題なし | 条件分岐による不要リソース非作成で適切 |

---

## テスト実行結果

```bash
cd infrastructure/cdk && npm test

Test Suites: 3 passed, 3 total
Tests:       74 passed, 74 total
Snapshots:   8 passed, 8 total
Time:        1.412 s
```

---

## ビルド結果

```bash
cd infrastructure/cdk && npm run build
# 出力なし（成功）
```

TypeScript コンパイルエラーなし。

---

## 品質判定

✅ **高品質**

- テスト結果: 全74件 PASS
- セキュリティ: 重大な脆弱性なし
- パフォーマンス: 重大な性能課題なし
- リファクタ品質: `as any` 除去・コメント簡潔化・テスト可読性向上を達成
- ファイルサイズ: 500行制限以下
- ドキュメント: 完成

---

## 信頼性レベルサマリー

| 改善項目 | 信頼性 | 根拠 |
|---|---|---|
| `as any` 除去 | 🔵 | `CognitoStackProps` に型が追加された事実に基づく |
| テストコメント簡潔化 | 🔵 | 既存コードの冗長性を明確に特定した改善 |
| 実装コメント整理 | 🔵 | Green フェーズ固有の表現を Refactor フェーズ向けに更新 |
