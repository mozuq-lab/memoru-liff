# TASK-0079: フロントエンド プリセットボタンUI - Greenフェーズ記録

**機能名**: interval-adjust (フロントエンド プリセットボタンUI)
**タスクID**: TASK-0079
**フェーズ**: Green（最小実装）
**作成日**: 2026-02-28

---

## 実装方針

Redフェーズで失敗していた16件のテストを通すために、以下の最小限の実装を行った。

1. **UpdateCardRequest 型拡張** - `interval?: number` フィールドの追加
2. **isAdjusting state 追加** - API呼び出し中のボタン無効化状態管理
3. **handleIntervalAdjust ハンドラ実装** - 既存の handleSave パターンを踏襲
4. **プリセットボタンUIレンダリング** - 表示モード限定、card-meta の下に配置

---

## 実装コード

### 変更ファイル 1: `frontend/src/types/card.ts`

`UpdateCardRequest` インターフェースに `interval` フィールドを追加。

```typescript
export interface UpdateCardRequest {
  front?: string;
  back?: string;
  deck_id?: string;
  tags?: string[];
  // 【追加フィールド】: 復習間隔調整機能（TASK-0079）で追加。1〜365の整数を受け付ける 🔵
  interval?: number;
}
```

**判断理由**: 🔵 タスクノートの「関連実装 3.1 UpdateCardRequest（変更対象）」に明記されているため、ほぼ推測なし。

---

### 変更ファイル 2: `frontend/src/pages/CardDetailPage.tsx`

#### 追加 state

```typescript
// 【状態追加】: 復習間隔調整APIの呼び出し中かどうかを管理する。プリセットボタンの disabled 制御に使用 🔵
const [isAdjusting, setIsAdjusting] = useState(false);
```

#### 追加ハンドラ

```typescript
/**
 * 【機能概要】: 復習間隔プリセットボタンのタップハンドラ
 * 【実装方針】: 既存の handleSave パターンに倣い、isAdjusting で処理中状態を管理する
 * 【テスト対応】: TC-F04〜F09, TC-F11〜F13, TC-F15, TC-F17 を通すための実装
 * 🔵 青信号: タスクノートの「データフロー（正常系）」「データフロー（エラー系）」に基づく実装
 * @param interval - 設定する復習間隔（日数）。プリセット値は 1, 3, 7, 14, 30
 */
const handleIntervalAdjust = async (interval: number) => {
  // 【ガード処理】: カードIDが取得できない場合は処理を中断する
  if (!id) return;

  // 【処理開始】: API呼び出し中状態に設定し、前回のエラーをクリアする 🔵
  setIsAdjusting(true);
  setError(null);

  try {
    // 【API呼び出し】: interval フィールドのみを送信してカードを更新する 🔵
    const updatedCard = await cardsApi.updateCard(id, { interval });
    // 【成功処理】: 更新後のカードデータで画面を更新し、成功メッセージを表示する 🔵
    setCard(updatedCard);
    setSuccessMessage('復習間隔を更新しました');
  } catch (_err) {
    // 【エラー処理】: 更新失敗時はカードデータを変更せず、エラーメッセージのみ表示する 🔵
    setError('復習間隔の更新に失敗しました');
  } finally {
    // 【状態復帰】: 成功・失敗いずれの場合も isAdjusting を false に戻してボタンを再有効化する 🔵
    setIsAdjusting(false);
  }
};
```

#### 追加UI（表示モード、card-meta の下）

```tsx
{/* 復習間隔プリセットボタンセクション */}
{/* 【配置理由】: タスクノートのUI設計に従い card-meta の下、削除ボタンの上に配置 🔵 */}
<div className="bg-white rounded-lg shadow p-4 mb-4">
  {/* 【セクションタイトル】: TC-F03 が期待する「復習間隔を調整」テキスト 🟡 */}
  <p className="text-sm text-gray-600 mb-3">復習間隔を調整</p>
  <div className="flex gap-2 flex-wrap">
    {/* 【プリセットボタン】: TC-F01〜F02, TC-F04〜F17 が期待するボタンを生成する 🔵 */}
    {[1, 3, 7, 14, 30].map((days) => (
      <button
        key={days}
        onClick={() => handleIntervalAdjust(days)}
        // 【無効化制御】: isAdjusting=true の間は全ボタンを disabled にして二重送信を防ぐ 🔵
        disabled={isAdjusting}
        // 【アクセシビリティ】: TC-F10 が期待する「復習間隔を{N}日に設定」形式の aria-label 🔵
        aria-label={`復習間隔を${days}日に設定`}
        // 【テスト識別子】: TC-F01〜F17 がボタンを特定するための data-testid 🔵
        data-testid={`preset-button-${days}`}
        className="flex-1 min-h-[44px] py-2 px-3 bg-blue-50 text-blue-700 border border-blue-200 rounded-lg hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {/* 【ボタンテキスト】: TC-F02 が期待する「{N}日」形式 🔵 */}
        {days}日
      </button>
    ))}
  </div>
</div>
```

---

## テスト実行結果

```
RUN v4.0.18

✓ src/pages/__tests__/CardDetailPage.test.tsx (35 tests) 622ms

 Test Files  1 passed (1)
       Tests  35 passed (35)
   Start at  19:12:48
   Duration  2.36s
```

**既存テスト 18件 + TASK-0079 新規テスト 17件 = 合計 35件全通過**

---

## 品質評価

| 項目 | 評価 |
|------|------|
| テスト結果 | ✅ 全35件通過 |
| TypeScript | ✅ 型エラーなし（tsc --noEmit）|
| 実装品質 | ✅ 既存パターン踏襲でシンプル |
| ファイルサイズ | ✅ CardDetailPage.tsx: 352行（制限800行以内）|
| モック使用 | ✅ 実装コードにモック・スタブなし |
| 日本語コメント | ✅ 全実装箇所にコメント付与 |

---

## 課題・改善点（Refactorフェーズで対応）

1. **`act(...)` 警告**: TC-F17（連続タップテスト）で `resolveFirst(mockCard)` 時に act 警告が発生。テストは通過しているが、`act()` でラップすることで警告を解消可能。
2. **プリセット値の定数化**: `[1, 3, 7, 14, 30]` をコンポーネント外の定数として抽出する候補。
3. **ハンドラのメモ化**: `handleIntervalAdjust` を `useCallback` でラップすることで不要な再生成を防げる可能性がある。

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 実装の大半 | 80%+ |
| 🟡 黄信号 | セクションタイトルテキスト等 | 少数 |
| 🔴 赤信号 | 0 | 0% |
