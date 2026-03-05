# learning-stats-dashboard 要件定義書 (軽量版)

## 概要

学習の進捗と傾向を可視化する統計ダッシュボードを実装する。基本統計の表示、連続学習ストリーク、苦手カード一覧、復習予測を提供し、学習モチベーションの維持と計画改善を支援する。

## 関連文書

- **コンテキストノート**: [note.md](note.md)
- **ヒアリング記録**: [interview-record.md](interview-record.md)
- **機能バックログ**: [../../feature-backlog.md](../../feature-backlog.md) セクション3

## 信頼性レベル凡例

- 🔵 **青信号**: feature-backlog.md・既存コードから確認できる確実な要件
- 🟡 **黄信号**: backlog・既存コードから妥当に推測した要件
- 🔴 **赤信号**: backlog にない仮定による要件

---

## Must Have 要件

### REQ-001: 統計 API エンドポイント

システムは `GET /stats` エンドポイントを提供し、以下の統計データを返却しなければならない 🔵 *backlog `GET /stats/summary` + 既存 `get_review_summary()` より*

- 総カード数 (`total_cards`)
- 学習済みカード数 (`learned_cards`: `repetitions >= 1` のカード)
- 未学習カード数 (`unlearned_cards`: `repetitions == 0` のカード)
- 本日の復習対象数 (`cards_due_today`)
- 総復習回数 (`total_reviews`)
- 平均グレード (`average_grade`)
- 連続学習日数 (`streak_days`)
- タグ別正答率 (`tag_performance`)

### REQ-002: 苦手カード API エンドポイント

システムは `GET /stats/weak-cards` エンドポイントを提供し、ease_factor が低い順にカードを返却しなければならない 🔵 *backlog「苦手カード TOP 10」より*

- デフォルト上限: 10 件
- `limit` クエリパラメータで件数指定可能
- 各カードの `card_id`, `front`, `back`, `ease_factor`, `repetitions` を含む

### REQ-003: 復習予測 API エンドポイント

システムは `GET /stats/forecast` エンドポイントを提供し、向こう 7 日間の日別 due カード数予測を返却しなければならない 🔵 *backlog「今後の復習予測（向こう 7 日間）」より*

- デフォルト: 7 日間
- `days` クエリパラメータで日数指定可能
- レスポンス形式: `{ "forecast": [{ "date": "YYYY-MM-DD", "due_count": N }, ...] }`

### REQ-004: StatsPage の実装

フロントエンドに `/stats` ルートの StatsPage を新規作成し、統計情報を表示しなければならない 🔵 *backlog「専用の『統計』タブを追加」より*

- HomePage またはナビゲーションから StatsPage に遷移可能
- モバイルファーストのレスポンシブレイアウト

### REQ-005: 基本統計・ストリーク表示

StatsPage は以下の基本統計をカード形式で表示しなければならない 🔵 *backlog「基本統計」セクションより*

- 総カード数 / 学習済み / 未学習 (進捗バー付き)
- 本日の復習対象数
- 連続学習日数 (ストリークを目立つアイコン + 日数で表示) 🔵 *backlog「炎アイコン + 日数」より*
- 総復習回数、平均グレード

### REQ-006: 苦手カードリスト表示

StatsPage は ease_factor が低い苦手カード TOP 10 をリスト表示しなければならない 🔵 *backlog「苦手カード TOP 10」より*

- カード表面テキスト、ease_factor、復習回数を表示
- カードタップで該当カードの詳細に遷移可能 🟡 *一般的な UX パターンから妥当な推測*

### REQ-007: 復習予測表示

StatsPage は向こう 7 日間の復習予測を表示しなければならない 🔵 *backlog「今後の復習予測」より*

- 日付と予測 due カード数のリスト表示
- 将来的にグラフ表示へ拡張可能な構成とする 🟡 *backlog のグラフ推奨から妥当な推測*

---

## 制約

- REQ-C01: フロントエンドは React 19 + TypeScript + Tailwind CSS 4 で実装する 🔵 *CLAUDE.md 技術スタックより*
- REQ-C02: バックエンドは Python 3.12 + AWS SAM (Lambda + API Gateway + DynamoDB) で実装する 🔵 *CLAUDE.md 技術スタックより*
- REQ-C03: 初期フェーズでは新規 DynamoDB テーブル (user_stats) は作成せず、既存テーブル (cards, reviews) からリアルタイム集計する 🔴 *軽量開発方針としての仮定*
- REQ-C04: グラフライブラリの導入は初期フェーズでは行わず、リスト/カード形式の表示とする 🔴 *軽量開発方針としての仮定。将来 Recharts 導入を想定*
- REQ-C05: 既存の `get_review_summary()` ロジックを最大限再利用する 🟡 *既存コードの活用から妥当な推測*

---

## ユーザーストーリー

### US-001: 学習進捗の確認

**ユーザーとして**、自分の学習統計（総カード数、学習済み数、ストリーク日数）を一目で確認したい。**それにより**、学習の進捗を把握しモチベーションを維持できる。

### US-002: 苦手分野の把握

**ユーザーとして**、ease_factor が低い苦手カードの一覧を確認したい。**それにより**、重点的に復習すべきカードを特定し、学習効率を改善できる。

### US-003: 復習計画の立案

**ユーザーとして**、向こう 7 日間に復習すべきカード数の予測を確認したい。**それにより**、学習時間の計画を立てやすくなる。

---

## 受け入れ基準

### AC-001: 統計 API

- `GET /stats` が認証済みユーザーに対して正しい統計データを返す
- `total_cards = learned_cards + unlearned_cards` が成立する
- `streak_days` が連続学習日数を正しく反映する

### AC-002: 苦手カード API

- `GET /stats/weak-cards` が ease_factor 昇順でカードを返す
- `limit` パラメータが正しく機能する
- カードが存在しない場合、空配列を返す

### AC-003: 復習予測 API

- `GET /stats/forecast` が指定日数分の予測を返す
- 各日の `due_count` が `next_review_at` に基づいて正確に算出される

### AC-004: StatsPage 表示

- StatsPage にアクセスすると基本統計、苦手カード、復習予測が表示される
- ローディング中はスケルトン/スピナーが表示される
- API エラー時はエラーメッセージが表示される

### AC-005: ナビゲーション

- HomePage または既存ナビゲーションから StatsPage に遷移できる
- StatsPage から他のページに正常に遷移できる

---

## 非機能要件

### パフォーマンス

- NFR-001: 統計 API のレスポンス時間は 1 秒以内とする 🟡 *既存 API のパフォーマンス基準から妥当な推測*
- NFR-002: StatsPage の初期表示は 2 秒以内に完了する 🟡 *一般的な Web UI パフォーマンス基準から妥当な推測*

### セキュリティ

- NFR-101: 統計 API は認証済みユーザーのみアクセス可能とする 🔵 *既存 API 認証設計より*
- NFR-102: ユーザーは自身のデータのみ閲覧可能とする 🔵 *既存 API 認可設計より*

### ユーザビリティ

- NFR-201: モバイル端末 (幅 375px 以上) で適切に表示される 🔵 *既存 LIFF アプリのモバイルファースト方針より*
- NFR-202: タッチターゲットは最小 44x44px を確保する 🔵 *既存 review-flow NFR-201 より*
