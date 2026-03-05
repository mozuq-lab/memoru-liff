# learning-stats-dashboard コンテキストノート

## 背景

ユーザーから自律開発の指示を受け、`docs/feature-backlog.md` の「3. 学習統計ダッシュボード」を基に要件を策定する。

## 既存資産の確認結果

### バックエンド

- `backend/src/services/review_service.py` の `get_review_summary()` が以下を返却済み:
  - `total_reviews`, `average_grade`, `total_cards`, `cards_due_today`
  - `streak_days` (連続学習日数、`_calculate_streak()` で算出)
  - `tag_performance` (タグ別正答率)
  - `recent_review_dates` (ユニーク復習日リスト)
- `ReviewSummary` dataclass は `backend/src/services/ai_service.py` に定義
- `GET /advice` エンドポイントが内部で `get_review_summary()` を使用しているが、統計専用の公開エンドポイントはない
- reviews テーブル: `user_id`, `reviewed_at`, `card_id`, `grade`, `ease_factor_before/after`, `interval_before/after`
- cards テーブル: `repetitions`, `interval`, `ease_factor`, `next_review_at`, `tags`, `deck_id`

### フロントエンド

- React 19 + TypeScript + Vite 7 + Tailwind CSS 4
- 既存ページ: HomePage, CardsPage, DecksPage, GeneratePage, ReviewPage, SettingsPage
- ナビゲーション: Home, Create, Decks, Cards, Settings の 5 項目
- HomePage は due カード数と DeckSummary のみ表示
- 統計ページは未実装

### feature-backlog.md の記載内容

- 基本統計: 総カード数、学習済み/未学習、平均 ease_factor、ストリーク
- 時系列グラフ: 日別復習カード数 (棒グラフ、30日)、日別正答率 (折れ線)
- 分析: 苦手カード TOP 10、復習予測 (7日)
- グラフライブラリ: Recharts or Chart.js を推奨
- API 案: `GET /stats/summary`, `GET /stats/daily`, `GET /stats/weak-cards`, `GET /stats/forecast`

## 軽量開発方針

- 既存の `get_review_summary()` を最大限活用し、新規テーブルは最小限
- Phase 1 では時系列グラフは省略し、基本統計 + 苦手カード + 復習予測に集中
- ナビゲーション追加は HomePage 内セクションまたは専用タブのいずれかで検討
