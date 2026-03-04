# TASK-0146 TDD テストケース定義書: CognitoStack LINE Login 外部 IdP 実装

**タスクID**: TASK-0146
**機能名**: cognito-line-login
**要件名**: cognito-stack.ts に LINE Login を外部 OIDC IdP として登録する機能を追加する
**出力ファイル名**: `docs/implements/cognito-line-login/TASK-0146/testcases.md`
**作成日**: 2026-03-04

---

## 1. 正常系テストケース（基本的な動作）

### TC-001: LINE Props 指定時に UserPoolIdentityProvider リソースが作成される

- **テスト名**: LINE IdP リソース存在確認テスト
  - **何をテストするか**: `lineLoginChannelId` と `lineLoginChannelSecret` の両方を指定した場合に、CloudFormation テンプレートに `AWS::Cognito::UserPoolIdentityProvider` リソースが含まれることを確認する
  - **期待される動作**: CognitoStack が LINE OIDC IdP リソースを条件付きで生成する
- **入力値**: `devPropsWithLine`（`lineLoginChannelId: 'test-channel-id'`, `lineLoginChannelSecret: 'test-channel-secret'` を含む Props）
  - **入力データの意味**: 両方の LINE Login Props が揃っている状態を代表する。値はテスト用ダミーであり、CDK synth レベルでは実際の LINE チャネルとの通信は発生しない
- **期待される結果**: `template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', { ProviderType: 'OIDC' })` がアサーション成功する
  - **期待結果の理由**: REQ-001 の受け入れ基準「Channel ID/Secret 指定時に CDK デプロイ成功」および architecture.md のコンポーネント構成に基づく
- **テストの目的**: LINE IdP の条件付き作成ロジックが正常に動作することを確認する
  - **確認ポイント**: リソースが存在すること、`ProviderType` が `OIDC` であること
- 🔵 **青信号**: REQ-001 受け入れ基準・既存テストパターン `hasResourceProperties` より

---

### TC-002: LINE IdP の ProviderName が 'LINE' であること

- **テスト名**: LINE IdP プロバイダ名確認テスト
  - **何をテストするか**: 作成される IdP リソースの `ProviderName` が `LINE` であることを確認する
  - **期待される動作**: CDK が `name: 'LINE'` を CloudFormation の `ProviderName` プロパティとして出力する
- **入力値**: `devPropsWithLine`（LINE Props 指定済み）
  - **入力データの意味**: LINE IdP が作成される条件を満たす Props
- **期待される結果**: `template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', { ProviderName: 'LINE' })` がアサーション成功する
  - **期待結果の理由**: architecture.md のコード例で `name: 'LINE'` と指定されている。Cognito のプロバイダ名制約に準拠
- **テストの目的**: IdP の識別名が正しく設定されていることを確認する
  - **確認ポイント**: `ProviderName` が `LINE` であること（大文字小文字含め正確に一致）
- 🔵 **青信号**: architecture.md「UserPoolIdentityProviderOidc の追加」セクションのコード例より

---

### TC-003: LINE OIDC エンドポイントが正しく設定されていること

- **テスト名**: LINE OIDC エンドポイント設定確認テスト
  - **何をテストするか**: LINE IdP リソースの OIDC エンドポイント（Authorization, Token, UserInfo, JWKS）が正しい URL で設定されていることを確認する
  - **期待される動作**: CDK が `endpoints` オブジェクトの各 URL を CloudFormation の `ProviderDetails` に出力する
- **入力値**: `devPropsWithLine`（LINE Props 指定済み）
  - **入力データの意味**: LINE IdP が作成される条件を満たす Props
- **期待される結果**: `ProviderDetails` に以下が含まれる:
  - `authorize_url`: `https://access.line.me/oauth2/v2.1/authorize`
  - `token_url`: `https://api.line.me/oauth2/v2.1/token`
  - `attributes_url`: `https://api.line.me/v2/profile`
  - `jwks_uri`: `https://api.line.me/oauth2/v2.1/certs`
  - `oidc_issuer`: `https://access.line.me`
  - **期待結果の理由**: REQ-002 「LINE Login の OIDC エンドポイントを手動指定」、architecture.md のエンドポイント一覧より
- **テストの目的**: LINE が `.well-known/openid-configuration` に対応していない前提で、手動指定の各エンドポイントが正しく反映されることを確認する
  - **確認ポイント**: URL が正確に一致すること。CloudFormation 出力時のプロパティ名（`authorize_url` 等）は CDK の内部変換に依存するため、スナップショットでも併せて確認
- 🟡 **黄信号**: LINE OIDC エンドポイント URL は LINE Developers ドキュメントからの推測。CloudFormation プロパティ名（`authorize_url` 等）は CDK の内部変換に依存するため、実際のテンプレート出力で確認が必要

---

### TC-004: LINE 属性マッピング（sub, name, picture）が正しく設定されていること

- **テスト名**: LINE 属性マッピング確認テスト
  - **何をテストするか**: LINE IdP の属性マッピングで `sub`、`name`、`picture` が Cognito ユーザー属性にマッピングされていることを確認する
  - **期待される動作**: CDK が `attributeMapping` を CloudFormation の `AttributeMapping` プロパティとして出力する
- **入力値**: `devPropsWithLine`（LINE Props 指定済み）
  - **入力データの意味**: LINE IdP が作成される条件を満たす Props
- **期待される結果**: `AttributeMapping` に以下のマッピングが含まれる:
  - `username` → `sub`（LINE ユーザー ID）
  - `name` → `name`（表示名）
  - `picture` → `picture`（プロフィール画像 URL）
  - **期待結果の理由**: REQ-003「LINE 属性（sub, name, picture）を Cognito ユーザー属性にマッピング」、architecture.md の属性マッピング表より
- **テストの目的**: LINE から取得するユーザー属性が正しく Cognito に連携されることを確認する
  - **確認ポイント**: マッピングのキー・値の組み合わせが正しいこと。`sub` の Cognito 側マッピング先が `username`（自動）であることに注意
- 🔵 **青信号**: REQ-003・architecture.md「属性マッピング」セクションより

---

### TC-005: UserPoolClient の supportedIdentityProviders に COGNITO と LINE が含まれること

- **テスト名**: UserPoolClient サポート IdP 確認テスト（LINE あり）
  - **何をテストするか**: LINE Props 指定時に `UserPoolClient` の `SupportedIdentityProviders` が `['COGNITO', 'LINE']` であることを確認する
  - **期待される動作**: CDK が `supportedIdentityProviders` 配列に LINE を条件付きで追加する
- **入力値**: `devPropsWithLine`（LINE Props 指定済み）
  - **入力データの意味**: LINE IdP が作成される条件を満たす Props
- **期待される結果**: `template.hasResourceProperties('AWS::Cognito::UserPoolClient', { SupportedIdentityProviders: ['COGNITO', 'LINE'] })` がアサーション成功する
  - **期待結果の理由**: REQ-004「supportedIdentityProviders に LINE を追加」、REQ-005「LINE Login とメール+パスワード認証の両方が利用可能」より
- **テストの目的**: Hosted UI に LINE ログインボタンとメール認証フォームの両方が表示される設定になっていることを確認する
  - **確認ポイント**: `COGNITO`（既存）と `LINE`（新規）の両方が含まれること。順序も確認（`COGNITO` が先）
- 🔵 **青信号**: REQ-004, REQ-005・architecture.md「UserPoolClient の更新」セクションより

---

### TC-006: LINE IdP の clientId と clientSecret が Props から正しく設定されること

- **テスト名**: LINE IdP クライアント情報設定確認テスト
  - **何をテストするか**: `lineLoginChannelId` と `lineLoginChannelSecret` の値が IdP リソースの `ProviderDetails` に正しく反映されていることを確認する
  - **期待される動作**: CDK が Props の値を CloudFormation の `ProviderDetails.client_id` / `ProviderDetails.client_secret` として出力する
- **入力値**: `devPropsWithLine`（`lineLoginChannelId: 'test-channel-id'`, `lineLoginChannelSecret: 'test-channel-secret'`）
  - **入力データの意味**: テスト用のダミー Channel ID / Secret。実際の値ではないが、Props → CloudFormation への値の伝搬を確認するのに十分
- **期待される結果**: `ProviderDetails` に `client_id: 'test-channel-id'`、`client_secret: 'test-channel-secret'` が含まれる
  - **期待結果の理由**: CDK の `UserPoolIdentityProviderOidc` の `clientId` / `clientSecret` プロパティが CloudFormation の `ProviderDetails` に出力される
- **テストの目的**: Props から IdP 設定への値の伝搬が正しく行われることを確認する
  - **確認ポイント**: 値が正確に一致すること（変換や加工が行われていないこと）
- 🟡 **黄信号**: CloudFormation 出力のプロパティ名（`client_id` / `client_secret`）は CDK の内部変換に依存。スナップショットで実際の出力を確認する必要がある

---

### TC-007: LINE IdP の OIDC スコープが openid, profile であること

- **テスト名**: LINE IdP スコープ設定確認テスト
  - **何をテストするか**: LINE IdP リソースの OIDC スコープが `openid` と `profile` に設定されていることを確認する
  - **期待される動作**: CDK が `scopes: ['openid', 'profile']` を CloudFormation の `ProviderDetails` に出力する
- **入力値**: `devPropsWithLine`（LINE Props 指定済み）
  - **入力データの意味**: LINE IdP が作成される条件を満たす Props
- **期待される結果**: `ProviderDetails` に `authorize_scopes: 'openid profile'` が含まれる（CDK が配列をスペース区切り文字列に変換する）
  - **期待結果の理由**: architecture.md のコード例で `scopes: ['openid', 'profile']` と指定されている。LINE Login が対応するスコープ
- **テストの目的**: LINE IdP が要求するスコープが正しく設定されていることを確認する
  - **確認ポイント**: `openid` と `profile` の両方が含まれること
- 🟡 **黄信号**: CDK が `scopes` 配列をどのように CloudFormation に出力するか（スペース区切り文字列 or 配列）は実際のテンプレートで確認が必要

---

### TC-008: LINE Props あり（dev 環境）のスナップショットテスト

- **テスト名**: LINE IdP 付き dev 環境スナップショットテスト
  - **何をテストするか**: LINE Props を含む dev 環境の CognitoStack が生成する CloudFormation テンプレートのスナップショットを取得・比較する
  - **期待される動作**: テンプレート全体の構造が期待通りであること（初回実行時にスナップショット生成、以降は差分検出）
- **入力値**: `devPropsWithLine`（dev 環境 + LINE Props 指定済み）
  - **入力データの意味**: LINE IdP を含む完全な dev 環境構成
- **期待される結果**: `expect(template.toJSON()).toMatchSnapshot()` がアサーション成功する
  - **期待結果の理由**: 既存のスナップショットテストパターンに準拠。テンプレート全体の整合性を保証する
- **テストの目的**: LINE IdP 追加によるテンプレート全体への影響を包括的に確認する
  - **確認ポイント**: IdP リソース、UserPoolClient の変更、その他のリソースへの意図しない影響がないこと
- 🔵 **青信号**: 既存テストパターン（`cognito-stack.test.ts` L26-29）より

---

### TC-009: prod 環境 + LINE IdP のスナップショットテスト

- **テスト名**: LINE IdP 付き prod 環境スナップショットテスト
  - **何をテストするか**: LINE Props を含む prod 環境の CognitoStack が生成する CloudFormation テンプレートのスナップショットを取得・比較する
  - **期待される動作**: prod 固有の設定（DeletionProtection: ACTIVE, RemovalPolicy: RETAIN）が LINE IdP 追加後も維持されること
- **入力値**: `prodPropsWithLine`（prod 環境 + LINE Props 指定済み）
  - **入力データの意味**: LINE IdP を含む完全な prod 環境構成。prod 固有の設定が維持されることを確認する
- **期待される結果**: `expect(template.toJSON()).toMatchSnapshot()` がアサーション成功する
  - **期待結果の理由**: 既存テストで prod/dev の環境差分テストが確立されており、LINE IdP 追加後もこのパターンを継続する
- **テストの目的**: prod 環境での LINE IdP 追加が環境固有の設定に影響しないことを確認する
  - **確認ポイント**: DeletionProtection、RemovalPolicy が prod 設定のまま維持されること
- 🔵 **青信号**: 既存テストパターン（`cognito-stack.test.ts` L31-34）・要件定義パターン4 より

---

## 2. 異常系テストケース（エラーハンドリング）

### TC-010: Channel ID のみ指定（Secret 未指定）で LINE IdP が作成されないこと

- **テスト名**: LINE Channel ID のみ指定時の IdP 非作成テスト
  - **エラーケースの概要**: `lineLoginChannelId` のみ指定し `lineLoginChannelSecret` を未指定にした場合、LINE IdP が作成されずエラーも発生しないことを確認する
  - **エラー処理の重要性**: 片方の Props のみ指定はユーザーの設定ミスの可能性があるが、CDK synth/deploy は正常に完了する必要がある（グレースフルデグラデーション）
- **入力値**: `{ ...devProps, lineLoginChannelId: 'test-channel-id' }`（`lineLoginChannelSecret` は undefined）
  - **不正な理由**: 条件分岐ロジック「両方指定時のみ作成」に対して片方のみの指定は不完全な設定
  - **実際の発生シナリオ**: 開発者が環境変数 `LINE_LOGIN_CHANNEL_SECRET` の設定を忘れた場合
- **期待される結果**: `AWS::Cognito::UserPoolIdentityProvider` リソースが CloudFormation テンプレートに含まれないこと。`UserPoolClient` の `SupportedIdentityProviders` が `['COGNITO']` のみ
  - **エラーメッセージの内容**: エラーメッセージは発生しない（暗黙的にスキップ）
  - **システムの安全性**: 既存の Cognito 動作がそのまま維持される
- **テストの目的**: 不完全な LINE Props での安全な動作を確認する
  - **品質保証の観点**: 設定ミスによるデプロイ失敗を防止し、後方互換性を保証する
- 🟡 **黄信号**: 条件分岐ロジック（両方指定時のみ作成）から妥当な推測。要件定義エッジケース1 に対応

---

### TC-011: Channel Secret のみ指定（ID 未指定）で LINE IdP が作成されないこと

- **テスト名**: LINE Channel Secret のみ指定時の IdP 非作成テスト
  - **エラーケースの概要**: `lineLoginChannelSecret` のみ指定し `lineLoginChannelId` を未指定にした場合、LINE IdP が作成されずエラーも発生しないことを確認する
  - **エラー処理の重要性**: TC-010 と同様のグレースフルデグラデーション。どちらの Props が欠けても同じ動作になることを保証する
- **入力値**: `{ ...devProps, lineLoginChannelSecret: 'test-channel-secret' }`（`lineLoginChannelId` は undefined）
  - **不正な理由**: 条件分岐ロジック「両方指定時のみ作成」に対して片方のみの指定は不完全な設定
  - **実際の発生シナリオ**: 開発者が環境変数 `LINE_LOGIN_CHANNEL_ID` の設定を忘れた場合
- **期待される結果**: `AWS::Cognito::UserPoolIdentityProvider` リソースが CloudFormation テンプレートに含まれないこと。`UserPoolClient` の `SupportedIdentityProviders` が `['COGNITO']` のみ
  - **エラーメッセージの内容**: エラーメッセージは発生しない（暗黙的にスキップ）
  - **システムの安全性**: 既存の Cognito 動作がそのまま維持される
- **テストの目的**: 不完全な LINE Props での安全な動作を確認する（ID/Secret の非対称テスト）
  - **品質保証の観点**: どちらの Props が欠けても同じ安全な動作になることを保証する
- 🟡 **黄信号**: 条件分岐ロジック（両方指定時のみ作成）から妥当な推測。要件定義エッジケース2 に対応

---

## 3. 境界値テストケース（最小値、最大値、null等）

### TC-012: LINE Props 両方 undefined（既存動作の後方互換性テスト）

- **テスト名**: LINE Props 未指定時の後方互換性テスト
  - **境界値の意味**: LINE Login 機能が追加される前の既存の Props 構成を代表する。オプショナル Props が全て `undefined` の状態
  - **境界値での動作保証**: 新機能追加後も既存の動作が完全に維持されることを保証する
- **入力値**: `devProps`（既存の Props、LINE Props なし）
  - **境界値選択の根拠**: REQ-001 受け入れ基準「未指定の場合 LINE IdP が登録されない」の直接的な検証
  - **実際の使用場面**: LINE Login を設定していない既存の全デプロイメントで発生する最も一般的なケース
- **期待される結果**:
  - `AWS::Cognito::UserPoolIdentityProvider` リソースが CloudFormation テンプレートに含まれない（`template.resourceCountIs('AWS::Cognito::UserPoolIdentityProvider', 0)`）
  - `UserPoolClient` の `SupportedIdentityProviders` が `['COGNITO']` のみ
  - **境界での正確性**: 既存のスナップショットと完全に一致すること
  - **一貫した動作**: Props 追加前後で生成されるテンプレートに差分がないこと
- **テストの目的**: 後方互換性を保証する最も重要なテスト
  - **堅牢性の確認**: 新しい Props の追加が既存動作に影響しないことを確認する
- 🔵 **青信号**: REQ-001 受け入れ基準・REQ-401〜404 後方互換性制約より

---

### TC-013: LINE Props 両方空文字列で LINE IdP が作成されないこと

- **テスト名**: LINE Props 空文字列時の IdP 非作成テスト
  - **境界値の意味**: `undefined` と空文字列 `''` の境界。JavaScript/TypeScript の truthy/falsy 評価で `''` は falsy であるため、`undefined` と同じ動作になることを確認する
  - **境界値での動作保証**: `if (props.lineLoginChannelId && props.lineLoginChannelSecret)` の条件判定が空文字列を正しく除外すること
- **入力値**: `{ ...devProps, lineLoginChannelId: '', lineLoginChannelSecret: '' }`
  - **境界値選択の根拠**: 環境変数が設定されているが空文字列の場合（`process.env.LINE_LOGIN_CHANNEL_ID` が `''`）の実運用シナリオに対応
  - **実際の使用場面**: 環境変数ファイル（.env）で `LINE_LOGIN_CHANNEL_ID=` のように値なしで設定された場合
- **期待される結果**:
  - `AWS::Cognito::UserPoolIdentityProvider` リソースが CloudFormation テンプレートに含まれない
  - `UserPoolClient` の `SupportedIdentityProviders` が `['COGNITO']` のみ
  - **境界での正確性**: `''`（falsy）が `undefined` と同等に扱われること
  - **一貫した動作**: 空文字列と未指定で同じ動作になること
- **テストの目的**: TypeScript の truthy/falsy 評価が正しく機能していることを確認する
  - **堅牢性の確認**: 空文字列による意図しない IdP 作成を防止する
- 🟡 **黄信号**: TypeScript の truthy/falsy 評価から妥当な推測。要件定義エッジケース3 に対応

---

### TC-014: 既存の dev スナップショットテストが LINE Props 追加後も変更なしで通過すること

- **テスト名**: 既存 dev スナップショット後方互換性テスト
  - **境界値の意味**: CognitoStackProps インターフェースにオプショナル Props を追加しても、既存の Props のみでスタックを作成した場合のテンプレートが変わらないことを確認する
  - **境界値での動作保証**: インターフェース拡張が既存のコードパスに影響しないことを保証する
- **入力値**: `devProps`（既存の devProps、変更なし）
  - **境界値選択の根拠**: 既存テスト（`cognito-stack.test.ts` L26-29）と完全に同じ入力
  - **実際の使用場面**: LINE Login を使用しない既存環境でのテスト実行
- **期待される結果**: `expect(template.toJSON()).toMatchSnapshot()` がアサーション成功する（既存のスナップショットと完全一致）
  - **境界での正確性**: スナップショットの差分がゼロであること
  - **一貫した動作**: 既存テストの変更なしでの通過
- **テストの目的**: 既存テストの安定性を保証する
  - **堅牢性の確認**: 新機能追加による既存テストの破壊を防止する
- 🔵 **青信号**: 既存テスト（`cognito-stack.test.ts` L26-29）・タスク完了条件「既存のスナップショットテストが更新されている」より

---

### TC-015: 既存の prod スナップショットテストが LINE Props 追加後も変更なしで通過すること

- **テスト名**: 既存 prod スナップショット後方互換性テスト
  - **境界値の意味**: TC-014 と同様だが prod 環境について確認。prod 固有の設定（DeletionProtection, RemovalPolicy）が影響を受けないこと
  - **境界値での動作保証**: prod 環境のテンプレートが CognitoStackProps 拡張後も変わらないこと
- **入力値**: `prodProps`（既存の prodProps、変更なし）
  - **境界値選択の根拠**: 既存テスト（`cognito-stack.test.ts` L31-34）と完全に同じ入力
  - **実際の使用場面**: LINE Login を使用しない本番環境でのテスト実行
- **期待される結果**: `expect(template.toJSON()).toMatchSnapshot()` がアサーション成功する（既存のスナップショットと完全一致）
  - **境界での正確性**: スナップショットの差分がゼロであること
  - **一貫した動作**: prod 固有設定の維持
- **テストの目的**: prod 環境の既存テストの安定性を保証する
  - **堅牢性の確認**: 新機能追加による本番環境テンプレートへの意図しない影響を防止する
- 🔵 **青信号**: 既存テスト（`cognito-stack.test.ts` L31-34）・タスク完了条件より

---

### TC-016: LINE Props 未指定時に UserPoolIdentityProvider リソースが 0 件であること

- **テスト名**: LINE Props 未指定時の IdP リソース数確認テスト
  - **境界値の意味**: `resourceCountIs` でリソース数を明示的に 0 と検証する。`hasResourceProperties` のアサーションエラーとは異なり、リソース自体が存在しないことを明確に保証する
  - **境界値での動作保証**: 条件分岐の false パスで IdP リソースが一切作成されないこと
- **入力値**: `devProps`（LINE Props なし）
  - **境界値選択の根拠**: 後方互換性テスト（TC-012）と同じ入力だが、検証方法が異なる（`resourceCountIs` を使用）
  - **実際の使用場面**: LINE Login 未設定の環境で IdP リソースが誤って作成されないことの確認
- **期待される結果**: `template.resourceCountIs('AWS::Cognito::UserPoolIdentityProvider', 0)` がアサーション成功する
  - **境界での正確性**: リソース数が厳密に 0 であること
  - **一貫した動作**: Props 指定なしで常に 0 件
- **テストの目的**: `hasResourceProperties` の否定では捉えにくいリソース存在の有無を明示的に検証する
  - **堅牢性の確認**: 意図しないリソース作成を防止する
- 🔵 **青信号**: CDK assertions API の `resourceCountIs` パターン・REQ-001 受け入れ基準より

---

## 4. 開発言語・フレームワーク

- **プログラミング言語**: TypeScript ~5.6.3
  - **言語選択の理由**: 既存の CDK プロジェクトが TypeScript で実装されており、既存テスト（`cognito-stack.test.ts`）と同じ言語を使用する
  - **テストに適した機能**: 型安全性により Props のインターフェース拡張が正しいことをコンパイル時に検証可能。`CognitoStackProps` の型チェックにより不正な Props の検出が可能
- **テストフレームワーク**: Jest ^29.7.0 + ts-jest ^29.2.5
  - **フレームワーク選択の理由**: 既存テスト環境（`infrastructure/cdk/package.json`）で使用されており、スナップショットテスト機能が CDK テンプレートの検証に適している
  - **テスト実行環境**: `cd infrastructure/cdk && npm test` で実行。ts-jest により TypeScript の直接実行が可能
- **CDK テストライブラリ**: `aws-cdk-lib/assertions` の `Template`
  - **ライブラリ選択の理由**: 既存テスト（`cognito-stack.test.ts`）で `Template.fromStack()`, `hasResourceProperties()`, `toMatchSnapshot()` が使用されており、同じパターンを継続する
- 🔵 **青信号**: 既存テストファイル（`cognito-stack.test.ts`）・`infrastructure/cdk/package.json` より

---

## 5. テストケース実装時の日本語コメント指針

### テストファイル全体の構成

```typescript
// 【テストファイル】: cognito-stack.test.ts
// 【テスト対象】: CognitoStack - LINE Login 外部 OIDC IdP 統合
// 【テスト方針】: CDK assertions の Template を使用し、CloudFormation テンプレートレベルで検証
```

### テスト用 Props 定義のコメント

```typescript
// 【テストデータ準備】: LINE Login Props を含む dev 環境の Props を定義
// 【前提条件】: lineLoginChannelId と lineLoginChannelSecret の両方が指定されている
const devPropsWithLine: CognitoStackProps = {
  ...devProps,
  lineLoginChannelId: 'test-channel-id',
  lineLoginChannelSecret: 'test-channel-secret',
};
```

### Given（準備フェーズ）のコメント

```typescript
// 【テストデータ準備】: LINE Props を含む CognitoStack を作成し CloudFormation テンプレートを取得
// 【初期条件設定】: devPropsWithLine を使用して LINE IdP が作成される条件を構築
// 【前提条件確認】: lineLoginChannelId と lineLoginChannelSecret の両方が truthy であること
const template = Template.fromStack(createStack(devPropsWithLine));
```

### When/Then（実行・検証フェーズ）のコメント

```typescript
// 【結果検証】: CloudFormation テンプレートに UserPoolIdentityProvider リソースが含まれることを確認
// 【期待値確認】: ProviderType が OIDC であること（LINE Login は OIDC プロトコルを使用）
// 【品質保証】: REQ-001 の受け入れ基準「CDK デプロイ成功」のテンプレートレベルでの保証
// 🔵 青信号: REQ-001 受け入れ基準より
template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', {
  ProviderType: 'OIDC',
  ProviderName: 'LINE',
});
```

### describe ブロックのコメント

```typescript
// 【テスト目的】: LINE Login 外部 OIDC IdP の条件付き登録機能をテスト
// 【テスト内容】: Props の有無による IdP 作成の条件分岐、属性マッピング、スナップショットを検証
// 【期待される動作】: LINE Props 指定時は IdP が作成され、未指定時は既存動作を維持
describe('LINE Login IdP', () => {
  // ...
});
```

### セットアップのコメント（既存パターン継続）

```typescript
// 【テスト前準備】: createStack ヘルパー関数で CognitoStack のインスタンスを作成
// 【環境初期化】: 各テストで新しい cdk.App() を作成し、スタック間の干渉を防止
function createStack(props: CognitoStackProps): CognitoStack {
  const app = new cdk.App();
  return new CognitoStack(app, 'TestCognitoStack', props);
}
```

---

## 6. 要件定義との対応関係

### 参照した機能概要

| テストケース | 参照した要件 | セクション |
|---|---|---|
| TC-001, TC-002 | REQ-001 | CDK で Cognito UserPool に LINE Login を UserPoolIdentityProviderOidc として登録 |
| TC-003 | REQ-002 | LINE Login の OIDC エンドポイントを手動指定 |
| TC-004 | REQ-003 | LINE 属性（sub, name, picture）を Cognito ユーザー属性にマッピング |
| TC-005 | REQ-004, REQ-005 | supportedIdentityProviders に LINE を追加、両方の認証方式が利用可能 |
| TC-006, TC-007 | REQ-001, REQ-002 | IdP リソースの Props 伝搬とスコープ設定 |

### 参照した入力・出力仕様

| テストケース | 参照した仕様 | セクション |
|---|---|---|
| TC-001〜TC-009 | CognitoStackProps 入力パラメータ | 要件定義書 2.1「入力パラメータ」 |
| TC-001〜TC-009 | 生成される AWS リソース | 要件定義書 2.2「出力」 |
| TC-003, TC-006, TC-007 | LINE OIDC エンドポイント構成 | 要件定義書 2.3「LINE OIDC エンドポイント構成」 |
| TC-004 | 属性マッピング仕様 | 要件定義書 2.4「属性マッピング仕様」 |

### 参照した制約条件

| テストケース | 参照した制約 | セクション |
|---|---|---|
| TC-012, TC-014, TC-015 | 後方互換性制約 | 要件定義書 3.1（REQ-401〜404） |
| TC-005 | アーキテクチャ制約 | 要件定義書 3.2（変数宣言順序） |
| TC-014, TC-015 | ビルド・テスト制約 | 要件定義書 3.3 |
| TC-010, TC-011, TC-013 | スコープ制約 | 要件定義書 3.5 |

### 参照した使用例

| テストケース | 参照した使用例 | セクション |
|---|---|---|
| TC-001〜TC-009 | パターン1: LINE IdP あり | 要件定義書 4.1 |
| TC-012, TC-014, TC-015 | パターン2: LINE IdP なし | 要件定義書 4.2 |
| TC-010 | エッジケース1: Channel ID のみ指定 | 要件定義書 4.3 |
| TC-011 | エッジケース2: Channel Secret のみ指定 | 要件定義書 4.4 |
| TC-013 | エッジケース3: 空文字列の指定 | 要件定義書 4.5 |
| TC-009 | エッジケース4: prod 環境 + LINE IdP あり | 要件定義書 4.6 |

---

## 7. テスト用データ定義

### 既存 Props（変更なし）

```typescript
// 【テストデータ】: 既存の dev 環境 Props（LINE Props なし）
const devProps: CognitoStackProps = {
  environment: 'dev',
  cognitoDomainPrefix: 'memoru-dev-test',
  callbackUrls: ['http://localhost:3000/callback'],
  logoutUrls: ['http://localhost:3000/'],
};

// 【テストデータ】: 既存の prod 環境 Props（LINE Props なし）
const prodProps: CognitoStackProps = {
  environment: 'prod',
  cognitoDomainPrefix: 'memoru-prod-test',
  callbackUrls: ['https://app.example.com/callback'],
  logoutUrls: ['https://app.example.com/'],
};
```

### 新規 Props（LINE Login 付き）

```typescript
// 【テストデータ】: LINE Login Props 付き dev 環境 Props
const devPropsWithLine: CognitoStackProps = {
  ...devProps,
  lineLoginChannelId: 'test-channel-id',
  lineLoginChannelSecret: 'test-channel-secret',
};

// 【テストデータ】: LINE Login Props 付き prod 環境 Props
const prodPropsWithLine: CognitoStackProps = {
  ...prodProps,
  lineLoginChannelId: 'test-channel-id',
  lineLoginChannelSecret: 'test-channel-secret',
};
```

### エッジケース Props

```typescript
// 【テストデータ】: Channel ID のみ指定（Secret 未指定）
const devPropsWithLineIdOnly: CognitoStackProps = {
  ...devProps,
  lineLoginChannelId: 'test-channel-id',
};

// 【テストデータ】: Channel Secret のみ指定（ID 未指定）
const devPropsWithLineSecretOnly: CognitoStackProps = {
  ...devProps,
  lineLoginChannelSecret: 'test-channel-secret',
};

// 【テストデータ】: 両方空文字列
const devPropsWithEmptyLine: CognitoStackProps = {
  ...devProps,
  lineLoginChannelId: '',
  lineLoginChannelSecret: '',
};
```

---

## 8. テストケースと完了条件の対応

| 完了条件 | 対応テストケース |
|---|---|
| `CognitoStackProps` に `lineLoginChannelId?` と `lineLoginChannelSecret?` が追加 | TC-001（Props を使用してスタック作成が成功することで暗黙的に検証） |
| LINE Props 指定時に `UserPoolIdentityProviderOidc` が作成 | TC-001, TC-002, TC-003, TC-006, TC-007 |
| LINE Props 未指定時、既存動作に影響なし | TC-012, TC-014, TC-015, TC-016 |
| LINE 属性（sub, name, picture）がマッピング | TC-004 |
| `supportedIdentityProviders` に LINE が条件付きで追加 | TC-005 |
| 既存スナップショットテストが更新 | TC-014, TC-015 |
| LINE IdP 登録テストが追加 | TC-001〜TC-009 |
| LINE Props 未指定時の後方互換性テストが追加 | TC-010, TC-011, TC-012, TC-013, TC-016 |
| `npm run build` が成功 | ビルド確認（テストケース外・実行時確認） |
| `npm test` が全件パス | 全テストケースの通過（テスト実行時確認） |

---

## 9. テストファイル構成案

```typescript
describe('CognitoStack', () => {
  // 【既存テスト】: 変更なし
  describe('Snapshot', () => {
    test('dev environment matches snapshot', () => { /* TC-014 */ });
    test('prod environment matches snapshot', () => { /* TC-015 */ });
  });

  // 【既存テスト】: 変更なし
  describe('Environment differences', () => { /* 既存テスト */ });
  describe('Security', () => { /* 既存テスト */ });
  describe('OIDC', () => { /* 既存テスト */ });
  describe('Domain', () => { /* 既存テスト */ });

  // 【新規テスト】: LINE Login IdP テスト
  describe('LINE Login IdP', () => {
    describe('LINE Props 指定時', () => {
      test('UserPoolIdentityProvider リソースが作成される', () => { /* TC-001 */ });
      test('ProviderName が LINE である', () => { /* TC-002 */ });
      test('OIDC エンドポイントが正しく設定されている', () => { /* TC-003 */ });
      test('属性マッピング（sub, name, picture）が設定されている', () => { /* TC-004 */ });
      test('UserPoolClient の SupportedIdentityProviders に COGNITO と LINE が含まれる', () => { /* TC-005 */ });
      test('clientId と clientSecret が Props から設定される', () => { /* TC-006 */ });
      test('OIDC スコープが openid, profile である', () => { /* TC-007 */ });
    });

    describe('Snapshot（LINE あり）', () => {
      test('dev + LINE IdP のスナップショット', () => { /* TC-008 */ });
      test('prod + LINE IdP のスナップショット', () => { /* TC-009 */ });
    });

    describe('LINE Props 未指定時（後方互換性）', () => {
      test('UserPoolIdentityProvider リソースが存在しない', () => { /* TC-012, TC-016 */ });
      test('Channel ID のみ指定で IdP が作成されない', () => { /* TC-010 */ });
      test('Channel Secret のみ指定で IdP が作成されない', () => { /* TC-011 */ });
      test('空文字列で IdP が作成されない', () => { /* TC-013 */ });
    });
  });
});
```

---

## 信頼性レベルサマリー

| カテゴリ | 項目数 | 🔵 青 | 🟡 黄 | 🔴 赤 |
|---|---|---|---|---|
| 正常系テストケース | 9 | 6 | 3 | 0 |
| 異常系テストケース | 2 | 0 | 2 | 0 |
| 境界値テストケース | 5 | 4 | 1 | 0 |
| 開発言語・フレームワーク | 1 | 1 | 0 | 0 |
| **合計** | **17** | **11 (65%)** | **6 (35%)** | **0 (0%)** |

**🟡 黄信号の内訳**:
- TC-003: LINE OIDC エンドポイント URL / CloudFormation プロパティ名の CDK 内部変換
- TC-006: `client_id` / `client_secret` の CloudFormation プロパティ名
- TC-007: `scopes` 配列の CloudFormation 出力形式
- TC-010: Channel ID のみ指定時の動作（条件分岐ロジックからの推測）
- TC-011: Channel Secret のみ指定時の動作（条件分岐ロジックからの推測）
- TC-013: 空文字列の truthy/falsy 評価（TypeScript 動作からの推測）

**🔴 赤信号**: 0件（設計文書・要件定義に基づかない推測なし）
