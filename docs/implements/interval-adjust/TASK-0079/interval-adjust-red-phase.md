# TASK-0079: フロントエンド プリセットボタンUI - Redフェーズ記録

**機能名**: interval-adjust (フロントエンド プリセットボタンUI)
**タスクID**: TASK-0079
**フェーズ**: Red（失敗するテスト作成）
**作成日**: 2026-02-28

---

## 作成したテストケースの一覧

**テストファイル**: `frontend/src/pages/__tests__/CardDetailPage.test.tsx`（既存ファイルに追記）

**追加した describe ブロック**: `describe('復習間隔プリセットボタン', ...)`

| テストID | テスト名 | 対応要件 | 信頼性 |
|---------|---------|---------|--------|
| TC-F01 | プリセットボタン5つが表示される | REQ-001, TC-001-01 | 🔵 |
| TC-F02 | プリセットボタンに正しいテキストが表示される | REQ-001, TC-001-01 | 🔵 |
| TC-F03 | プリセットボタンセクションのタイトルが表示される | REQ-001 | 🟡 |
| TC-F04 | プリセットボタン「1日」タップで updateCard API が interval=1 で呼ばれる | REQ-002, TC-002-01 | 🔵 |
| TC-F05 | プリセットボタン「30日」タップで updateCard API が interval=30 で呼ばれる | REQ-002, TC-002-02 | 🔵 |
| TC-F06 | プリセットボタン「7日」タップで updateCard API が interval=7 で呼ばれる | REQ-002 | 🟡 |
| TC-F07 | API成功時にカード詳細のメタ情報（復習間隔）が更新される | REQ-203, TC-002-03 | 🔵 |
| TC-F08 | API成功時に「復習間隔を更新しました」メッセージが表示される | NFR-203 | 🔵 |
| TC-F09 | API成功後にプリセットボタンが再度有効になる | REQ-202 | 🟡 |
| TC-F10 | プリセットボタンに正しい aria-label が設定される | NFR-301 | 🔵 |
| TC-F11 | API失敗時に「復習間隔の更新に失敗しました」エラーメッセージが表示される | REQ-103, TC-103-01 | 🟡 |
| TC-F12 | API失敗時にカードのメタ情報が変更前の値のまま保持される | REQ-103, TC-103-02 | 🟡 |
| TC-F13 | API失敗後にプリセットボタンが再度有効になる | REQ-103 | 🟡 |
| TC-F14 | 編集モード時にプリセットボタンセクションが非表示になる | REQ-201, TC-001-02 | 🔵 |
| TC-F15 | API呼び出し中に全プリセットボタンが disabled になる | REQ-202, TC-202-01 | 🟡 |
| TC-F16 | 編集キャンセル後にプリセットボタンが再表示される | REQ-201 | 🟡 |
| TC-F17 | API呼び出し中は2回目のプリセットボタンクリックが disabled でブロックされる | REQ-202, EDGE-002 | 🟡 |

**合計**: 17 テストケース

---

## テスト実行結果（Redフェーズ確認）

```
FAIL src/pages/__tests__/CardDetailPage.test.tsx (35 tests | 16 failed)

✓ 既存テスト: 18件 全通過
✓ TC-F14（編集モード時プリセットボタン非表示）: 1件 通過（既存の表示モード条件分岐で偶然通過）
✗ TASK-0079 新規テスト: 16件 失敗
```

### 失敗したテストケース（16件）

```
× プリセットボタン5つが表示される
× プリセットボタンに正しいテキストが表示される
× プリセットボタンセクションのタイトルが表示される
× プリセットボタン「1日」タップで updateCard API が interval=1 で呼ばれる
× プリセットボタン「30日」タップで updateCard API が interval=30 で呼ばれる
× プリセットボタン「7日」タップで updateCard API が interval=7 で呼ばれる
× API成功時にカード詳細のメタ情報（復習間隔）が更新される
× API成功時に「復習間隔を更新しました」メッセージが表示される
× API成功後にプリセットボタンが再度有効になる
× プリセットボタンに正しい aria-label が設定される
× API失敗時に「復習間隔の更新に失敗しました」エラーメッセージが表示される
× API失敗時にカードのメタ情報が変更前の値のまま保持される
× API失敗後にプリセットボタンが再度有効になる
× API呼び出し中に全プリセットボタンが disabled になる
× 編集キャンセル後にプリセットボタンが再表示される
× API呼び出し中は2回目のプリセットボタンクリックが disabled でブロックされる
```

### 失敗原因の分類

#### プリセットボタンUI未実装（16件全失敗の主原因）

**原因**: `CardDetailPage.tsx` にプリセットボタンUIが存在しない

```
TestingLibraryElementError: Unable to find an element by: [data-testid="preset-button-1"]
```

以下のUI要素が `CardDetailPage.tsx` に未実装:
- プリセットボタン（`data-testid="preset-button-{N}"`、N=1,3,7,14,30）
- セクションタイトル「復習間隔を調整」
- `isAdjusting` 状態による disabled 制御
- `aria-label="復習間隔を{N}日に設定"` アクセシビリティ属性

#### UpdateCardRequest 型未拡張

**原因**: `frontend/src/types/card.ts` の `UpdateCardRequest` に `interval` フィールドがない

```typescript
// 現在（拡張前）
export interface UpdateCardRequest {
  front?: string;
  back?: string;
  deck_id?: string;
  tags?: string[];
  // interval が存在しない
}
```

---

## テスト実行コマンド

```bash
# プリセットボタンテストのみ実行
cd frontend && npx vitest run src/pages/__tests__/CardDetailPage.test.tsx

# ウォッチモードで実行
cd frontend && npx vitest src/pages/__tests__/CardDetailPage.test.tsx
```

---

## Greenフェーズで実装すべき内容

### 1. UpdateCardRequest 型拡張（frontend/src/types/card.ts）

```typescript
export interface UpdateCardRequest {
  front?: string;
  back?: string;
  deck_id?: string;
  tags?: string[];
  interval?: number;  // 追加: 1〜365の整数
}
```

### 2. isAdjusting 状態追加（frontend/src/pages/CardDetailPage.tsx）

```typescript
const [isAdjusting, setIsAdjusting] = useState(false);
```

### 3. handleIntervalAdjust ハンドラ実装（frontend/src/pages/CardDetailPage.tsx）

```typescript
const handleIntervalAdjust = async (interval: number) => {
  if (!id) return;

  setIsAdjusting(true);
  setError(null);

  try {
    const updatedCard = await cardsApi.updateCard(id, { interval });
    setCard(updatedCard);
    setSuccessMessage('復習間隔を更新しました');
  } catch (err) {
    setError('復習間隔の更新に失敗しました');
  } finally {
    setIsAdjusting(false);
  }
};
```

### 4. プリセットボタンUIレンダリング（frontend/src/pages/CardDetailPage.tsx）

表示モード（`isEditing === false`）の `card-meta` 下、削除ボタンの上に配置:

```tsx
{/* 復習間隔プリセットボタン */}
<div className="bg-white rounded-lg shadow p-4 mb-4">
  <p className="text-sm text-gray-600 mb-3">復習間隔を調整</p>
  <div className="flex gap-2 flex-wrap">
    {[1, 3, 7, 14, 30].map((days) => (
      <button
        key={days}
        onClick={() => handleIntervalAdjust(days)}
        disabled={isAdjusting}
        aria-label={`復習間隔を${days}日に設定`}
        data-testid={`preset-button-${days}`}
        className="flex-1 min-h-[44px] py-2 px-3 bg-blue-50 text-blue-700 border border-blue-200 rounded-lg hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {days}日
      </button>
    ))}
  </div>
</div>
```

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 8 | 47% |
| 🟡 黄信号 | 9 | 53% |
| 🔴 赤信号 | 0 | 0% |

**品質評価**: ✅ 高品質（赤信号 0%、青信号・黄信号のみ）
