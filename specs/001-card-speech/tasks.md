# Tasks: Card Text-to-Speech

**Input**: Design documents from `/specs/001-card-speech/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅
**Tech Stack**: TypeScript 5.x / React 19, Web Speech API（ブラウザ組み込み）, Vitest + React Testing Library
**Tests**: Constitution 原則 I (TDD) により必須。各 hook・component は Red → Green → Refactor サイクルで実装

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: 並行実行可能（別ファイル、未完了タスクへの依存なし）
- **[Story]**: 対応するユーザーストーリー (US1 / US2 / US3)
- 各タスクには正確なファイルパスを記載

---

## Phase 1: Setup（共有インフラ）

**Purpose**: 全ユーザーストーリーが依存する型定義を作成する

- [x] T001 Create `SpeechRate` and `SpeechSettings` type definitions in `frontend/src/types/speech.ts`

**Checkpoint**: 型定義完了 → フェーズ2 開始可能

---

## Phase 2: Foundational（ブロッキング前提条件）

**Purpose**: 全ユーザーストーリーが依存する2つの hook を TDD で実装する

**⚠️ CRITICAL**: このフェーズの完了後に各ユーザーストーリーの実装を開始できる

- [x] T002 [P] Write `useSpeech` contract tests (TDD red) in `frontend/src/hooks/__tests__/useSpeech.test.ts` — isSupported・speak・cancel・isSpeaking・cleanup の各ルールをカバー
- [x] T003 [P] Write `useSpeechSettings` contract tests (TDD red) in `frontend/src/hooks/__tests__/useSpeechSettings.test.ts` — userId undefined 時のデフォルト値・parse エラー時のフォールバック・partial update をカバー
- [x] T004 Implement `useSpeech` hook (TDD green) in `frontend/src/hooks/useSpeech.ts` — T002 のテストをパスさせる
- [x] T005 Implement `useSpeechSettings` hook (TDD green) in `frontend/src/hooks/useSpeechSettings.ts` — T003 のテストをパスさせる

**Checkpoint**: 両 hook のテストがグリーン → US1 / US2 / US3 の並行実装開始可能

---

## Phase 3: User Story 1 — カードを手動で読み上げる (Priority: P1) 🎯 MVP

**Goal**: 復習画面の各カード面に読み上げボタンを表示し、タップで再生・停止できる

**Independent Test**: 復習画面を開き、カード表面の読み上げボタンをタップして音声が再生されれば US1 完了。`FlipCard`, `SpeechButton` の unit test がすべてグリーンであること

### Tests for User Story 1（TDD red、先に失敗させる）

- [x] T006 [P] [US1] Write `SpeechButton` contract tests (TDD red) in `frontend/src/components/__tests__/SpeechButton.test.tsx` — disabled・isSpeaking トグル・aria-label・onClick コールバックをカバー
- [x] T007 [P] [US1] Add `speechProps` scenarios to `FlipCard` tests (TDD red) in `frontend/src/components/__tests__/FlipCard.test.tsx` — speechProps なし時の後方互換・isSupported false 時の非表示・表面/裏面別ボタン表示をカバー

### Implementation for User Story 1

- [x] T008 [US1] Implement `SpeechButton` component (TDD green) in `frontend/src/components/SpeechButton.tsx` — T006 のテストをパスさせる
- [x] T009 [US1] Extend `FlipCard` with optional `speechProps` prop (TDD green) in `frontend/src/components/FlipCard.tsx` — T007 のテストをパスさせる（後方互換必須）
- [x] T010 [US1] Integrate `useSpeech` and `SpeechButton` into `ReviewPage` in `frontend/src/pages/ReviewPage.tsx` — カード遷移時に `cancel()` を呼び出すロジックを含む

**Checkpoint**: US1 完了 — 手動読み上げが単独で動作・デモ可能な MVP 状態

---

## Phase 4: User Story 2 — カード表示時に自動読み上げ (Priority: P2)

**Goal**: 設定で自動読み上げをオンにすると、カードが表示されるたびに自動再生される。手動停止は現在カードのみ適用。自動フリップなし

**Independent Test**: 設定で自動読み上げをオンにして復習を開始し、カードが表示されるたびに自動再生されることを確認

### Tests for User Story 2（TDD red）

- [ ] T011 [P] [US2] Add autoPlay behavior tests to `frontend/src/hooks/__tests__/useSpeechSettings.test.ts` — autoPlay のデフォルト false・更新・次カードで継続するシナリオをカバー

### Implementation for User Story 2

- [ ] T012 [P] [US2] Add autoPlay logic to `ReviewPage` in `frontend/src/pages/ReviewPage.tsx` — `useEffect` でカード遷移時に `settings.autoPlay` が true なら自動発話。手動停止は現在カードのみ（設定変更しない）
- [ ] T013 [P] [US2] Add `SpeechSettingsSection` (autoPlay toggle) to `SettingsPage` in `frontend/src/pages/SettingsPage.tsx` — isSupported false 時は非対応メッセージを表示しセクション非表示

**Checkpoint**: US2 完了 — US1（手動）と US2（自動）が両方独立して動作

---

## Phase 5: User Story 3 — 読み上げ速度の調整 (Priority: P3)

**Goal**: ユーザーが遅め (0.5) / 標準 (1.0) / 速め (1.5) の3段階で読み上げ速度を設定できる

**Independent Test**: 設定で「遅め」を選択し読み上げボタンをタップ。通常より遅い速度で再生されることを確認

### Tests for User Story 3（TDD red）

- [ ] T014 [P] [US3] Add `rate` option tests to `frontend/src/hooks/__tests__/useSpeech.test.ts` — rate 0.5 / 1 / 1.5 が `SpeechSynthesisUtterance.rate` に正しく渡されることをカバー

### Implementation for User Story 3

- [ ] T015 [US3] Connect `rate` option in `useSpeech` hook in `frontend/src/hooks/useSpeech.ts` — T014 のテストをパスさせる（`utter.rate = options.rate ?? 1` を設定）
- [ ] T016 [US3] Add rate radio buttons (`遅め` / `標準` / `速め`) to `SettingsPage` in `frontend/src/pages/SettingsPage.tsx` — SpeechSettingsSection 内に追加

**Checkpoint**: US3 完了 — 全ユーザーストーリーが独立して動作

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: テストカバレッジの確認とドキュメント整備

- [ ] T017 [P] Verify Vitest coverage ≥ 80% for `frontend/src/hooks/useSpeech.ts`, `useSpeechSettings.ts`, `frontend/src/components/SpeechButton.tsx` (`npm run test -- --coverage`)
- [ ] T018 Create test scenario guide in `specs/001-card-speech/quickstart.md` — SC-001 〜 SC-004 の手動確認手順を記載

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
    └─ T001 (speech.ts types)
Phase 2 (Foundational)
    ├─ T002 [P] useSpeech.test.ts (red)
    ├─ T003 [P] useSpeechSettings.test.ts (red)
    ├─ T004 useSpeech.ts (green, ← T002)
    └─ T005 useSpeechSettings.ts (green, ← T003)
Phase 3 (US1)
    ├─ T006 [P] SpeechButton.test.tsx (red)
    ├─ T007 [P] FlipCard.test.tsx (red/update)
    ├─ T008 SpeechButton.tsx (green, ← T006)
    ├─ T009 FlipCard.tsx (green, ← T007)
    └─ T010 ReviewPage.tsx (← T008, T009)
Phase 4 (US2)
    ├─ T011 [P] useSpeechSettings.test.ts (追加, ← T005)
    ├─ T012 [P] ReviewPage.tsx autoPlay (← T010)
    └─ T013 [P] SettingsPage.tsx autoPlay toggle (← T005)
Phase 5 (US3)
    ├─ T014 [P] useSpeech.test.ts (rate 追加)
    ├─ T015 useSpeech.ts rate (green, ← T014)
    └─ T016 SettingsPage.tsx rate radio (← T015)
Phase 6 (Polish)
    ├─ T017 [P] coverage check
    └─ T018 quickstart.md
```

### User Story Dependencies

- **US1 (P1)**: Phase 2 完了後に開始可能。他ストーリーへの依存なし
- **US2 (P2)**: Phase 2 完了後に開始可能 かつ US1 の ReviewPage 統合（T010）が必要
- **US3 (P3)**: Phase 2 完了後に開始可能。US1・US2 と独立してフックと設定 UI のみを変更

---

## Parallel Examples

### Phase 2 内の並行実行

```
同時実行可能:
  T002: useSpeech.test.ts (red)
  T003: useSpeechSettings.test.ts (red)
↓
T004: useSpeech.ts (T002 完了後)
T005: useSpeechSettings.ts (T003 完了後、T004 と並行可)
```

### Phase 3 内の並行実行

```
同時実行可能:
  T006: SpeechButton.test.tsx (red)
  T007: FlipCard.test.tsx (red/update)
↓
T008: SpeechButton.tsx (T006 完了後)
T009: FlipCard.tsx (T007 完了後、T008 と並行可)
↓
T010: ReviewPage.tsx (T008・T009 完了後)
```

### Phase 4 内の並行実行

```
同時実行可能（T010 完了後）:
  T011: useSpeechSettings.test.ts (autoPlay テスト追加)
  T012: ReviewPage.tsx autoPlay ロジック
  T013: SettingsPage.tsx autoPlay トグル
```

---

## Implementation Strategy

### MVP First (US1 のみ)

1. Phase 1: types/speech.ts を作成
2. Phase 2: useSpeech・useSpeechSettings を TDD で実装
3. Phase 3: SpeechButton・FlipCard 拡張・ReviewPage 統合
4. **STOP & VALIDATE**: 手動読み上げを復習画面でテスト（SC-001・SC-002 確認）
5. MVP としてデプロイ・デモ可能

### Incremental Delivery

1. Phase 1 + 2 → 基盤 hook 完成
2. Phase 3 (US1) → 手動読み上げ MVP → Deploy/Demo
3. Phase 4 (US2) → 自動読み上げ → Deploy/Demo
4. Phase 5 (US3) → 速度調整 → Deploy/Demo
5. Phase 6 → カバレッジ確認・ドキュメント整備

---

## Notes

- `[P]` タスク = 別ファイル・フェーズ内で依存関係なし
- `[Story]` ラベルでタスクとユーザーストーリーのトレーサビリティを確保
- TDD 必須（Constitution 原則 I）: テストを先に書いて失敗させてから実装する
- `isSupported === false` のパスは必ず unit test でカバーすること（SC-003 対応）
- `FlipCard` の `speechProps` は完全 optional（既存テストを破壊しない）
- 各タスク完了後にコミット（CLAUDE.md: タスクごとにコミット）
