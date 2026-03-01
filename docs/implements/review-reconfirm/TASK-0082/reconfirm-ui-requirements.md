# TASK-0082: UIコンポーネント実装 - TDD用要件定義書

**タスクID**: TASK-0082
**機能名**: reconfirm loop UI components
**要件名**: review-reconfirm
**作成日**: 2026-02-28

---

## 1. 機能の概要（EARS要件定義書・設計文書ベース）

### 1.1 何をする機能か 🔵

**信頼性**: 🔵 *TASK-0082.md タスク概要、要件定義書 REQ-002, REQ-101, REQ-102, REQ-501 より*

復習セッション中の再確認ループに関するUIコンポーネント群を実装する。具体的には以下の5つのUI要素を対象とする:

1. **GradeButtons 再確認モードUI**: 再確認カード表示時に「覚えた」「覚えていない」の2択ボタンを表示し、6段階評価ボタンとスキップボタンを非表示にする
2. **ReconfirmBadge 新規コンポーネント**: 再確認モード時に「再確認」テキストのバッジを表示する
3. **ReviewPage UI統合**: 再確認モード表示ブロックに ReconfirmBadge を統合する
4. **ReviewResultItem 拡張**: type='reconfirmed' のカードに元の評価バッジと「覚えた✔」サブラベルを表示する
5. **ReviewComplete 拡張**: reconfirmed カードを graded カウントに含めた正しい復習枚数表示を確認する

### 1.2 どのような問題を解決するか 🔵

**信頼性**: 🔵 *要件定義書 背景セクション・ユーザストーリーより*

- 再確認モード中にユーザーが通常評価と区別できるよう、視覚的に明確なUI（2択ボタン、バッジ）を提供する
- 復習完了画面で再確認されたカードの結果を適切に表示し、学習状況を正確に把握できるようにする

### 1.3 想定されるユーザー 🔵

**信頼性**: 🔵 *ユーザストーリーより*

- LINE LIFF アプリのモバイルユーザー（暗記カード学習者）

### 1.4 システム内での位置づけ 🔵

**信頼性**: 🔵 *architecture.md コンポーネント構成より*

フロントエンドのみの変更で完結する。TASK-0081 で実装済みのコアロジック（reconfirmQueue, isReconfirmMode state、handleReconfirmRemembered/handleReconfirmForgotten ハンドラ、GradeButtons の props 定義と基本分岐、Undo 連携）の上に、UIの仕上げと未実装部分の追加を行う。

**前提（TASK-0081 完了済み）**:
- `frontend/src/types/card.ts`: ReconfirmCard 型、SessionCardResultType 'reconfirmed' 拡張済み
- `frontend/src/pages/ReviewPage.tsx`: reconfirmQueue/isReconfirmMode state、moveToNext 拡張、handleReconfirmRemembered/handleReconfirmForgotten 実装済み、再確認モード表示ブロック実装済み（ただし ReconfirmBadge 未統合）
- `frontend/src/components/GradeButtons.tsx`: isReconfirmMode/onReconfirmRemembered/onReconfirmForgotten props と基本的な2択ボタン UI 実装済み
- `frontend/src/components/ReviewComplete.tsx`: gradedCount に 'reconfirmed' 含める実装済み
- `frontend/src/components/ReviewResultItem.tsx`: Undo ボタンの type='reconfirmed' 対応済み（ただし再確認カードのバッジ・サブラベル表示は未実装）

**参照した EARS 要件**: REQ-002, REQ-005, REQ-101, REQ-102, REQ-501
**参照した設計文書**: architecture.md コンポーネント構成、dataflow.md 全体フロー概要

---

## 2. 入力・出力の仕様（EARS機能要件・TypeScript型定義ベース）

### 2.1 GradeButtons コンポーネント 🔵

**信頼性**: 🔵 *既存実装 GradeButtons.tsx の Props インターフェース、要件定義書 REQ-002, REQ-102 より*

**入力（Props）**:

```typescript
interface GradeButtonsProps {
  onGrade: (grade: number) => void;       // 通常モードで使用（必須）
  onSkip?: () => void;                    // スキップハンドラ（再確認モードでは渡さない）
  disabled: boolean;                      // 送信中のボタン無効化
  isReconfirmMode?: boolean;              // 再確認モードフラグ（デフォルト: false/undefined）
  onReconfirmRemembered?: () => void;     // 「覚えた」ハンドラ
  onReconfirmForgotten?: () => void;      // 「覚えていない」ハンドラ
}
```

**出力（レンダリング結果）**:

| 条件 | 表示内容 |
|------|---------|
| `isReconfirmMode = true` | 「覚えた」ボタン（緑系）+ 「覚えていない」ボタン（赤系）の2択。6段階ボタン非表示。スキップボタン非表示。 |
| `isReconfirmMode = false` または未指定 | 6段階評価ボタン（0-5）+ スキップボタン（onSkip が渡された場合のみ） |

**再確認モード時のボタン仕様**:

| ボタン | テキスト | 背景色 | テキスト色 | ボーダー | タップ領域 | クリック時 |
|--------|---------|--------|-----------|---------|-----------|-----------|
| 覚えた | `覚えた` | bg-green-50 | text-green-700 | border-green-300 | min-h-[44px] | onReconfirmRemembered() |
| 覚えていない | `覚えていない` | bg-red-50 | text-red-700 | border-red-300 | min-h-[44px] | onReconfirmForgotten() |

**disabled 状態**: 両ボタンに `opacity-50 cursor-not-allowed` が適用され、クリックイベントが発火しない

### 2.2 ReconfirmBadge コンポーネント（新規） 🔵

**信頼性**: 🔵 *要件定義書 REQ-101、note.md セクション3B より*

**入力（Props）**: なし（パラメータ不要のプレゼンテーションコンポーネント）

**出力（レンダリング結果）**:

```typescript
// 「再確認」テキストを含むインラインバッジ
<span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-sm font-medium bg-blue-100 text-blue-700">
  再確認
</span>
```

| 項目 | 値 |
|------|-----|
| テキスト | `再確認` |
| 背景色 | bg-blue-100 |
| テキスト色 | text-blue-700 |
| 形状 | rounded-full（ピル型） |
| サイズ | text-sm, px-2.5, py-0.5 |

**表示タイミング**: ReviewPage 内で `isReconfirmMode === true` の場合のみ表示

### 2.3 ReviewPage UI統合 🔵

**信頼性**: 🔵 *architecture.md コンポーネント構成、dataflow.md 再確認フロー・カード進行判定フローより*

**入力**: ReviewPage の既存 state（isReconfirmMode, reconfirmQueue）

**出力（再確認モード表示ブロック）**:
- ReconfirmBadge を再確認カード表示領域の上部に表示
- FlipCard に reconfirmQueue[0] の front/back を渡す
- GradeButtons に isReconfirmMode=true と対応ハンドラを渡す

**現状（TASK-0081 実装済み）**: 再確認モード表示ブロックは実装済みだが、ReconfirmBadge が未統合

**追加実装**: ReconfirmBadge の import と条件付き表示の統合

### 2.4 ReviewResultItem 拡張 🔵

**信頼性**: 🔵 *要件定義書 REQ-501、受け入れ基準 TC-501-01, TC-501-02 より*

**入力（Props）**:

```typescript
interface ReviewResultItemProps {
  result: SessionCardResult;   // type='reconfirmed' を含む
  index: number;
  onUndo?: (index: number) => void;
  isUndoing?: boolean;
}
```

**出力（type='reconfirmed' の場合）**:

| UI要素 | 表示内容 | スタイル |
|--------|---------|---------|
| グレードバッジ | 元の評価値（例: `0`, `1`, `2`）| GRADE_DISPLAY_CONFIGS[grade] の色（円形バッジ） |
| カード表面テキスト | result.front（truncate） | text-sm text-gray-800 |
| サブラベル | `覚えた✔` | text-xs text-green-600 |
| Undo ボタン | `取消` | min-h-[44px] min-w-[44px]（既存実装済み） |

**出力（type='graded', grade 3-5 の場合）**: 従来通り変更なし

| UI要素 | 表示内容 |
|--------|---------|
| グレードバッジ | grade値 + GRADE_DISPLAY_CONFIGS 色 |
| カード表面テキスト | result.front |
| サブラベル | `次回: {nextReviewDate}` |
| Undo ボタン | `取消` |

**既存の type 別表示（変更なし）**:
- `type='skipped'`: グレーバッジ（`—`）+ 「スキップ」サブラベル、Undo ボタンなし
- `type='undone'`: 青バッジ（`↩`）+ 「取り消し済み」サブラベル、Undo ボタンなし

### 2.5 ReviewComplete 拡張 🔵

**信頼性**: 🔵 *既存実装 ReviewComplete.tsx より確認*

**入力（Props）**: 既存の ReviewCompleteProps（変更なし）

**出力**: `gradedCount` 計算に `type === 'reconfirmed'` が含まれていることを検証

```typescript
const gradedCount = results.filter((r) => r.type === 'graded' || r.type === 'reconfirmed').length;
```

**現状**: TASK-0081 で既に上記の gradedCount 計算は実装済み。テストで動作を検証する。

**参照した EARS 要件**: REQ-002, REQ-101, REQ-102, REQ-501
**参照した設計文書**: architecture.md 状態管理設計、card.ts インターフェース

---

## 3. 制約条件（EARS非機能要件・アーキテクチャ設計ベース）

### 3.1 パフォーマンス要件 🔵

**信頼性**: 🔵 *要件定義書 NFR-001, NFR-002 より*

- 再確認モードのUI切り替えは即座に行われること（API呼び出しなし）
- ReconfirmBadge はシンプルな DOM 要素のみで構成し、追加の計算やレンダリングコストを発生させないこと
- GradeButtons の再確認モード分岐は早期リターンパターン（既存実装済み）で実装し、不要な DOM 生成を避けること

### 3.2 ユーザビリティ要件 🟡

**信頼性**: 🟡 *要件定義書 NFR-201, NFR-202 から妥当な推測*

- **44px タップ領域**: すべてのインタラクティブ要素（「覚えた」「覚えていない」ボタン、Undo ボタン）は `min-h-[44px]` かつ `min-w-[44px]`（WCAG 2.1 Level AAA、LIFF モバイル推奨）
- **カラーコントラスト**:
  - green-50 背景 + green-700 テキスト: 十分なコントラスト比
  - red-50 背景 + red-700 テキスト: 十分なコントラスト比
  - blue-100 背景 + blue-700 テキスト: 十分なコントラスト比
- **視覚的フィードバック**: hover/active 状態で色変化、disabled 状態で opacity-50

### 3.3 互換性要件 🔵

**信頼性**: 🔵 *要件定義書 REQ-103、TASK-0082.md 完了条件より*

- **通常モード非破壊**: isReconfirmMode=false（デフォルト）のとき、GradeButtons・ReviewPage・ReviewResultItem・ReviewComplete すべてで従来通りの表示・動作であること
- **既存テスト維持**: GradeButtons 既存テスト（8件）、ReviewComplete 既存テスト（5件）が引き続きパスすること

### 3.4 アーキテクチャ制約 🔵

**信頼性**: 🔵 *要件定義書 REQ-401, REQ-403、architecture.md より*

- バックエンド API の変更を行わない（フロントエンドのみ）
- SM-2 アルゴリズムの計算ロジックを変更しない
- 既存の useState フラットパターンを維持する（useReducer への移行不要）
- 新規コンポーネント（ReconfirmBadge）は `frontend/src/components/` ディレクトリに配置する

### 3.5 テスト要件 🔵

**信頼性**: 🔵 *CLAUDE.md テストカバレッジ目標より*

- Vitest + React Testing Library でユニットテストを実装する
- テストカバレッジ 80% 以上を維持する
- 既存テストを破壊しない

**参照した EARS 要件**: NFR-001, NFR-002, NFR-201, NFR-202, REQ-103, REQ-401, REQ-403
**参照した設計文書**: architecture.md 技術的制約、非機能要件の実現方法

---

## 4. 想定される使用例（EARSEdgeケース・データフローベース）

### 4.1 基本的な使用パターン

#### パターン1: 再確認モードでの「覚えた」選択 🔵

**信頼性**: 🔵 *要件定義書 REQ-002, REQ-003, REQ-101・dataflow.md 再確認フロー「覚えた」より*

**前提条件**: 通常カードを全て評価済み、reconfirmQueue に1枚以上のカードがある

**フロー**:
1. ReviewPage が再確認モード表示ブロックをレンダリング
2. 画面上部に「再確認」バッジ（ReconfirmBadge）が表示される
3. FlipCard に reconfirmQueue[0] のカード情報が表示される
4. GradeButtons が再確認モード（「覚えた」「覚えていない」2択）で表示される
5. 6段階評価ボタンとスキップボタンは非表示
6. ユーザーが「覚えた」をタップ
7. カードが reconfirmQueue から除外される
8. reviewResults の該当カードが type='reconfirmed' に更新される

#### パターン2: 再確認モードでの「覚えていない」選択 🔵

**信頼性**: 🔵 *要件定義書 REQ-004・dataflow.md 再確認フロー「覚えていない」より*

**前提条件**: 再確認モード中

**フロー**:
1. ユーザーが「覚えていない」をタップ
2. 現在のカードが reconfirmQueue の末尾に再追加される
3. 次の再確認カード（またはキュー先頭に回ってきた同じカード）が表示される

#### パターン3: 復習完了画面での再確認結果表示 🔵

**信頼性**: 🔵 *要件定義書 REQ-501・dataflow.md 完了画面表示フローより*

**前提条件**: セッション完了後

**フロー**:
1. ReviewComplete が reviewResults をループ
2. type='reconfirmed' のカード: ReviewResultItem が元のグレードバッジ（例: `2` の amber 色バッジ）と「覚えた✔」サブラベルを表示
3. type='graded' のカード（grade 3-5）: 従来通りのグレードバッジと次回復習日を表示
4. type='reconfirmed' のカードにも Undo ボタンが表示される

#### パターン4: 通常モードでの従来動作（非破壊確認） 🟡

**信頼性**: 🟡 *REQ-103 の既存動作維持確認、妥当な推測*

**前提条件**: すべてのカードを quality 3-5 で評価（再確認キューが空）

**フロー**:
1. GradeButtons は6段階評価 + スキップの従来表示
2. ReconfirmBadge は表示されない
3. ReviewResultItem は従来のグレードバッジ + 次回復習日で表示
4. ReviewComplete の枚数表示は従来通り

### 4.2 エッジケース

#### EDGE-001: disabled 状態での再確認ボタン 🟡

**信頼性**: 🟡 *既存 GradeButtons disabled パターンから妥当な推測*

**条件**: isReconfirmMode=true かつ disabled=true
**期待動作**: 「覚えた」「覚えていない」両ボタンが disabled になり、クリックしてもハンドラが呼ばれない

#### EDGE-002: isReconfirmMode=true だが onReconfirmRemembered/onReconfirmForgotten が未設定 🟡

**信頼性**: 🟡 *TypeScript オプショナルプロパティの安全な扱いとして妥当な推測*

**条件**: isReconfirmMode=true だが onReconfirmRemembered/onReconfirmForgotten が undefined
**期待動作**: ボタンは表示されるが、クリック時に undefined コールが発生しないこと（onClick={onReconfirmRemembered} は undefined の場合イベントが無視される）

#### EDGE-003: type='reconfirmed' だが grade が undefined 🟡

**信頼性**: 🟡 *TypeScript 型定義上 grade はオプショナルであるため妥当な推測*

**条件**: result.type='reconfirmed' かつ result.grade=undefined
**期待動作**: グレードバッジが表示されず、「覚えた✔」サブラベルのみ表示される（グレースフルデグラデーション）

#### EDGE-004: type='reconfirmed' で Undo ボタン表示 🔵

**信頼性**: 🔵 *要件定義書 REQ-404、既存実装 ReviewResultItem.tsx 68行目より確認*

**条件**: result.type='reconfirmed' かつ onUndo が渡されている
**期待動作**: Undo ボタンが表示され、クリックで onUndo(index) が呼ばれる（既存実装で対応済み）

**参照した EARS 要件**: REQ-002, REQ-003, REQ-004, REQ-101, REQ-103, REQ-404, REQ-501, EDGE-001
**参照した設計文書**: dataflow.md 全体フロー概要、再確認フロー（覚えた/覚えていない）、完了画面表示フロー

---

## 5. EARS要件・設計文書との対応関係

### 参照したユーザストーリー
- US-1.1: 復習で間違えたカードをセッション内で再確認する（再確認ループ全体）
- US-1.2: 再確認カードの結果を復習完了画面で確認する

### 参照した機能要件
- **REQ-002**: 再確認カード表示時に「覚えた」「覚えていない」の2択を表示 → GradeButtons 再確認モード
- **REQ-003**: 「覚えた」選択でセッションから除外（API呼び出しなし）→ handleReconfirmRemembered（TASK-0081済み、UIテストで検証）
- **REQ-004**: 「覚えていない」選択でキュー末尾に再追加 → handleReconfirmForgotten（TASK-0081済み、UIテストで検証）
- **REQ-005**: 表面→裏面→ボタンの表示フロー → 再確認モードでも同じフロー
- **REQ-101**: 再確認モードで「再確認」バッジ表示 → ReconfirmBadge コンポーネント
- **REQ-102**: 再確認モードでスキップボタン非表示 → GradeButtons の isReconfirmMode 分岐
- **REQ-103**: quality 3-5 は再確認ループに入らない → 通常モード非破壊確認
- **REQ-404**: Undo 機能は再確認カードにも使用可能 → ReviewResultItem の Undo ボタン表示
- **REQ-501**: 復習完了画面で元の評価 + 再確認結果を表示 → ReviewResultItem 拡張

### 参照した非機能要件
- **NFR-001**: フロントエンドメモリ内で完結（API呼び出しなし）
- **NFR-002**: 通常カードと同等の応答速度
- **NFR-201**: 44px 以上のタップ領域
- **NFR-202**: 再確認バッジで通常復習と明確に区別

### 参照したEdgeケース
- **EDGE-001**: セッション中断時の状態消失（SM-2 が翌日復習を設定済み）
- **EDGE-101**: 全カード quality 0-2 の場合
- **EDGE-102**: 無限ループ（「覚えていない」繰り返し）

### 参照した受け入れ基準
- **TC-002-01**: 再確認カードで「覚えた」「覚えていない」の2択が表示される
- **TC-101-01**: 再確認カードに「再確認」バッジが表示される
- **TC-101-02**: 通常カードには「再確認」バッジが表示されない
- **TC-102-01**: 再確認カードでスキップボタンが非表示
- **TC-501-01**: 再確認カードの完了画面表示が正しい
- **TC-501-02**: 通常カードの完了画面表示が変わらない

### 参照した設計文書
- **アーキテクチャ**: architecture.md コンポーネント構成、状態管理設計、非機能要件の実現方法
- **データフロー**: dataflow.md 全体フロー概要、再確認フロー（覚えた）、再確認フロー（覚えていない）、完了画面表示フロー
- **型定義**: `frontend/src/types/card.ts` - SessionCardResultType, SessionCardResult, ReconfirmCard
- **コンポーネント**:
  - `frontend/src/components/GradeButtons.tsx` - GradeButtonsProps, GRADE_CONFIGS
  - `frontend/src/components/ReviewResultItem.tsx` - ReviewResultItemProps, GRADE_DISPLAY_CONFIGS
  - `frontend/src/components/ReviewComplete.tsx` - ReviewCompleteProps, gradedCount 計算
  - `frontend/src/pages/ReviewPage.tsx` - 状態管理、ハンドラ、再確認モード表示ブロック

---

## 6. 実装対象ファイルと変更内容の詳細

### 6.1 GradeButtons.tsx - 再確認モードUIポリッシュ 🔵

**信頼性**: 🔵 *既存実装確認済み + 要件定義書 REQ-002, REQ-102*

**ファイルパス**: `frontend/src/components/GradeButtons.tsx`

**現状**: TASK-0081 で基本的な再確認モード2択UIは実装済み。以下が確認済み:
- Props に `isReconfirmMode?`, `onReconfirmRemembered?`, `onReconfirmForgotten?` が定義されている
- `isReconfirmMode = true` 時に早期リターンで2択UIを返す
- 「覚えた」ボタン: bg-green-50, text-green-700, border-green-300, min-h-[44px]
- 「覚えていない」ボタン: bg-red-50, text-red-700, border-red-300, min-h-[44px]
- スキップボタンは再確認モードブロック外（早期リターン後）のため自動的に非表示
- disabled 時に opacity-50 cursor-not-allowed が適用される

**必要なテスト項目**（既存テストに追加）:
1. `isReconfirmMode=true` で「覚えた」「覚えていない」ボタンが表示される
2. `isReconfirmMode=true` で6段階評価ボタン（0-5）が非表示
3. `isReconfirmMode=true` でスキップボタンが非表示
4. `isReconfirmMode=false` または未指定で従来通りの6段階評価UI
5. 「覚えた」ボタンクリックで `onReconfirmRemembered` が呼ばれる
6. 「覚えていない」ボタンクリックで `onReconfirmForgotten` が呼ばれる
7. `disabled=true` で再確認モード両ボタンが disabled 状態
8. `disabled=true` でクリックしても `onReconfirmRemembered` が呼ばれない
9. 再確認ボタンに min-h-[44px] が適用されている（アクセシビリティ）

### 6.2 ReconfirmBadge.tsx - 新規コンポーネント 🔵

**信頼性**: 🔵 *要件定義書 REQ-101、note.md セクション3B*

**ファイルパス**: `frontend/src/components/ReconfirmBadge.tsx`

**新規作成**: シンプルなプレゼンテーションコンポーネント

```typescript
export const ReconfirmBadge = () => {
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-sm font-medium bg-blue-100 text-blue-700">
      再確認
    </span>
  );
};
```

**必要なテスト項目**:
1. 「再確認」テキストが表示される
2. 適切なスタイリングクラスが適用されている（bg-blue-100, text-blue-700）
3. バッジ形状が rounded-full（ピル型）

### 6.3 ReviewPage.tsx - ReconfirmBadge 統合 🔵

**信頼性**: 🔵 *architecture.md コンポーネント構成、dataflow.md*

**ファイルパス**: `frontend/src/pages/ReviewPage.tsx`

**現状**: 再確認モード表示ブロック（371-399行目）は実装済みだが、ReconfirmBadge が未統合

**変更内容**:
- `ReconfirmBadge` の import 追加
- 再確認モード表示ブロック内の FlipCard 上部に `<ReconfirmBadge />` を条件付き表示

**変更後の構造**:
```
<div> (再確認モード表示ブロック)
  <main>
    <div> (バッジ表示領域 - 新規追加)
      <ReconfirmBadge />
    </div>
    <div> (FlipCard 領域)
      <FlipCard ... />
    </div>
    <div> (ボタン領域)
      <GradeButtons isReconfirmMode={true} ... />
    </div>
  </main>
</div>
```

**必要なテスト項目**（ReviewPage 統合テストとして）:
1. 再確認モード時に ReconfirmBadge が表示される
2. 通常モード時に ReconfirmBadge が表示されない
3. 再確認モードで GradeButtons に isReconfirmMode=true が渡される
4. 再確認カードの front/back が FlipCard に渡される

### 6.4 ReviewResultItem.tsx - 再確認結果表示 🔵

**信頼性**: 🔵 *要件定義書 REQ-501、受け入れ基準 TC-501-01, TC-501-02*

**ファイルパス**: `frontend/src/components/ReviewResultItem.tsx`

**現状**: type='reconfirmed' のバッジ・サブラベル表示が未実装。Undo ボタンの type='reconfirmed' 対応は実装済み（68行目）。

**変更内容**: 以下の2箇所に `type === 'reconfirmed'` の条件分岐を追加

1. **グレードバッジ表示領域**（30-48行目付近）:
   ```typescript
   {result.type === 'reconfirmed' && gradeConfig && (
     <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold ${gradeConfig.bgClass} ${gradeConfig.textClass}`}>
       {gradeConfig.label}
     </span>
   )}
   ```

2. **サブラベル表示領域**（51-64行目付近）:
   ```typescript
   {result.type === 'reconfirmed' && (
     <p className="text-xs text-green-600 mt-0.5">覚えた✔</p>
   )}
   ```

**必要なテスト項目**:
1. `type='reconfirmed'` で元の評価値（grade）のバッジが表示される
2. `type='reconfirmed'` で「覚えた✔」サブラベルが表示される
3. `type='reconfirmed'` で「次回: {date}」の表示がないこと（通常 graded と区別）
4. `type='graded'`（grade 3-5）で従来通りのバッジ + 次回復習日
5. `type='graded'`（grade 0-2）で従来通りのバッジ + 次回復習日
6. `type='skipped'` で従来通りの表示
7. `type='undone'` で従来通りの表示
8. `type='reconfirmed'` かつ `onUndo` あり → Undo ボタン表示
9. `type='reconfirmed'` かつ grade=undefined → グレードバッジ非表示、「覚えた✔」のみ

### 6.5 ReviewComplete.tsx - graded カウント検証 🔵

**信頼性**: 🔵 *既存実装確認済み*

**ファイルパス**: `frontend/src/components/ReviewComplete.tsx`

**現状**: TASK-0081 で `gradedCount` に `type === 'reconfirmed'` を含める実装は完了済み。

**必要なテスト項目**（既存テストに追加）:
1. `type='reconfirmed'` のカードが `gradedCount` に含まれ、表示枚数に反映される
2. `type='graded'` + `type='reconfirmed'` の合計が正しく表示される
3. results に各 type が混在する場合の表示枚数
4. 各 result が ReviewResultItem にマップされる

---

## 7. テストファイルと実装ファイルの対応

| テストファイル | 実装ファイル | テスト種別 |
|---------------|-------------|-----------|
| `frontend/src/components/__tests__/GradeButtons.test.tsx` | `frontend/src/components/GradeButtons.tsx` | 既存テスト追加 |
| `frontend/src/components/__tests__/ReconfirmBadge.test.tsx` | `frontend/src/components/ReconfirmBadge.tsx` | 新規テスト |
| `frontend/src/components/__tests__/ReviewResultItem.test.tsx` | `frontend/src/components/ReviewResultItem.tsx` | 新規テスト |
| `frontend/src/components/__tests__/ReviewComplete.test.tsx` | `frontend/src/components/ReviewComplete.tsx` | 既存テスト追加 |

**テスト実行コマンド**:
```bash
cd frontend && npx vitest run
```

---

## 8. 信頼性レベルサマリー

### 項目別信頼性

| セクション | 🔵 青信号 | 🟡 黄信号 | 🔴 赤信号 |
|-----------|-----------|-----------|-----------|
| 1. 機能の概要 | 4 | 0 | 0 |
| 2. 入力・出力の仕様 | 5 | 0 | 0 |
| 3. 制約条件 | 4 | 1 | 0 |
| 4. 想定される使用例 | 4 | 3 | 0 |
| 5. EARS対応関係 | — | — | — |
| 6. 実装対象ファイル | 5 | 0 | 0 |
| **合計** | **22** | **4** | **0** |

### 分布

- 🔵 **青信号**: 22項目 (85%) - EARS要件定義書・設計文書・既存実装で確認済み
- 🟡 **黄信号**: 4項目 (15%) - ユーザビリティ・エッジケースの妥当な推測
- 🔴 **赤信号**: 0項目 (0%)

### 品質評価

**✅ 高品質**: 要件の曖昧さなし、入出力定義完全、制約条件明確、実装可能性確実

**根拠**:
- TASK-0081 完了済みのためコアロジックは検証済みであり、UI層のテストに集中できる
- 既存実装（GradeButtons.tsx, ReviewResultItem.tsx, ReviewComplete.tsx, ReviewPage.tsx）のコードを直接確認し、変更箇所を特定済み
- 全ての変更はフロントエンドのみで完結し、API変更不要
- 既存テスト（GradeButtons 8件、ReviewComplete 5件）との互換性を明確に定義済み
