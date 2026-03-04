# TASK-0147 設定作業実行

## 作業概要

- **タスクID**: TASK-0147
- **作業内容**: `app.ts` の dev/prod 環境の `CognitoStack` インスタンス化に LINE Login の Props（`lineLoginChannelId`, `lineLoginChannelSecret`）を追加
- **実行日時**: 2026-03-04
- **実行者**: Claude Code

## 設計文書参照

- **参照文書**:
  - `docs/tasks/cognito-line-login/TASK-0147.md`
  - `docs/spec/cognito-line-login/requirements.md`
  - `docs/design/cognito-line-login/architecture.md`
  - `docs/spec/cognito-line-login/note.md`
- **関連要件**: REQ-006, REQ-007

## 実行した作業

### 1. dev 環境の `CognitoStack` に LINE Login Props を追加

**変更ファイル**: `infrastructure/cdk/bin/app.ts`

```typescript
new CognitoStack(app, 'MemoruCognitoDev', {
  environment: 'dev',
  cognitoDomainPrefix: 'memoru-dev',
  callbackUrls: ['http://localhost:3000/callback', 'https://localhost:3000/callback'],
  logoutUrls: ['http://localhost:3000/', 'https://localhost:3000/'],
  lineLoginChannelId: process.env.LINE_LOGIN_CHANNEL_ID,      // 追加
  lineLoginChannelSecret: process.env.LINE_LOGIN_CHANNEL_SECRET, // 追加
});
```

### 2. prod 環境の `CognitoStack` に LINE Login Props を追加

**変更ファイル**: `infrastructure/cdk/bin/app.ts`

```typescript
new CognitoStack(app, 'MemoruCognitoProd', {
  environment: 'prod',
  cognitoDomainPrefix: 'memoru-prod',
  callbackUrls: ['https://liff.example.com/callback'],
  logoutUrls: ['https://liff.example.com/'],
  lineLoginChannelId: process.env.LINE_LOGIN_CHANNEL_ID,      // 追加
  lineLoginChannelSecret: process.env.LINE_LOGIN_CHANNEL_SECRET, // 追加
});
```

### 3. ビルド確認

```bash
cd infrastructure/cdk
npm run build
```

**結果**: TypeScript コンパイルエラーなく成功

## 作業結果

- [x] dev 環境の `CognitoStack` に `lineLoginChannelId` と `lineLoginChannelSecret` が Props として渡されている
- [x] prod 環境の `CognitoStack` に `lineLoginChannelId` と `lineLoginChannelSecret` が Props として渡されている
- [x] Channel ID/Secret は `process.env` から取得し、ハードコードしていない
- [x] `npm run build` が成功する

## 注意事項

- `process.env.LINE_LOGIN_CHANNEL_ID` が `undefined` の場合、Props は `undefined` となり、TASK-0146 の条件分岐で LINE IdP は作成されない（意図した動作）
- dev/prod で異なる LINE Login チャネルを使用する場合は、環境変数名を分離する必要がある（例: `LINE_LOGIN_CHANNEL_ID_DEV` / `LINE_LOGIN_CHANNEL_ID_PROD`）。現在は共通の環境変数を使用

## 次のステップ

- `/tsumiki:direct-verify` を実行してビルドおよびコード内容を確認
