# TASK-0082: UIコンポーネント実装 - 開発ノート

**作成日**: 2026-02-28
**タスクID**: TASK-0082
**フェーズ**: Phase 1 - review-reconfirm実装
**予定工数**: 4時間

---

## 関連文書リンク

- **タスク定義**: [TASK-0082.md](../../review-reconfirm/TASK-0082.md)
- **要件定義**: [requirements.md](../../spec/review-reconfirm/requirements.md)
- **アーキテクチャ**: [architecture.md](../../design/review-reconfirm/architecture.md)
- **データフロー**: [dataflow.md](../../design/review-reconfirm/dataflow.md)
- **型定義タスク**: [TASK-0081.md](../../review-reconfirm/TASK-0081.md) ← 前提条件

---

## 1. 技術スタック

### フロントエンド環境

| 項目 | バージョン | 用途 |
|------|----------|------|
| **Node.js** | v18+ | ランタイム |
| **React** | 18.x | UIフレームワーク |
| **TypeScript** | 5.x | 型安全性 |
| **Vite** | 5.x | ビルドツール |
| **Vitest** | 最新 | ユニットテスト |
| **Tailwind CSS** | 3.x | スタイリング |
| **LIFF SDK** | 2.x | LINE統合 |

### 主要依存ライブラリ

```json
{
  "react": "^18.x",
  "react-router-dom": "^6.x",
  "react-dom": "^18.x",
  "zod": "^3.x"
}
```

### 開発環境

- **テストフレームワーク**: Vitest
- **スタイリング**: Tailwind CSS (min-h-[44px], min-w-[44px])
- **型チェック**: TypeScript strict mode
- **リント**: ESLint + Prettier

---

## 2. 開発ルール・コーディング規約

### コンポーネント実装規約

**ファイル構成**:
```typescript
// 1. Import 句（グループ化）
import { /* 外部ライブラリ */ } from 'react';
import type { /* Type imports */ } from '@/types';
import { /* コンポーネント・ユーティリティ */ } from '@/components';

// 2. Props インターフェース
interface ComponentProps {
  // 必須プロパティを上に
  requiredProp: string;
  // オプションプロパティを下に
  optionalProp?: number;
}

// 3. 定数（GRADE_CONFIGS など）
const CONSTANT_NAME = [...] as const;

// 4. コンポーネント定義
export const ComponentName = ({ prop1, prop2 }: ComponentProps) => {
  // ロジック
  return /* JSX */;
};
```

### 型定義ルール

1. **Props インターフェース**: `ComponentNameProps` 命名規約を統一
2. **Union型**: `SessionCardResultType = 'graded' | 'skipped' | 'undone' | 'reconfirmed'`
3. **オプショナル**: `?` を使用、デフォルト値はコンポーネント内で `= false` 等
4. **型アサーション**: `as const` を使用し、Tailwind クラス等の値を固定

### 状態管理ルール

**useState フラットパターン（既存実装を継承）**:
```typescript
const [reconfirmQueue, setReconfirmQueue] = useState<ReconfirmCard[]>([]);
const [isReconfirmMode, setIsReconfirmMode] = useState<boolean>(false);
```

**特性**:
- 既存の ReviewPage と同じパターンで一貫性を保つ
- 状態数が少ないため useReducer は不要
- 非同期性を避けるため、setState のコールバック引数で最新状態を受け取る

### カラースキーム（Tailwind CSS）

| 目的 | 背景 | テキスト | ボーダー |
|------|------|---------|--------|
| 「覚えた」 | bg-green-50 | text-green-700 | border-green-300 |
| 「覚えていない」 | bg-red-50 | text-red-700 | border-red-300 |
| 「再確認」バッジ | bg-blue-100 | text-blue-700 | — |
| 通常mode (grade) | bg-{color}-50 | text-{color}-700 | border-{color}-300 |

### タップ領域ルール

**WCAG2.1 対応**: すべてのインタラクティブ要素
- 最小サイズ: **44px × 44px** (LIFF モバイル推奨)
- 実装: `min-h-[44px]` + `min-w-[44px]`

---

## 3. 関連実装・既存パターン

### 既存コンポーネント構造

```
frontend/src/
├── pages/
│   └── ReviewPage.tsx
│       ├── 状態: cards, currentIndex, isFlipped, isSubmitting, reviewedCount, isComplete
│       ├── 拡張: reconfirmQueue, isReconfirmMode (TASK-0081 済み)
│       └── ハンドラ: handleGrade, handleSkip, handleReconfirmRemembered, handleReconfirmForgotten
│
├── components/
│   ├── GradeButtons.tsx
│   │   ├── Props: onGrade, onSkip?, disabled, isReconfirmMode?, onReconfirmRemembered?, onReconfirmForgotten?
│   │   ├── 6段階評価UI (通常モード)
│   │   └── 2択UI (再確認モード) ← 実装対象
│   │
│   ├── ReconfirmBadge.tsx ← 新規作成
│   │   ├── 機能: 「再確認」バッジ表示
│   │   └── 条件: isReconfirmMode = true のみ表示
│   │
│   ├── ReviewComplete.tsx
│   │   ├── Props: reviewedCount, results, onUndo?, isUndoing?, undoingIndex?
│   │   └── 再確認結果: type='reconfirmed' の表示対応
│   │
│   ├── ReviewResultItem.tsx
│   │   ├── result.type: 'graded' | 'skipped' | 'undone' | 'reconfirmed'
│   │   └── 再確認表示: 元の評価 + 「覚えた✔」サブラベル
│   │
│   ├── FlipCard.tsx (変更なし)
│   └── ReviewProgress.tsx (変更なし)
└── types/
    └── card.ts
        ├── ReconfirmCard (TASK-0081 済み)
        └── SessionCardResultType 拡張 (TASK-0081 済み)
```

### ハンドラ関数の呼び出し順序

**通常モード時のカード処理フロー**:
```
ユーザー入力
  ↓
handleGrade(grade) [GradeButtonsから]
  ↓
quality 0-2? → reconfirmQueue に追加
quality 3-5? → キューに追加しない
  ↓
moveToNext(newReconfirmQueue, currentIndex, cards.length)
  ↓
通常カード残? → currentIndex++
通常カード終? & キュー非空? → isReconfirmMode = true
通常カード終? & キュー空? → isComplete = true
```

**再確認モード時のカード処理フロー**:
```
再確認カード表示 (reconfirmQueue[0])
  ↓
「覚えた」: handleReconfirmRemembered()
  → キュー先頭を除外
  → reviewResults の該当カード type を 'reconfirmed' に更新
  → rest.length > 0? → 次の再確認カード | 空? → セッション完了

「覚えていない」: handleReconfirmForgotten()
  → キュー先頭をキュー末尾に再追加
  → 次のループへ（通常カードがあれば通常カード、なければ再確認キュー）
```

### 既存実装パターン（参考）

**GradeButtons 既存モード**:
- 6つのボタン（grade 0-5）を 3×2 グリッドで配置
- 各ボタンに色分けと説明文を表示
- スキップボタンは全幅（w-full）

**ReviewResultItem 既存表示**:
- グレードバッジ（色付き円形）
- カード表面テキスト（truncate）
- 次回復習日（type='graded' のみ表示）
- Undoボタン（type='graded' のみ）

**Undoハンドラ既存ロジック**:
- API呼び出し → 結果をreviewResults に type='undone' で追記
- regradeCardIndex に設定して再採点画面へ遷移

---

## 4. 設計文書・アーキテクチャ

### 要件定義との対応表

| 要件 | 実装対象 | 信頼性 | 説明 |
|------|---------|--------|------|
| **REQ-002** | GradeButtons | 🔵 | 再確認モードで「覚えた」「覚えていない」2択のみ表示 |
| **REQ-101** | ReconfirmBadge | 🔵 | 再確認モード時に「再確認」バッジ表示 |
| **REQ-102** | GradeButtons | 🔵 | 再確認モードでスキップボタン非表示 |
| **REQ-501** | ReviewResultItem | 🔵 | type='reconfirmed' で元の評価 + 「覚えた✔」表示 |
| **REQ-502** | ReviewPage | 🔵 | 通常カード → 再確認キュー の順序で表示 |

### 状態管理設計図

```typescript
// ReviewPage state (既に実装済み TASK-0081)
const [reconfirmQueue, setReconfirmQueue] = useState<ReconfirmCard[]>([]);
const [isReconfirmMode, setIsReconfirmMode] = useState<boolean>(false);

// ReconfirmCard 型定義 (既に実装済み TASK-0081)
interface ReconfirmCard {
  cardId: string;
  front: string;
  back: string;
  originalGrade: number;  // 0, 1, or 2
}

// SessionCardResult 拡張 (既に実装済み TASK-0081)
interface SessionCardResult {
  cardId: string;
  front: string;
  grade?: number;
  nextReviewDate?: string;
  type: SessionCardResultType;
  reconfirmResult?: 'remembered';  // 再確認の場合のみ設定
}

// SessionCardResultType 拡張 (既に実装済み TASK-0081)
type SessionCardResultType = 'graded' | 'skipped' | 'undone' | 'reconfirmed';
```

### コンポーネント間のデータフロー

```
ReviewPage (状態管理)
  │
  ├─ reconfirmQueue: ReconfirmCard[]
  ├─ isReconfirmMode: boolean
  ├─ reviewResults: SessionCardResult[]
  └─ ハンドラ: handleReconfirmRemembered, handleReconfirmForgotten
      │
      ├→ GradeButtons
      │   ├─ Input: isReconfirmMode, onReconfirmRemembered, onReconfirmForgotten
      │   └─ Output: 2択ボタン (再確認) or 6段階ボタン (通常)
      │
      ├→ ReconfirmBadge
      │   ├─ Input: isReconfirmMode
      │   └─ Output: 「再確認」バッジ (isReconfirmMode=true のみ)
      │
      └→ ReviewComplete
          ├─ Input: reviewResults (type='reconfirmed' 含む)
          └→ ReviewResultItem (各結果）
              ├─ type='graded': グレードバッジ + 次回日付
              └─ type='reconfirmed': 元の評価バッジ + 「覚えた✔」
```

---

## 5. 実装対象ファイル・変更内容

### A. GradeButtons.tsx - 再確認モード対応

**既存状態**: ✅ 実装済み (コードより確認)
**確認内容**:
- Props に `isReconfirmMode?`, `onReconfirmRemembered?`, `onReconfirmForgotten?` 追加
- isReconfirmMode=true で 2択UI に切り替え
- スキップボタンは再確認モードで非表示 ✔
- 「覚えた」: bg-green-50 (成功イメージ) ✔
- 「覚えていない」: bg-red-50 (注意イメージ) ✔

**テスト項目**:
```typescript
describe('GradeButtons - 再確認モード', () => {
  it('isReconfirmMode=true で「覚えた」「覚えていない」ボタンが表示される', () => {});
  it('isReconfirmMode=true で6段階評価ボタンが非表示', () => {});
  it('isReconfirmMode=true でスキップボタンが非表示', () => {});
  it('isReconfirmMode=false で従来通りの6段階評価UI', () => {});
  it('「覚えた」ボタンのクリックで onReconfirmRemembered が呼ばれる', () => {});
  it('「覚えていない」ボタンのクリックで onReconfirmForgotten が呼ばれる', () => {});
  it('disabled=true で両ボタンが disabled 状態', () => {});
});
```

---

### B. ReconfirmBadge.tsx - 新規コンポーネント作成

**概要**: 再確認カード表示時に「再確認」バッジを表示
**ファイル場所**: `/Volumes/external/dev/memoru-liff/frontend/src/components/ReconfirmBadge.tsx`

**実装仕様**:
```typescript
interface ReconfirmBadgeProps {
  // パラメータ不要（内部で UI のみ）
  // または isVisible を使用する場合もある
}

export const ReconfirmBadge = () => {
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-sm font-medium bg-blue-100 text-blue-700">
      再確認
    </span>
  );
};
```

**表示タイミング** (ReviewPage.tsx で制御):
```typescript
{isReconfirmMode && <ReconfirmBadge />}
```

**テスト項目**:
```typescript
describe('ReconfirmBadge', () => {
  it('「再確認」テキストが表示される', () => {});
  it('背景色が blue-100, テキスト色が blue-700', () => {});
  it('バッジサイズが適切（padding, border-radius）', () => {});
});
```

---

### C. ReviewPage.tsx - UI統合

**既存状態**: ✅ 実装済み (コードより確認)
**確認項目**:
- reconfirmQueue, isReconfirmMode state 追加 ✔
- handleReconfirmRemembered, handleReconfirmForgotten ハンドラ実装 ✔
- 再確認モード時の UI ブロック実装 ✔
- GradeButtons へ props 渡し ✔
- ReconfirmBadge の条件付き表示 → **実装予定**

**変更予定**:
```typescript
// 再確認モード表示ブロック内に ReconfirmBadge を追加
if (isReconfirmMode && reconfirmQueue.length > 0) {
  const reconfirmCard = reconfirmQueue[0];
  return (
    <div className="flex flex-col min-h-screen bg-gray-50">
      <main className="flex-1 flex flex-col px-4">
        {/* ReconfirmBadge の表示 */}
        <div className="mt-4 flex justify-center">
          <ReconfirmBadge />
        </div>

        <div className="flex-1 flex items-center justify-center">
          <FlipCard {...} />
        </div>

        <div className="pb-6 min-h-[200px]">
          <GradeButtons
            onGrade={handleGrade}
            disabled={isSubmitting}
            isReconfirmMode={true}
            onReconfirmRemembered={handleReconfirmRemembered}
            onReconfirmForgotten={handleReconfirmForgotten}
          />
        </div>
      </main>
    </div>
  );
}
```

**テスト項目**:
```typescript
describe('ReviewPage - 再確認UI統合', () => {
  it('isReconfirmMode=true で ReconfirmBadge が表示される', () => {});
  it('再確認モードで GradeButtons の isReconfirmMode が true', () => {});
  it('再確認カードの front/back が正しく表示される', () => {});
  it('「覚えた」クリック後に次の再確認カード or セッション完了', () => {});
  it('「覚えていない」クリック後にキュー末尾に再追加される', () => {});
});
```

---

### D. ReviewComplete.tsx - 再確認結果対応

**既存状態**: ✅ 実装済み (コードより確認)
**確認内容**:
- results フィルタで type='reconfirmed' も計数対象 ✔
- ReviewResultItem への props 渡し ✔

**テスト項目**:
```typescript
describe('ReviewComplete', () => {
  it('type="reconfirmed" のカードも gradedCount に含まれる', () => {});
  it('results が空でも reviewedCount で表示', () => {});
  it('各 result が ReviewResultItem にマップされる', () => {});
});
```

---

### E. ReviewResultItem.tsx - 再確認結果表示

**既存状態**: ✅ 部分実装 (コードより確認)
**確認内容**:
- type='reconfirmed' の条件分岐 → **実装必要**
- Undoボタンは type='reconfirmed' でも表示 ✔

**実装予定**:
```typescript
// 再確認結果の表示ロジック（追加）
if (result.type === 'reconfirmed' && result.grade !== undefined) {
  const gradeConfig = GRADE_DISPLAY_CONFIGS[result.grade];
  return (
    <div className="flex items-center gap-3 py-3 px-4 bg-white rounded-lg border border-gray-200">
      {/* グレードバッジ（元の評価） */}
      <div className="shrink-0 w-10">
        <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold ${gradeConfig.bgClass} ${gradeConfig.textClass}`}>
          {gradeConfig.label}
        </span>
      </div>

      {/* カード表面 + サブラベル */}
      <div className="flex-1 min-w-0">
        <p className="text-sm text-gray-800 truncate">{result.front}</p>
        <p className="text-xs text-green-600 mt-0.5">覚えた✔</p>
      </div>

      {/* Undoボタン */}
      <div className="shrink-0">
        {onUndo && (
          <button
            type="button"
            onClick={() => onUndo(index)}
            disabled={isUndoing}
            aria-label={`${result.front} の採点を取り消す`}
            className={`min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg text-sm text-gray-500 hover:bg-gray-100 active:bg-gray-200 transition-colors ${isUndoing ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {isUndoing ? (
              <svg className="animate-spin h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              <span className="text-xs">取消</span>
            )}
          </button>
        )}
      </div>
    </div>
  );
}
```

**テスト項目**:
```typescript
describe('ReviewResultItem - 再確認表示', () => {
  it('type="reconfirmed" で元の評価バッジが表示される', () => {});
  it('type="reconfirmed" で「覚えた✔」サブラベルが表示される', () => {});
  it('type="graded" (quality 3-5) で従来通りの表示', () => {});
  it('Undoボタンは type="reconfirmed" でも表示される', () => {});
  it('type="skipped" では Undoボタン非表示', () => {});
});
```

---

## 6. テスト実装ガイドライン

### Vitest 環境セットアップ

```typescript
// 例: GradeButtons.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { GradeButtons } from './GradeButtons';

describe('GradeButtons', () => {
  describe('再確認モード', () => {
    it('isReconfirmMode=true で「覚えた」「覚えていない」ボタンが表示される', () => {
      const onReconfirmRemembered = vi.fn();
      const onReconfirmForgotten = vi.fn();

      render(
        <GradeButtons
          onGrade={vi.fn()}
          disabled={false}
          isReconfirmMode={true}
          onReconfirmRemembered={onReconfirmRemembered}
          onReconfirmForgotten={onReconfirmForgotten}
        />
      );

      expect(screen.getByRole('button', { name: '覚えた' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '覚えていない' })).toBeInTheDocument();
    });

    it('isReconfirmMode=true で6段階評価ボタンが非表示', () => {
      render(
        <GradeButtons
          onGrade={vi.fn()}
          disabled={false}
          isReconfirmMode={true}
          onReconfirmRemembered={vi.fn()}
          onReconfirmForgotten={vi.fn()}
        />
      );

      expect(screen.queryByRole('button', { name: /0 -/ })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /5 -/ })).not.toBeInTheDocument();
    });

    it('disabled=true で両ボタンが disabled', async () => {
      const user = userEvent.setup();
      const onReconfirmRemembered = vi.fn();

      render(
        <GradeButtons
          onGrade={vi.fn()}
          disabled={true}
          isReconfirmMode={true}
          onReconfirmRemembered={onReconfirmRemembered}
          onReconfirmForgotten={vi.fn()}
        />
      );

      const button = screen.getByRole('button', { name: '覚えた' });
      expect(button).toBeDisabled();
      await user.click(button);
      expect(onReconfirmRemembered).not.toHaveBeenCalled();
    });

    it('「覚えた」ボタンのクリックで onReconfirmRemembered が呼ばれる', async () => {
      const user = userEvent.setup();
      const onReconfirmRemembered = vi.fn();

      render(
        <GradeButtons
          onGrade={vi.fn()}
          disabled={false}
          isReconfirmMode={true}
          onReconfirmRemembered={onReconfirmRemembered}
          onReconfirmForgotten={vi.fn()}
        />
      );

      const button = screen.getByRole('button', { name: '覚えた' });
      await user.click(button);
      expect(onReconfirmRemembered).toHaveBeenCalledOnce();
    });
  });

  describe('通常モード', () => {
    it('isReconfirmMode=false or 未指定で6段階評価ボタンが表示される', () => {
      render(
        <GradeButtons
          onGrade={vi.fn()}
          onSkip={vi.fn()}
          disabled={false}
        />
      );

      expect(screen.getByRole('button', { name: /0 -/ })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /5 -/ })).toBeInTheDocument();
    });

    it('onSkip が渡されるとスキップボタンが表示される', () => {
      render(
        <GradeButtons
          onGrade={vi.fn()}
          onSkip={vi.fn()}
          disabled={false}
        />
      );

      expect(screen.getByRole('button', { name: 'スキップ' })).toBeInTheDocument();
    });
  });
});
```

### テストヘルパー・ユーティリティ

```typescript
// tests/utils/test-helpers.ts (参考)
import { ReconfirmCard, SessionCardResult } from '@/types';

export const createReconfirmCard = (overrides?: Partial<ReconfirmCard>): ReconfirmCard => ({
  cardId: 'card-1',
  front: 'テスト問題',
  back: 'テスト回答',
  originalGrade: 0,
  ...overrides,
});

export const createSessionCardResult = (overrides?: Partial<SessionCardResult>): SessionCardResult => ({
  cardId: 'card-1',
  front: 'テスト問題',
  type: 'graded',
  ...overrides,
});
```

### テスト実行コマンド

```bash
# 全テスト実行
npm run test

# ファイル指定実行
npm run test -- GradeButtons.test.tsx

# Watch モード
npm run test -- --watch

# Coverage 確認
npm run test -- --coverage
```

---

## 7. 重要な注意事項・制約

### セキュリティ・パフォーマンス

1. **API呼び出しなし** 🔵
   - 再確認ループはフロントエンド state のみで管理
   - `handleReconfirmRemembered`, `handleReconfirmForgotten` は API を呼ばない
   - SM-2 再計算も行わない（最初の quality 0-2 評価時に設定済み）

2. **メモリ効率**
   - reconfirmQueue は配列の slice/push のみで操作
   - 大量再確認時もパフォーマンス劣化なし（配列操作は O(n)）

3. **状態同期**
   - setState の非同期性を考慮
   - `moveToNext(newReconfirmQueue, currentIndex, cards.length)` で最新状態を引数で受け取る

### ユーザビリティ

1. **44px タップ領域**
   - すべてのボタンに `min-h-[44px]` + `min-w-[44px]` を適用
   - WCAG2.1 Level AAA 対応

2. **カラーコントラスト**
   - green-50 背景 + green-700 テキスト: 十分なコントラスト比
   - red-50 背景 + red-700 テキスト: 十分なコントラスト比

3. **フィードバック**
   - hover/active 状態で視覚的フィードバック
   - disabled 状態で opacity-50 で対応不可を表示

### 既存実装との互換性

1. **通常カードの表示は変更なし** ✅
   - isReconfirmMode=false (デフォルト) で従来通り
   - GradeButtons は 6 段階評価 + スキップボタン表示

2. **Undo 機能との連携** ✅
   - 再確認カードも Undo 可能（type='reconfirmed'）
   - handleUndo で reconfirmQueue からも除去

3. **プログレスバー表示** 🟡
   - 通常カードのみを分母とする（既存実装で実装済み）
   - 再確認カードは含めない

### エッジケース

| ケース | 動作 | 信頼性 |
|--------|------|--------|
| 全カードがquality 0-2 | セッション全体が再確認ループ | 🟡 |
| 1枚のカードを無限ループ | 「覚えていない」を繰り返すと無限ループ | 🔵 |
| アプリが再確認中に閉じる | セッションリセット、再確認キュー消失（翌日に再表示） | 🔵 |
| Undo後に再評価で quality 0-2 | 再び再確認キューに追加される | 🔵 |

---

## 8. デバッグ・トラブルシューティング

### よくある問題

**Q1: 「覚えた」ボタンクリック後も画面が変わらない**
- A: `handleReconfirmRemembered` で `rest.length === 0` の判定を確認
- セッション完了時に `setIsComplete(true)` が呼ばれているか確認

**Q2: reconfirmQueue に重複カードが入る**
- A: `handleGrade` で `grade < 3` の判定が正しいか確認
- 再採点時も同じ判定をしているか確認

**Q3: 「再確認」バッジが表示されない**
- A: `isReconfirmMode === true` かつ `reconfirmQueue.length > 0` か確認
- ReconfirmBadge のインポート漏れをチェック

**Q4: スキップボタンが再確認モードで表示される**
- A: GradeButtons の `if (isReconfirmMode)` 分岐が最初に来ているか確認
- onSkip が undefined でも JSX 条件分岐で非表示になっているか確認

### ローカルテスト手順

```bash
# 1. フロントエンド起動
cd frontend && npm run dev

# 2. ブラウザで http://localhost:3000 アクセス
# 3. Keycloak ログイン（test-user / test-password-123）
# 4. 復習開始 → quality 0-2 で評価
# 5. 再確認画面確認
#    - 「再確認」バッジ表示 ✓
#    - 「覚えた」「覚えていない」2ボタン表示 ✓
#    - スキップボタン非表示 ✓
```

---

## 9. 実装チェックリスト

### A. GradeButtons.tsx

- [ ] Props に `isReconfirmMode?`, `onReconfirmRemembered?`, `onReconfirmForgotten?` 追加
- [ ] isReconfirmMode=true で 2択UI に切り替え
- [ ] 「覚えた」ボタン: bg-green-50, text-green-700, border-green-300
- [ ] 「覚えていない」ボタン: bg-red-50, text-red-700, border-red-300
- [ ] 両ボタンに min-h-[44px] 確保
- [ ] スキップボタンは再確認モードで非表示
- [ ] disabled 状態で両ボタン disabled
- [ ] テスト実装（6項目）

### B. ReconfirmBadge.tsx

- [ ] ファイル新規作成
- [ ] 「再確認」テキスト表示
- [ ] bg-blue-100, text-blue-700 スタイリング
- [ ] padding, border-radius 設定
- [ ] コンポーネント export

### C. ReviewPage.tsx

- [ ] ReconfirmBadge import
- [ ] 再確認モード表示ブロック内に ReconfirmBadge 追加
- [ ] GradeButtons に isReconfirmMode=true, onReconfirmRemembered, onReconfirmForgotten 渡す
- [ ] テスト実装（5項目）

### D. ReviewComplete.tsx

- [ ] type='reconfirmed' を gradedCount に含める（既に実装確認）
- [ ] テスト実装（3項目）

### E. ReviewResultItem.tsx

- [ ] type='reconfirmed' の条件分岐追加
- [ ] 元のグレードバッジ表示
- [ ] 「覚えた✔」サブラベル表示（text-green-600）
- [ ] Undoボタンは type='reconfirmed' でも表示
- [ ] テスト実装（5項目）

### F. 全体テスト

- [ ] 全ユニットテスト実行: `npm run test`
- [ ] TypeScript 型チェック: `npm run type-check`
- [ ] E2E確認: ローカル環境で実際に動作確認
- [ ] アクセシビリティ: 44px タップ領域確認、カラーコントラスト確認
- [ ] テストカバレッジ目標: 80% 以上

---

## 10. コミット・ドキュメント更新計画

### タスク完了時の更新

**ファイル**:
1. `/Volumes/external/dev/memoru-liff/docs/tasks/review-reconfirm/TASK-0082.md`
   - 完了条件の `[ ]` を `[x]` に更新

2. `/Volumes/external/dev/memoru-liff/docs/tasks/review-reconfirm/overview.md`
   - TASK-0082 の状態列を `[x]` に更新

**コミットメッセージ例**:
```
TASK-0082: UIコンポーネント実装

- GradeButtons に再確認モード（「覚えた」「覚えていない」2択）を追加
- ReconfirmBadge 新規コンポーネント作成
- ReviewPage に ReconfirmBadge 統合
- ReviewResultItem に再確認結果表示（元の評価 + 「覚えた✔」）
- 全テスト実装・通過（6項目）

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

## 参考資料

| 項目 | リンク | 備考 |
|------|--------|------|
| 要件定義 | [requirements.md](../../spec/review-reconfirm/requirements.md) | 機能要件・非機能要件 |
| アーキテクチャ | [architecture.md](../../design/review-reconfirm/architecture.md) | 状態管理・コンポーネント設計 |
| データフロー | [dataflow.md](../../design/review-reconfirm/dataflow.md) | 処理フロー図 |
| 受け入れ基準 | [acceptance-criteria.md](../../spec/review-reconfirm/acceptance-criteria.md) | テストケース |
| 既存設計 | [review-flow/architecture.md](../review-flow/architecture.md) | ReviewPage パターン参考 |
| 型定義 | `/frontend/src/types/card.ts` | ReconfirmCard, SessionCardResultType |

---

**作成者**: Claude Code
**最終更新**: 2026-02-28
