# 認証プロバイダ切り替え 要件定義書（軽量版）

## 概要

認証プロバイダ（Keycloak / Amazon Cognito）を環境変数・SAMパラメータで切り替え可能にする。コード変更なしにデプロイ時の設定のみでプロバイダを選択できる構成を目指す。データ移行（ユーザーの `sub` マッピング等）は本要件のスコープ外とする。

## 関連文書

- **ヒアリング記録**: [💬 interview-record.md](interview-record.md)
- **コンテキストノート**: [📝 note.md](note.md)
- **既存アーキテクチャ設計**: [architecture.md](../../design/memoru-liff/architecture.md)

## 背景・動機

現在の認証基盤は Keycloak (ECS/Fargate) を使用しているが、以下の課題がある：

- ECS/Fargate の常時稼働コスト（月$30-100+）
- Keycloak 自体のアップデート・監視の運用負荷
- 小規模アプリに対してオーバースペック

Amazon Cognito に切り替えることでこれらを解消できるが、将来的に Keycloak の高度な機能（細かいロール管理、Identity Brokering 等）が必要になる可能性もある。そのため、プロバイダを切り替え可能にしておく。

## 主要機能要件

**【信頼性レベル凡例】**:
- 🔵 **青信号**: 設計文書・実装コード・ユーザヒアリングを参考にした確実な要件
- 🟡 **黄信号**: 設計文書・実装コード・ユーザヒアリングから妥当な推測による要件
- 🔴 **赤信号**: 設計文書・実装コード・ユーザヒアリングにない推測による要件

### 必須機能（Must Have）

- REQ-001: バックエンドの API Gateway JWT Authorizer の `issuer` と `audience` を SAM パラメータで切り替え可能にしなければならない 🔵 *`backend/template.yaml:36-39,260-263` の現状構成・ユーザヒアリングより*
- REQ-002: フロントエンドの OIDC 接続先（authority URL, client_id）を環境変数で切り替え可能にしなければならない 🔵 *`frontend/src/config/oidc.ts` の現状構成・ユーザヒアリングより*
- REQ-003: Keycloak 使用時と Cognito 使用時で、バックエンドの Lambda コードに変更が不要でなければならない 🔵 *ユーザヒアリング「環境変数のみで切り替え」より*
- REQ-004: 切り替えはデプロイ時の設定変更のみで完結し、コード変更を必要としてはならない 🔵 *ユーザヒアリングより*

### 基本的な制約

- REQ-401: 両プロバイダとも OIDC 標準（OpenID Connect Discovery）に準拠した JWT を発行しなければならない 🔵 *Keycloak・Cognito ともに OIDC 準拠であることは公知*
- REQ-402: JWT の `sub` クレームをユーザー識別子として使用する既存設計を維持しなければならない 🔵 *`backend/src/api/shared.py:74-79` の実装より*
- REQ-403: `oidc-client-ts` ライブラリの使用を継続しなければならない（Keycloak 専用ライブラリを導入しない） 🔵 *`frontend/src/services/auth.ts` の実装より*
- REQ-404: Cognito 使用時の LINE Login 統合方式は本要件では未定とし、設計フェーズで決定する 🔵 *ユーザヒアリングより*
- REQ-405: ユーザーデータの移行（`sub` のマッピング等）は本要件のスコープ外とする 🔵 *ユーザヒアリング「データ自体の移行が別途必要なのは承知」より*

## 簡易ユーザーストーリー

### ストーリー1: Cognito への切り替え

**私は** インフラ管理者 **として**
**SAM パラメータと フロントエンド環境変数を変更するだけで認証プロバイダを Cognito に切り替えたい**
**そうすることで** Keycloak の ECS/Fargate 運用コストを削減できる

**関連要件**: REQ-001, REQ-002, REQ-004

### ストーリー2: Keycloak への復帰

**私は** インフラ管理者 **として**
**Cognito 運用中に高度な認証機能が必要になった場合、設定変更のみで Keycloak に戻したい**
**そうすることで** ベンダーロックインのリスクなく認証基盤を選択できる

**関連要件**: REQ-001, REQ-002, REQ-003

## 基本的な受け入れ基準

### REQ-001: バックエンド JWT Authorizer の切り替え

**Given（前提条件）**: SAM テンプレートに OIDC issuer URL と audience のパラメータが定義されている
**When（実行条件）**: Cognito の issuer URL と audience を指定してデプロイする
**Then（期待結果）**: API Gateway が Cognito 発行の JWT を正しく検証し、Lambda が `sub` クレームを取得できる

**テストケース**:
- [ ] 正常系: Keycloak issuer 設定でデプロイし、Keycloak JWT で API 呼び出しが成功する
- [ ] 正常系: Cognito issuer 設定でデプロイし、Cognito JWT で API 呼び出しが成功する
- [ ] 異常系: issuer と異なるプロバイダの JWT で 401 エラーが返る

### REQ-002: フロントエンド OIDC 接続先の切り替え

**Given（前提条件）**: フロントエンドの環境変数に OIDC authority URL と client_id が設定されている
**When（実行条件）**: Cognito の OIDC discovery URL と client_id を環境変数に設定してビルドする
**Then（期待結果）**: `oidc-client-ts` が Cognito の OIDC エンドポイントを使用して認証フローを実行できる

**テストケース**:
- [ ] 正常系: Keycloak の authority URL でログイン・トークン取得が成功する
- [ ] 正常系: Cognito の authority URL でログイン・トークン取得が成功する
- [ ] 正常系: トークンリフレッシュが両プロバイダで動作する

## 最小限の非機能要件

- **パフォーマンス**: プロバイダ切り替えによる API レスポンスタイムへの影響がないこと（API Gateway JWT Authorizer の検証速度はプロバイダ非依存） 🟡 *API Gateway の JWT 検証はプロバイダ非依存と推測*
- **セキュリティ**: 両プロバイダとも PKCE フローを使用し、トークンの安全性を維持すること 🔵 *既存の PKCE 設定を維持*

## 変更箇所の概要

### バックエンド（`backend/template.yaml`）

| 変更箇所 | 現状 | 変更後 |
|----------|------|--------|
| パラメータ名 | `KeycloakIssuer` | `OidcIssuer`（汎用名に変更）🟡 |
| audience | `liff-client` 固定 | パラメータ化（`OidcAudience`）🟡 |
| Lambda 環境変数 | `KEYCLOAK_ISSUER` | `OIDC_ISSUER`（汎用名に変更）🟡 |

### フロントエンド（`frontend/src/config/oidc.ts`）

| 変更箇所 | 現状 | 変更後 |
|----------|------|--------|
| 環境変数 | `VITE_KEYCLOAK_URL` + `VITE_KEYCLOAK_REALM` | `VITE_OIDC_AUTHORITY`（authority URL 直接指定）🟡 |
| 環境変数 | `VITE_KEYCLOAK_CLIENT_ID` | `VITE_OIDC_CLIENT_ID`（汎用名に変更）🟡 |
| authority 構築 | `${URL}/realms/${REALM}`（Keycloak 固有形式） | 環境変数の値をそのまま使用 🟡 |

### 変更不要な箇所

| ファイル | 理由 |
|----------|------|
| `backend/src/api/shared.py` | JWT の `sub` クレーム取得ロジックはプロバイダ非依存 🔵 |
| `frontend/src/services/auth.ts` | `oidc-client-ts` の API はプロバイダ非依存 🔵 |
| `frontend/src/hooks/useAuth.ts` | 認証状態管理はプロバイダ非依存 🔵 |
| `frontend/src/contexts/AuthContext.tsx` | Context 層はプロバイダ非依存 🔵 |
| `backend/src/services/*` | ビジネスロジック層は認証に依存しない 🔵 |

## スコープ外（明示的除外）

- Cognito User Pool の作成・設定（インフラ側の作業）
- LINE Login と Cognito の統合方式の決定（設計フェーズで決定）
- ユーザーデータ（`sub`）の移行
- Keycloak インフラ（ECS/Fargate）の削除
- 既存テストの Keycloak 固有テストデータの更新（設計フェーズで検討）
