# Implementation Plan: カード検索

**Branch**: `001-card-search` | **Date**: 2026-02-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-card-search/spec.md`

## Summary

カード一覧画面にキーワード検索・復習状態フィルター・ソートを追加する。Phase 1 はバックエンド変更なしのフロントエンドのみのクライアントサイド実装。既存 `GET /cards` API で取得済みのカードデータに対して React の `useMemo` + フィルタリング関数で即座に絞り込む。新規コンポーネント（`SearchBar`, `FilterChips`, `SortSelect`, `HighlightText`）と新規フック（`useCardSearch`）を追加し、既存の `CardsPage.tsx` に組み込む。

## Technical Context

**Language/Version**: TypeScript 5.x, React 18
**Primary Dependencies**: Tailwind CSS（既存）, Vitest + React Testing Library（テスト）、新規ライブラリ追加なし
**Storage**: N/A（クライアントサイドのみ、`useState` でフィルター状態を管理）
**Testing**: Vitest + React Testing Library（フロントエンド）
**Target Platform**: LINE LIFF（モバイルブラウザ、Chrome/Safari）
**Project Type**: web-app（React SPA）
**Performance Goals**: フィルタリング応答 <300ms（500枚カード想定、`Array.filter` は即時処理可能）
**Constraints**: バックエンドAPI変更なし、新規 npm パッケージ追加なし、Tailwind CSS のみでスタイリング
**Scale/Scope**: 最大 500 枚カード（クライアントサイド）、フロントエンドのみ変更

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| 原則                          | チェック                                                                                                                      | 判定    | 根拠                                                                                     |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ------- | ---------------------------------------------------------------------------------------- |
| I. Test-Driven Development    | `useCardSearch` フック・各コンポーネントはユニットテスト必須。受け入れシナリオを先にテストで記述                              | ✅ PASS | Vitest + RTL でカバー可能。TDDサイクルを適用                                             |
| II. Security First            | 検索キーワードは React の JSX レンダリング経由のため XSS は自動エスケープ。ただし `HighlightText` での `innerHTML` 使用は禁止 | ✅ PASS | `innerHTML` 不使用。テキスト分割＋`<mark>` タグで実装（[research.md §2](./research.md)） |
| III. API Contract Integrity   | `GET /cards` API は変更なし。型定義 `Card` は既存のまま。新規型 `CardFilterState` はフロントエンドのみ                        | ✅ PASS | バックエンドへの変更なし（[contracts/frontend-state.md](./contracts/frontend-state.md)） |
| IV. Performance & Scalability | 500枚 × `Array.filter` は <1ms。`useMemo` で再計算を最小化                                                                    | ✅ PASS | デバウンス不要（[research.md §6](./research.md)）                                        |
| V. Documentation Excellence   | 新規フック・コンポーネントに JSDoc コメント必須。設計文書完備                                                                 | ✅ PASS | data-model.md, contracts/, quickstart.md で補完                                          |

**結論**: 全 5 原則通過。設計後も問題なし。実装に進む。

## Project Structure

### Documentation (this feature)

```text
specs/001-card-search/
├── plan.md              # このファイル
├── research.md          # Phase 0 出力
├── data-model.md        # Phase 1 出力
├── quickstart.md        # Phase 1 出力
├── contracts/           # Phase 1 出力
│   └── frontend-state.md
└── tasks.md             # Phase 2 出力（/speckit.tasks コマンドで生成）
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── components/
│   │   ├── SearchBar.tsx           # 新規: 検索バー + クリアボタン
│   │   ├── FilterChips.tsx         # 新規: 復習状態フィルターチップ
│   │   ├── SortSelect.tsx          # 新規: ソート順ドロップダウン
│   │   ├── HighlightText.tsx       # 新規: キーワードハイライト
│   │   ├── CardList.tsx            # 変更: highlightQuery props 追加
│   │   └── __tests__/
│   │       ├── SearchBar.test.tsx   # 新規
│   │       ├── FilterChips.test.tsx # 新規
│   │       ├── SortSelect.test.tsx  # 新規
│   │       └── HighlightText.test.tsx # 新規
│   ├── hooks/
│   │   ├── useCardSearch.ts        # 新規: 検索・フィルター・ソート状態管理
│   │   └── __tests__/
│   │       └── useCardSearch.test.ts # 新規
│   ├── pages/
│   │   ├── CardsPage.tsx           # 変更: SearchBar/FilterChips/SortSelect 組み込み
│   │   └── __tests__/
│   │       └── CardsPage.test.tsx  # 変更: 検索・フィルター・ソートのテスト追加
│   └── types/
│       └── card.ts                 # 変更: CardFilterState 型定義追加
└── tests/ (既存のまま)
```

**Structure Decision**: フロントエンドのみの変更。バックエンドは変更なし。新規コンポーネントは `frontend/src/components/` に追加し、フィルター状態管理は `frontend/src/hooks/useCardSearch.ts` に集約する。

## Complexity Tracking

_Constitution Check に違反なし。このセクションは空。_
