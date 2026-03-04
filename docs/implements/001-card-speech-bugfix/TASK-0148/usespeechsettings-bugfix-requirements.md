# TDD用要件整理: useSpeechSettings hook 修正

**機能名**: useSpeechSettings hook バグ修正（userId 遅延対応 + localStorage 例外処理）
**タスクID**: TASK-0148
**要件名**: 001-card-speech-bugfix
**出力ファイル**: `docs/implements/001-card-speech-bugfix/TASK-0148/usespeechsettings-bugfix-requirements.md`

---

## 1. 機能の概要

- 🔵 `useSpeechSettings` hook は localStorage に保存されたユーザーごとの音声設定（autoPlay, rate）を読み書きするカスタムフック
- 🔵 **問題1（REQ-002）**: `useState` の初期化関数は React の仕様で1回のみ実行される。認証が非同期で完了する場合、hook 初期化時に `userId` が `undefined` のため `loadSettings` が呼ばれず、後から `userId` が確定しても保存済み設定が反映されない
- 🔵 **問題2（REQ-102）**: `updateSettings` 内の `localStorage.setItem` が try/catch で保護されていない。Safari Private Mode や容量超過時に例外が throw されるとアプリがクラッシュする
- 🔵 **想定ユーザー**: LINE ログイン後に復習を行うユーザー（userId は LIFF SDK / OIDC 認証完了後に非同期で確定）
- 🔵 **システム内での位置づけ**: フロントエンド hooks 層。ReviewPage・SettingsPage から利用される設定管理フック
- **参照したEARS要件**: REQ-002, REQ-102, REQ-103(b)
- **参照した設計文書**: architecture.md REQ-002, REQ-102 セクション

## 2. 入力・出力の仕様

### 入力

- 🔵 `userId: string | undefined` — ユーザー識別子。認証完了前は `undefined`、完了後は文字列

### 出力（hook 返却値）

- 🔵 `settings: SpeechSettings` — 現在の読み上げ設定
  - `autoPlay: boolean` — カード表示時に自動読み上げするか（デフォルト: `false`）
  - `rate: SpeechRate (0.5 | 1 | 1.5)` — 読み上げ速度（デフォルト: `1`）
- 🔵 `updateSettings: (patch: Partial<SpeechSettings>) => void` — 設定を部分更新して localStorage に保存

### データフロー（修正後）

```
userId: undefined → string に変化
  ↓
useEffect([userId]) が発火
  ↓
userId が truthy なら loadSettings(userId) を実行
  ↓
setSettings() で state を更新
```

```
updateSettings(patch) 呼び出し
  ↓
setSettings(prev => { ...prev, ...patch })
  ↓
userId が truthy なら try { localStorage.setItem(...) } catch { /* 無視 */ }
  ↓
state は常に更新される（localStorage 書き込み失敗でも）
```

- **参照したEARS要件**: REQ-002, REQ-102
- **参照した設計文書**: architecture.md REQ-002 修正方針、`frontend/src/types/speech.ts` SpeechSettings インターフェース

## 3. 制約条件

- 🔵 **既存テスト維持（REQ-401）**: 既存の `useSpeechSettings.test.ts` 全テストケースがパスし続けること
- 🔵 **インターフェース不変**: `UseSpeechSettingsReturn` の型定義を変更しないこと
- 🔵 **冪等性**: `userId` が最初から有効な場合、`useEffect` による `loadSettings` 再実行は `useState` 初期化と同じ値を返すため副作用なし（冪等）
- 🟡 **localStorage 例外の黙殺**: `setItem` の例外は catch して無視する。ログ出力・ユーザー通知は不要（`loadSettings` 側の既存パターンに倣う）
- 🔵 **React Strict Mode 対応**: `useEffect` は Strict Mode で2回実行されるが、`loadSettings` は冪等なので問題なし
- **参照したEARS要件**: REQ-401, REQ-402
- **参照した設計文書**: architecture.md 技術的制約セクション

## 4. 想定される使用例

### 基本パターン

#### 4.1 userId 遅延確定（REQ-002）

- 🔵 **正常系**: `userId` が `undefined` → `"user-123"` に変化 → localStorage から `{ autoPlay: true, rate: 1.5 }` が読み込まれ `settings` に反映される
- 🔵 **正常系**: `userId` が最初から `"user-123"` → `useState` 初期化時に読み込み済み、`useEffect` は同じ値で上書き（冪等、既存動作維持）
- 🔵 **正常系**: `userId` が `undefined` のまま変化しない → デフォルト設定 `{ autoPlay: false, rate: 1 }` のまま
- 🟡 **エッジケース**: `userId` が `"user-A"` → `"user-B"` に変化（ユーザー切り替え）→ user-B の設定が読み込まれる

#### 4.2 localStorage.setItem 例外処理（REQ-102）

- 🟡 **異常系**: Safari Private Mode で `localStorage.setItem` が `QuotaExceededError` を throw → state は正常に更新され、アプリはクラッシュしない
- 🟡 **異常系**: 容量超過で `localStorage.setItem` が例外を throw → 同上
- 🔵 **正常系**: `localStorage.setItem` が成功する通常ケース → state 更新 + localStorage 保存（既存動作維持）

### テストケース一覧（REQ-103(b)）

#### userId 遅延確定テスト

| # | テストケース | 信頼性 |
|---|---|---|
| 1 | userId が undefined → 有効値に変化したとき、保存済み設定が読み込まれる | 🔵 |
| 2 | userId が最初から有効な場合は初期化時に正しく読み込まれる（既存動作維持） | 🔵 |
| 3 | userId が undefined のまま変化しない場合はデフォルト設定のまま | 🔵 |

#### localStorage 例外テスト

| # | テストケース | 信頼性 |
|---|---|---|
| 4 | localStorage.setItem が throw しても state が更新される | 🟡 |
| 5 | localStorage.setItem が throw してもエラーがスローされない（アプリクラッシュしない） | 🟡 |

- **参照したEARS要件**: REQ-002, REQ-102, REQ-103(b)
- **参照した設計文書**: architecture.md REQ-103 テスト設計 (b) セクション、TASK-0148.md テスト要件

## 5. EARS要件・設計文書との対応関係

- **参照したユーザストーリー**: ストーリー 2「設定の確実な読み込み」
- **参照した機能要件**: REQ-002, REQ-102, REQ-103(b)
- **参照した非機能要件**: REQ-401（既存テスト維持）, REQ-402（後方互換）
- **参照したEdgeケース**: なし（EDGE 要件は定義されていない）
- **参照した受け入れ基準**:
  - REQ-002: userId が undefined → 有効値に変化したとき loadSettings が実行される
  - REQ-102: setItem が throw しても state が更新され、エラーがスローされない
- **参照した設計文書**:
  - **アーキテクチャ**: `docs/design/001-card-speech-bugfix/architecture.md` — REQ-002, REQ-102, REQ-103 セクション
  - **型定義**: `frontend/src/types/speech.ts` — SpeechSettings, SpeechRate
  - **対象実装**: `frontend/src/hooks/useSpeechSettings.ts`
  - **テストファイル**: `frontend/src/hooks/__tests__/useSpeechSettings.test.ts`

---

## 信頼性レベルサマリー

- **総項目数**: 18項目
- 🔵 **青信号**: 14項目 (78%) — EARS要件定義書・設計文書に基づく確実な要件
- 🟡 **黄信号**: 4項目 (22%) — 既存パターンからの妥当な推測（localStorage 例外処理の詳細動作）
- 🔴 **赤信号**: 0項目 (0%)

**品質評価**: ✅ 高品質
