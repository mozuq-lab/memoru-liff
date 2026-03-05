# TASK-0148 タスクノート

## 技術スタック

- React 19 + TypeScript 5.x / Vite 7
- Vitest + React Testing Library (`renderHook`, `act`)
- localStorage モック（`setup.ts` で `vi.fn()` に置き換え済み）

## 開発ルール

- TDD タスク: Red → Green → Refactor
- テストカバレッジ 80% 以上
- タスクごとにコミット

## 関連実装

- `frontend/src/hooks/useSpeechSettings.ts` — 修正対象
- `frontend/src/hooks/__tests__/useSpeechSettings.test.ts` — テスト追加対象
- `frontend/src/types/speech.ts` — SpeechSettings, SpeechRate 型定義

## 設計文書

- 要件定義: `docs/spec/001-card-speech-bugfix/requirements.md`
- 設計: `docs/design/001-card-speech-bugfix/architecture.md`

## 注意事項

- `loadSettings` は既に try/catch で保護されている（getItem + JSON.parse）
- `updateSettings` の `setItem` は未保護（今回の修正対象）
- `useState` の初期化関数は1回のみ実行される React の仕様に注意
- `useEffect([userId])` は初回レンダリング時にも実行される（userId が有効なら冪等）
- localStorage は `setup.ts` で `vi.fn()` モック済み
