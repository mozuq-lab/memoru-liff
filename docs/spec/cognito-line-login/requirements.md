# Cognito LINE Login 外部 IdP 統合 要件定義書（軽量版）

## 概要

Amazon Cognito User Pool に LINE Login を外部 OIDC IdP として登録し、Cognito Hosted UI 経由で LINE アカウントによるサインインを可能にする（方式A）。CDK による IaC 実装を中心とし、フロントエンド・バックエンドのコード変更は最小限に抑える。

## 関連文書

- **ヒアリング記録**: [interview-record.md](interview-record.md)
- **コンテキストノート**: [note.md](note.md)
- **認証プロバイダ切り替え 設計**: [architecture.md](../../design/auth-provider-switch/architecture.md)
- **認証プロバイダ切り替え 要件**: [requirements.md](../auth-provider-switch/requirements.md)
- **デプロイ手順書**: [deployment-guide-dev.md](../../deployment-guide-dev.md)（Step 3 が本要件に対応）

## 背景・動機

認証プロバイダ切り替え（`auth-provider-switch`）の OIDC 汎用化は完了したが、Cognito 単体では LINE Login との統合がない。LIFF アプリとして LINE ユーザーがシームレスにログインするには、Cognito に LINE Login をフェデレーテッド IdP として登録する必要がある。

現在の手動リンク方式（`/users/link-line`）では、ユーザーが OIDC ログインと LINE リンクを別々に行う必要があり、UX が悪い。方式A により、LINE ユーザーは Cognito Hosted UI の「LINE でログイン」ボタンからワンステップで認証できるようになる。

## 主要機能要件

**【信頼性レベル凡例】**:
- 🔵 **青信号**: 設計文書・実装コード・ユーザヒアリングを参考にした確実な要件
- 🟡 **黄信号**: 設計文書・実装コード・ユーザヒアリングから妥当な推測による要件
- 🔴 **赤信号**: 設計文書・実装コード・ユーザヒアリングにない推測による要件

### 必須機能（Must Have）

- REQ-001: CDK で Cognito UserPool に LINE Login を `UserPoolIdentityProviderOidc` として登録できなければならない 🔵 *デプロイ手順書 Step 3・ユーザヒアリング「方式A で進める」より*
- REQ-002: CDK で LINE Login の OIDC エンドポイント（Authorization, Token, UserInfo, JWKS）を手動指定できなければならない 🟡 *LINE が標準 OIDC Discovery を提供しない可能性に基づく妥当な推測*
- REQ-003: CDK で LINE から取得した属性（sub, name, picture）を Cognito ユーザー属性にマッピングできなければならない 🔵 *デプロイ手順書 Step 3.4・Cognito IdP 仕様より*
- REQ-004: CDK で UserPoolClient の `supportedIdentityProviders` に LINE を追加し、Hosted UI に LINE ログインボタンを表示しなければならない 🔵 *ユーザヒアリング「両方併存」より*
- REQ-005: Cognito Hosted UI で LINE Login とメール+パスワード認証の両方が利用可能でなければならない 🔵 *ユーザヒアリング「両方併存（推奨）」より*
- REQ-006: `CognitoStackProps` に LINE Login チャネル情報（Channel ID, Channel Secret）を受け取る Props を追加しなければならない 🟡 *CDK 実装パターンから妥当な推測*
- REQ-007: LINE Login チャネル情報はハードコードせず、Props 経由で環境ごとに設定可能でなければならない 🔵 *既存の `app.ts` の環境分離パターンより*

### 基本的な制約

- REQ-401: 既存の OIDC 汎用化（`OidcIssuer`/`OidcAudience` パラメータ、`VITE_OIDC_AUTHORITY`/`VITE_OIDC_CLIENT_ID` 環境変数）を変更してはならない 🔵 *TASK-0123〜0125 の実装を維持*
- REQ-402: 既存の手動 LINE リンク機能（`/users/link-line` エンドポイント）は変更・削除してはならない 🔵 *ユーザヒアリング「後回し — 手動リンクは維持」より*
- REQ-403: フロントエンドの `oidc-client-ts` の設定変更は不要でなければならない（Cognito Hosted UI へのリダイレクトで動作する） 🔵 *ユーザヒアリング「Hosted UI 許容」・oidc-client-ts の OIDC 標準互換性より*
- REQ-404: バックエンドの Lambda コード変更は不要でなければならない 🔵 *auth-provider-switch REQ-003 の継続*
- REQ-405: LINE ユーザー ID の自動連携（Cognito 属性 → DynamoDB `line_user_id`）は本要件のスコープ外とする 🔵 *ユーザヒアリング「後回し」より*

## 簡易ユーザーストーリー

### ストーリー1: LINE アカウントでログイン

**私は** LINE ユーザー **として**
**LIFF アプリ起動時に Cognito Hosted UI の「LINE でログイン」ボタンからワンステップで認証したい**
**そうすることで** メールアドレスやパスワードを入力せずに、すぐにアプリを利用できる

**関連要件**: REQ-001, REQ-004, REQ-005

### ストーリー2: メールアドレスでログイン（LINE なし）

**私は** LINE を使っていないユーザー **として**
**メールアドレスとパスワードで従来どおりログインしたい**
**そうすることで** LINE アカウントがなくてもアプリを利用できる

**関連要件**: REQ-005

### ストーリー3: インフラ管理者による環境構築

**私は** インフラ管理者 **として**
**`npx cdk deploy` のみで LINE Login 統合を含む Cognito 環境を構築したい**
**そうすることで** AWS Console での手動設定を最小限に抑え、再現可能な環境構築ができる

**関連要件**: REQ-001, REQ-006, REQ-007

## 基本的な受け入れ基準

### REQ-001: CDK で LINE Login 外部 IdP を登録

**Given（前提条件）**: `CognitoStackProps` に LINE Login の Channel ID と Channel Secret が指定されている
**When（実行条件）**: `npx cdk deploy MemoruCognitoDev` を実行する
**Then（期待結果）**: Cognito UserPool に LINE が OIDC IdP として登録され、Hosted UI に LINE ログインボタンが表示される

**テストケース**:
- [ ] 正常系: LINE Login チャネル情報を指定して CDK デプロイが成功する
- [ ] 正常系: Cognito コンソールで LINE IdP が登録されていることを確認
- [ ] 正常系: Hosted UI に LINE ログインボタンが表示される
- [ ] 正常系: LINE Login チャネル情報が未指定の場合、LINE IdP が登録されない（既存動作に影響なし）

### REQ-005: 両方の認証方式が利用可能

**Given（前提条件）**: Cognito Hosted UI に LINE IdP とメール認証が設定されている
**When（実行条件）**: ユーザーが Hosted UI にアクセスする
**Then（期待結果）**: LINE ログインボタンとメール+パスワードフォームの両方が表示される

**テストケース**:
- [ ] 正常系: LINE ログインボタンから LINE 認証が完了し、Cognito JWT が発行される
- [ ] 正常系: メール+パスワードでログインが成功し、Cognito JWT が発行される
- [ ] 正常系: 発行された JWT で API Gateway の JWT Authorizer を通過できる

## 最小限の非機能要件

- **互換性**: 既存のフロントエンド（`oidc-client-ts`）・バックエンド（API Gateway JWT Authorizer）に変更を加えないこと 🔵 *OIDC 汎用化済みの設計を維持*
- **セキュリティ**: LINE Login チャネルの Channel Secret は CDK コード内にハードコードせず、環境変数またはシークレット管理で運用すること 🟡 *セキュリティベストプラクティスから妥当な推測*
- **可用性**: LINE Login の OIDC エンドポイントが一時的に利用不可の場合でも、メール+パスワード認証はフォールバックとして動作すること 🟡 *両方併存の設計から妥当な推測*

## 変更箇所の概要

### 変更対象

| ファイル | 変更内容 | 信頼性 |
|----------|---------|--------|
| `infrastructure/cdk/lib/cognito-stack.ts` | `UserPoolIdentityProviderOidc` 追加、属性マッピング、`supportedIdentityProviders` 更新 | 🔵 |
| `infrastructure/cdk/bin/app.ts` | LINE Login チャネル情報の Props 追加（dev/prod） | 🔵 |

### 変更不要（確認済み）

| ファイル | 理由 | 信頼性 |
|----------|------|--------|
| `frontend/src/config/oidc.ts` | OIDC 汎用化済み。Cognito Hosted UI と互換 | 🔵 |
| `frontend/src/services/auth.ts` | `oidc-client-ts` の API はプロバイダ非依存 | 🔵 |
| `frontend/src/services/liff.ts` | LIFF SDK は OIDC 認証と独立して動作 | 🔵 |
| `backend/template.yaml` | `OidcIssuer`/`OidcAudience` パラメータ化済み | 🔵 |
| `backend/src/api/shared.py` | JWT `sub` クレーム抽出のみ。プロバイダ非依存 | 🔵 |
| `backend/src/services/line_service.py` | 手動リンク機能は維持。変更不要 | 🔵 |
| `backend/src/api/handlers/user_handler.py` | `/users/link-line` はそのまま維持 | 🔵 |

## スコープ外（明示的除外）

- LINE ユーザー ID の自動連携（Cognito 属性 → DynamoDB `line_user_id`）
- 既存の手動リンク機能（`/users/link-line`）の変更・廃止
- Cognito Hosted UI のカスタムブランディング
- ユーザーデータ（`sub`）の移行
- LIFF 内でのシームレス認証（方式B）
