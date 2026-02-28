---
description: "Task list for 001-card-search feature implementation"
---

# Tasks: カード検索（001-card-search）

**Input**: `specs/001-card-search/`（plan.md, spec.md, data-model.md, contracts/frontend-state.md, research.md, quickstart.md）
**Branch**: `001-card-search`
**Scope**: フロントエンド専用（バックエンド変更なし）

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 別ファイルかつ依存なしのため並列実行可
- **[Story]**: 対応するユーザーストーリー（US1, US2, US3）
- TDD 必須: テストタスクは対応する実装タスクの **前** に実行し、RED を確認してから実装する

---

## Phase 1: セットアップ（Setup）

**Purpose**: テスト環境の確認と作業ブランチ確認

- [X] T001 `frontend/` で `npm run test` が通ることを確認し、テスト実行環境が正常であることを検証する

---

## Phase 2: 基盤（Foundational）— 全ユーザーストーリーの前提条件

**Purpose**: 3つのユーザーストーリーすべてで使用する型定義を追加する

**⚠️ CRITICAL**: このフェーズが完了するまで US1〜US3 の実装を開始してはいけない

- [X] T002 `frontend/src/types/card.ts` に `ReviewStatusFilter` 型を追加する（`'all' | 'new' | 'due' | 'learning'`）
- [X] T003 `frontend/src/types/card.ts` に `SortByOption` 型を追加する（`'created_at' | 'next_review_at' | 'ease_factor'`）
- [X] T004 `frontend/src/types/card.ts` に `SortOrder` 型を追加する（`'asc' | 'desc'`）
- [X] T005 `frontend/src/types/card.ts` に `CardFilterState` インターフェースを追加する（query, reviewStatus, sortBy, sortOrder）

**Checkpoint**: `npm run type-check` が通ること → ユーザーストーリー実装開始可能

---

## Phase 3: ユーザーストーリー1 — キーワード検索 + ハイライト（Priority: P1）🎯 MVP

**Goal**: カード一覧ページでキーワード入力によりカードをリアルタイムにフィルタリングし、マッチ箇所をハイライト表示する

**Independent Test**:

1. CardsPage を開き SearchBar にキーワードを入力 → 表示カードが絞り込まれる
2. マッチ箇所が `<mark>` タグでハイライトされる
3. ✕ボタンでクリアできる
4. 全角・半角・大小文字の区別なく検索できる

### TDD テスト（先に作成し FAIL を確認すること）⚠️

> **NOTE: 以下のテストを先に記述し、すべて RED（失敗）であることを確認してから実装に進む**

- [X] T006 [P] [US1] `frontend/src/components/__tests__/HighlightText.test.tsx` を作成する（HT-001〜HT-006 の 6 ケース: 空クエリ, mark タグ, 大小文字無視, 全角半角無視, XSS エスケープ, 複数マッチ）
- [X] T007 [P] [US1] `frontend/src/hooks/__tests__/useCardSearch.test.ts` を作成する（クエリフィルター: 空クエリ全件返す, 部分一致, 全角half-width 正規化, useMemo が依存変化時のみ再計算）
- [X] T008 [P] [US1] `frontend/src/components/__tests__/SearchBar.test.tsx` を作成する（SB-001〜SB-008 の 8 ケース: 表示, onChange 呼び出し, クリアボタン表示/非表示/押下, maxLength, data-testid）

### 実装（テストが RED であることを確認後に実装し GREEN にする）

- [X] T009 [P] [US1] `frontend/src/components/HighlightText.tsx` を新規作成する（`text.normalize('NFKC').toLowerCase()` で正規化, `<mark>` タグ分割, `dangerouslySetInnerHTML` 不使用）
- [X] T010 [P] [US1] `frontend/src/hooks/useCardSearch.ts` を新規作成する（クエリフィルターのみ実装: `useMemo`, `normalize('NFKC').toLowerCase()`, 初期値 `query: ''`）
- [X] T011 [P] [US1] `frontend/src/components/SearchBar.tsx` を新規作成する（入力フィールド, クリアボタン, `data-testid="search-bar-input"`, `data-testid="search-bar-clear"`, `maxLength={100}`）
- [X] T012 [US1] `frontend/src/components/CardList.tsx` を更新する（`highlightQuery?: string` prop を追加し、CardListItem の front/back テキストを `HighlightText` コンポーネントで表示する）
- [X] T013 [US1] `frontend/src/pages/CardsPage.tsx` に `useCardSearch` フックと `SearchBar` を組み込む（`displayCards` を `filteredCards` に差し替え, `CardList` に `highlightQuery={query}` を渡す）

**Checkpoint**: この時点で US1 が単独で動作・テスト可能であること（`npm test`全通過, Vitest coverage US1 ファイル 80%+ ）

---

## Phase 4: ユーザーストーリー2 — 復習状態フィルター（Priority: P2）

**Goal**: チップ UI（all / due / learning / new）でカードを復習状態別にフィルタリングできる

**Independent Test**:

1. `FilterChips` で「期日（due）」を選択 → due カードのみ表示
2. `FilterChips` で「新規」を選択 → `repetitions === 0` のカードのみ表示
3. キーワード検索と組み合わせて AND フィルタリングされる

### TDD テスト（先に作成し FAIL を確認すること）⚠️

- [ ] T014 [P] [US2] `frontend/src/components/__tests__/FilterChips.test.tsx` を作成する（FC-001〜FC-004 の 4 ケース: 4チップ表示, aria-pressed, onChange 呼び出し, 選択状態 UI）
- [ ] T015 [P] [US2] `frontend/src/hooks/__tests__/useCardSearch.test.ts` に reviewStatus フィルターのテストケースを追記する（all=全件, new=repetitions===0, due=期日超過, learning=学習中, キーワードとの AND）

### 実装

- [ ] T016 [P] [US2] `frontend/src/components/FilterChips.tsx` を新規作成する（`data-testid="filter-chip-all/due/learning/new"`, `aria-pressed`, Tailwind で選択状態スタイル）
- [ ] T017 [US2] `frontend/src/hooks/useCardSearch.ts` に `reviewStatus` フィルターロジックを追加する（`repetitions === 0` → new, `next_review_at <= today` → due, それ以外 → learning, `useMemo` の依存配列に `reviewStatus` を追加）
- [ ] T018 [US2] `frontend/src/pages/CardsPage.tsx` に `FilterChips` を組み込む（`reviewStatus`, `setReviewStatus` を useCardSearch から取得して渡す）

**Checkpoint**: この時点で US1 + US2 が両方独立して動作可能であること

---

## Phase 5: ユーザーストーリー3 — ソート（Priority: P3）

**Goal**: ソートキー（作成日 / 次回復習日 / 習熟度）と方向（昇順 / 降順）でカードを並び替えられる

**Independent Test**:

1. `SortSelect` で「習熟度（昇順）」を選択 → `ease_factor` の低いカードが上位
2. 「次回復習日（降順）」を選択 → `next_review_at` が遠いカードが上位（null は末尾）
3. キーワード検索・状態フィルターと組み合わせて動作する

### TDD テスト（先に作成し FAIL を確認すること）⚠️

- [ ] T019 [P] [US3] `frontend/src/components/__tests__/SortSelect.test.tsx` を作成する（SS-001〜SS-006 の 6 ケース: ドロップダウン表示, トグルボタン表示, data-testid, onSortByChange/onSortOrderChange 呼び出し）
- [ ] T020 [P] [US3] `frontend/src/hooks/__tests__/useCardSearch.test.ts` にソートのテストケースを追記する（created_at 昇降順, next_review_at・null は末尾, ease_factor 昇降順, 安定ソート, フィルター後ソートの順序）

### 実装

- [ ] T021 [P] [US3] `frontend/src/components/SortSelect.tsx` を新規作成する（`<select>` で sortBy 選択, `data-testid="sort-by-select"`, `data-testid="sort-order-toggle"`, Tailwind スタイル）
- [ ] T022 [US3] `frontend/src/hooks/useCardSearch.ts` にソートロジックを追加する（`Array.sort` コンパレーター, `next_review_at` null 末尾処理, `useMemo` 依存配列に `sortBy`, `sortOrder` を追加）
- [ ] T023 [US3] `frontend/src/pages/CardsPage.tsx` に `SortSelect` を組み込む（`sortBy`, `sortOrder`, `setSortBy`, `setSortOrder` を渡す）

**Checkpoint**: この時点で US1 + US2 + US3 すべてが動作可能であること

---

## Phase 6: ポリッシュ & 横断的関心事

**Purpose**: 複数ストーリーに影響する品質改善

- [ ] T024 `frontend/src/pages/CardsPage.tsx` で SearchBar / FilterChips / SortSelect のレイアウト調整を行う（モバイル縦並び, Tailwind `flex-col gap-2`）
- [ ] T025 [P] `frontend/src/components/SearchBar.tsx` に `aria-label="カードを検索"` を設定し, FilterChips の各チップに `aria-label` を付与してアクセシビリティを強化する
- [ ] T026 [P] `specs/001-card-search/quickstart.md` の手順に従ってローカル動作確認を行い、すべてのシナリオ（SC-001〜SC-005）をブラウザで目視検証する
- [ ] T027 `npm test` を実行してカバレッジレポートを確認する（新規ファイル全体で 80% 以上であることを確認）

---

## 依存関係と実行順序

### フェーズ依存

```
Phase 1 (Setup)
    └── Phase 2 (Foundational: 型定義)
            ├── Phase 3 (US1: キーワード検索) ← MVP
            ├── Phase 4 (US2: 状態フィルター)  ← US1 完了後が望ましいが独立可
            └── Phase 5 (US3: ソート)         ← US1 完了後が望ましいが独立可
                    └── Phase 6 (Polish)
```

### ユーザーストーリー依存

- **US1 (P1)**: Phase 2 完了後に開始可能。他のストーリーへの依存なし
- **US2 (P2)**: Phase 2 完了後に開始可能。`useCardSearch` の拡張のため US1 後が推奨
- **US3 (P3)**: Phase 2 完了後に開始可能。`useCardSearch` の拡張のため US1・US2 後が推奨

### 各ストーリー内の順序

1. テストを記述 → `npm test` で **RED（失敗）** を確認
2. 実装 → `npm test` で **GREEN（成功）** を確認
3. リファクタリング（必要であれば）
4. タスク完了後にコミット

---

## 並列実行例

### Phase 3（US1）の並列タスク

```
同時実行可能（別ファイルのため）:
  T006: HighlightText.test.tsx 作成
  T007: useCardSearch.test.ts 作成（クエリ部分）
  T008: SearchBar.test.tsx 作成

上記完了後、同時実行可能:
  T009: HighlightText.tsx 実装
  T010: useCardSearch.ts 実装（クエリ部分）
  T011: SearchBar.tsx 実装

上記完了後（CardList.tsx, CardsPage.tsx は直列）:
  T012: CardList.tsx 更新
  → T013: CardsPage.tsx 統合
```

### Phase 4（US2）の並列タスク

```
同時実行可能:
  T014: FilterChips.test.tsx 作成
  T015: useCardSearch.test.ts にテスト追記

上記完了後:
  T016: FilterChips.tsx 実装
  → T017: useCardSearch.ts 拡張（reviewStatus）
  → T018: CardsPage.tsx 統合
```

### Phase 5（US3）の並列タスク

```
同時実行可能:
  T019: SortSelect.test.tsx 作成
  T020: useCardSearch.test.ts にテスト追記

上記完了後:
  T021: SortSelect.tsx 実装
  → T022: useCardSearch.ts 拡張（sort）
  → T023: CardsPage.tsx 統合
```

---

## 実装戦略

### MVP ファースト（US1 のみ）

1. Phase 1: セットアップ確認（T001）
2. Phase 2: 型定義追加（T002〜T005）
3. Phase 3: US1 のみ実装（T006〜T013）
4. **STOP & VALIDATE**: ブラウザで US1 を手動検証
5. 問題なければデプロイ/デモ可能

### インクリメンタルデリバリー

1. Setup + Foundational → 基盤完成
2. US1 追加 → 独立テスト → デプロイ/デモ（MVP）
3. US2 追加 → 独立テスト → デプロイ/デモ
4. US3 追加 → 独立テスト → デプロイ/デモ
5. Polish → 品質向上

---

## 作成・変更ファイル一覧

| ファイル                                                   | 操作              | 対応フェーズ |
| ---------------------------------------------------------- | ----------------- | ------------ |
| `frontend/src/types/card.ts`                               | 変更（型追加）    | Phase 2      |
| `frontend/src/components/__tests__/HighlightText.test.tsx` | 新規              | Phase 3      |
| `frontend/src/hooks/__tests__/useCardSearch.test.ts`       | 新規              | Phase 3〜5   |
| `frontend/src/components/__tests__/SearchBar.test.tsx`     | 新規              | Phase 3      |
| `frontend/src/components/HighlightText.tsx`                | 新規              | Phase 3      |
| `frontend/src/hooks/useCardSearch.ts`                      | 新規              | Phase 3〜5   |
| `frontend/src/components/SearchBar.tsx`                    | 新規              | Phase 3      |
| `frontend/src/components/CardList.tsx`                     | 変更（prop 追加） | Phase 3      |
| `frontend/src/pages/CardsPage.tsx`                         | 変更（統合）      | Phase 3〜5   |
| `frontend/src/components/__tests__/FilterChips.test.tsx`   | 新規              | Phase 4      |
| `frontend/src/components/FilterChips.tsx`                  | 新規              | Phase 4      |
| `frontend/src/components/__tests__/SortSelect.test.tsx`    | 新規              | Phase 5      |
| `frontend/src/components/SortSelect.tsx`                   | 新規              | Phase 5      |

**合計**: 新規 9 ファイル、変更 4 ファイル

---

## Notes

- `[P]` タスクは別ファイルかつ依存なし → 並列実行可能
- `[Story]` ラベルでトレーサビリティを確保
- 各ユーザーストーリーは独立して完成・テスト可能
- **TDD 必須**: テスト記述 → RED 確認 → 実装 → GREEN 確認 → リファクタ
- タスクごとにコミットする（CLAUDE.md のコミットルール参照）
- `next_review_at` null 処理: null は sort 末尾扱い（research.md §5 参照）
- XSS 対策: `HighlightText` は `dangerouslySetInnerHTML` 不使用（research.md §2 参照）
- 新規 npm パッケージ追加禁止（plan.md 制約）
