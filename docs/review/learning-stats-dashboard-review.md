# レビュー: feature/learning-stats-dashboard

> **レビュー日**: 2026-03-05
> **レビュアー**: Claude Code (Opus 4.6) + Codex (OpenAI)
> **対象ブランチ**: `feature/learning-stats-dashboard` (10 commits, main..HEAD)
> **判定**: **条件付き承認（修正後マージ）**

---

## 概要

LINE ベースの暗記カードアプリ「Memoru LIFF」に学習統計ダッシュボードを追加するブランチ。バックエンドに 3 つの API エンドポイント（`/stats`, `/stats/weak-cards`, `/stats/forecast`）、フロントエンドに `StatsPage` と関連コンポーネント群を新規実装。

加えて、未使用となった音声機能（`SpeechButton`, `useSpeech`, `useSpeechSettings`, `SettingsPage`）と旧 spec/design/tasks ドキュメント（`001-card-speech-bugfix`）のクリーンアップ削除を含む。

### 変更規模

- **89 files changed**: +4,463 / -5,917 lines
- 新規: stats バックエンド (models/service/handler) + フロントエンド (8 components, hook, page, types, API)
- 削除: 音声関連コード + 旧ドキュメント群

---

## 評価ポイント（良い点）

- Pydantic モデルが明確で `Field` 記述が適切
- ハンドラーテストが成功/空/上限キャップ/デフォルト/エラー伝播を網羅
- `StatsPage.test.tsx` が loading/error/empty/streak バリアント/ナビゲーション/アクセシビリティを広くカバー
- `ProgressBar` で `total == 0` のゼロ除算を正しく処理
- クエリパラメータ上限（limit <= 50, days <= 30）をハンドラー層で制御
- `useStats` フックの loading/error/data 状態分離が明快
- フロントエンド/バックエンド間の型定義が整合

---

## 指摘事項

### Critical (1件)

#### C-1: 全テーブルスキャン + 3 API 並列で高コスト化

| 項目 | 値 |
|------|-----|
| ファイル | `stats_service.py:65-108`, `useStats.ts:31` |
| 合意 | Claude / Codex 双方 |

`_fetch_all_cards` / `_fetch_all_reviews` がユーザーの全データをメモリに読み込む。フロントエンドの `Promise.all` で 3 エンドポイントを並列呼び出しするため、1 ページロードで cards テーブルを **3 回**、reviews テーブルを **1 回**フルスキャンする。

ユーザーが 2,000 枚のカードと 20,000 件のレビューを持つ場合、Lambda タイムアウトリスクが高い。

**推奨対応**: Phase 2 で Issue 化し以下を実施:
- `cards_due_today` → GSI (`user_id-due-index`) を利用した条件付きクエリに変更
- 集計カウンター（total_cards, learned_cards）をメタデータアイテムに保持し、書き込み時に更新
- `_fetch_all_cards` に `ProjectionExpression` を追加して不要属性を除外
- reviews 取得を直近 90 日に制限
- 3 エンドポイントの統合、またはバックエンド内で `_fetch_all_cards` のキャッシュ共有

---

### Major (5件)

#### M-1: クエリパラメータ検証不足

| 項目 | 値 |
|------|-----|
| ファイル | `stats_handler.py:39, 57` |
| 合意 | Claude / Codex 双方 |

```python
limit = min(int(params.get("limit", 10)), 50)
```

- `int("abc")` → `ValueError` → 500 Internal Server Error
- `limit=-1` → `min(-1, 50)` = `-1` → `reviewed_cards[:-1]` で最後の1件が欠ける

**修正案**: `try/except ValueError` で 400 を返却。`max(1, ...)` で下限を設定。

```python
try:
    limit = max(1, min(int(params.get("limit", 10)), 50))
except (ValueError, TypeError):
    raise BadRequestError("limit must be a positive integer")
```

#### M-2: `cards_due_today` の空文字列比較バグ

| 項目 | 値 |
|------|-----|
| ファイル | `stats_service.py:138-142` |
| 合意 | Claude / Codex 双方 |

```python
cards_due_today = sum(
    1 for c in cards if c.get("next_review_at", "") <= now_iso
)
```

- `next_review_at` 未設定のカードは空文字列 `""` となり、任意の ISO 文字列より小さいため **全て due 扱い** になる
- `get_forecast` では `next_review_at` が `None` のカードをスキップしており、**動作が矛盾**

**修正案**: `next_review_at` が未設定のカードをスキップ。可能であれば ISO 文字列比較でなく `datetime` パースして比較。

```python
now = datetime.now(timezone.utc)
cards_due_today = 0
for c in cards:
    raw = c.get("next_review_at")
    if not raw:
        continue
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt <= now:
            cards_due_today += 1
    except (ValueError, TypeError):
        continue
```

#### M-3: DynamoDB 障害時の 200 + 空データ返却（エラー隠蔽）

| 項目 | 値 |
|------|-----|
| ファイル | `stats_service.py:122-132, 202-203, 248-249` |
| 合意 | Claude / Codex 双方 |

`ClientError` を catch してゼロ/空データの正常レスポンスを返すため、DynamoDB 障害やテーブル名誤りが「新規ユーザー」と区別できない。

**修正案**: `ClientError` は logger.error で記録後、再 raise して handler 層の `try/except` に委ねる（500 レスポンスになる）。
または `StatsServiceError`（現在未使用）でラップして raise する。

#### M-4: `ReviewService._calculate_streak` への private メソッド依存

| 項目 | 値 |
|------|-----|
| ファイル | `stats_service.py:157` |
| 合意 | Claude / Codex 双方 |

```python
streak_days = ReviewService._calculate_streak(unique_dates)
```

Python の `_` prefix は「実装詳細」の慣習。`ReviewService` 側の変更で予告なく壊れるリスク。

**修正案**: `utils/streak.py` にピュア関数として抽出し、両サービスから参照。

#### M-5: `ForecastBar` の日付パースがタイムゾーン非対応

| 項目 | 値 |
|------|-----|
| ファイル | `ForecastBar.tsx:17-20` |
| 合意 | Claude / Codex 双方 |

```typescript
const date = new Date(dateStr);  // "2026-03-05" → UTC midnight
return `${date.getMonth() + 1}/${String(date.getDate()).padStart(2, '0')}`;
// UTC-N では前日の日付になる
```

日本向けアプリ（UTC+9）では現時点で実害なし。ただし文字列パースが安全。

**修正案**:
```typescript
const [, month, day] = dateStr.split('-');
return `${parseInt(month)}/${day}`;
```

---

### Minor (7件)

| # | 指摘 | ファイル | 合意 |
|---|------|----------|------|
| m-1 | `Promise.all` の all-or-nothing 挙動で部分的成功を捨てる | `useStats.ts:31-35` | 双方 |
| m-2 | `useStats` にアンマウントガードなし（React 19 では warning は出ないが cleanup 推奨） | `useStats.ts` | 双方 |
| m-3 | `StatsServiceError` が定義されたまま未使用。使うか削除するか統一 | `stats_service.py:24-27` | 双方 |
| m-4 | テスト fixtures が DynamoDB 実データ（`Decimal`）でなく `str`/`int` を使用 | `test_stats_service.py` | 双方 |
| m-5 | `WeakCardsList` の "TOP 10" がハードコードで実際の件数と不一致の可能性 | `WeakCardsList.tsx:22` | 双方 |
| m-6 | `ProgressBar` の label/no-label で重複 JSX ブロック | `ProgressBar.tsx:19-31` | Claude のみ |
| m-7 | `ReviewForecast.tsx` のデコレーティブ絵文字に `aria-hidden` 欠如 | `ReviewForecast.tsx:24` | Claude のみ |

---

### Suggestion (1件)

| # | 指摘 | 説明 |
|---|------|------|
| s-1 | `test_stats_handler.py` で `StatsServiceError` の未使用 import | m-3 と関連。import を削除するか、テストケースを追加 |

---

## 音声機能削除について

### 事実確認

`git diff --name-status main..HEAD` で確認した結果、以下のファイルが**このブランチで削除**されている:

- `frontend/src/components/SpeechButton.tsx` + テスト
- `frontend/src/hooks/useSpeech.ts` + `useSpeechSettings.ts` + テスト
- `frontend/src/pages/SettingsPage.tsx` + テスト
- `frontend/src/types/speech.ts`
- `docs/tasks/001-card-speech-bugfix/` 配下全ファイル
- `docs/design/001-card-speech-bugfix/` 配下全ファイル
- `docs/spec/001-card-speech-bugfix/` 配下全ファイル
- `docs/review/001-card-speech-review.md`
- `specs/001-card-speech/` 配下全ファイル

### 合意判断

**A 案を採用**: このPRに含めてマージする。

- 音声機能は既に未使用状態であり、削除は意図的なクリーンアップ
- 10 コミット済みブランチの git history 書き換えはコスト高
- ただし **PR description に削除意図を明記** し、レビュアー同意を取ること

---

## マージ判定

### 今回 PR で必須修正（マージ前）

1. **M-1**: クエリパラメータの入力検証追加
2. **M-2**: `cards_due_today` の空文字列比較バグ修正
3. **M-3**: `ClientError` の握りつぶしをやめ、エラーを伝播
4. PR description に「統計機能追加 + 音声/旧spec のクリーンアップ削除」を明記

### Phase 2 送り（Issue 化して追跡）

1. **C-1**: 全件取得のスケーラビリティ改善（DynamoDB クエリ最適化、集計カウンター導入）
2. **M-4**: streak ロジックの共通ユーティリティ抽出
3. **M-5**: `ForecastBar` の日付パース修正
4. フロントエンドの部分成功戦略（`Promise.allSettled`）検討

### 対応不要（現時点で許容）

- Minor / Suggestion の指摘は品質改善として Phase 2 以降で段階的に対応

---

## 付録: レビュープロセス

本レビューは以下のプロセスで実施:

1. **Claude Code (Opus 4.6)**: コードリーダーエージェントによる全ファイル精読 + テスト品質分析
2. **Codex (OpenAI)**: `git diff main..HEAD` の全差分レビュー + セキュリティ/パフォーマンス分析
3. **クロスレビュー**: 両者の指摘を突き合わせ、重複確認・追加指摘の整理・優先度合意
4. **議論**: 音声機能削除の扱い（A案/B案）、マージ判定基準を議論し合意
