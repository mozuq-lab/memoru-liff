# cognito-line-login TDD開発完了記録

## 確認すべきドキュメント

- `docs/tasks/cognito-line-login/TASK-0146.md`
- `docs/implements/cognito-line-login/TASK-0146/cognito-line-login-requirements.md`
- `docs/implements/cognito-line-login/TASK-0146/testcases.md`

## 最終結果 (2026-03-04)

- **実装率**: 100% (14/14 テストケース)
- **テスト成功率**: 100% (74/74 全テスト PASS)
- **ビルド**: 成功（TypeScript コンパイルエラーなし）
- **品質判定**: 合格（✅ 高品質）
- **TDDフェーズ完了**: Red → Green → Refactor → Verify 全完了

## テストケース実装状況

| テストケース | 内容 | 状態 |
|---|---|---|
| TC-001 | UserPoolIdentityProvider リソース存在確認 | ✅ PASS |
| TC-002 | ProviderName が LINE であること | ✅ PASS |
| TC-003 | OIDC エンドポイント設定確認 | ✅ PASS |
| TC-004 | 属性マッピング（sub, name, picture）確認 | ✅ PASS |
| TC-005 | SupportedIdentityProviders に COGNITO + LINE | ✅ PASS |
| TC-006 | clientId / clientSecret の Props 伝搬確認 | ✅ PASS |
| TC-007 | OIDC スコープ openid, profile 確認 | ✅ PASS |
| TC-008 | dev + LINE IdP スナップショット | ✅ PASS |
| TC-009 | prod + LINE IdP スナップショット | ✅ PASS |
| TC-010 | Channel ID のみ指定時 IdP 非作成確認 | ✅ PASS |
| TC-011 | Channel Secret のみ指定時 IdP 非作成確認 | ✅ PASS |
| TC-012 | LINE Props 未指定時 IdP リソース 0 件確認 | ✅ PASS |
| TC-013 | 空文字列指定時 IdP 非作成確認 | ✅ PASS |
| TC-016 | LINE Props 未指定時 SupportedIdentityProviders が COGNITO のみ | ✅ PASS |

※ testcases.md の TC-014, TC-015 は既存スナップショットテスト（TC-001 より前の既存テストブロック）と重複するため別管理。TC-016 は TC-012 と同 describe ブロック内で検証。

## 💡 重要な技術学習

### 実装パターン

- **条件付き IdP 作成**: `let lineProvider: T | undefined` を宣言し `if (id && secret)` で条件付き作成後、`UserPoolClient` の `supportedIdentityProviders` にスプレッド演算子で追加するパターン
- **変数宣言順序**: `lineProvider` は `UserPoolClient` の `addClient` 呼び出し前に定義する必要がある（TypeScript の変数スコープ制約）
- **LINE OIDC エンドポイント手動指定**: LINE は `.well-known/openid-configuration` に非対応のため `endpoints` オブジェクトで各エンドポイントを明示指定
- **属性マッピング**: `attributeMapping.username` を使うと CloudFormation で `"undefined": "sub"` になる CDK バグがあるため `attributeMapping.custom` を使用

### テスト設計

- **CDK assertions の `resourceCountIs`**: `hasResourceProperties` の否定では捉えにくい「リソースが存在しない」ことを明示的に検証できる
- **スナップショットテスト**: 初回実行時に自動生成され、以降の変更を差分検出する。LINE IdP あり/なしで別スナップショットを管理
- **型安全なテストデータ**: Red フェーズでは `as any` を一時使用し、Green フェーズで型追加後は明示的な `CognitoStackProps` 型アノテーションに切り替える

### 品質保証

- **後方互換性**: オプショナル Props を追加する場合は、未指定時の動作が既存と完全に同一であることを複数の検証方法（resourceCountIs + hasResourceProperties）で確認する
- **エッジケース**: 片方のみ指定・空文字列など実運用で発生しうるケースを必ず網羅する

## 関連情報

- **実装ファイル**: `infrastructure/cdk/lib/cognito-stack.ts`（166行）
- **テストファイル**: `infrastructure/cdk/test/cognito-stack.test.ts`（330行）
- **スナップショット**: `infrastructure/cdk/test/__snapshots__/cognito-stack.test.ts.snap`
- **後続タスク**: TASK-0147（app.ts への環境変数注入）
