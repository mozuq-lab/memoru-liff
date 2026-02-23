# ローカル開発環境構築 データフロー図

**作成日**: 2026-02-23
**関連アーキテクチャ**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/local-dev-environment/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: 計画ファイル・ユーザヒアリングから確実なフロー
- 🟡 **黄信号**: 技術仕様・実装経験から妥当な推測によるフロー
- 🔴 **赤信号**: 推測によるフロー

---

## 認証フロー（Keycloak OIDC + JWT フォールバック） 🔵

**信頼性**: 🔵 *計画ファイル・realm-local.json・ユーザヒアリングより*
**関連要件**: REQ-LD-033, REQ-LD-034, REQ-LD-061〜064

```mermaid
sequenceDiagram
    participant U as ブラウザ
    participant V as Vite :3000
    participant K as Keycloak :8180
    participant S as SAM Local :8080
    participant L as Lambda コンテナ
    participant D as DynamoDB :8000

    U->>V: http://localhost:3000 にアクセス
    V->>U: React アプリ返却
    U->>K: OIDC 認証リクエスト (PKCE)
    K->>U: ログインフォーム表示
    U->>K: test-user / test-password-123
    K->>U: Authorization Code 返却
    U->>K: Token Exchange (code → tokens)
    K->>U: Access Token (JWT) 返却

    Note over U,L: 以降、API リクエストに JWT を付与

    U->>S: GET /users/me (Authorization: Bearer {jwt})
    S->>L: Lambda 起動 + イベント送信

    Note over L: get_user_id_from_context()

    alt API Gateway Authorizer Context あり（本番）
        L->>L: authorizer.jwt.claims.sub を使用
    else Authorizer Context なし（SAM local）
        L->>L: ENVIRONMENT == "dev" を確認
        L->>L: Authorization ヘッダーから JWT 取得
        L->>L: JWT ペイロードを base64url デコード
        L->>L: payload.sub をユーザー ID として使用
    end

    L->>D: GetItem (user_id)
    D-->>L: ユーザーデータ
    L-->>S: HTTP 200 + User JSON
    S-->>U: レスポンス表示
```

---

## SAM Local ルーティングフロー（ステージプレフィックス修正） 🔵

**信頼性**: 🔵 *計画ファイルより*
**関連要件**: REQ-LD-011, REQ-LD-012

```mermaid
sequenceDiagram
    participant C as クライアント
    participant S as SAM Local
    participant H as handler()
    participant P as Powertools Resolver
    participant R as ルートハンドラー

    C->>S: GET http://localhost:8080/users/me
    S->>H: event = { rawPath: "/users/me", requestContext: { stage: "dev" } }

    Note over H: ステージプレフィックス修正

    H->>H: stage = "dev" (≠ "$default")
    H->>H: rawPath "/users/me" は "/dev" で始まらない
    H->>H: rawPath = "/dev/users/me" に変更

    H->>P: app.resolve(event)

    Note over P: Powertools の path 解決

    P->>P: path = rawPath[len("/dev"):] = "/users/me"
    P->>P: _static_routes でパターンマッチ
    P->>R: GET /users/me ハンドラー呼び出し

    R-->>P: レスポンス
    P-->>H: HTTP レスポンス
    H-->>S: レスポンス
    S-->>C: HTTP 200
```

**比較: 修正前の動作（バグ）**:
```
rawPath: "/users/me" → Powertools: rawPath[len("/dev"):] = "/rs/me" → 404 Not Found
```

---

## DynamoDB 接続フロー 🔵

**信頼性**: 🔵 *計画ファイルより・ユーザヒアリングより*
**関連要件**: REQ-LD-021, REQ-LD-022, REQ-LD-071〜073

```mermaid
flowchart TD
    A[サービスクラス初期化] --> B{DYNAMODB_ENDPOINT_URL<br/>が設定されている?}
    B -->|Yes| C[endpoint_url = DYNAMODB_ENDPOINT_URL]
    B -->|No| D{AWS_ENDPOINT_URL<br/>が設定されている?}
    D -->|Yes| E[endpoint_url = AWS_ENDPOINT_URL]
    D -->|No| F[デフォルト AWS エンドポイント<br/>（本番動作）]

    C --> G[boto3.resource&#40;dynamodb, endpoint_url&#41;]
    E --> G
    F --> H[boto3.resource&#40;dynamodb&#41;]

    G --> I[DynamoDB Local :8000]
    H --> J[AWS DynamoDB 本番]

    style I fill:#4CAF50,color:#fff
    style J fill:#2196F3,color:#fff
```

### Docker Network 経由の接続 🔵

```
Lambda コンテナ → memoru-network → dynamodb-local:8000
  (endpoint_url = "http://dynamodb-local:8000")

ホストマシン → localhost:8000 (ポートフォワード)
  (endpoint_url = "http://localhost:8000")
```

---

## env.json → Lambda 環境変数フロー 🔵

**信頼性**: 🔵 *計画ファイルより*
**関連要件**: REQ-LD-022

```mermaid
flowchart LR
    A[env.json] -->|sam local start-api<br/>--env-vars env.json| B[SAM CLI]
    C[template.yaml<br/>Globals.Function.Environment] --> B
    B -->|template.yaml に定義<br/>された変数のみ通過| D[Lambda コンテナ<br/>環境変数]

    style A fill:#FFC107,color:#000
    style C fill:#FFC107,color:#000

    subgraph "フィルタリングルール"
        E[env.json の変数] --> F{template.yaml に<br/>定義あり?}
        F -->|Yes| G[✅ Lambda に渡される]
        F -->|No| H[❌ 無視される]
    end
```

**解決策（計画ファイルより）**:
```yaml
# template.yaml Globals に追加
Globals:
  Function:
    Environment:
      Variables:
        DYNAMODB_ENDPOINT_URL: ""  # 空文字で定義 → env.json の値で上書き
        AWS_ENDPOINT_URL: ""       # 同上
```

---

## DynamoDB Local SigV4 問題と解決フロー 🔵

**信頼性**: 🔵 *ユーザヒアリング（Docker イメージ変更方針決定）*
**関連要件**: REQ-LD-071, REQ-LD-103

```mermaid
flowchart TD
    A[問題: amazon/dynamodb-local:latest が<br/>SigV4 署名付きリクエストでハング] --> B[原因調査]

    B --> C[boto3 は常に SigV4 署名を付与]
    B --> D[latest イメージの SigV4 検証が<br/>ハング（タイムアウト）]

    A --> E[解決アプローチ]

    E --> F[Step 1: Docker イメージバージョン固定]
    F --> G[docker-compose.yaml 変更<br/>image: amazon/dynamodb-local:X.X.X]
    G --> H{動作確認}
    H -->|成功| I[✅ 解決]
    H -->|失敗| J[Step 2: フォールバック]

    J --> K[代替案1: -disableTelemetry]
    J --> L[代替案2: ダミー認証情報]
    J --> M[代替案3: localstack]

    style A fill:#f44336,color:#fff
    style I fill:#4CAF50,color:#fff
```

---

## ローカル環境起動シーケンス 🔵

**信頼性**: 🔵 *計画ファイルより*

```mermaid
sequenceDiagram
    participant Dev as 開発者
    participant DC as Docker Compose
    participant DDB as DynamoDB Local
    participant ST as setup-tables
    participant KC as Keycloak
    participant SAM as SAM CLI
    participant V as Vite

    Dev->>DC: make local-all
    DC->>DDB: 起動 (:8000)
    DC->>KC: 起動 (:8180)
    DDB-->>DC: healthcheck OK
    DC->>ST: テーブル作成
    ST->>DDB: CREATE TABLE (users, cards, reviews)
    ST-->>DC: 完了 & 終了

    Note over KC: realm-local.json インポート中...
    KC-->>DC: healthcheck OK (約60秒)

    Dev->>SAM: make local-api
    SAM-->>Dev: API 起動 (:8080)

    Dev->>V: cd frontend && npm run dev
    V-->>Dev: フロントエンド起動 (:3000)

    Dev->>Dev: ブラウザで localhost:3000 にアクセス
```

---

## エラーハンドリングフロー 🔵

**信頼性**: 🔵 *計画ファイルより*

```mermaid
flowchart TD
    A[フロントエンド画面表示] --> B{API レスポンス}

    B -->|200 OK| C[データ表示]
    B -->|401 Unauthorized| D[Keycloak にリダイレクト]
    B -->|接続エラー| E[エラーメッセージ表示<br/>+ 再試行ボタン]
    B -->|500 Error| F[エラーメッセージ表示<br/>+ 再試行ボタン]

    E --> G{再試行ボタン押下}
    F --> G
    G -->|Yes| A
```

**計画ファイルよりの画面**:
| 画面 | エラー時の表示 |
|------|--------------|
| カード一覧 | 「カードの取得に失敗しました」+ 再試行 |
| 設定 | 「設定の取得に失敗しました」+ 再試行 |
| LINE連携 | 「LINE連携状態の取得に失敗しました」+ 再試行 |

---

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **要件定義**: [requirements.md](../../spec/local-dev-environment/requirements.md)
- **受け入れ基準**: [acceptance-criteria.md](../../spec/local-dev-environment/acceptance-criteria.md)

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 8件 | 100% |
| 🟡 黄信号 | 0件 | 0% |
| 🔴 赤信号 | 0件 | 0% |

**品質評価**: ✅ 高品質（全フローが計画ファイル・要件定義・ユーザヒアリングに基づく）
