# learning-stats-dashboard アーキテクチャ設計

**作成日**: 2026-03-05
**関連要件定義**: [requirements.md](../../spec/learning-stats-dashboard/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: 要件定義書・既存コードから確認できる確実な設計
- 🟡 **黄信号**: 要件定義書・既存コードから妥当な推測による設計
- 🔴 **赤信号**: 要件定義書・既存コードにない推測による設計

---

## 1. システム概要 🔵

**信頼性**: 🔵 *要件定義書 REQ-001〜007 より*

学習統計ダッシュボードは、ユーザーの学習進捗を可視化する機能である。バックエンドに 3 つの統計 API エンドポイントを追加し、フロントエンドに `/stats` ルートの StatsPage を新設する。既存の `get_review_summary()` ロジックを拡張し、新規 DynamoDB テーブルは作成せず既存の cards / reviews テーブルからリアルタイム集計する。

## 2. アーキテクチャパターン 🔵

**信頼性**: 🔵 *既存 review-flow 設計・CLAUDE.md 技術スタックより*

- **パターン**: 既存のレイヤードアーキテクチャ（Handler → Service → DynamoDB）を踏襲
- **選択理由**: 既存の `review_handler.py` / `ReviewService` パターンに合わせ、新規 `stats_handler.py` / `StatsService` を追加する

### 変更方針

バックエンドは新規サービスクラス `StatsService` を追加する。`ReviewService.get_review_summary()` の既存ロジック（カード取得・レビュー取得・ストリーク計算）を内部で活用する。フロントエンドは新規ページ・フック・コンポーネントを追加する。

---

## 3. バックエンド API 設計

### 3.1 新規エンドポイント一覧 🔵

**信頼性**: 🔵 *要件定義書 REQ-001〜003 より*

| メソッド | パス | 説明 | ハンドラー |
|---------|------|------|-----------|
| GET | `/stats` | 基本統計サマリー | `stats_handler.get_stats` |
| GET | `/stats/weak-cards` | 苦手カード一覧 | `stats_handler.get_weak_cards` |
| GET | `/stats/forecast` | 復習予測 | `stats_handler.get_forecast` |

### 3.2 GET /stats レスポンス 🔵

**信頼性**: 🔵 *REQ-001・既存 `ReviewSummary` フィールドより*

```json
{
  "total_cards": 120,
  "learned_cards": 95,
  "unlearned_cards": 25,
  "cards_due_today": 12,
  "total_reviews": 450,
  "average_grade": 3.2,
  "streak_days": 7,
  "tag_performance": { "英語": 0.85, "数学": 0.62 }
}
```

### 3.3 GET /stats/weak-cards レスポンス 🔵

**信頼性**: 🔵 *REQ-002 より*

**クエリパラメータ**: `limit` (デフォルト: 10, 最大: 50)

```json
{
  "weak_cards": [
    {
      "card_id": "uuid-1",
      "front": "カード表面テキスト",
      "back": "カード裏面テキスト",
      "ease_factor": 1.3,
      "repetitions": 5,
      "deck_id": "deck-uuid-1"
    }
  ],
  "total_count": 10
}
```

### 3.4 GET /stats/forecast レスポンス 🔵

**信頼性**: 🔵 *REQ-003 より*

**クエリパラメータ**: `days` (デフォルト: 7, 最大: 30)

```json
{
  "forecast": [
    { "date": "2026-03-05", "due_count": 12 },
    { "date": "2026-03-06", "due_count": 8 },
    { "date": "2026-03-07", "due_count": 15 },
    { "date": "2026-03-08", "due_count": 5 },
    { "date": "2026-03-09", "due_count": 10 },
    { "date": "2026-03-10", "due_count": 3 },
    { "date": "2026-03-11", "due_count": 7 }
  ]
}
```

### 3.5 Pydantic レスポンスモデル 🔵

**信頼性**: 🔵 *既存 `models/review.py` パターン・REQ-001〜003 より*

新規ファイル: `backend/src/models/stats.py`

```python
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class StatsResponse(BaseModel):
    """GET /stats レスポンスモデル。"""
    total_cards: int
    learned_cards: int
    unlearned_cards: int
    cards_due_today: int
    total_reviews: int
    average_grade: float
    streak_days: int
    tag_performance: Dict[str, float] = Field(default_factory=dict)


class WeakCard(BaseModel):
    """苦手カード情報。"""
    card_id: str
    front: str
    back: str
    ease_factor: float
    repetitions: int
    deck_id: Optional[str] = None


class WeakCardsResponse(BaseModel):
    """GET /stats/weak-cards レスポンスモデル。"""
    weak_cards: List[WeakCard]
    total_count: int


class ForecastDay(BaseModel):
    """1日分の復習予測。"""
    date: str
    due_count: int


class ForecastResponse(BaseModel):
    """GET /stats/forecast レスポンスモデル。"""
    forecast: List[ForecastDay]
```

### 3.6 StatsService 設計 🔵

**信頼性**: 🔵 *REQ-C05・既存 `ReviewService` パターンより*

新規ファイル: `backend/src/services/stats_service.py`

`ReviewService` とは独立したサービスとして実装する。`ReviewService.get_review_summary()` のカード・レビュー取得ロジックと同様の DynamoDB クエリを行うが、統計固有の集計（learned/unlearned 分類、苦手カードソート、予測計算）を追加する。

```python
class StatsService:
    def __init__(self, cards_table_name=None, reviews_table_name=None, dynamodb_resource=None):
        # ReviewService と同じ DynamoDB 初期化パターン

    def get_stats(self, user_id: str) -> StatsResponse:
        """基本統計を集計して返す。
        - cards テーブルから全カード取得
        - reviews テーブルから全レビュー取得
        - learned_cards: repetitions >= 1 のカード数
        - unlearned_cards: repetitions == 0 のカード数
        - streak_days: ReviewService._calculate_streak() と同じロジック
        """

    def get_weak_cards(self, user_id: str, limit: int = 10) -> WeakCardsResponse:
        """ease_factor が低い順にカードを返す。
        - cards テーブルから全カード取得
        - repetitions >= 1 のカードのみ対象（未学習カードは除外）
        - ease_factor 昇順でソート → limit 件取得
        """

    def get_forecast(self, user_id: str, days: int = 7) -> ForecastResponse:
        """向こう N 日間の日別 due カード数を予測する。
        - cards テーブルから全カード取得
        - 各カードの next_review_at を日付に変換
        - 今日〜N 日後の各日に due になるカード数を集計
        - next_review_at が過去のカードは今日の due_count に加算
        """
```

**ストリーク計算の再利用**: `ReviewService._calculate_streak()` は `@staticmethod` なので、`StatsService` から直接呼び出すか、共通ユーティリティに抽出する。設計上は `ReviewService._calculate_streak()` を直接インポートして再利用する。

### 3.7 ハンドラー設計 🔵

**信頼性**: 🔵 *既存 `review_handler.py` パターンより*

新規ファイル: `backend/src/api/handlers/stats_handler.py`

```python
router = Router()
stats_service = StatsService()

@router.get("/stats")
def get_stats():
    user_id = get_user_id_from_context(router)
    response = stats_service.get_stats(user_id)
    return response.model_dump(mode="json")

@router.get("/stats/weak-cards")
def get_weak_cards():
    user_id = get_user_id_from_context(router)
    params = router.current_event.query_string_parameters or {}
    limit = min(int(params.get("limit", 10)), 50)
    response = stats_service.get_weak_cards(user_id, limit=limit)
    return response.model_dump(mode="json")

@router.get("/stats/forecast")
def get_forecast():
    user_id = get_user_id_from_context(router)
    params = router.current_event.query_string_parameters or {}
    days = min(int(params.get("days", 7)), 30)
    response = stats_service.get_forecast(user_id, days=days)
    return response.model_dump(mode="json")
```

`handler.py` に `stats_router` を登録:

```python
from api.handlers.stats_handler import router as stats_router
app.include_router(stats_router)
```

---

## 4. フロントエンド設計

### 4.1 コンポーネント階層 🔵

**信頼性**: 🔵 *REQ-004〜007・既存ページ構成より*

```
StatsPage (新規)
├── StatsSummary (新規)      # 基本統計カード群
│   ├── StatCard (新規)      # 個別の統計カード（再利用可能）
│   └── ProgressBar (新規)   # 学習進捗バー
├── StreakDisplay (新規)      # ストリーク表示（炎アイコン + 日数）
├── WeakCardsList (新規)      # 苦手カード TOP 10 リスト
│   └── WeakCardItem (新規)  # 個別の苦手カード行
└── ReviewForecast (新規)     # 7日間の復習予測表示
    └── ForecastBar (新規)   # 個別の日付行（バー表示）
```

### 4.2 StatsPage レイアウト 🔵

**信頼性**: 🔵 *REQ-004〜007・既存モバイルファーストレイアウトより*

```
┌──────────────────────────┐
│  📊 学習統計              │  ← ページヘッダー
├──────────────────────────┤
│ 🔥 5日連続学習中！        │  ← StreakDisplay
├──────────────────────────┤
│ ┌──────┐ ┌──────┐       │
│ │総カード│ │学習済み│       │  ← StatsSummary (2列グリッド)
│ │  120  │ │  95  │       │
│ └──────┘ └──────┘       │
│ ┌──────┐ ┌──────┐       │
│ │未学習 │ │今日  │       │
│ │  25  │ │ 12枚 │       │
│ └──────┘ └──────┘       │
│ ┌──────────────────┐    │
│ │ ████████░░░ 79%  │    │  ← ProgressBar
│ └──────────────────┘    │
│ 総復習: 450回 平均: 3.2  │
├──────────────────────────┤
│ 📅 今後7日の復習予測      │  ← ReviewForecast
│ 3/05  ████████████  12   │
│ 3/06  ██████        8    │
│ 3/07  ███████████████ 15 │
│ ...                      │
├──────────────────────────┤
│ ⚠ 苦手カード TOP 10      │  ← WeakCardsList
│ 1. "What is..."  EF:1.3  │
│ 2. "Define..."   EF:1.5  │
│ ...                      │
└──────────────────────────┘
│ nav │ nav │ nav │ nav │nav│  ← Navigation
```

### 4.3 TypeScript インターフェース 🔵

**信頼性**: 🔵 *バックエンド API レスポンスモデルより*

新規ファイル: `frontend/src/types/stats.ts`

```typescript
/** GET /stats レスポンス */
export interface StatsResponse {
  total_cards: number;
  learned_cards: number;
  unlearned_cards: number;
  cards_due_today: number;
  total_reviews: number;
  average_grade: number;
  streak_days: number;
  tag_performance: Record<string, number>;
}

/** 苦手カード情報 */
export interface WeakCard {
  card_id: string;
  front: string;
  back: string;
  ease_factor: number;
  repetitions: number;
  deck_id?: string | null;
}

/** GET /stats/weak-cards レスポンス */
export interface WeakCardsResponse {
  weak_cards: WeakCard[];
  total_count: number;
}

/** 1日分の復習予測 */
export interface ForecastDay {
  date: string;
  due_count: number;
}

/** GET /stats/forecast レスポンス */
export interface ForecastResponse {
  forecast: ForecastDay[];
}
```

`frontend/src/types/index.ts` に追加:

```typescript
export type * from './stats';
```

### 4.4 useStats カスタムフック 🟡

**信頼性**: 🟡 *既存 `useAuth` パターンから妥当な推測*

新規ファイル: `frontend/src/hooks/useStats.ts`

```typescript
interface UseStatsReturn {
  stats: StatsResponse | null;
  weakCards: WeakCard[];
  forecast: ForecastDay[];
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useStats(): UseStatsReturn {
  // 3 つの API を並列で fetch（Promise.all）
  // ローディング・エラー状態を統合管理
  // refresh 関数で手動リフレッシュ対応
}
```

### 4.5 API サービス追加 🔵

**信頼性**: 🔵 *既存 `api.ts` パターンより*

`frontend/src/services/api.ts` に追加:

```typescript
// ApiClient クラスに追加
async getStats(): Promise<StatsResponse> {
  return this.request<StatsResponse>('/stats');
}

async getWeakCards(limit?: number): Promise<WeakCardsResponse> {
  const searchParams = new URLSearchParams();
  if (limit) searchParams.set('limit', String(limit));
  const qs = searchParams.toString();
  return this.request<WeakCardsResponse>(`/stats/weak-cards${qs ? `?${qs}` : ''}`);
}

async getForecast(days?: number): Promise<ForecastResponse> {
  const searchParams = new URLSearchParams();
  if (days) searchParams.set('days', String(days));
  const qs = searchParams.toString();
  return this.request<ForecastResponse>(`/stats/forecast${qs ? `?${qs}` : ''}`);
}

// statsApi オブジェクト
export const statsApi = {
  getStats: () => apiClient.getStats(),
  getWeakCards: (limit?: number) => apiClient.getWeakCards(limit),
  getForecast: (days?: number) => apiClient.getForecast(days),
};
```

### 4.6 ルーティング 🔵

**信頼性**: 🔵 *REQ-004・既存ルーティング構成より*

React Router に `/stats` ルートを追加:

```typescript
<Route path="/stats" element={<StatsPage />} />
```

---

## 5. ナビゲーション統合 🟡

**信頼性**: 🟡 *REQ-004, AC-005・既存 Navigation コンポーネントから妥当な推測*

現在のナビゲーションは 5 項目（ホーム、作成、デッキ、カード、設定）。統計タブの追加方法:

**方針**: 「設定」を「統計」に置き換え、設定はホーム画面のヘッダーアイコンからアクセスする形に変更する。

**変更後のナビゲーション** (5 項目維持):

| 順序 | ラベル | パス | アイコン |
|------|--------|------|---------|
| 1 | ホーム | `/` | ホームアイコン |
| 2 | 作成 | `/generate` | + アイコン |
| 3 | デッキ | `/decks` | フォルダアイコン |
| 4 | カード | `/cards` | カードアイコン |
| 5 | 統計 | `/stats` | グラフアイコン (棒グラフ SVG) |

設定ページへは HomePage のヘッダーに歯車アイコンリンクを追加してアクセスする。

---

## 6. データフロー 🔵

**信頼性**: 🔵 *既存 review-flow データフロー・技術スタックより*

```
[ユーザー]
    │
    │ (1) /stats ページにアクセス
    ▼
[StatsPage]
    │
    │ (2) useStats() フック初期化
    ▼
[useStats]
    │
    │ (3) 3 API を並列呼び出し (Promise.all)
    ├──→ GET /stats          ──→ [stats_handler] ──→ [StatsService.get_stats()]
    ├──→ GET /stats/weak-cards ─→ [stats_handler] ──→ [StatsService.get_weak_cards()]
    └──→ GET /stats/forecast  ──→ [stats_handler] ──→ [StatsService.get_forecast()]
                                                          │
                                                          ▼
                                                   [DynamoDB]
                                                   ├── Cards Table (user_id PK)
                                                   │   → 全カード取得 (Query)
                                                   └── Reviews Table (user_id-reviewed_at GSI)
                                                       → 全レビュー取得 (Query)
                                                          │
                                                          ▼
                                                   [集計処理]
                                                   ├── learned/unlearned 分類
                                                   ├── ストリーク計算
                                                   ├── ease_factor ソート
                                                   └── next_review_at 日付集計
                                                          │
    ┌──────────────────────────────────────────────────────┘
    │ (4) レスポンス受信
    ▼
[useStats] → state 更新
    │
    │ (5) React 再描画
    ▼
[StatsPage]
    ├── [StreakDisplay]     ← stats.streak_days
    ├── [StatsSummary]     ← stats.total_cards, learned_cards, ...
    ├── [ReviewForecast]   ← forecast[]
    └── [WeakCardsList]    ← weakCards[]
         │
         │ (6) カードタップ
         ▼
    [CardDetailPage] (/cards/:id)
```

---

## 7. システム構成図 🔵

**信頼性**: 🔵 *既存構成・要件定義より*

```
┌─────────────────────────────────────────────────┐
│                Frontend (React)                  │
│                                                  │
│  StatsPage ──→ useStats ──→ apiClient            │
│    ├── StreakDisplay                              │
│    ├── StatsSummary                               │
│    │     ├── StatCard (x4)                        │
│    │     └── ProgressBar                          │
│    ├── ReviewForecast                             │
│    │     └── ForecastBar (x7)                     │
│    └── WeakCardsList                              │
│          └── WeakCardItem (x10)                   │
│                                                  │
│  Navigation ──→ /stats リンク追加                 │
└─────────────────┬───────────────────────────────┘
                  │ HTTPS (JWT Bearer)
                  ▼
┌─────────────────────────────────────────────────┐
│           Backend (Lambda + API Gateway)          │
│                                                  │
│  handler.py ──→ stats_router 登録                │
│                                                  │
│  stats_handler.py                                │
│    ├── GET /stats                                │
│    ├── GET /stats/weak-cards                     │
│    └── GET /stats/forecast                       │
│              │                                   │
│              ▼                                   │
│  StatsService                                    │
│    ├── get_stats()                               │
│    ├── get_weak_cards()                          │
│    └── get_forecast()                            │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│              DynamoDB                             │
│                                                  │
│  Cards Table                                     │
│    PK: user_id / SK: card_id                     │
│    GSI: user_id-due-index (user_id + next_review_at) │
│    Fields: ease_factor, repetitions, interval,   │
│            next_review_at, front, back, deck_id  │
│                                                  │
│  Reviews Table                                   │
│    PK: user_id / SK: reviewed_at                 │
│    GSI: user_id-reviewed_at-index                │
│    Fields: card_id, grade                        │
└─────────────────────────────────────────────────┘
```

---

## 8. ディレクトリ構造（変更対象） 🔵

**信頼性**: 🔵 *既存プロジェクト構造より*

```
backend/src/
├── api/
│   ├── handler.py                  # 修正: stats_router 登録追加
│   └── handlers/
│       └── stats_handler.py        # 新規: 統計 API ハンドラー
├── models/
│   └── stats.py                    # 新規: 統計レスポンスモデル
└── services/
    └── stats_service.py            # 新規: 統計サービス

backend/template.yaml               # 修正: /stats, /stats/weak-cards, /stats/forecast ルート追加

frontend/src/
├── components/
│   ├── Navigation.tsx              # 修正: 統計タブ追加（設定タブ置換）
│   ├── stats/                      # 新規ディレクトリ
│   │   ├── StatsSummary.tsx        # 新規: 基本統計カード群
│   │   ├── StatCard.tsx            # 新規: 個別統計カード
│   │   ├── ProgressBar.tsx         # 新規: 学習進捗バー
│   │   ├── StreakDisplay.tsx       # 新規: ストリーク表示
│   │   ├── WeakCardsList.tsx       # 新規: 苦手カードリスト
│   │   ├── WeakCardItem.tsx        # 新規: 苦手カード行
│   │   ├── ReviewForecast.tsx      # 新規: 復習予測表示
│   │   └── ForecastBar.tsx         # 新規: 予測バー行
├── hooks/
│   └── useStats.ts                 # 新規: 統計データフック
├── pages/
│   ├── StatsPage.tsx               # 新規: 統計ページ
│   └── HomePage.tsx                # 修正: 設定アイコンリンク追加
├── services/
│   └── api.ts                      # 修正: statsApi 追加
└── types/
    ├── index.ts                    # 修正: stats エクスポート追加
    └── stats.ts                    # 新規: 統計型定義
```

---

## 9. 非機能要件の実現方法

### パフォーマンス 🟡

**信頼性**: 🟡 *NFR-001, NFR-002 から妥当な推測*

- **API レスポンス**: DynamoDB Query 2 回（cards + reviews）で集計。1 秒以内を目標
- **フロントエンド**: 3 API を `Promise.all` で並列呼び出しし、初期表示 2 秒以内を実現
- **ローディング UX**: 各セクション独立のスケルトンローダーで体感速度を向上

### セキュリティ 🔵

**信頼性**: 🔵 *NFR-101, NFR-102・既存 API 認証設計より*

- **認証**: 既存の JWT Bearer Token 認証を適用（API Gateway Authorizer）
- **認可**: `get_user_id_from_context()` でユーザー ID を取得し、自身のデータのみ返却

### ユーザビリティ 🔵

**信頼性**: 🔵 *NFR-201, NFR-202 より*

- **モバイルファースト**: 幅 375px 以上で適切に表示される 2 列グリッドレイアウト
- **タッチターゲット**: 苦手カード行のタップ領域は最小 44x44px を確保

---

## 10. 技術的制約と注意点

### REQ-C03: 新規テーブル不使用 🔴

**信頼性**: 🔴 *軽量開発方針としての仮定*

初期フェーズでは `user_stats` 等の集計テーブルを作成せず、cards / reviews テーブルからリアルタイム集計する。カード数が増加した場合（1000 枚超）はパフォーマンス劣化の可能性があるが、Lambda のメモリ・タイムアウト設定で対応する。将来的にはキャッシュテーブルまたは DynamoDB Streams による事前集計を検討する。

### REQ-C04: グラフライブラリ不使用 🔴

**信頼性**: 🔴 *軽量開発方針としての仮定*

初期フェーズではグラフライブラリ（Recharts 等）を導入せず、Tailwind CSS のみでバー表示を実装する。`ForecastBar` コンポーネントは `div` の `width` スタイルを動的に設定してバー表示を実現する。将来的に Recharts を導入する場合、`ReviewForecast` コンポーネントの内部実装のみ差し替えればよい設計とする。

---

## 信頼性レベルサマリー

- 🔵 青信号: 18 件 (78%)
- 🟡 黄信号: 3 件 (13%)
- 🔴 赤信号: 2 件 (9%)

**品質評価**: ✅ 高品質
