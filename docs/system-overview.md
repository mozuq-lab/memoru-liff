# Memoru システム全体像

## このドキュメントについて

Memoru は LINE ベースの暗記カードアプリです。AI がテキストからフラッシュカードを自動生成し、SM-2 アルゴリズムによる間隔反復学習（SRS）で効率的な暗記を支援します。

---

## 1. システム全体構成

```mermaid
graph TB
    subgraph ユーザー
        Browser[ブラウザ]
        LINE[LINE アプリ]
    end

    subgraph フロントエンド
        Vite[React + Vite<br/>localhost:3000]
    end

    subgraph 認証
        KC[Keycloak<br/>OIDC Provider<br/>localhost:8180]
    end

    subgraph バックエンド["バックエンド (AWS Lambda)"]
        API[API Function<br/>localhost:8080]
        Webhook[LINE Webhook<br/>Function]
        Job[通知ジョブ<br/>5分毎実行]
    end

    subgraph データ
        DDB[(DynamoDB<br/>localhost:8000)]
    end

    subgraph 外部サービス
        Bedrock[Amazon Bedrock<br/>Claude AI]
        LINEAPI[LINE<br/>Messaging API]
    end

    Browser -->|アクセス| Vite
    LINE -->|LIFF で開く| Vite
    LINE -->|メッセージ送信| Webhook

    Vite -->|ログイン| KC
    Vite -->|API 呼び出し<br/>Bearer JWT| API

    API -->|データ読み書き| DDB
    API -->|カード生成| Bedrock

    Webhook -->|復習処理| DDB
    Webhook -->|返信| LINEAPI

    Job -->|ユーザー取得| DDB
    Job -->|通知送信| LINEAPI

    KC -.->|JWT 検証| API
```

---

## 2. ポート一覧（ローカル環境）

| ポート | サービス | 用途 |
|--------|---------|------|
| 3000 | Vite dev server | フロントエンド |
| 8080 | SAM local API | バックエンド API |
| 8180 | Keycloak | 認証サーバー |
| 8000 | DynamoDB Local | データベース |
| 8001 | DynamoDB Admin | DB 管理 UI |

---

## 3. 認証フロー

### 3.1 ログイン（OIDC + PKCE）

```mermaid
sequenceDiagram
    actor User as ユーザー
    participant FE as フロントエンド<br/>(localhost:3000)
    participant KC as Keycloak<br/>(localhost:8180)
    participant API as バックエンド API<br/>(localhost:8080)

    User->>FE: ブラウザでアクセス
    FE->>FE: useAuth() でセッション確認
    Note over FE: セッションなし

    FE->>KC: 認証リクエスト<br/>（PKCE code_challenge 付き）
    KC->>User: ログイン画面表示
    User->>KC: ユーザー名/パスワード入力<br/>（test-user / test-password-123）
    KC->>FE: リダイレクト /callback?code=xxx
    FE->>KC: 認可コード交換<br/>（code + code_verifier）
    KC->>FE: アクセストークン（JWT）+<br/>リフレッシュトークン

    Note over FE: トークンを localStorage に保存<br/>ApiClient にセット

    FE->>API: GET /users/me<br/>Authorization: Bearer {JWT}
    API->>API: JWT の sub クレームから<br/>user_id を抽出
    API->>FE: ユーザー情報返却

    Note over FE: ホーム画面表示<br/>「こんにちは、Test Userさん」
```

### 3.2 JWT フォールバック（ローカル開発専用）

SAM local では API Gateway の JWT Authorizer が動作しないため、バックエンドに dev 環境限定のフォールバックがあります。

```mermaid
flowchart TD
    A[API リクエスト受信] --> B{API Gateway の<br/>authorizer context<br/>に sub がある?}
    B -->|Yes| C[sub からユーザーID取得<br/>本番環境のパス]
    B -->|No| D{ENVIRONMENT<br/>== 'dev' ?}
    D -->|No| E[401 エラー]
    D -->|Yes| F[Authorization ヘッダーの<br/>JWT を base64 デコード]
    F --> G[payload の sub を取得]
    G --> H[ユーザーID として使用]

    style C fill:#90EE90
    style H fill:#FFE4B5
    style E fill:#FFB6C1
```

> **安全性**: 本番では API Gateway が JWT 検証済みの sub を渡すので、フォールバックには到達しません。

---

## 4. 画面遷移

```mermaid
flowchart TD
    Login[ログイン画面<br/>Keycloak] --> Callback[/callback<br/>トークン交換]
    Callback --> Home

    subgraph アプリ画面
        Home[🏠 ホーム<br/>復習カード数表示]
        Generate[✨ カード作成<br/>AI テキスト→カード生成]
        Cards[📚 カード一覧<br/>全カード表示]
        CardDetail[📝 カード詳細<br/>編集・復習]
        Settings[⚙️ 設定<br/>通知時刻・アカウント]
        LinkLine[🔗 LINE 連携<br/>LINE アカウント紐付け]
    end

    Home -->|ナビ: 作成| Generate
    Home -->|ナビ: カード| Cards
    Home -->|ナビ: 設定| Settings
    Home -->|クイックアクション| Generate
    Home -->|クイックアクション| Cards

    Cards -->|カードタップ| CardDetail
    Cards -->|カードを作成する| Generate

    Settings -->|LINE連携設定| LinkLine
    LinkLine -->|戻る| Settings

    Generate -->|保存後| Cards
```

### 各画面の役割

| 画面 | パス | 主な機能 |
|------|------|----------|
| ホーム | `/` | 今日の復習カード数、クイックアクション |
| カード作成 | `/generate` | テキスト入力 → AI でカード自動生成 → 選択して保存 |
| カード一覧 | `/cards` | 全カード表示（フィルター・検索） |
| カード詳細 | `/cards/:id` | カード内容の確認・編集・削除 |
| 設定 | `/settings` | 通知時刻変更、アカウント情報、ログアウト |
| LINE 連携 | `/link-line` | LINE アカウントとの紐付け（LIFF 環境でのみ動作） |

---

## 5. データフロー

### 5.1 カード生成フロー

```mermaid
sequenceDiagram
    actor User as ユーザー
    participant FE as フロントエンド
    participant API as バックエンド
    participant Bedrock as Amazon Bedrock<br/>(Claude AI)
    participant DB as DynamoDB

    User->>FE: テキスト入力<br/>「日本の首都は東京で...」
    FE->>API: POST /cards/generate<br/>{input_text, language: "ja"}

    API->>Bedrock: Claude にプロンプト送信<br/>「以下のテキストから<br/>暗記カードを生成して」
    Bedrock->>API: JSON レスポンス<br/>[{front: "日本の首都は?",<br/>  back: "東京"}]

    API->>FE: 生成されたカード一覧

    Note over FE: ユーザーが保存するカードを選択

    loop 選択した各カードに対して
        FE->>API: POST /cards<br/>{front, back, tags}
        API->>DB: ユーザー存在確認<br/>(get_or_create_user)
        API->>DB: カード作成 +<br/>card_count インクリメント<br/>（トランザクション）
        API->>FE: 作成完了
    end

    Note over FE: カード一覧に遷移<br/>「3枚のカードを保存しました」
```

> **ローカル環境の制限**: Bedrock はローカルでは利用できないため、カード生成は `BedrockServiceError` で失敗します。

### 5.2 復習（SRS）フロー

```mermaid
sequenceDiagram
    actor User as ユーザー
    participant FE as フロントエンド
    participant API as バックエンド
    participant SRS as SM-2 アルゴリズム
    participant DB as DynamoDB

    User->>FE: 復習カード画面を開く
    FE->>API: GET /cards/due?limit=10
    API->>DB: GSI (user_id-due-index) で<br/>next_review_at <= 現在時刻 のカード取得
    API->>FE: 復習対象カード一覧

    Note over FE: カードの表面を表示

    User->>FE: 裏面を見る
    Note over FE: カードの裏面を表示

    User->>FE: 評価を選択（0〜5）
    FE->>API: POST /reviews/{cardId}<br/>{grade: 4}

    API->>DB: カードの現在の SRS パラメータ取得
    API->>SRS: calculate_sm2(grade=4,<br/>reps=2, ease=2.5, interval=6)

    Note over SRS: grade >= 3 → 成功<br/>interval = 6 × 2.5 = 15日<br/>reps = 3<br/>ease = 2.5 + 0.1 - 0.04 = 2.56

    SRS->>API: {interval: 15, ease: 2.56,<br/>reps: 3}
    API->>DB: カード更新<br/>next_review_at = 今日 + 15日
    API->>DB: レビュー履歴保存<br/>(TTL: 90日後に自動削除)
    API->>FE: 復習結果

    Note over FE: 次のカードへ
```

### SM-2 アルゴリズム概要

| 評価 | 意味 | 動作 |
|------|------|------|
| 0 | 全く覚えていない | リセット: interval=1, reps=0 |
| 1 | ほぼ覚えていない | リセット: interval=1, reps=0 |
| 2 | 間違えた | リセット: interval=1, reps=0 |
| 3 | 思い出すのに苦労した | 成功: 次回間隔を計算 |
| 4 | 少し迷ったが思い出せた | 成功: 次回間隔を計算 |
| 5 | 完璧に覚えていた | 成功: 次回間隔を計算 |

```
次回間隔の計算:
  1回目の成功 → 1日後
  2回目の成功 → 6日後
  3回目以降   → 前回間隔 × ease_factor
```

### 5.3 LINE 通知フロー

```mermaid
sequenceDiagram
    participant EB as EventBridge<br/>(5分毎)
    participant Job as 通知ジョブ<br/>Lambda
    participant DB as DynamoDB
    participant LINE as LINE<br/>Messaging API
    actor User as ユーザー

    EB->>Job: 定期実行トリガー

    Job->>DB: 全ユーザー取得
    Note over Job: 各ユーザーについて:

    loop ユーザーごと
        Job->>Job: line_user_id がある?
        Job->>Job: 通知時刻チェック<br/>（ユーザーのタイムゾーンで<br/>±5分以内か?）
        Job->>Job: 今日すでに通知済み?

        alt 通知条件を満たす
            Job->>DB: 復習対象カード数を取得
            alt カードがある場合
                Job->>LINE: プッシュ通知送信<br/>「復習カードが3枚<br/>あります!」
                Job->>DB: last_notified_date 更新
            end
        end
    end

    LINE->>User: LINE に通知表示
    User->>User: 通知タップで<br/>LIFF アプリを開く
```

### 5.4 LINE アカウント連携フロー

```mermaid
sequenceDiagram
    actor User as ユーザー
    participant LIFF as LIFF アプリ<br/>(LINE 内ブラウザ)
    participant FE as フロントエンド
    participant API as バックエンド
    participant LINEAPI as LINE API

    Note over User: LINE アプリから<br/>LIFF URL をタップ

    User->>LIFF: LIFF で開く
    LIFF->>FE: 画面表示

    User->>FE: 「LINEと連携する」タップ
    FE->>FE: LIFF SDK 初期化
    FE->>LIFF: ID トークン取得
    LIFF->>FE: LINE の ID トークン

    FE->>API: POST /users/link-line<br/>{id_token: "xxx"}
    API->>LINEAPI: ID トークン検証<br/>POST /oauth2/v2.1/verify
    LINEAPI->>API: {sub: "U1234...",<br/>name: "田中太郎"}

    API->>API: 同じ line_user_id で<br/>別ユーザーが紐付いて<br/>いないか確認

    API->>API: ユーザーの line_user_id を更新
    API->>FE: 連携成功

    Note over FE: 「連携済み」表示<br/>通知機能が有効に
```

---

## 6. データベース構造

### テーブル一覧

```mermaid
erDiagram
    USERS {
        string user_id PK "Keycloak の sub"
        string line_user_id "LINE ユーザーID (nullable)"
        string display_name "表示名"
        string picture_url "プロフィール画像"
        map settings "通知設定 JSON"
        string last_notified_date "最終通知日"
        string created_at "作成日時"
        string updated_at "更新日時"
    }

    CARDS {
        string user_id PK "ユーザーID"
        string card_id SK "カードID (UUID)"
        string front "表面（質問）"
        string back "裏面（答え）"
        list tags "タグ一覧"
        string next_review_at "次回復習日時"
        int interval "復習間隔（日）"
        float ease_factor "容易さ係数"
        int repetitions "成功回数"
        string created_at "作成日時"
    }

    REVIEWS {
        string card_id PK "カードID"
        string reviewed_at SK "復習日時"
        string user_id "ユーザーID"
        int grade "評価 (0-5)"
        int expires_at "TTL (90日後)"
    }

    USERS ||--o{ CARDS : "所有"
    CARDS ||--o{ REVIEWS : "復習履歴"
```

### GSI（グローバルセカンダリインデックス）

| テーブル | インデックス名 | PK | SK | 用途 |
|---------|--------------|----|----|------|
| Users | `line_user_id-index` | line_user_id | - | LINE ID → ユーザー逆引き |
| Cards | `user_id-due-index` | user_id | next_review_at | 復習対象カード取得 |
| Reviews | `user_id-reviewed_at-index` | user_id | reviewed_at | ユーザー別復習履歴 |

### settings フィールドの構造

```json
{
  "notification_time": "09:00",
  "timezone": "Asia/Tokyo"
}
```

---

## 7. バックエンド API 一覧

### ユーザー API

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/users/me` | 現在のユーザー情報取得 |
| PUT | `/users/me/settings` | 通知時刻・タイムゾーン更新 |
| POST | `/users/link-line` | LINE アカウント連携 |
| POST | `/users/me/unlink-line` | LINE 連携解除 |

### カード API

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/cards` | カード一覧（ページネーション対応） |
| POST | `/cards` | カード作成（上限 2000枚） |
| GET | `/cards/{cardId}` | カード詳細取得 |
| PUT | `/cards/{cardId}` | カード更新 |
| DELETE | `/cards/{cardId}` | カード削除（レビュー履歴も削除） |
| GET | `/cards/due` | 復習対象カード取得 |
| POST | `/cards/generate` | AI でカード生成（Bedrock） |

### レビュー API

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/reviews/{cardId}` | 復習結果送信（grade 0-5） |

---

## 8. ディレクトリ構造（主要ファイル）

```
memoru-liff/
├── frontend/                          # React フロントエンド
│   ├── src/
│   │   ├── App.tsx                    # ルーティング定義
│   │   ├── config/oidc.ts             # OIDC 設定（Keycloak 接続先）
│   │   ├── services/
│   │   │   ├── auth.ts                # 認証サービス（oidc-client-ts）
│   │   │   ├── api.ts                 # API クライアント（fetch + 401 リトライ）
│   │   │   └── liff.ts                # LIFF SDK 操作
│   │   ├── contexts/
│   │   │   ├── AuthContext.tsx         # 認証状態管理
│   │   │   └── CardsContext.tsx        # カード状態管理
│   │   ├── hooks/useAuth.ts           # 認証フック
│   │   ├── pages/
│   │   │   ├── HomePage.tsx           # ホーム画面
│   │   │   ├── GeneratePage.tsx       # AI カード生成
│   │   │   ├── CardsPage.tsx          # カード一覧
│   │   │   ├── CardDetailPage.tsx     # カード詳細
│   │   │   ├── SettingsPage.tsx       # 設定
│   │   │   ├── LinkLinePage.tsx       # LINE 連携
│   │   │   └── CallbackPage.tsx       # OIDC コールバック
│   │   └── types/                     # TypeScript 型定義
│   ├── .env.development               # ローカル開発環境変数
│   └── vite.config.ts                 # Vite 設定（プロキシ含む）
│
├── backend/                           # Python バックエンド
│   ├── src/
│   │   ├── api/handler.py             # API エンドポイント（全ルート定義）
│   │   ├── models/
│   │   │   ├── user.py                # ユーザーモデル
│   │   │   ├── card.py                # カードモデル（SRS パラメータ含む）
│   │   │   ├── review.py              # レビューモデル
│   │   │   └── generate.py            # AI 生成リクエスト/レスポンス
│   │   ├── services/
│   │   │   ├── user_service.py        # ユーザー CRUD
│   │   │   ├── card_service.py        # カード CRUD（上限管理）
│   │   │   ├── review_service.py      # レビュー処理 + SRS 更新
│   │   │   ├── srs.py                 # SM-2 アルゴリズム
│   │   │   ├── bedrock.py             # Amazon Bedrock (Claude) 呼び出し
│   │   │   ├── line_service.py        # LINE API 通信
│   │   │   ├── notification_service.py # 通知判定ロジック
│   │   │   └── prompts.py             # AI プロンプトテンプレート
│   │   ├── webhook/line_handler.py    # LINE Webhook 処理
│   │   └── jobs/due_push_handler.py   # 定期通知ジョブ
│   ├── tests/                         # テスト（260件）
│   ├── template.yaml                  # SAM テンプレート（Lambda + API Gateway）
│   ├── docker-compose.yaml            # ローカルサービス定義
│   ├── env.json                       # SAM local 環境変数
│   └── Makefile                       # 開発コマンド
│
└── infrastructure/
    ├── keycloak/
    │   ├── realm-local.json           # ローカル用 Keycloak 設定
    │   └── test-users.json            # テストユーザー定義
    └── liff-hosting/                  # CloudFront + S3 (本番用)
```

---

## 9. 本番環境 vs ローカル環境の違い

```mermaid
flowchart LR
    subgraph 本番環境
        LIFF_P[LIFF SDK<br/>LINE 内ブラウザ] --> CF[CloudFront<br/>+ S3]
        CF --> APIGW[API Gateway<br/>JWT Authorizer]
        APIGW --> Lambda[Lambda]
        Lambda --> DDB_P[(DynamoDB)]
        Lambda --> Bedrock_P[Bedrock]
        EB_P[EventBridge] --> Lambda_N[通知 Lambda]
        Lambda_N --> LINE_P[LINE API]
    end

    subgraph ローカル環境
        Browser_L[ブラウザ<br/>localhost:3000] --> Vite_L[Vite<br/>dev server]
        Vite_L --> SAM[SAM local<br/>:8080]
        SAM --> DDB_L[(DynamoDB<br/>Local :8000)]
        SAM -.->|❌ 接続不可| Bedrock_L[Bedrock]
        Browser_L --> KC[Keycloak<br/>:8180]
    end

    style Bedrock_L fill:#FFB6C1,stroke:#FF0000
```

| 項目 | 本番 | ローカル |
|------|------|---------|
| 認証 | LINE Login → Keycloak (AWS) | ユーザー名/パスワード → Keycloak (Docker) |
| JWT 検証 | API Gateway JWT Authorizer | JWT フォールバック（base64 デコード） |
| データベース | DynamoDB (AWS) | DynamoDB Local (Docker) |
| AI カード生成 | Amazon Bedrock (Claude) | **利用不可**（エラーになる） |
| LINE 通知 | EventBridge → Lambda → LINE API | 未対応 |
| LINE 連携 | LIFF SDK で ID トークン取得 | **利用不可**（LIFF 環境外） |

---

## 10. ローカル開発でできること/できないこと

### できること

- ログイン/ログアウト（Keycloak テストユーザー）
- ホーム画面表示（復習カード数）
- カード一覧の閲覧
- カードの手動作成・編集・削除（API 直接）
- 設定画面の表示・通知時刻変更
- 全 260 件のテスト実行

### できないこと（外部サービス依存）

- **AI カード生成**: Bedrock に接続できないため失敗する
- **LINE 連携**: LIFF SDK は LINE アプリ内でのみ動作
- **LINE 通知**: LINE Messaging API のトークンが必要
- **LINE Bot 復習**: Webhook が外部から到達不可
