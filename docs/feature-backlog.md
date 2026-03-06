# Memoru LIFF 機能バックログ

作成日: 2026-02-28
更新日: 2026-03-06

## 概要

今後実装を検討する機能の一覧。優先度と実装難易度を整理し、開発計画の参考とする。

---

## 実装済み機能

以下の機能は実装済みのため、バックログから除外。

| 機能 | 実装ブランチ | 備考 |
|------|-------------|------|
| カード検索 | `card-search-review-fixes` 他 | SearchBar、FilterChips、SortSelect、useCardSearch フック、ハイライト表示 |
| カテゴリ（デッキ）管理 | `deck-review-fixes` 他 | デッキ CRUD、カード割り当て、デッキ別フィルタ、DecksPage / DeckSummary |
| 学習統計ダッシュボード（基本） | `feature/learning-stats-dashboard` | StatsPage、基本統計、ストリーク、苦手カード TOP 10、7日間復習予測 |

---

## 1. 日別復習グラフ（統計ダッシュボード Phase 2）

### 目的
直近30日間の復習履歴を時系列で可視化し、学習の継続性と正答率の傾向を把握できるようにする。

### 現状
- `GET /stats`、`GET /stats/weak-cards`、`GET /stats/forecast` は実装済み
- StatsPage にストリーク・基本統計・苦手カード・復習予測セクションが存在
- reviews テーブルに `user_id`、`reviewed_at`、`card_id`、`grade` が記録されている
- `ForecastBar` コンポーネント（CSS バー表示）が再利用可能

### 機能要件

#### 日別復習履歴バーチャート
- 直近30日間の日別復習カード数を棒グラフで表示
- 各日の棒をタップすると詳細（復習枚数・正答率）をツールチップ表示
- 復習0件の日もバーなしで表示（連続性を視覚化）

#### 日別正答率の表示
- 各日の正答率を表示（grade 3 以上を正答とみなす）
- バーの色で正答率を表現（高: 緑系、中: 黄系、低: 赤系）

#### 週別サマリー（オプション）
- 週単位での復習量を集計表示
- 週ごとの平均正答率

### UI イメージ
```
📊 復習履歴（直近30日）

2/04  ██                    3  (67%)
2/05  ████████              12 (83%)
2/06  ██████                9  (78%)
2/07                        0
2/08  ████                  6  (100%)
 ...
3/04  ██████████████        20 (90%)
3/05  ████████              12 (75%) ← 今日
```

### API エンドポイント
- `GET /stats/daily?from=YYYY-MM-DD&to=YYYY-MM-DD`
  - レスポンス:
    ```json
    {
      "daily_stats": [
        { "date": "2026-03-05", "reviews_count": 12, "correct_count": 9 }
      ]
    }
    ```

### 実装方針
- **バックエンド**: reviews テーブルの `user_id-reviewed_at-index` GSI を使用し、日付範囲で Query。日別に集計
- **フロントエンド**: 既存の `ForecastBar` パターンを流用した CSS-only バー表示（グラフライブラリ不要）
- StatsPage に新セクション「復習履歴」を追加
- `useStats` フックに `GET /stats/daily` 呼び出しを追加

### 実装難易度
低〜中 — 既存の reviews テーブル・StatsService パターン・ForecastBar コンポーネントを流用可能。インフラ変更なし。

---

## 2. カード画像対応

### 目的
テキストだけでなく画像を使った暗記カードを作成可能にし、図解・写真による記憶定着を促進する。

### ユースケース
- 解剖学・生物学の図解
- 地図・地理の学習
- 化学構造式
- 外国語の文字（漢字・ハングルなど）の書き順
- 数学の公式やグラフ

### 機能要件
- カードの表面・裏面にそれぞれ画像を 1 枚添付可能（任意）
  - テキスト + 画像の組み合わせ、または画像のみ
- 対応形式: JPEG, PNG, WebP
- ファイルサイズ上限: 5MB / 画像
- 画像のリサイズ・圧縮（サーバーサイド or クライアントサイド）
- 画像の削除・差し替え

### UI イメージ
- カード作成/編集フォームに画像アップロードエリアを追加
- ドラッグ&ドロップ or タップでファイル選択
- プレビュー表示（サムネイル）
- 復習画面で画像をタップすると拡大表示

### アーキテクチャ
- **画像ストレージ**: S3 バケット（`memoru-card-images-{env}`）
  - パス: `{user_id}/{card_id}/{front|back}.{ext}`
- **アップロードフロー**:
  1. フロントエンドが Pre-signed URL を API に要求
  2. API が S3 Pre-signed URL を生成して返却
  3. フロントエンドが Pre-signed URL に直接アップロード
  4. カード保存時に画像 URL を cards テーブルに記録
- **配信**: CloudFront 経由で画像を配信（キャッシュ有効）

### データモデル変更
- **cards テーブル**
  - `front_image_key`: S3 オブジェクトキー（任意）
  - `back_image_key`: S3 オブジェクトキー（任意）

### API エンドポイント（案）
- `POST /cards/{cardId}/upload-url` — Pre-signed URL 取得
  - リクエスト: `{ "side": "front" | "back", "content_type": "image/jpeg" }`
  - レスポンス: `{ "upload_url": "...", "image_key": "..." }`
- `DELETE /cards/{cardId}/image` — 画像削除
  - リクエスト: `{ "side": "front" | "back" }`

### 前提条件
- S3 バケット + CloudFront の CDK スタック構築が必要（インフラ依存）
- デプロイはユーザーが手動実行

### 実装難易度
中〜高 — S3 + CloudFront のインフラ構築、Pre-signed URL の実装、フロントエンドの画像 UI が必要。Lambda のペイロード制限（6MB）を避けるため、直接 S3 アップロード方式が必須。

---

## 3. AI 要約カード自動生成（URL / PDF 入力）

### 目的
Web ページや PDF ドキュメントの内容を AI が要約し、学習カードを自動生成する。手動でテキストをコピペする手間を省く。

### 現状
- テキスト入力からの AI カード生成は実装済み（`POST /cards/generate`）
- Strands Agents SDK / Bedrock Claude 統合済み

### 機能要件

#### URL 入力
- Web ページの URL を入力すると、ページ内容を取得・要約してカード生成
- 対応: 一般的な Web ページ（HTML）
- JavaScript レンダリングが必要なページは非対応（初期版）
- robots.txt を尊重

#### PDF 入力
- PDF ファイルをアップロードすると、テキストを抽出してカード生成
- ページ範囲を指定可能（例: 1-10 ページ）
- ファイルサイズ上限: 10MB
- 対応: テキストベース PDF（スキャン画像 PDF は初期版では非対応）

#### 共通
- 生成前に要約プレビューを表示
- カード候補を表示し、ユーザーが選択して保存（既存フローと同じ）
- 生成カード数を指定可能（5〜20 枚）
- デッキ（カテゴリ）を指定して保存

### UI イメージ
- 既存の GeneratePage を拡張
  - 入力方式のタブ切り替え: 「テキスト」「URL」「PDF」
  - URL タブ: URL 入力欄 + 「取得」ボタン → 要約プレビュー → カード生成
  - PDF タブ: ファイルアップロード + ページ範囲指定 → 要約プレビュー → カード生成
- 要約プレビュー画面（新規）
  - 抽出されたテキストの要約を表示
  - ユーザーが確認後「カード生成」ボタンで進む

### アーキテクチャ

#### URL 処理フロー
1. フロントエンドが URL を API に送信
2. Lambda が URL のコンテンツを取得（`requests` + `BeautifulSoup`）
3. HTML → テキスト変換、不要な要素（ナビ、フッター等）を除去
4. テキストを AI に渡してカード生成（既存のカード生成パイプラインを再利用）

#### PDF 処理フロー
1. フロントエンドが PDF を S3 にアップロード（Pre-signed URL 方式、画像対応と共通化）
2. Lambda が S3 から PDF を取得、テキスト抽出（`pypdf` ライブラリ）
3. 抽出テキストを AI に渡してカード生成

### API エンドポイント（案）
- `POST /cards/generate-from-url`
  - リクエスト: `{ "url": "https://...", "card_count": 10, "deck_id": "xxx" }`
  - レスポンス: 既存の generate レスポンスと同形式
- `POST /cards/generate-from-pdf`
  - リクエスト: `{ "s3_key": "...", "page_range": "1-10", "card_count": 10, "deck_id": "xxx" }`
  - レスポンス: 既存の generate レスポンスと同形式

### 考慮事項
- Lambda のタイムアウト: URL 取得 + AI 生成で 30 秒を超える可能性
  - 対策: Step Functions で非同期処理、またはタイムアウトを延長（最大 15 分）
- コンテンツの長さ制限: AI モデルのコンテキストウィンドウに収まるよう、テキストをチャンク分割 or 要約してから生成
- コスト: 長文の AI 処理はトークン消費が大きいため、利用回数制限を検討

### 前提条件
- PDF 入力は S3 バケットが必要（カード画像対応と S3 基盤を共用可能）
- URL 入力は S3 不要で先行実装可能

### 実装難易度
高 — URL スクレイピング、PDF テキスト抽出、長文処理の最適化、非同期処理の検討が必要。ただし既存の AI カード生成パイプラインを再利用できる部分は多い。

---

## 4. AI チューター（インタラクティブ学習）

### 目的
デッキ単位で AI と対話しながら学習を深める。カードの暗記だけでなく、「なぜそうなるのか」を理解し、関連知識を広げることで記憶の定着率を向上させる。

### ユースケース
- 復習で不正解だったカードの内容を AI に質問して理解を深める
- デッキのテーマについて AI と対話し、関連知識を補完する
- 試験前にデッキ内容を AI がクイズ形式で出題し、理解度を確認する
- 苦手カード（ease_factor が低い）を中心に AI が重点的に解説する

### 機能要件

#### チャットベースの対話学習
- デッキを選択して AI チューターセッションを開始
- AI がデッキ内のカード内容をコンテキストとして理解
- ユーザーが自由にテキストで質問・対話
- AI が回答、解説、関連情報を提供
- セッション中の会話履歴を保持（AgentCore Memory の短期メモリで自動管理）

#### 学習モード
- **フリートーク**: デッキ内容について自由に質問
- **クイズモード**: AI がカード内容に基づいた質問を出題し、理解度を確認
- **弱点克服**: 苦手カード（低 ease_factor / 低正答率）を AI が重点的に解説

#### コンテキスト活用
- デッキ内の全カード（front/back）を AI のコンテキストに投入
- ユーザーの復習履歴（正答率、苦手パターン）を参照
- 会話の流れに応じて関連カードを自動提示

### UI イメージ
```
┌─────────────────────────────┐
│ 📚 AI チューター            │
│ デッキ: 日本史 近代          │
│ モード: [フリートーク ▼]     │
├─────────────────────────────┤
│                             │
│  🤖 このデッキには45枚のカー │
│     ドがあります。日本の近代 │
│     史について質問してくださ │
│     い。                    │
│                             │
│  👤 明治維新の三大改革って   │
│     何？                    │
│                             │
│  🤖 明治維新の三大改革は：  │
│     1. 版籍奉還・廃藩置県   │
│     2. 学制の公布           │
│     3. 徴兵令              │
│                             │
│     📎 関連カード:           │
│     • 「廃藩置県の目的は？」 │
│     • 「学制公布の年は？」   │
│                             │
│  👤 ...                     │
│                             │
├─────────────────────────────┤
│ [メッセージを入力...]  [送信]│
└─────────────────────────────┘
```

### アーキテクチャ

#### バックエンド
- **Strands Agent 拡張**: 既存の `StrandsService` に `tutor_chat()` メソッドを追加
- **コンテキスト構築**: デッキ内カード + 復習統計を System Prompt に組み込み
- **会話履歴管理**: 環境変数 `TUTOR_SESSION_BACKEND` で切り替え可能
  - `agentcore`（デフォルト / 本番）: AgentCore Memory 短期メモリ
  - `dynamodb`（フォールバック / ローカル開発）: DynamoDB テーブルで自前管理
  - Strands SDK の `SessionManager` インターフェースにより、Agent 側のコード変更なしで切り替え可能
  - 将来的に長期メモリ戦略（`summaryMemoryStrategy` 等）を追加し、
    過去セッションの学習傾向をセマンティック検索で活用可能（AgentCore のみ）

#### フロントエンド
- 新規ページ: `TutorPage.tsx`（`/tutor/:deckId`）
- コンポーネント:
  - `ChatMessage` — メッセージ吹き出し（AI / ユーザー）
  - `ChatInput` — テキスト入力 + 送信ボタン
  - `ModeSelector` — 学習モード切り替え
  - `RelatedCardChip` — 関連カードへのリンク
- HomePage のデッキカードに「AI チューター」ボタンを追加

### API エンドポイント
- `POST /tutor/sessions` — セッション開始
  - リクエスト: `{ "deck_id": "xxx", "mode": "free_talk" | "quiz" | "weak_focus" }`
  - レスポンス: `{ "session_id": "xxx", "initial_message": "..." }`
- `POST /tutor/sessions/{sessionId}/messages` — メッセージ送信
  - リクエスト: `{ "message": "ユーザーの質問" }`
  - レスポンス: `{ "reply": "AI の回答", "related_cards": [...] }`
- `DELETE /tutor/sessions/{sessionId}` — セッション終了

> **Note**: API インターフェースはバックエンドの切り替えに関わらず同一。
> セッション履歴の復元は `SessionManager` が内部で自動処理する。

### データモデル

セッションメタデータはアプリ側で管理。会話メッセージ履歴は `SessionManager` が管理する。

```python
class TutorSessionMeta(BaseModel):
    """セッションメタデータ"""
    user_id: str
    session_id: str
    deck_id: str
    mode: Literal["free_talk", "quiz", "weak_focus"]
    created_at: str

class TutorResponse(BaseModel):
    """API レスポンス"""
    reply: str
    related_card_ids: list[str] = []
```

#### SessionManager ファクトリ（環境変数による切り替え）

```python
import os
from strands.session import SessionManager

def create_tutor_session_manager() -> SessionManager:
    """環境変数 TUTOR_SESSION_BACKEND に応じた SessionManager を生成"""
    backend = os.environ.get("TUTOR_SESSION_BACKEND", "agentcore")

    if backend == "agentcore":
        from bedrock_agentcore.memory import AgentCoreMemoryClient
        from bedrock_agentcore.memory.integrations.strands import (
            AgentCoreMemorySessionManager,
        )

        memory_client = AgentCoreMemoryClient()
        memory_id = os.environ["AGENTCORE_MEMORY_ID"]
        return AgentCoreMemorySessionManager(
            memory_client=memory_client,
            memory_id=memory_id,
        )

    if backend == "dynamodb":
        # DynamoDB ベースの自前 SessionManager（フォールバック / ローカル開発用）
        from src.services.tutor_session_manager import DynamoDBSessionManager

        return DynamoDBSessionManager(
            table_name=os.environ.get("TUTOR_SESSIONS_TABLE", "tutor_sessions"),
        )

    raise ValueError(f"Unknown TUTOR_SESSION_BACKEND: {backend}")


# Agent 生成時に session_manager を注入（バックエンドを意識しない）
session_manager = create_tutor_session_manager()
agent = Agent(
    model=bedrock_model,
    system_prompt=tutor_system_prompt,
    session_manager=session_manager,
    session_id=session_id,
)
```

#### 環境変数一覧

| 変数名 | 値 | 用途 |
|--------|-----|------|
| `TUTOR_SESSION_BACKEND` | `agentcore` (デフォルト) / `dynamodb` | バックエンド切り替え |
| `AGENTCORE_MEMORY_ID` | Memory ID | AgentCore 使用時に必須 |
| `TUTOR_SESSIONS_TABLE` | テーブル名 | DynamoDB 使用時（デフォルト: `tutor_sessions`） |

#### DynamoDB バックエンド（フォールバック用）

DynamoDB バックエンドは Strands SDK の `SessionManager` を実装し、以下のスキーマで動作:
- PK: `user_id`, SK: `session_id`
- Attributes: `messages[]`, `created_at`, `updated_at`, `ttl`（7日間）

> **使い分け**: 本番環境では AgentCore Memory を推奨（運用コスト削減 + 将来の長期メモリ活用）。
> ローカル開発・テスト・AgentCore 未対応リージョンでは DynamoDB にフォールバック。

### 考慮事項
- **初のマルチターン会話**:
  - 既存の Strands 利用は全て単発（Agent を毎回生成 → 1回呼び出し → 破棄）
  - チューターは初のマルチターン機能。会話が長くなるとコンテキストウィンドウにメッセージが蓄積
  - 対策: セッション当たりのメッセージ上限（例: 20往復）を設け、上限到達時はセッション再開を促す
  - 将来: AgentCore Memory の `summaryMemoryStrategy` で古い会話を自動要約し、コンテキストを圧縮
- **コンテキストウィンドウ**: デッキのカード数が多い場合（100枚以上）、全カードを System Prompt に含めるとトークン消費が大きい
  - 対策: カード数に応じて要約 or 関連カードのみ選択的に含める
- **レスポンス時間**: 対話はリアルタイム性が重要。ストリーミングレスポンスの検討
  - 初期版: 通常の HTTP リクエスト/レスポンス（Lambda の制約内）
  - 将来: API Gateway WebSocket + Lambda でストリーミング対応
- **コスト**:
  - AI 推論: 対話は複数回の AI 呼び出しが発生するため、セッション回数制限を検討
  - AgentCore Memory: 約 $0.01/セッション（20イベント + 10取得の場合）。月100セッションで約 $1
- **Lambda タイムアウト**: チューター用 Lambda は 60秒に設定（既存の advice Lambda と同等）
- **Lambda コールドスタート**:
  - AgentCore Memory クライアントの初期化がコールドスタートに加算される
  - 対策: Lambda のグローバルスコープで `SessionManager` を初期化し、ハンドラ間で再利用
- **ローカル開発の整合性**:
  - dev 環境は `OllamaModel` を使用しており、AgentCore Memory は利用不可
  - ローカル開発パス: `TUTOR_SESSION_BACKEND=dynamodb` + `OllamaModel`（DynamoDB Local）
  - `USE_STRANDS` フラグとの関係を整理し、既存の `create_ai_service()` ファクトリと一貫性を保つ
- **既存 AI サービスファクトリとの統合**:
  - 既存の `create_ai_service(use_strands)` パターンに合わせ、チューター用ファクトリも統一的に管理
  - `StrandsAIService` に `tutor_chat()` を追加する際、`SessionManager` の注入方法を設計
- **エラーハンドリングの拡張**:
  - 既存の `_handle_ai_errors()` コンテキストマネージャに AgentCore Memory 固有エラーを追加
  - ネットワーク障害、メモリ ID 不正、セッション期限切れ等を適切な HTTP レスポンスにマッピング
- **バックエンド切り替え戦略**:
  - ファクトリパターンで `SessionManager` を差し替えるため、Agent 側のコード変更は不要
  - ローカル開発は DynamoDB Local で即座に動作確認可能
  - 本番は AgentCore Memory で運用コスト削減 + 将来の長期メモリ活用
  - AgentCore 固有機能（`batch_size`、セマンティック検索）は AgentCore バックエンド選択時のみ有効

### 前提条件
- Strands Agents SDK 統合済み（ai-strands-migration Phase 1-2 完了が前提）
- AgentCore Memory 使用時: 利用可能な AWS リージョン（us-east-1 / us-west-2 等）+ `bedrock-agentcore-sdk-python`
- DynamoDB 使用時: `tutor_sessions` テーブルの作成（SAM テンプレートに定義）
- デッキ機能実装済み（✅ 完了）
- 回答採点 / 学習アドバイス機能の知見を活用（Phase 3 と並行 or 後続で実装可能）

### 実装難易度
中 — AgentCore Memory により会話履歴管理の実装コストが大幅に削減。チャット UI の新規構築が主な作業。Strands Agent の対話機能・既存のカード/デッキ/統計データを活用できる。ストリーミング対応は将来の拡張とすれば初期版の難易度は抑えられる。

---

## 優先度・実装順序の提案

| # | 機能 | 難易度 | 依存関係 | 推奨順序 |
|---|------|--------|----------|----------|
| 1 | 日別復習グラフ | 低〜中 | なし（既存 StatsPage 拡張） | 1st |
| 2 | カード画像対応 | 中〜高 | S3 + CloudFront インフラ | 2nd |
| 3 | AI URL/PDF カード生成 | 高 | URL のみなら独立、PDF は S3 基盤共用 | 3rd |
| 4 | AI チューター | 中 | Strands Agents 統合 + AgentCore Memory | 3rd（並行可） |

### 推奨理由
1. **日別復習グラフ**はインフラ変更なし・既存コンポーネント流用で最もコスト効率が高い
2. **カード画像対応**は S3 インフラ構築が必要だが、PDF 生成と基盤を共有できる
3. **AI URL/PDF 生成**は最も複雑だが、差別化機能として価値が高い。URL 入力のみなら S3 不要で先行実装も可能
4. **AI チューター**は Strands Agents + AgentCore Memory 基盤が整えば着手可能。AgentCore Memory により会話履歴管理の実装コストが大幅に削減され、難易度が「中」に低下。暗記アプリとしての差別化・学習効果向上の核となる機能。AI URL/PDF 生成と並行して進められる
