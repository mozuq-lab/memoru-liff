# ローカル開発環境構築 アーキテクチャ設計

**作成日**: 2026-02-23
**関連要件定義**: [requirements.md](../../spec/local-dev-environment/requirements.md)
**ヒアリング記録**: [design-interview.md](design-interview.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: 要件定義書・計画ファイル・計画ファイル・ユーザヒアリングから確実な設計
- 🟡 **黄信号**: 技術仕様・実装経験から妥当な推測による設計
- 🔴 **赤信号**: 推測による設計

---

## システム概要 🔵

**信頼性**: 🔵 *要件定義書・計画ファイルより*

LINE 環境なしで Memoru アプリの全機能をローカルで動作確認できる開発環境。Docker Compose で DynamoDB local と Keycloak を管理し、SAM CLI でバックエンド API を起動、Vite で フロントエンドを提供する。

## システム構成図 🔵

**信頼性**: 🔵 *計画ファイル・docker-compose.yaml 設計より*

```
┌──────────────────────────────────────────────────────────────────┐
│  ホストマシン                                                      │
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌──────────────────────┐  │
│  │ Vite Dev    │    │ SAM Local   │    │ Docker Compose       │  │
│  │ Server      │    │ API         │    │                      │  │
│  │ :3000       │───▶│ :8080       │    │ ┌─────────────────┐  │  │
│  │             │    │             │    │ │ Keycloak :8180   │  │  │
│  │ (Frontend)  │───▶│ (Lambda     │    │ │ (認証サーバー)    │  │  │
│  └─────────────┘    │  コンテナ)  │    │ └─────────────────┘  │  │
│        │            │             │    │                      │  │
│        │            │  ┌────────┐ │    │ ┌─────────────────┐  │  │
│        │            │  │Lambda  │─┼───▶│ │ DynamoDB Local  │  │  │
│        │            │  │Container│ │    │ │ :8000           │  │  │
│        │            │  └────────┘ │    │ │ (データストア)    │  │  │
│        │            └─────────────┘    │ └─────────────────┘  │  │
│        │                               │                      │  │
│        └──────────────────────────────▶│ ┌─────────────────┐  │  │
│                                        │ │ DynamoDB Admin  │  │  │
│                                        │ │ :8001           │  │  │
│                                        │ │ (管理UI)        │  │  │
│                                        │ └─────────────────┘  │  │
│                                        └──────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘

                     Docker Network: memoru-network
```

## コンポーネント詳細

### 1. フロントエンド（Vite Dev Server :3000） 🔵

**信頼性**: 🔵 *.env.development 設計より*

| 項目 | 値 |
|------|-----|
| フレームワーク | React + TypeScript |
| ビルドツール | Vite |
| 認証ライブラリ | oidc-client-ts |
| API ベース URL | `http://localhost:8080` |
| Keycloak URL | `http://localhost:8180` |
| OIDC Client ID | `liff-client` |

### 2. バックエンド API（SAM Local :8080） 🔵

**信頼性**: 🔵 *template.yaml・handler.py 設計より*

| 項目 | 値 |
|------|-----|
| ランタイム | Python 3.12 |
| フレームワーク | AWS Lambda Powertools |
| API Resolver | APIGatewayHttpResolver |
| Docker Network | memoru-network |
| 環境変数ファイル | env.json |

**SAM Local の制約と対策**:

| 制約 | 対策 | 要件ID |
|------|------|--------|
| JWT Authorizer 不適用 | JWT フォールバック（dev 限定） | REQ-LD-061〜064 |
| stage="dev" でパス不正 | rawPath にステージプレフィックス前置 | REQ-LD-011〜012 |
| env-vars フィルタリング | template.yaml に変数定義必須 | REQ-LD-022 |

### 3. Keycloak（Docker :8180） 🔵

**信頼性**: 🔵 *計画ファイル・realm-local.json 設計より*

| 項目 | 値 |
|------|-----|
| バージョン | 24.0 |
| モード | dev（`start-dev --import-realm`） |
| DB | H2 組み込み（再起動でリセット） |
| Realm | memoru |
| Admin | admin / admin |

### 4. DynamoDB Local（Docker :8000） 🔵

**信頼性**: 🔵 *計画ファイルより*

| 項目 | 値 |
|------|-----|
| イメージ | `amazon/dynamodb-local:{version}` |
| モード | `-sharedDb` |
| データ永続化 | Docker Volume (`memoru-dynamodb-data`) |
| テーブル自動作成 | setup-tables コンテナ |

---

## 残タスク設計

### A. JWT フォールバック設計 🔵

**信頼性**: 🔵 *計画ファイル・ユーザヒアリングより*

**関連要件**: REQ-LD-061〜064, REQ-LD-101

**変更対象**: `backend/src/api/handler.py` の `get_user_id_from_context()` 関数

**設計方針**:

```
get_user_id_from_context(event):
  1. API Gateway authorizer context から sub を取得
     → 成功: sub を返す（本番動作）

  2. ENVIRONMENT != "dev" の場合:
     → 401 Unauthorized

  3. Authorization ヘッダーを取得
     → ヘッダーなし: 401 Unauthorized
     → "Bearer " プレフィックスなし: 401 Unauthorized

  4. JWT ペイロードを base64url デコード
     → デコード失敗: 401 Unauthorized

  5. ペイロードの "sub" クレームを返す
     → sub なし: 401 Unauthorized
```

**セキュリティ考慮** 🔵:
- 署名検証は行わない（dev 環境限定。Keycloak が発行した正規トークンのみ到達する前提）
- 本番では API Gateway が JWT 検証済みのため、この関数に到達する時点でトークンは検証済み
- `ENVIRONMENT` 環境変数のみで制御（ハードコーディング禁止）

**影響範囲**:
- `handler.py` の 1 関数のみ変更
- 既存テストへの影響なし（テストは mock で authorizer context を直接設定）

### B. DynamoDB Local 接続問題解決 🔵

**信頼性**: 🔵 *ユーザヒアリングより（Dockerイメージ変更方針決定）*

**関連要件**: REQ-LD-071〜073, REQ-LD-103

**問題**: `amazon/dynamodb-local:latest` が boto3 の SigV4 署名付きリクエストでハングする

**解決アプローチ**: Docker イメージバージョン固定 🔵

```
現在: amazon/dynamodb-local:latest（ハングする）
変更: amazon/dynamodb-local:{安定バージョン}
```

**変更対象**: `backend/docker-compose.yaml`

**実装手順**:

```
1. 既存の dynamodb-local コンテナを停止・削除
   $ docker compose down -v

2. docker-compose.yaml の image を特定バージョンに変更
   image: amazon/dynamodb-local:{stable-version}

3. コンテナを再起動
   $ make local-db

4. 動作確認
   $ aws dynamodb list-tables --endpoint-url http://localhost:8000
   $ python -c "import boto3; db = boto3.resource('dynamodb', endpoint_url='http://localhost:8000'); print(list(db.tables.all()))"
```

**候補バージョン** 🟡:
- `2.5.3`（2024年後半リリース、安定版）
- `2.4.0`（広く使われている安定版）
- 実際のバージョンはタスク実装時に Docker Hub で確認

**フォールバック** 🟡:
イメージ変更で解決しない場合の代替案:
1. `-disableTelemetry` オプション追加
2. AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY をダミー値に設定
3. localstack の DynamoDB を使用

---

## ネットワーク構成 🔵

**信頼性**: 🔵 *計画ファイルより*

```
memoru-network (bridge)
├── memoru-dynamodb-local (:8000)
├── memoru-dynamodb-admin (:8001)
├── memoru-keycloak (:8180)
├── memoru-setup-tables (初期化後終了)
└── SAM Lambda コンテナ (--docker-network memoru-network で接続)
```

| 接続元 | 接続先 | プロトコル | 備考 |
|--------|--------|-----------|------|
| ブラウザ | Vite :3000 | HTTP | フロントエンド |
| ブラウザ | Keycloak :8180 | HTTP | OIDC 認証フロー |
| Vite | SAM :8080 | HTTP | API プロキシ |
| Lambda コンテナ | DynamoDB :8000 | HTTP | データアクセス（Docker Network 経由） |
| ホスト | DynamoDB :8000 | HTTP | テーブル確認・データ投入 |
| ホスト | DynamoDB Admin :8001 | HTTP | 管理 UI |

## 起動手順 🔵

**信頼性**: 🔵 *計画ファイルより*

```bash
# ターミナル1: インフラ起動
cd backend && make local-all
# → DynamoDB local + Keycloak が起動

# ターミナル2: API 起動
cd backend && make local-api
# → SAM local API がポート 8080 で起動

# ターミナル3: フロントエンド起動
cd frontend && npm run dev
# → Vite がポート 3000 で起動

# ブラウザで http://localhost:3000 にアクセス
# → Keycloak ログイン → test-user / test-password-123
```

## 技術的制約 🔵

**信頼性**: 🔵 *計画ファイル・要件定義より*

1. **SAM local は API Gateway JWT Authorizer を適用しない** → JWT フォールバックで対応
2. **SAM local の `--env-vars` は template.yaml に定義された変数のみ渡す** → Globals に定義
3. **Keycloak dev モードは H2 DB 使用** → 再起動でデータリセット（テストユーザーは realm-local.json で再インポート）
4. **DynamoDB local の SigV4 問題** → Docker イメージバージョン固定で対応

## 関連文書

- **データフロー**: [dataflow.md](dataflow.md)
- **要件定義**: [requirements.md](../../spec/local-dev-environment/requirements.md)
- **ユーザストーリー**: [user-stories.md](../../spec/local-dev-environment/user-stories.md)

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 14件 | 88% |
| 🟡 黄信号 | 2件 | 12% |
| 🔴 赤信号 | 0件 | 0% |

**品質評価**: ✅ 高品質（大半が計画ファイル・要件定義に基づく。黄信号はDynamoDBバージョン候補のみ）
