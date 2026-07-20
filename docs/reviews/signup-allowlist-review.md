# signup-allowlist ブランチレビュー

**ブランチ**: `feat/signup-allowlist`
**レビュー日**: 2026-07-20
**体制**: 実装・レビュー = Claude Sonnet 5（サブエージェント）/ 最終確認 = Claude Fable 5
**変更規模**: 既存 11 ファイル +605/-10 行、新規 6 ファイル 約 990 行（テスト 3 ファイル含む）
**設計**: [docs/design/signup-allowlist/architecture.md](../design/signup-allowlist/architecture.md)（設計段階のレビューは [design-review.md](../design/signup-allowlist/design-review.md)）

---

## 総合評価

Cognito PreSignUp トリガー + DynamoDB 許可リストによるサインアップ招待制化。
2 系統レビュー（backend/SAM/運用 CLI 系統・CDK/docs/横断整合性系統）で **High 1 件・Medium 4 件・
Low 5 件**を検出し、**全件修正済み**。横断整合性（Parameter 名・環境変数名・関数/テーブル名・
Output 名・make ターゲット名）は全項目実測突合で指摘ゼロ。

---

## Critical / High（修正済み）

### 1. `make allowlist-approve` が DynamoDB 予約語 `ttl` で必ず失敗する

- **場所**: `backend/Makefile` (allowlist-approve)
- **問題**: `UpdateExpression` の `REMOVE ttl` が予約語 `TTL` を素のまま使用。moto で本番同等の
  API 呼び出しを再現し `ValidationException: reserved keyword: ttl` を確認（`status` は `#s` で
  回避済みだった）
- **影響**: LINE 承認フローの中核コマンドが実 AWS で 100% 失敗する
- **対応**: ✅ `--expression-attribute-names` に `"#t": "ttl"` を追加し `REMOVE #t` に変更。
  moto で修正後の成功を再現確認

## Medium（修正済み）

### 2. NOTE / ID のシングルクォートでシェル構文エラー

- **場所**: `backend/Makefile` (allowlist-add / approve / remove)
- **問題**: `NOTE="friend's account"` 等で生成コマンドが構文エラー（再現確認済み）
- **対応**: ✅ python3 `json.dumps` で JSON リテラル化 → シェル変数経由のダブルクォート展開に変更

### 3. インフラ例外の生メッセージが Hosted UI に露出しうる

- **場所**: `backend/src/auth/pre_signup.py`
- **問題**: DynamoDB の ClientError / タイムアウト例外が素通しで Cognito に渡り、native 経路では
  AWS API 名等の内部情報が Hosted UI に表示されうる
- **対応**: ✅ 専用例外 `SignupNotAllowedError` を導入し、予期しない例外は `logger.exception` で
  サーバー側記録のうえ一般文言のみに変換（フェイルクローズ維持）。回帰テスト追加

### 4. `verify-presignup` のドキュメント記載漏れ

- **場所**: README.md / deployment-guide-prod.md / architecture.md
- **問題**: `COGNITO_USER_POOL_ARN` が必須なのにコマンド例が `ENV=prod` のみ（実行失敗を再現確認）
- **対応**: ✅ 全コマンド例に `COGNITO_USER_POOL_ARN=<...>` を明記

### 5. ブートストラップ警告が `console.warn`（非 TTY で失われる）

- **場所**: `infrastructure/cdk/lib/prod-config.ts`
- **問題**: 非 TTY の `cdk synth` では console.warn の出力が失われることを実証。「無自覚な
  フェイルオープン防止」という設計意図が環境依存で機能しない
- **対応**: ✅ `CognitoStack` 側で `isProd && 未配線` のとき `cdk.Annotations.addWarning`
  （keycloak-stack の M-40 と同型）。`Annotations.fromStack` によるテスト 3 件追加

## Low（修正済み）

| # | 指摘 | 対応 |
|---|---|---|
| 6 | Makefile の email 正規化が trim なし（Python 側と非対称。空白混じりコピペで照合不一致の運用事故リスク） | ✅ `tr -d '[:space:]'` を追加 |
| 7 | `allowlist_service.py` が共通ファクトリ `get_dynamodb_resource()` 不使用の意図が不明 | ✅ 理由（Cognito 5 秒制限用の専用短タイムアウト Config）をコメント化 |
| 8 | ruff format 非準拠 3 ファイル | ✅ 対象 3 ファイルのみ format 適用 |
| 9 | `userAttributes.email` 欠落ケースのテストなし | ✅ テスト追加（未登録扱いで拒否 = フェイルクローズ） |

## 指摘なしと確認された観点（抜粋）

- **横断整合性**: `CognitoUserPoolArn` / `COGNITO_USER_POOL_ARN` / `MEMORU_{PROD,DEV}_PRESIGNUP_LAMBDA_ARN` /
  `BOOTSTRAP-NO-TRIGGER` / `memoru-presignup-{env}` / `memoru-signup-allowlist-{env}` /
  `PreSignupFunctionArn` / make ターゲット名 — 全箇所で一致（grep + `make -n` 実測）
- **CDK**: `fromFunctionAttributes` の `sameEnvironment: false` + `skipPermissions: true` の挙動を
  aws-cdk-lib ソースで裏取り（addPermission の恒久 no-op 化・警告抑止）
- **セキュリティ**: PII をログに出さない（`log_event` 無効も確認）/ IAM は対象テーブルの
  GetItem/PutItem のみ / `ConditionalCheckFailedException` のみ握りつぶす例外処理 /
  pending 書き込みの冪等性
- **テスト品質**: 新規 2 モジュールはカバレッジ 100%、空振りテストなし（実装前コードで
  失敗することを確認済みのテストを含む）

---

## 最終確認（Fable）

- backend: pytest **1860 件全通過** / ruff check / mypy（84 ファイル）/ `sam validate --lint` すべてクリーン
- CDK: `npm run build`（tsc）クリーン / Jest **116 件全通過**（snapshot 8 件、更新なし）
- 全差分の通読により設計（architecture.md v1.1）との一致を確認
- IDE 上の TypeScript エラー表示（`process` 未解決等）は tsc がクリーンなことから
  型サーバーの表示上の問題と確認（実害なし）
