# Cognito LINE Login 外部 IdP 統合 設計ヒアリング記録

**作成日**: 2026-03-03
**ヒアリング実施**: 要件定義フェーズで実施済み（設計判断は確定済み）

## ヒアリング目的

要件定義フェーズ（`/tsumiki:kairo-requirements`）で実施したヒアリングにて、設計に必要な判断事項がすべて確定した。本記録は要件ヒアリングの結果を設計観点で整理したものである。

## 設計判断の確認事項

### D1: LINE Login 統合方式

**カテゴリ**: アーキテクチャ
**背景**: auth-provider-switch 設計文書で方式A（Cognito 外部 OIDC IdP）と方式B（LIFF カスタム認証）が提案されており、方式選択が必要。

**確認結果**: **方式A を採用** 🔵

**設計への影響**:
- `UserPoolIdentityProviderOidc` を使用した CDK 実装
- Cognito Hosted UI 経由のフェデレーション認証
- フロントエンド・バックエンドのコード変更不要

---

### D2: LINE IdP の Props 設計（必須 vs オプショナル）

**カテゴリ**: アーキテクチャ
**背景**: `CognitoStackProps` に LINE Login 情報をどのように受け渡すか。必須にすると LINE なしデプロイができなくなる。

**確認結果**: **オプショナル Props** 🔵 *REQ-001 受け入れ基準「未指定の場合 LINE IdP が登録されない」より*

**設計への影響**:
- `lineLoginChannelId?: string` / `lineLoginChannelSecret?: string`（オプショナル）
- 条件分岐で LINE IdP の作成を制御
- 既存デプロイへの後方互換性を確保

---

### D3: Channel Secret の管理方式

**カテゴリ**: セキュリティ
**背景**: LINE Login の Channel Secret をどのように安全に管理するか。CDK コードへのハードコード禁止（REQ-007）は確定済みだが、具体的な管理方式の選択が必要。

**確認結果**: **環境変数（`process.env`）経由** 🟡 *セキュリティベストプラクティスから妥当な推測*

**設計への影響**:
- `app.ts` で `process.env.LINE_LOGIN_CHANNEL_ID` / `process.env.LINE_LOGIN_CHANNEL_SECRET` を参照
- 将来的な Secrets Manager 移行パスを残す（Props 経由のインターフェースは同じ）

---

### D4: Cognito Hosted UI の利用形態

**カテゴリ**: アーキテクチャ
**背景**: LIFF 内で Cognito Hosted UI へのリダイレクトが発生するが、UX として許容可能か。

**確認結果**: **許容する** 🔵 *ユーザヒアリング「Hosted UI 許容」より*

**設計への影響**:
- カスタム UI 開発はスコープ外
- `oidc-client-ts` の `signinRedirect()` がそのまま Hosted UI にリダイレクト
- Hosted UI に LINE ボタン + メールフォームの両方を表示

---

### D5: 認証方式の併存

**カテゴリ**: アーキテクチャ
**背景**: LINE Login のみにするか、メール+パスワード認証も残すかの判断。

**確認結果**: **両方併存** 🔵 *ユーザヒアリング「両方併存（推奨）」より*

**設計への影響**:
- `supportedIdentityProviders` に `COGNITO` + `LINE` の両方を設定
- LINE 障害時のフォールバックとしてメール認証が機能
- 開発者のデバッグにもメール認証が利用可能

---

### D6: LINE ユーザー ID 自動連携

**カテゴリ**: データモデル
**背景**: LINE Login 経由で取得した LINE ユーザー ID を DynamoDB の `line_user_id` に自動反映するか。

**確認結果**: **スコープ外（後回し）** 🔵 *ユーザヒアリング「後回し」より*

**設計への影響**:
- 属性マッピングは `name` / `picture` のみ（Cognito 属性として保存）
- 既存の手動リンク（`/users/link-line`）はそのまま維持
- 将来的な自動連携は Cognito Post-Authentication Lambda Trigger で実装可能

---

## ヒアリング結果サマリー

### 確認できた事項
- 方式A（Cognito 外部 OIDC IdP）で設計を進めること
- CDK のみの変更スコープであること
- LINE IdP は Props オプショナルで後方互換性を確保すること
- Cognito Hosted UI のリダイレクトフローを採用すること
- LINE Login とメール+パスワード認証の両方を Hosted UI で提供すること
- LINE ユーザー ID 自動連携は本設計のスコープ外であること

### 設計方針の決定事項
- `CognitoStackProps` にオプショナルな LINE Login Props を追加
- `UserPoolIdentityProviderOidc` で LINE Login を登録（Props 指定時のみ）
- Channel Secret は環境変数経由で管理
- `supportedIdentityProviders` を条件付きで COGNITO + LINE に拡張

### 残課題
- LINE Login の OIDC エンドポイントが Cognito の自動検出（`issuerUrl`）に対応しているかはデプロイ時に確認
- `endpoints` 手動指定が必要な場合の CDK API の動作確認

### 信頼性レベル分布

**設計全体**:
- 🔵 青信号: 5件
- 🟡 黄信号: 1件（Channel Secret 管理方式）
- 🔴 赤信号: 0件

## 関連文書

- **要件ヒアリング記録**: [interview-record.md](../../spec/cognito-line-login/interview-record.md)
- **アーキテクチャ設計**: [architecture.md](architecture.md)
- **データフロー**: [dataflow.md](dataflow.md)
- **要件定義**: [requirements.md](../../spec/cognito-line-login/requirements.md)
