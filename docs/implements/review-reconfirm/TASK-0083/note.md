# TASK-0083 実装ノート：統合テスト・動作確認

**作成日**: 2026-02-28
**タスクID**: TASK-0083
**タスク名**: 統合テスト・動作確認
**フェーズ**: Phase 1 - review-reconfirm実装（最終フェーズ）
**推定工数**: 2時間
**ステータス**: 計画・分析段階

---

## 1. 技術スタック

### フロントエンド環境

| 項目 | バージョン | 用途 |
|------|----------|------|
| **Node.js** | v18+ | ランタイム |
| **React** | 18.x | UIフレームワーク |
| **TypeScript** | 5.x | 型安全性 |
| **Vite** | 5.x | ビルドツール |
| **Vitest** | 最新 | ユニット/統合テスト |
| **React Testing Library** | 最新 | コンポーネントテスト |
| **Tailwind CSS** | 3.x | スタイリング |

### テスト環境

```typescript
// テストフレームワーク構成
{
  "vitest": "latest",
  "@testing-library/react": "latest",
  "@testing-library/user-event": "latest"
}
```

### 参考元
- `frontend/package.json` - 依存関係定義
- `frontend/vite.config.ts` - ビルド設定
- `frontend/vitest.config.ts` - テスト設定

---

## 2. 開発ルール・コーディング規約

### TDD開発フロー（CLAUDE.md）

**実装手順**:
```
1. `/tsumiki:tdd-requirements review-reconfirm TASK-0083` - 詳細要件定義
2. `/tsumiki:tdd-testcases` - テストケース作成
3. `/tsumiki:tdd-red` - テスト実装（失敗）
4. `/tsumiki:tdd-green` - 最小実装
5. `/tsumiki:tdd-refactor` - リファクタリング
6. `/tsumiki:tdd-verify-complete` - 品質確認
```

**信頼性**: 🔵 *CLAUDE.md より*

### コミットルール

**コミットメッセージ形式**:
```
TASK-XXXX: タスク名

- 実装内容1
- 実装内容2

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

**ルール**:
- タスクごとにコミットする（複数タスクはまとめない）
- コミット前に`npm run test`と`npm run type-check`で検証

**参考元**: `CLAUDE.md` - コミットルール

### テスト実装規約

**Vitest構成**:
```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
```

**テストカバレッジ目標**: 80% 以上

**参考元**: `frontend/src/pages/__tests__/ReviewPage.test.tsx` - 既存テスト実装パターン

### コーディング規約

**型定義**:
- SessionCardResultType に `'reconfirmed'` を追加（TASK-0081で実装済み）
- ReconfirmCard インターフェースを使用（TASK-0081で実装済み）

**状態管理**:
- useState フラットパターンを維持（CLAUDE.md）
- reconfirmQueue: `ReconfirmCard[]` (TASK-0081で実装済み)
- isReconfirmMode: `boolean` (TASK-0081で実装済み)

**参考元**:
- `docs/rule/` - プロジェクト開発ルール
- `CLAUDE.md` - 全体開発ガイドライン

---

## 3. 関連実装・既存パターン

### TASK-0081: コアロジック実装（完了）

**実装内容**:
- 型定義拡張: `ReconfirmCard`, `SessionCardResultType`, `SessionCardResult`
- ReviewPage 状態管理: `reconfirmQueue`, `isReconfirmMode`
- ハンドラロジック:
  - `handleGrade`: quality 0-2 で `reconfirmQueue` に追加
  - `handleReconfirmRemembered`: 「覚えた」処理（API呼び出しなし）
  - `handleReconfirmForgotten`: 「覚えていない」処理（API呼び出しなし）
  - `moveToNext`: 再確認キュー遷移ロジック
  - `handleUndo`: 再確認キュー連携

**テスト実装**: 26個のテストケース + 既存テスト互換性確保

**参考元**:
- `docs/implements/review-reconfirm/TASK-0081/note.md` - TASK-0081実装ノート
- `frontend/src/pages/ReviewPage.tsx` - 実装コード
- `frontend/src/pages/__tests__/ReviewPage.test.tsx` - テストコード

### TASK-0082: UIコンポーネント実装（完了）

**実装内容**:
- `GradeButtons`: 再確認モード対応（2択UI）
- `ReconfirmBadge`: 新規コンポーネント（「再確認」バッジ表示）
- `ReviewPage`: UI統合（再確認モード表示、ReconfirmBadge追加）
- `ReviewComplete`: 再確認結果対応
- `ReviewResultItem`: 再確認結果表示（元の評価 + 「覚えた✔」）

**テスト実装**: GradeButtons, ReconfirmBadge, ReviewPage, ReviewComplete, ReviewResultItem の各テスト

**参考元**:
- `docs/implements/review-reconfirm/TASK-0082/note.md` - TASK-0082実装ノート
- `frontend/src/components/GradeButtons.tsx` - 実装コード
- `frontend/src/components/ReconfirmBadge.tsx` - 新規コンポーネント

### 既存設計パターン

**ReviewPage パターン** (review-flow):
```typescript
// 既存パターン: useState フラット + useCallback で各ハンドラ
const [cards, setCards] = useState<DueCard[]>([]);
const [currentIndex, setCurrentIndex] = useState(0);
const [isFlipped, setIsFlipped] = useState(false);
// ... 他の状態

const handleGrade = useCallback(async (grade: number) => {
  // 状態更新と API 呼び出し
}, [dependencies]);
```

**API 統合パターン**:
```typescript
// reviewsApi.submitReview: quality 評価を送信
const response = await reviewsApi.submitReview(cardId, grade);
// response.updated: { ease_factor, interval, repetitions, due_date }
```

**参考元**:
- `frontend/src/pages/ReviewPage.tsx` - 既存実装
- `docs/design/review-flow/architecture.md` - 既存設計
- `frontend/src/services/api.ts` - API定義

---

## 4. 設計文書・アーキテクチャ

### システム概要（review-reconfirm）

**機能**: 復習セッション中に quality 0-2（想起失敗）で評価されたカードを、セッション内の再確認ループに追加する機能

**スコープ**:
- フロントエンドのみの変更（TASK-0081, TASK-0082）
- バックエンド API・データベース・SM-2 アルゴリズムは変更なし

**参考元**: `docs/design/review-reconfirm/architecture.md` - アーキテクチャ設計

### カード進行フロー（REQ-502）

```
通常カード表示
  ↓
ユーザー評価（grade 0-5）
  ↓
grade 0-2:
  → SM-2 API呼び出し（interval=1, next_review_at=翌日）
  → reconfirmQueue に追加
  → 次のカード

grade 3-5:
  → SM-2 API呼び出し（通常のSM-2計算）
  → reconfirmQueue に追加しない
  → 次のカード

moveToNext 判定:
  → 通常カード残 → 次の通常カード
  → 通常カード終 & reconfirmQueue非空 → 再確認キューから取り出し
  → 両方なし → セッション完了
```

**重要**: 通常カードと再確認カードは同一キューで流れる（実装上は順序制御）

**参考元**: `docs/design/review-reconfirm/dataflow.md` - データフロー図

### 再確認ハンドラロジック

**handleReconfirmRemembered**（「覚えた」）:
- reconfirmQueue から先頭を除外
- reviewResults を 'reconfirmed' に更新
- reconfirmResult: 'remembered' を設定
- API呼び出しなし

**handleReconfirmForgotten**（「覚えていない」）:
- 先頭カードを末尾に再追加
- API呼び出しなし
- セッション続行

**参考元**: `docs/design/review-reconfirm/architecture.md` - 状態管理設計

### Undo 連携（REQ-404）

**Undo対象**: quality 0-2 で評価済みのカード

**処理フロー**:
1. undoReview API呼び出し → SM-2復元
2. reviewResults を 'undone' に変更
3. reconfirmQueue から除去
4. regradeMode に入る

**再評価**: Undo後の再評価で quality 0-2 を選択 → 再び再確認キューに追加

**参考元**: `docs/design/review-reconfirm/architecture.md` - Undo連携設計

---

## 5. テスト設計・テストケース体系

### テストの目的と方針

**TASK-0083の役割**: TASK-0081（コアロジック）と TASK-0082（UIコンポーネント）の統合確認

**テスト範囲**:
1. ✅ **エンドツーエンドフロー**: 通常評価 → 再確認 → 覚えた/覚えていない → 完了
2. ✅ **エッジケース**: 全カード再確認、無限ループ、セッション中断
3. ✅ **Undo連携**: Undo → 再確認キュー除去 → regrade
4. ✅ **回帰テスト**: 既存機能（quality 3-5フロー、スキップ）の変更なし
5. ✅ **型チェック**: TypeScript strict mode での型検証
6. ✅ **全テスト**: `npm test` で全フロントエンドテスト通過

**参考元**: `docs/tasks/review-reconfirm/TASK-0083.md` - タスク定義

### テストケース一覧（受け入れ基準）

#### 1. エンドツーエンドフローテスト

| ID | テスト内容 | 前提条件 | 期待結果 | 参照 |
|---|---|---|---|---|
| **TC-001** | 通常評価 → 再確認 → 覚えた → 完了 | 通常カード3枚のうち1枚を quality 0-2 で評価 | 再確認キューに追加される → 通常カード全消化後に再確認カード表示 → 「覚えた」で完了 | TC-001-01～03 |
| **TC-002** | 再確認カード表示（2択） | 再確認キューにカードが存在 | 「覚えた」「覚えていない」2択のみ表示 | TC-002-01, TC-002-02 |
| **TC-003** | 「覚えた」選択 | 再確認カード表示中 | カードがセッションから除外、API呼び出しなし | TC-003-01, TC-003-02 |
| **TC-004** | 「覚えていない」選択 | 再確認カード表示中 | カードがキュー末尾に再追加、セッション継続 | TC-004-01, TC-004-02, TC-004-03 |

#### 2. エッジケーステスト

| ID | テスト内容 | 前提条件 | 期待結果 | 参照 |
|---|---|---|---|---|
| **EDGE-001** | セッション中断 | quality 0-2評価 → アプリ閉じる | 翌日に通常の復習対象として表示 | EDGE-001 |
| **EDGE-101** | 全カード再確認 | 全3枚を quality 0-2 で評価 | 全て再確認ループに入る → 全て「覚えた」で完了 | EDGE-101 |
| **EDGE-102** | 無限ループ | 再確認で「覚えていない」を繰り返す | 正常にループ、4回目でも2択ボタン表示 | EDGE-102 |

#### 3. Undo連携テスト

| ID | テスト内容 | 前提条件 | 期待結果 | 参照 |
|---|---|---|---|---|
| **TC-404-01** | Undo時のキュー除去 | quality 0-2評価済み → Undo | reconfirmQueue から該当カード除去 | TC-404-01 |
| **TC-404-02** | Undo後 regrade quality 0-2 | Undo後 regrade質 → quality 0-2選択 | 再び再確認キューに追加 | TC-404-02 |
| **TC-404-03** | Undo後 regrade quality 3+ | Undo後 regrade質 → quality 3-5選択 | 再確認キューに追加されない | TC-404-03 |

#### 4. 回帰テスト（既存機能）

| ID | テスト内容 | 確認内容 | 参照 |
|---|---|---|---|
| **REGRESSION** | quality 3-5フロー | 既存の通常復習フローが変わらない | 既存テストケース 1-10 |
| **TYPE-CHECK** | TypeScript型チェック | `npm run type-check` で型エラーなし | 全TypeScriptファイル |
| **ALL-TESTS** | 全テスト実行 | `npm test` で全テスト通過 | 全フロントエンドテスト |

**参考元**:
- `docs/spec/review-reconfirm/acceptance-criteria.md` - 受け入れ基準定義
- `docs/implements/review-reconfirm/TASK-0081/requirements.md` - TDD要件定義

### テスト実装上の注意点

**1. UI ボタンの選択方法**

TASK-0082 で実装された GradeButtons と ReconfirmBadge を使用してテストを実行

```typescript
// 再確認モード: 「覚えた」「覚えていない」ボタン
const rememberedButton = screen.getByRole('button', { name: '覚えた' });
const forgottenButton = screen.getByRole('button', { name: '覚えていない' });

// 通常モード: 0-5 の6段階ボタン
const grade0Button = screen.getByRole('button', { name: /0 -/ });
const grade5Button = screen.getByRole('button', { name: /5 -/ });
```

**2. 非同期処理の待機**

```typescript
// API呼び出し待機
await waitFor(() => {
  expect(mockSubmitReview).toHaveBeenCalled();
});

// 状態更新待機
await userEvent.click(button);
await waitFor(() => {
  expect(screen.getByText('再確認')).toBeInTheDocument();
});
```

**3. モック設定**

既存のモック構成を利用:
- `mockGetDueCards`: 3枚のテストカード
- `mockSubmitReview`: quality別の応答
- `mockUndoReview`: SM-2復元応答

**参考元**:
- `frontend/src/pages/__tests__/ReviewPage.test.tsx` - テスト実装パターン
- `docs/implements/review-reconfirm/TASK-0082/note.md` - UI実装パターン

---

## 6. 統合テストシナリオ詳細

### シナリオ1: 通常カード3枚 + 再確認1枚（TC-001）

**準備**:
- カード3枚を用意（mockGetDueCards）

**手順**:
```typescript
1. カード1を quality 0 で評価（submitReview 呼び出し）
   → reconfirmQueue: [card-1]
   → 次のカード表示

2. カード2を quality 4 で評価
   → reconfirmQueue: [card-1]（変わらず）
   → 次のカード表示

3. カード3を quality 5 で評価
   → 通常カード全消化
   → isReconfirmMode = true
   → 再確認カード表示（「再確認」バッジ + FlipCard + 「覚えた」「覚えていない」）

4. 再確認: card-1 「覚えた」ボタンクリック
   → reconfirmQueue: []
   → 完了画面表示

5. 完了画面で card-1 の結果確認
   → type: 'reconfirmed'
   → reconfirmResult: 'remembered'
   → グレード表示: 0 + 「覚えた✔」
```

**検証**:
- submitReview は3回のみ呼び出し（quality 0-2の再評価時に追加呼び出しなし）
- 完了画面に「3枚のカードを復習しました」表示
- Undoボタンが全カードで有効

**参考元**: `docs/implements/review-reconfirm/TASK-0081/requirements.md` - TC-TDD-INT-01

### シナリオ2: 全カード再確認ループ（EDGE-101）

**準備**:
- カード3枚を用意

**手順**:
```typescript
1. カード1を quality 0 で評価
   → reconfirmQueue: [card-1]

2. カード2を quality 1 で評価
   → reconfirmQueue: [card-1, card-2]

3. カード3を quality 2 で評価
   → 通常カード全消化
   → isReconfirmMode = true
   → reconfirmQueue: [card-1, card-2, card-3]

4. 再確認: card-1 「覚えた」
   → reconfirmQueue: [card-2, card-3]
   → card-2 を表示

5. 再確認: card-2 「覚えた」
   → reconfirmQueue: [card-3]
   → card-3 を表示

6. 再確認: card-3 「覚えた」
   → reconfirmQueue: []
   → 完了画面
```

**検証**:
- submitReview は3回のみ
- 全カードが type: 'reconfirmed' で完了
- セッション総時間は予想通り（UI は即座）

**参考元**: `docs/spec/review-reconfirm/acceptance-criteria.md` - EDGE-101

### シナリオ3: 「覚えていない」ループ（EDGE-102）

**準備**:
- カード1枚のみ

**手順**:
```typescript
1. カード1を quality 0 で評価
   → reconfirmQueue: [card-1]
   → 通常カード全消化（1枚のため）
   → isReconfirmMode = true

2. 再確認: card-1 「覚えていない」ボタンクリック
   → reconfirmQueue: [card-1]（末尾に再追加）
   → card-1 を再度表示（「覚えた」「覚えていない」2択のまま）

3. 再確認: card-1 「覚えていない」（2回目）
   → reconfirmQueue: [card-1]

4. 再確認: card-1 「覚えた」（3回目）
   → reconfirmQueue: []
   → 完了画面
```

**検証**:
- submitReview は1回のみ（初回 quality 0）
- 再確認中は API 呼び出しなし
- 4回以上「覚えていない」しても正常動作

**参考元**: `docs/spec/review-reconfirm/acceptance-criteria.md` - EDGE-102

### シナリオ4: Undo → regrade （TC-404）

**準備**:
- カード1枚のみ

**手順**:
```typescript
1. カード1を quality 4 で評価
   → reconfirmQueue: []
   → isComplete = true

2. 完了画面で Undo ボタンクリック
   → undoReview API呼び出し
   → reviewResults[0].type: 'undone'
   → reconfirmQueue: []（空）
   → regradeMode に移行（再採点画面表示）

3. Regrade: quality 2 を選択
   → submitReview API呼び出し
   → reconfirmQueue: [card-1]
   → isComplete = true（完了画面に戻る）

4. 完了画面で結果確認
   → type: 'reconfirmed'
   → reconfirmResult: 'remembered'（再確認まで完了）
```

**検証**:
- undoReview は1回
- submitReview は2回（初回quality 4 + regrade quality 2）
- 再採점 quality 2후 자동으로 재확인 루프 진입 확인

**参考元**: `docs/spec/review-reconfirm/acceptance-criteria.md` - TC-404-01, TC-404-02

---

## 7. 重要な注意事項

### API呼び出しの制約

**重要**: 以下の処理では **API呼び出しがない**

```typescript
// ❌ API呼び出しなし
handleReconfirmRemembered() {
  // キューから除外のみ
  setReconfirmQueue((prev) => prev.slice(1));
}

// ❌ API呼び出しなし
handleReconfirmForgotten() {
  // キュー末尾に再追加のみ
  setReconfirmQueue((prev) => {
    const [current, ...rest] = prev;
    return [...rest, current];
  });
}
```

**理由**: quality 0-2 の SM-2 パラメータは最初の評価時に既に設定済み（interval=1, next_review_at=翌日）。再確認フェーズではこれを変更しない。

**参考元**: `docs/design/review-reconfirm/architecture.md` - REQ-203, REQ-404

### セッション状態の管理

**reconfirmQueue はセッション内フロントエンド state のみ**:
- セッション終了時にリセット（localStorage 永続化なし）
- アプリ閉じるとreconfirmQueue消失
- SM-2の next_review_at=翌日のため、翌日に通常の復習対象として再表示

**参考元**: `docs/design/review-reconfirm/architecture.md` - REQ-201, EDGE-001

### 型安全性

**TypeScript strict mode での検証**:
```bash
npm run type-check
```

**確認項目**:
- ReconfirmCard 型が正しく使用されている
- SessionCardResultType に 'reconfirmed' が含まれている
- sessionCardResult.reconfirmResult?: 'remembered' が正しい

**参考元**: `frontend/tsconfig.json` - strict: true

### 既存機能との互換性

**quality 3-5 の通常フロー**:
- 既存テストが全てパスする必要がある
- reconfirmQueue への追加が発生しない
- handleReconfirmRemembered / handleReconfirmForgotten は呼ばれない

**参考元**:
- `frontend/src/pages/__tests__/ReviewPage.test.tsx` - 既存テストケース
- `docs/implements/review-reconfirm/TASK-0081/requirements.md` - 互換性要件

---

## 8. デバッグ・ローカル確認手順

### 環境準備

```bash
# 1. 全ローカルサービス起動
cd backend && make local-all

# 2. Keycloak 起動待ち（初回約20秒）
#    http://localhost:8180/health/ready で確認

# 3. バックエンド API 起動（別ターミナル）
cd backend && make local-api

# 4. フロントエンド起動（別ターミナル）
cd frontend && npm run dev

# 5. ブラウザで http://localhost:3000 にアクセス
#    → Keycloak ログイン（test-user / test-password-123）
```

### 手動テスト手順

**シナリオ1: 再確認ループ**

```
1. 復習開始
2. 3枚のカードのうち1枚目を quality 0-2 で評価
3. 2枚目を quality 4 で評価
4. 3枚目を quality 5 で評価
   ✓ 「再確認」バッジが表示される
   ✓ 「覚えた」「覚えていない」2択のみ表示
   ✓ スキップボタン非表示
5. 「覚えた」ボタンクリック
   ✓ 完了画面に遷移
   ✓ 1枚目の結果に「覚えた✔」表示
```

**シナリオ2: 「覚えていない」ループ**

```
1. 1枚のカードのみで復習開始
2. quality 0 で評価
   ✓ 再確認カード表示
3. 「覚えていない」クリック
   ✓ 同じカードが再度表示される（無限ループ防止確認）
4. もう1回「覚えていない」クリック
   ✓ 同じカードが再度表示
5. 「覚えた」クリック
   ✓ 完了画面に遷移
```

**シナリオ3: Undo機能**

```
1. 1枚のカードを quality 4 で評価
   ✓ 完了画面に遷移
2. Undo ボタンクリック
   ✓ 再採点モード画面表示
3. 今度は quality 2 で再評価
   ✓ 完了画面に戻る
   ✓ 再確認ループが自動で実行
   ✓ 再確認カード表示
4. 「覚えた」クリック
   ✓ セッション完了
```

### テスト実行コマンド

```bash
# 全テスト実行
npm run test

# 特定ファイルのテスト
npm run test -- ReviewPage.test.tsx

# Watch モード
npm run test -- --watch

# カバレッジ確認
npm run test -- --coverage

# TypeScript 型チェック
npm run type-check

# リント確認
npm run lint
```

**参考元**: `CLAUDE.md` - ローカル開発環境

---

## 9. 実装チェックリスト

### Phase 完了条件（TASK-0083）

**エンドツーエンドテスト**:
- [ ] 通常評価 → 再確認 → 覚えた → 完了 のフロー全通過
- [ ] 通常評価 → 再確認 → 覚えていない → 覚えた のフロー全通過

**エッジケーステスト**:
- [ ] 全カード quality 0-2 の場合、全て再確認ループで「覚えた」で完了
- [ ] 同一カード複数回「覚えていない」でも正常ループ
- [ ] 通常カード + 再確認カード混在フロー正常

**Undo連携テスト**:
- [ ] quality 0-2 評価 → 再確認ループ → Undo → reconfirmQueue除去 → regrade
- [ ] Undo後 quality 0-2 再評価で再び再確認ループ
- [ ] Undo後 quality 3+ 再評価で再確認ループに入らない

**回帰テスト**:
- [ ] `npm test` で全テスト通過
- [ ] `npm run type-check` で型エラーなし
- [ ] quality 3-5 通常フロー変更なし

**参考元**: `docs/tasks/review-reconfirm/TASK-0083.md` - 完了条件

### ファイル更新予定

**タスク完了時**:
1. `docs/tasks/review-reconfirm/TASK-0083.md` - 完了条件の `[ ]` を `[x]` に更新
2. `docs/tasks/review-reconfirm/overview.md` - TASK-0083 の状態列を `[x]` に更新

**コミット**: タスク完了後に1回

---

## 10. 参考資料一覧

### 要件定義・設計文書

| 資料 | パス | 内容 |
|------|------|------|
| 要件定義 | `docs/spec/review-reconfirm/requirements.md` | 機能要件・非機能要件 |
| 受け入れ基準 | `docs/spec/review-reconfirm/acceptance-criteria.md` | テストケース定義 |
| ユーザストーリー | `docs/spec/review-reconfirm/user-stories.md` | ユーザーニーズ |
| アーキテクチャ | `docs/design/review-reconfirm/architecture.md` | システム設計 |
| データフロー | `docs/design/review-reconfirm/dataflow.md` | 処理フロー図 |

### 実装参考資料

| 資料 | パス | 参考箇所 |
|------|------|--------|
| TASK-0081 ノート | `docs/implements/review-reconfirm/TASK-0081/note.md` | コアロジック実装内容 |
| TASK-0082 ノート | `docs/implements/review-reconfirm/TASK-0082/note.md` | UI実装パターン |
| ReviewPage 実装 | `frontend/src/pages/ReviewPage.tsx` | 状態管理・ハンドラ |
| ReviewPage テスト | `frontend/src/pages/__tests__/ReviewPage.test.tsx` | テスト実装パターン |
| GradeButtons | `frontend/src/components/GradeButtons.tsx` | 2択UI実装 |
| ReconfirmBadge | `frontend/src/components/ReconfirmBadge.tsx` | バッジコンポーネント |

### プロジェクト全般

| 資料 | パス | 内容 |
|------|------|------|
| 開発ガイドライン | `CLAUDE.md` | 全体開発ルール・TDD フロー |
| 既存設計（review-flow） | `docs/design/review-flow/architecture.md` | ReviewPage パターン参考 |
| 既存設計（review-undo） | `docs/design/review-undo/architecture.md` | Undo機能設計参考 |

---

## 11. 技術的なポイント

### setState の非同期性への対応

**問題**: `handleGrade` 内で `setReconfirmQueue` した直後に `moveToNext` を呼んでも、新しい state 値が反映されていない

**解決策**: 新しい state 値を引数で明示的に `moveToNext` に渡す

```typescript
// ✅ 推奨
let newReconfirmQueue = reconfirmQueue;
if (grade < 3) {
  newReconfirmQueue = [...reconfirmQueue, newCard];
  setReconfirmQueue(newReconfirmQueue);
}
setReviewResults(...);
setReviewedCount(...);
moveToNext(newReconfirmQueue, currentIndex, cards.length);  // ← 最新の state を引数で受け取る
```

**参考元**: `frontend/src/pages/ReviewPage.tsx` - handleGrade 実装

### 配列操作での state 更新

**reconfirmQueue の操作パターン**:
```typescript
// 末尾に追加
setReconfirmQueue((prev) => [...prev, newCard]);

// 先頭を除外
setReconfirmQueue((prev) => prev.slice(1));

// 先頭を末尾に再追加（「覚えていない」時）
setReconfirmQueue((prev) => {
  const [current, ...rest] = prev;
  return [...rest, current];
});

// 特定カード を除去（Undo時）
setReconfirmQueue((prev) => prev.filter((c) => c.cardId !== cardId));
```

**参考元**: `frontend/src/pages/ReviewPage.tsx` - 各ハンドラ実装

### リエンダリングの最適化

**useCallback の依存配列**:
```typescript
const handleGrade = useCallback(async (grade: number) => {
  // ...
}, [cards, currentIndex, moveToNext, regradeCardIndex, reviewResults, reconfirmQueue]);
```

**注意**:
- 参照の変更を避けるため、配列長ではなく配列そのものを依存に含める
- または `useCallback` 内で state update 関数を使う

**参考元**: `frontend/src/pages/ReviewPage.tsx` - useCallback 定義

---

## 12. まとめ

**TASK-0083** は TASK-0081（コアロジック）と TASK-0082（UIコンポーネント）の統合テストと最終動作確認です。

**主要な確認項目**:
1. ✅ 全フロー統合テスト（通常 → 再確認 → 完了）
2. ✅ エッジケーステスト（全再確認、無限ループ、セッション中断）
3. ✅ Undo連携テスト（キュー除去、regrade再追加）
4. ✅ 回帰テスト（既存機能の変更なし）
5. ✅ 型チェック・全テスト通過

**テスト方針**: TDD ワークフロー（Red → Green → Refactor）に従い、受け入れ基準で定義された22個のテストケースを全て通過させる。

**成功基準**:
- `npm test` で全テスト通過（新規 + 既存）
- `npm run type-check` で型エラーなし
- ローカル環境での手動確認で全シナリオ実行

**次の予定**: Phase 1 完了後、レビュー・デプロイへ

---

**作成者**: Claude Code (Haiku 4.5)
**最終更新**: 2026-02-28
