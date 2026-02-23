# ローカル開発環境構築 要件定義書

## 概要

LINE 環境なしでも Memoru アプリの全機能を動作確認できるローカル開発環境を構築する。Keycloak による認証、SAM CLI によるバックエンド API、DynamoDB local によるデータストアを Docker Compose で一括管理し、`make` コマンドで簡単に起動・停止できるようにする。

## 関連文書

- **ヒアリング記録**: [💬 interview-record.md](interview-record.md)
- **ユーザストーリー**: [📖 user-stories.md](user-stories.md)
- **受け入れ基準**: [✅ acceptance-criteria.md](acceptance-criteria.md)
- **コンテキストノート**: [📝 note.md](note.md)
- **計画ファイル**: CLAUDE.md plans（buzzing-coalescing-biscuit.md）

## 機能要件（EARS記法）

**【信頼性レベル凡例】**:
- 🔵 **青信号**: 計画ファイル・ユーザヒアリングから確実な要件
- 🟡 **黄信号**: 実装経験・技術仕様から妥当な推測による要件
- 🔴 **赤信号**: 推測による要件

---

### 通常要件

#### インポートパス統一

- REQ-LD-001: バックエンドソースコードは 絶対インポート（`from models.xxx`, `from services.xxx`）を使用しなければならない 🔵 *計画ファイルより。SAM ランタイムでは CodeUri: src/ が Python パスルートになるため相対インポート `from ..xxx` は動作しない*
- REQ-LD-002: テストコードは 絶対インポート（`from models.xxx`, `from services.xxx`）を使用しなければならない 🔵 *計画ファイルより。pytest の conftest.py で src/ を sys.path に追加する*
- REQ-LD-003: `backend/src/requirements.txt` を配置し、SAM ビルド時に依存関係を解決できなければならない 🔵 *計画ファイルより。SAM は CodeUri ディレクトリの requirements.txt を参照する*

#### SAM Local ルーティング修正

- REQ-LD-011: SAM local が stage="dev" で rawPath にステージプレフィックスを含まない場合、ハンドラーは rawPath に `/{stage}` を前置しなければならない 🔵 *計画ファイルより。Powertools の path 解決が `rawPath[len("/"+stage):]` でパスを切り詰めるため、プレフィックスがないと不正なパスになる*
- REQ-LD-012: 本番環境（stage="$default"）では rawPath の前置処理をスキップしなければならない 🔵 *計画ファイルより。条件分岐で `stage != "$default"` を確認*

#### DynamoDB 接続設定

- REQ-LD-021: サービスクラスは `DYNAMODB_ENDPOINT_URL` 環境変数を優先し、フォールバックとして `AWS_ENDPOINT_URL` を使用しなければならない 🔵 *計画ファイルより。SAM local が `AWS_ENDPOINT_URL` をフィルタするため*
- REQ-LD-022: `template.yaml` の Globals に `DYNAMODB_ENDPOINT_URL` と `AWS_ENDPOINT_URL` を空文字で定義しなければならない 🔵 *計画ファイルより。SAM `--env-vars` は template.yaml に定義された変数のみ Lambda に渡す*

#### Keycloak Docker セットアップ

- REQ-LD-031: docker-compose.yaml に Keycloak サービスを定義し、ポート 8180 で公開しなければならない 🔵 *計画ファイルより*
- REQ-LD-032: Keycloak は dev モード（`start-dev --import-realm`）で起動し、`realm-local.json` を自動インポートしなければならない 🔵 *計画ファイルより*
- REQ-LD-033: `realm-local.json` は LINE IdP を含まず、ユーザー名/パスワードでログイン可能でなければならない 🔵 *計画ファイルより*
- REQ-LD-034: テストユーザー（test-user / test-password-123）が realm-local.json に含まれなければならない 🔵 *計画ファイルより。test-users.json のユーザーを統合*

#### 開発コマンド

- REQ-LD-041: `make local-keycloak` で Keycloak を起動できなければならない 🔵 *計画ファイルより*
- REQ-LD-042: `make local-all` で DynamoDB local と Keycloak を一括起動できなければならない 🔵 *計画ファイルより*
- REQ-LD-043: `make local-api` で SAM local API をポート 8080 で起動できなければならない 🔵 *計画ファイルより。frontend の proxy 設定と一致*

#### フロントエンド設定

- REQ-LD-051: `frontend/.env.development` の `VITE_KEYCLOAK_CLIENT_ID` は `liff-client` でなければならない 🔵 *計画ファイルより。realm-export.json のクライアント ID と一致*
- REQ-LD-052: `frontend/.env.example` の `VITE_KEYCLOAK_CLIENT_ID` は `liff-client` でなければならない 🔵 *計画ファイルより*

---

#### Backend JWT フォールバック

- REQ-LD-061: dev 環境（`ENVIRONMENT=dev`）で API Gateway authorizer context が利用できない場合、ハンドラーは Authorization ヘッダーの JWT トークンからユーザー ID を抽出しなければならない 🔵 *計画ファイル・ユーザヒアリングより。SAM local では API Gateway JWT Authorizer が動作しない*
- REQ-LD-062: JWT フォールバックは ペイロードの `sub` クレームをユーザー ID として使用しなければならない 🔵 *計画ファイルより。Keycloak の標準クレーム*
- REQ-LD-063: JWT フォールバックは dev 環境以外では絶対に有効化されてはならない 🔵 *計画ファイルより。本番では API Gateway が JWT 検証済み*
- REQ-LD-064: JWT フォールバックは base64url デコードのみ行い、署名検証は行わない（dev 環境限定のため） 🟡 *計画ファイルから妥当な推測。dev 環境では Keycloak が発行した正規トークンのみ到達する前提*

#### DynamoDB Local 接続問題解決

- REQ-LD-071: DynamoDB local に対する boto3 リクエストがハングせず正常に応答しなければならない 🔵 *ユーザヒアリングより。現在 SigV4 署名付きリクエストでハングする問題が発生中*
- REQ-LD-072: SAM local Lambda コンテナから DynamoDB local へ接続できなければならない 🔵 *ユーザヒアリングより。Docker ネットワーク経由*
- REQ-LD-073: ホストマシンから DynamoDB local へ接続できなければならない 🔵 *ユーザヒアリングより。テーブル確認・データ投入用*

---

### 条件付き要件

- REQ-LD-101: API Gateway authorizer context に `sub` が含まれる場合、JWT フォールバックは使用されてはならない 🔵 *計画ファイルより。本番動作との互換性*
- REQ-LD-102: `DYNAMODB_ENDPOINT_URL` が空文字またはの場合、boto3 はデフォルトの AWS エンドポイントに接続しなければならない 🔵 *計画ファイルより。本番環境での動作*
- REQ-LD-103: DynamoDB local が SigV4 署名で問題を起こす場合、認証を無効化するか Docker イメージバージョンを変更して回避しなければならない 🟡 *技術仕様から妥当な推測。`-sharedDb` オプションや古いバージョンでの挙動差異*

---

### 制約要件

- REQ-LD-401: ローカル開発環境の変更は既存の 251 件のバックエンドテストと 256 件のフロントエンドテストに影響を与えてはならない 🔵 *全テスト pass を維持すること*
- REQ-LD-402: 本番環境のデプロイ（template.yaml）に悪影響を与えてはならない 🔵 *CLAUDE.md 注意事項より*
- REQ-LD-403: JWT フォールバックは `ENVIRONMENT` 環境変数のみで制御し、コード内のハードコーディングで切り替えてはならない 🟡 *計画ファイルから妥当な推測。環境変数ベースの設定管理*
- REQ-LD-404: Docker Compose の既存サービス（DynamoDB local, dynamodb-admin, setup-tables）は変更してはならない 🔵 *既存実装より*

---

## 非機能要件

### 起動性能

- NFR-LD-001: `make local-all` による全サービス起動が 120 秒以内に完了すべき（Keycloak 初回起動含む） 🟡 *Keycloak 24.0 の起動時間から推測。healthcheck の start_period: 60s*
- NFR-LD-002: `make local-api` による SAM local API 起動が 30 秒以内に完了すべき 🟡 *SAM CLI の起動時間から推測*

### セキュリティ

- NFR-LD-101: JWT フォールバックが本番環境で誤って有効化された場合でも、API Gateway JWT Authorizer が先にリクエストをブロックするため、セキュリティ上の影響はない 🔵 *計画ファイルより。API Gateway が検証済みトークンのみ Lambda に到達させる*
- NFR-LD-102: テストユーザーの認証情報は realm-local.json にのみ含まれ、本番 realm には含まれてはならない 🔵 *計画ファイルより*

### 開発者体験

- NFR-LD-201: 開発者は `make local-all && make local-api` の 2 コマンドでバックエンドを起動できるべき 🔵 *計画ファイルより*
- NFR-LD-202: フロントエンドは `npm run dev` で起動し、自動的にローカル API とKeycloak に接続できるべき 🔵 *計画ファイルより*

---

## Edge ケース

### エラー処理

- EDGE-LD-001: Keycloak が未起動の状態でフロントエンドにアクセスした場合、適切なエラーメッセージを表示する 🟡 *Playwright テストで確認済み（接続エラー表示）*
- EDGE-LD-002: DynamoDB local が未起動の状態で API にアクセスした場合、適切なエラーレスポンスを返す 🟡 *Playwright テストで確認済み（エラー + 再試行ボタン表示）*
- EDGE-LD-003: JWT トークンが不正な形式（base64 デコード不可）の場合、JWT フォールバックは安全に失敗する 🟡 *セキュリティのベストプラクティスから推測*

### 境界値

- EDGE-LD-101: SAM local の rawPath が `/` のみ（ルートパス）の場合でもルーティングが正常動作する 🟡 *計画ファイルから推測*
- EDGE-LD-102: Authorization ヘッダーが `Bearer ` プレフィックスを含まない場合、JWT フォールバックはスキップする 🟡 *計画ファイルから推測*

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 30件 | 77% |
| 🟡 黄信号 | 9件 | 23% |
| 🔴 赤信号 | 0件 | 0% |

**品質評価**: ✅ 高品質（青信号 77%、赤信号なし）

---

## 対応フェーズ

### Phase 1: 基盤構築（TASK-0048）

| # | 要件ID | 対応項目 | 優先度 |
|---|--------|---------|--------|
| 1 | REQ-LD-001〜003 | インポートパス統一 | Must Have |
| 2 | REQ-LD-011〜012 | SAM local ルーティング修正 | Must Have |
| 3 | REQ-LD-021〜022 | DynamoDB 接続設定 | Must Have |
| 4 | REQ-LD-031〜034 | Keycloak Docker セットアップ | Must Have |
| 5 | REQ-LD-041〜043 | 開発コマンド | Must Have |
| 6 | REQ-LD-051〜052 | フロントエンド設定 | Must Have |
| 7 | REQ-LD-061〜064 | Backend JWT フォールバック実装 | Must Have |

### Phase 2: 残課題解決

| # | 要件ID | 対応項目 | 優先度 |
|---|--------|---------|--------|
| 8 | REQ-LD-061〜064 | JWT フォールバック テスト検証 | Must Have |
| 9 | REQ-LD-071〜073, 103 | DynamoDB local 接続問題解決 | Must Have |
