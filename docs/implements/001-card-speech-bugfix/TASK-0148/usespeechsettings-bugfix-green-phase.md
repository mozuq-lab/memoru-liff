# Green フェーズ記録: useSpeechSettings hook バグ修正

**機能名**: useSpeechSettings hook バグ修正（userId 遅延対応 + localStorage 例外処理）
**タスクID**: TASK-0148
**要件名**: 001-card-speech-bugfix
**実装日時**: 2026-03-05

---

## 実装方針

### 変更点の概要

1. **`useEffect` / `useRef` インポート追加**: `useState` のみだったインポートに `useEffect` と `useRef` を追加
2. **useEffect による userId 変化時の再読み込み (REQ-002)**:
   - `useState` 初期化関数は React の仕様で1回のみ実行されるため、userId が非同期で確定する場合に対応できない
   - `useEffect([userId])` を追加し、userId 変化時に `loadSettings` を再実行
   - 初回マウント時は `useState` で既に読み込み済みのため `useRef` でスキップ
3. **localStorage.setItem の try/catch 保護 (REQ-102)**:
   - Safari Private Mode や容量超過時に `setItem` が throw しても state 更新を保証
   - `loadSettings` 側の既存パターン（try/catch）に倣って実装

### 実装上の判断

- **初回スキップの必要性**: `useEffect` は初回マウント時も実行される。`mockReturnValueOnce` を使う既存テストでは、初回実行をスキップしないと2回目の `getItem` が `undefined` を返し、デフォルト値で上書きされてしまう
- **`useRef` 使用**: Refactor フェーズで別のアプローチ（prevUserIdRef による比較）に変更する余地がある。Green フェーズでは最もシンプルな実装を選択
- **例外の黙殺**: `loadSettings` の既存パターンに合わせてコメントのみ。ログ出力・ユーザー通知は要件外

---

## 実装コード全文

```typescript
/**
 * 【機能概要】: localStorage に保存された SpeechSettings を読み書きするフック
 * 【テスト対応】: useSpeechSettings.test.ts
 */
import { useState, useEffect, useRef } from "react";
import type { SpeechRate, SpeechSettings } from "@/types/speech";

const DEFAULT_SETTINGS: SpeechSettings = { autoPlay: false, rate: 1 };

const VALID_RATES: SpeechRate[] = [0.5, 1, 1.5];

const isValidRate = (value: unknown): value is SpeechRate =>
  VALID_RATES.includes(value as SpeechRate);

function loadSettings(userId: string): SpeechSettings {
  try {
    const raw = localStorage.getItem(`speech-settings:${userId}`);
    if (!raw) return { ...DEFAULT_SETTINGS };
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const rate = isValidRate(parsed.rate) ? parsed.rate : DEFAULT_SETTINGS.rate;
    const autoPlay =
      typeof parsed.autoPlay === "boolean"
        ? parsed.autoPlay
        : DEFAULT_SETTINGS.autoPlay;
    return { autoPlay, rate };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

interface UseSpeechSettingsReturn {
  /** 現在の読み上げ設定 */
  settings: SpeechSettings;
  /** 設定を更新して localStorage に保存する（partial パッチ） */
  updateSettings: (patch: Partial<SpeechSettings>) => void;
}

export const useSpeechSettings = (
  userId: string | undefined,
): UseSpeechSettingsReturn => {
  const [settings, setSettings] = useState<SpeechSettings>(() => {
    if (!userId) return { ...DEFAULT_SETTINGS };
    return loadSettings(userId);
  });

  // 【機能概要】: userId が変化したとき localStorage から設定を再読み込みする
  // 【実装方針】: useState 初期化関数は1回のみ実行されるため、userId の遅延確定に対応できない
  //               useEffect([userId]) で userId 変化を検知し loadSettings を再実行する
  //               初回マウント時は useState 初期化で既に読み込み済みのためスキップする
  // 【テスト対応】: TC-001 userId 遅延確定時の設定再読み込み (REQ-002)
  // 🔵 REQ-002 受け入れ基準 + architecture.md 設計方針に基づく
  const isFirstRender = useRef(true);
  useEffect(() => {
    // 【初回スキップ】: useState 初期化で既に loadSettings を実行済みのため、初回マウントはスキップ
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    if (userId) {
      setSettings(loadSettings(userId));
    }
  }, [userId]);

  const updateSettings = (patch: Partial<SpeechSettings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      // 【機能概要】: localStorage に設定を保存する。Safari Private Mode や容量超過時の例外を抑制する
      // 【実装方針】: setItem が throw しても state の更新は保証する（try/catch でエラーを黙殺）
      // 【テスト対応】: TC-004 setItem 例外時の state 更新保証、TC-005 エラー非伝播 (REQ-102)
      // 🟡 REQ-102 受け入れ基準 + loadSettings 側の既存 try/catch パターンからの推測
      if (userId) {
        try {
          localStorage.setItem(`speech-settings:${userId}`, JSON.stringify(next));
        } catch {
          // Safari Private Mode / quota exceeded — state only update
        }
      }
      return next;
    });
  };

  return { settings, updateSettings };
};
```

---

## テスト実行結果

```
RUN  v4.0.18

 ✓ src/hooks/__tests__/useSpeechSettings.test.ts (21 tests) 21ms

 Test Files  1 passed (1)
       Tests  21 passed (21)
    Start at  01:25:25
    Duration  742ms (transform 40ms, setup 72ms, import 69ms, tests 21ms, environment 507ms)
```

- 既存テスト: 18件 全て通過
- 新規テスト (Red フェーズで追加): 3件 全て通過
- 合計: 21件 全て通過

---

## 課題・改善点（Refactor フェーズで対応）

1. **`isFirstRender` ref の位置**: フック本体の中間にあるため、変数宣言の順序が自然ではない。Refactor フェーズで整理を検討
2. **`useRef` の代替アプローチ**: `prevUserIdRef` で前回の userId を記録し、変化したときのみ再読み込みする方式も検討できる。ただし複雑になるため現状維持でも可
3. **Strict Mode の考慮**: React Strict Mode では `useEffect` が2回実行される。`isFirstRender.current = false` が1回目の実行後にセットされるため、2回目も実行されてしまう可能性がある。本番は Strict Mode 非依存のため問題は軽微

---

## 品質判定

```
✅ 高品質:
- テスト結果: 21件全て成功
- 実装品質: シンプルかつ動作する
- リファクタ箇所: useRef の位置・Strict Mode 対応
- 機能的問題: なし
- コンパイルエラー: なし
- ファイルサイズ: 84行（800行以下）
- モック使用: 実装コードにモック・スタブなし
```
