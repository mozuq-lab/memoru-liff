# Implementation Plan: Card Text-to-Speech

**Branch**: `001-card-speech` | **Date**: 2026-03-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-card-speech/spec.md`

## Summary

Web Speech API (`SpeechSynthesis`) を使って復習カードのテキストを音声で読み上げる機能をフロントエンドに追加する。読み上げボタンの手動タップ（P1）、自動読み上げ設定（P2）、速度調整（P3）の3フェーズで実装する。変更はフロントエンドのみ（新規ファイル2件 + 既存ファイル3件の改修）。バックエンド変更不要。

## Technical Context

**Language/Version**: TypeScript 5.x / React 19
**Primary Dependencies**: Web Speech API（ブラウザ組み込み、追加ライブラリ不要）、Vitest 3、React Testing Library
**Storage**: ブラウザ localStorage（`speech-settings:<userId>` キー）
**Testing**: Vitest + `vi.stubGlobal` で `speechSynthesis` モック、Playwright E2E（P3まで完了後）
**Target Platform**: LIFF - LINE in-app browser（iOS WebKit / Android Chrome ベース）+ 主要デスクトップブラウザ
**Project Type**: フロントエンド機能追加（SPA 既存ページへの統合）
**Performance Goals**: 読み上げボタンタップ → 音声開始 ≤ 1秒（SC-001）
**Constraints**: 音声合成非対応環境でのゼロエラー（SC-003）、後方互換必須（`FlipCard` への optional prop 追加）
**Scale/Scope**: 既存フロントエンドへの追加のみ。新規ファイル4件（`useSpeech.ts`、`useSpeechSettings.ts`、`SpeechButton.tsx`、それぞれのテスト）、改修3件（`FlipCard`、`ReviewPage`、`SettingsPage`）

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle                     | Status  | Notes                                                                                    |
| ----------------------------- | ------- | ---------------------------------------------------------------------------------------- |
| I. Test-Driven Development    | ✅ PASS | TDD サイクル適用。各 hook / component の unit test を先行作成。カバレッジ 80%+ 目標      |
| II. Security First            | ✅ PASS | フロントエンドのみの変更。ユーザーデータ送信なし。localStorage はユーザーID キーで分離   |
| III. API Contract Integrity   | ✅ PASS | バックエンド API 変更なし。`FlipCard` の prop 追加は optional で後方互換                 |
| IV. Performance & Scalability | ✅ PASS | Web Speech API はブラウザネイティブ（追加レイテンシなし）。非対応環境は graceful degrade |
| V. Documentation Excellence   | ✅ PASS | `research.md`・`data-model.md`・`contracts/` 作成済み。`quickstart.md` を Phase 1 で作成 |

**Post-design re-check**: 全ゲート引き続きパス。アーキテクチャ変更なし。

## Project Structure

### Documentation (this feature)

```text
specs/001-card-speech/
├── plan.md              ← このファイル
├── spec.md
├── research.md          ✅ 作成済み
├── data-model.md        ✅ 作成済み
├── contracts/
│   ├── components.md    ✅ 作成済み
│   └── hooks.md         ✅ 作成済み
└── tasks.md             # /speckit.tasks で作成
```

### Source Code (repository root)

```text
frontend/src/
├── hooks/
│   ├── useSpeech.ts                    # 新規: SpeechSynthesis ラッパー hook
│   ├── useSpeechSettings.ts            # 新規: localStorage 設定 hook
│   └── __tests__/
│       ├── useSpeech.test.ts           # 新規: unit test (TDD)
│       └── useSpeechSettings.test.ts   # 新規: unit test (TDD)
├── components/
│   ├── SpeechButton.tsx                # 新規: 読み上げ/停止トグルボタン
│   ├── FlipCard.tsx                    # 改修: speechProps オプショナル prop 追加
│   └── __tests__/
│       ├── SpeechButton.test.tsx       # 新規: unit test (TDD)
│       └── FlipCard.test.tsx           # 既存改修: speechProps のシナリオ追加
├── pages/
│   ├── ReviewPage.tsx                  # 改修: useSpeech / useSpeechSettings 統合
│   └── SettingsPage.tsx                # 改修: SpeechSettingsSection 追加
└── types/
    └── speech.ts                       # 新規: SpeechSettings・SpeechRate 型定義
```

**Structure Decision**: フロントエンド単体変更。既存の「コンポーネント・フック・型」の分離パターンを踏襲。

## Phase 0: Research

**Status**: ✅ Complete — [research.md](research.md) 参照

Key findings:

- Web Speech API は全対象ブラウザでサポート済み。外部ライブラリ不要
- `vi.stubGlobal('speechSynthesis', ...)` で Vitest モック可能
- 設定は `speech-settings:<userId>` キーで localStorage に保存（ユーザーID分離）
- `FlipCard` への `speechProps` optional prop 追加で後方互換維持

## Phase 1: Design

**Status**: ✅ Complete

### Data Model

→ [data-model.md](data-model.md)

```ts
type SpeechRate = 0.5 | 1 | 1.5;

interface SpeechSettings {
  autoPlay: boolean; // default: false
  rate: SpeechRate; // default: 1
}
// Storage key: `speech-settings:${userId}`
```

### Interface Contracts

→ [contracts/hooks.md](contracts/hooks.md)
→ [contracts/components.md](contracts/components.md)

| Contract                 | ファイル                                           |
| ------------------------ | -------------------------------------------------- |
| `useSpeech` hook         | `frontend/src/hooks/useSpeech.ts`                  |
| `useSpeechSettings` hook | `frontend/src/hooks/useSpeechSettings.ts`          |
| `SpeechButton` component | `frontend/src/components/SpeechButton.tsx`         |
| `FlipCard` props 拡張    | `frontend/src/components/FlipCard.tsx`             |
| `SpeechSettingsSection`  | `frontend/src/pages/SettingsPage.tsx` (インライン) |

### Constitution Check (post-design)

全ゲート引き続きパス。変更スコープはフロントエンドのみ。新規ファイルはすべて TDD で実装。

## Implementation Order

### Story P1: 手動読み上げ（MVP）

1. `types/speech.ts` — `SpeechRate`・`SpeechSettings` 型定義
2. `useSpeech.ts` (TDD red → green → refactor)
3. `SpeechButton.tsx` (TDD red → green → refactor)
4. `FlipCard.tsx` — `speechProps` optional prop 追加
5. `ReviewPage.tsx` — `useSpeech`・`useSpeechSettings` を接続

### Story P2: 自動読み上げ

6. `useSpeechSettings.ts` (TDD red → green → refactor)
7. `ReviewPage.tsx` — `autoPlay` ロジック追加（`useEffect` でカード遷移時に発火）
8. `SettingsPage.tsx` — `SpeechSettingsSection` 追加

### Story P3: 読み上げ速度調整

9. `useSpeech.ts` — `rate` オプション接続
10. `SettingsPage.tsx` — 速度ラジオボタン追加

## Complexity Tracking

特記事項なし。既存パターンから逸脱する設計判断はない。
