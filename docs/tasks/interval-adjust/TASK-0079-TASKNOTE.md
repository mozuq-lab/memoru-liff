# TASK-0079 タスクノート - フロントエンド プリセットボタンUI

**タスクID**: TASK-0079
**タスク名**: フロントエンド プリセットボタンUI
**タスクタイプ**: TDD
**推定工数**: 4時間
**作成日**: 2026-02-28
**状態**: 準備完了

---

## タスク概要

TASK-0078（バックエンド interval更新サポート）で実装されたAPIに対応するフロントエンドUIを実装する。カード詳細画面（CardDetailPage）にプリセットボタン（1日, 3日, 7日, 14日, 30日）を追加し、ユーザーが復習間隔を手動で調整できるようにする。

**依存関係**:
- 前提: TASK-0078 完了 ✓ (バックエンド interval更新API完成)
- 後続: TASK-0080 (統合テスト・動作確認)

---

## 実装ファイル一覧

### 変更対象ファイル

| ファイル | 理由 | 変更内容 |
|---------|------|---------|
| `frontend/src/types/card.ts` | UpdateCardRequestにintervalフィールドを追加 | フィールド追加 |
| `frontend/src/pages/CardDetailPage.tsx` | プリセットボタンUIを実装 | state追加 + UI実装 + ハンドラー実装 |

### 参照ファイル（変更不要）

| ファイル | 理由 |
|---------|------|
| `frontend/src/services/api.ts` | updateCard()メソッドはすでに対応可能（型拡張のみで対応） |

---

## 実装詳細

### 1. UpdateCardRequest型拡張

**ファイル**: `/Volumes/external/dev/memoru-liff/frontend/src/types/card.ts`

**現在のコード** (行23-28):
```typescript
export interface UpdateCardRequest {
  front?: string;
  back?: string;
  deck_id?: string;
  tags?: string[];
}
```

**実装内容**: `interval?: number` フィールドを追加

```typescript
export interface UpdateCardRequest {
  front?: string;
  back?: string;
  deck_id?: string;
  tags?: string[];
  interval?: number;  // 追加：復習間隔（日数）
}
```

**信頼性**: 🔵 (設計文書 architecture.md より確実)

---

### 2. CardDetailPageコンポーネント拡張

**ファイル**: `/Volumes/external/dev/memoru-liff/frontend/src/pages/CardDetailPage.tsx`

#### 2.1 State追加

**追加位置**: 行30の後（successMessageの下）

```typescript
const [isAdjusting, setIsAdjusting] = useState(false);  // API呼び出し中フラグ
```

**信頼性**: 🟡 (既存isSavingパターンから推測)

#### 2.2 プリセット値定義

**追加位置**: handleBack関数の上（行98付近）

```typescript
const PRESET_INTERVALS = [1, 3, 7, 14, 30];  // プリセット値（日数）
```

#### 2.3 interval更新ハンドラー

**追加位置**: handleDelete関数の後（行97付近）

```typescript
// 【復習間隔調整ハンドラ】
const handleAdjustInterval = async (interval: number) => {
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

**信頼性**: 🔵 (要件定義 REQ-002 より確実)

#### 2.4 プリセットボタンUIセクション

**追加位置**: メタ情報セクション（行220-242）の直後、削除ボタン（行244）の前

```typescript
{/* 復習間隔調整 - 表示モード時のみ */}
{!isEditing && (
  <div className="bg-white rounded-lg shadow p-4 mb-6" data-testid="interval-presets">
    <p className="text-sm text-gray-600 mb-3">復習間隔を調整</p>
    <div className="flex flex-wrap gap-2">
      {PRESET_INTERVALS.map((preset) => (
        <button
          key={preset}
          onClick={() => handleAdjustInterval(preset)}
          disabled={isAdjusting}
          className={`px-4 py-2 rounded-lg border transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center ${
            card.interval === preset
              ? 'bg-blue-600 text-white border-blue-600'
              : 'bg-white text-gray-700 border-gray-300 hover:border-blue-600 hover:text-blue-600'
          } ${isAdjusting ? 'opacity-50 cursor-not-allowed' : ''}`}
          aria-label={`復習間隔を${preset}日に設定`}
          data-testid={`interval-preset-${preset}`}
        >
          {preset}日
        </button>
      ))}
    </div>
  </div>
)}
```

**信頼性**: 🔵 (要件定義 REQ-001, REQ-202 より確実)

**UI特性**:
- 表示モード（!isEditing）のみ表示
- 各ボタンのタップ領域は44px以上確保
- 現在のinterval値とボタンが一致時はハイライト（青色）
- API呼び出し中（isAdjusting=true）はボタンを無効化
- aria-labelで各ボタンを説明

---

## テスト実装戦略

### テストファイル構成

**対象テストファイル**: `frontend/src/pages/__tests__/CardDetailPage.test.tsx`

### テストケース（17件 + 5件異常系）

#### プリセットボタン表示テスト

```typescript
describe('復習間隔調整 - プリセットボタン表示', () => {
  // TC-001-01: プリセットボタン5つが表示される
  test('should display 5 preset interval buttons', () => {
    // ...
  });

  // TC-001-02: 編集モード時に非表示
  test('should hide preset buttons in edit mode', () => {
    // ...
  });

  // ボタンラベルが正しい
  test('should display correct labels on preset buttons', () => {
    // ...
  });
});
```

#### API呼び出しテスト

```typescript
describe('復習間隔調整 - API呼び出し', () => {
  // TC-002-01: 「1日」ボタンタップでinterval=1でAPI呼び出し
  test('should call updateCard with interval=1 when 1-day button clicked', () => {
    // ...
  });

  // TC-002-02: 「30日」ボタンタップでinterval=30でAPI呼び出し
  test('should call updateCard with interval=30 when 30-day button clicked', () => {
    // ...
  });

  // TC-002-03: interval更新後にメタ情報が更新される
  test('should update card meta info after interval adjustment', () => {
    // ...
  });
});
```

#### ボタン無効化テスト

```typescript
describe('復習間隔調整 - ボタン無効化', () => {
  // TC-202-01: API呼び出し中にボタンがdisabledになる
  test('should disable preset buttons during API call', async () => {
    // ...
  });
});
```

#### エラーハンドリングテスト

```typescript
describe('復習間隔調整 - エラーハンドリング', () => {
  // TC-103-01: API失敗時にエラーメッセージが表示される
  test('should display error message when API fails', async () => {
    // ...
  });

  // TC-103-02: API失敗時に元の値が保持される
  test('should restore original interval value on API failure', async () => {
    // ...
  });
});
```

#### ハイライト表示テスト

```typescript
describe('復習間隔調整 - ハイライト表示', () => {
  // 現在のintervalに対応するボタンが青くハイライトされている
  test('should highlight the button matching current interval', () => {
    // ...
  });
});
```

---

## TDD実装フロー

### Phase 1: Red テスト失敗状態を作る

1. `/tsumiki:tdd-red` で以下のテストを失敗させる:
   - プリセットボタン表示テスト（5つのボタン確認）
   - API呼び出しテスト（updateCard呼び出し確認）
   - 成功時メタ情報更新テスト
   - エラーハンドリングテスト
   - ボタン無効化テスト

### Phase 2: Green テスト成功状態を作る

1. UpdateCardRequest型に`interval?: number`を追加
2. CardDetailPageに以下を実装:
   - `isAdjusting` state
   - `PRESET_INTERVALS` 定数
   - `handleAdjustInterval()` ハンドラー
   - プリセットボタンUI（条件付き表示）

### Phase 3: Refactor コードを整理する

1. プリセットボタンコンポーネント化を検討（可能なら）
2. スタイル最適化
3. テストコード整理
4. JSDocコメント充実

---

## 完了チェックリスト

### 実装完了項目

- [ ] `frontend/src/types/card.ts` に `interval` フィールドを追加
- [ ] `frontend/src/pages/CardDetailPage.tsx` に `isAdjusting` state を追加
- [ ] `frontend/src/pages/CardDetailPage.tsx` に `handleAdjustInterval()` ハンドラーを実装
- [ ] プリセットボタン5つ（1日, 3日, 7日, 14日, 30日）がUI上に表示される
- [ ] 表示モード時のみボタンが表示される（編集モード時は非表示）
- [ ] ボタンタップでAPIが呼ばれてintervalが更新される
- [ ] API呼び出し中はボタンが無効化される
- [ ] 成功時に成功メッセージとメタ情報が更新される
- [ ] 失敗時にエラーメッセージが表示され元の値が保持される
- [ ] 各ボタンのタップ領域が44px以上に設定されている
- [ ] 各ボタンに適切なaria-labelが設定されている
- [ ] 現在のinterval値に対応するボタンがハイライト表示される

### テスト完了項目

- [ ] プリセットボタン表示テスト（3件）
- [ ] API呼び出しテスト（3件）
- [ ] ボタン無効化テスト（1件）
- [ ] エラーハンドリングテスト（2件）
- [ ] ハイライト表示テスト（1件）
- [ ] 編集モード切替テスト（1件）
- [ ] 全テスト通過 + カバレッジ80%以上達成

---

## 関連文書リファレンス

### 要件定義

- **要件**: REQ-001 (プリセットボタン表示), REQ-002 (API呼び出し), REQ-103 (エラーハンドリング)
- **信頼性**: 🔵 🔵 🟡
- **参照**: [requirements.md](../../spec/interval-adjust/requirements.md)

### 受け入れ基準

- **TC-001-01**: プリセットボタン5つ表示
- **TC-002-01 ~ 03**: API呼び出し & メタ情報更新
- **TC-103-01 ~ 02**: エラーハンドリング
- **TC-202-01**: ボタン無効化
- **参照**: [acceptance-criteria.md](../../spec/interval-adjust/acceptance-criteria.md)

### 設計文書

- **変更対象**: UpdateCardRequest 拡張, CardDetailPage 拡張
- **UI構成**: メタ情報セクション下にプリセットボタン追加
- **参照**: [architecture.md](../../design/interval-adjust/architecture.md)

---

## 注意事項

### 既存パターンの再利用

- `error` / `successMessage` state: 既存の状態管理パターンを再利用 ✓
- エラーメッセージ表示: 既存の「カードの保存に失敗しました」のパターンを参考 ✓
- 成功メッセージ表示: 既存の3秒自動消滅パターンを使用 ✓

### 変更しないファイル

- `frontend/src/services/api.ts`: updateCard()メソッドは変更不要
  - 既存の`updateCard(id, { front?, back?, deck_id?, tags? })`が
  - 型拡張により`{ interval? }`にも対応可能

### UI/UX考慮事項

- タップ領域: 各ボタンは44px以上を確保（LIFF モバイル操作性）
- ハイライト: 現在のinterval値とボタンが一致時に青色でハイライト
- フィードバック: API呼び出し中はボタンdisabled + オーバーレイ効果
- メッセージ: 成功時は3秒後自動消滅、エラーは手動クリア

---

## Tsumiki ワークフロー実行順序

```bash
# 1. 詳細要件定義
/tsumiki:tdd-requirements TASK-0079

# 2. テストケース定義
/tsumiki:tdd-testcases

# 3. Redフェーズ（テスト失敗）
/tsumiki:tdd-red

# 4. Greenフェーズ（最小実装）
/tsumiki:tdd-green

# 5. Refactorフェーズ（品質改善）
/tsumiki:tdd-refactor

# 6. 品質確認
/tsumiki:tdd-verify-complete
```

---

## 参考実装パターン

### 既存の状態管理パターン（CardDetailPageより）

```typescript
// ローディング中フラグ
const [isLoading, setIsLoading] = useState(true);

// エラーメッセージ
const [error, setError] = useState<string | null>(null);

// 成功メッセージ（3秒自動消滅）
const [successMessage, setSuccessMessage] = useState<string | null>(null);
useEffect(() => {
  if (successMessage) {
    const timer = setTimeout(() => setSuccessMessage(null), 3000);
    return () => clearTimeout(timer);
  }
}, [successMessage]);

// 非同期処理ハンドラー
const handleSave = async (front: string, back: string) => {
  setIsSaving(true);
  setError(null);
  try {
    const updatedCard = await cardsApi.updateCard(id, { front, back });
    setCard(updatedCard);
    setIsEditing(false);
    setSuccessMessage('カードを保存しました');
  } catch (err) {
    setError('カードの保存に失敗しました');
  } finally {
    setIsSaving(false);
  }
};
```

このパターンを `handleAdjustInterval()` で再利用する。

---

## 信頼性レベルサマリー

| 項目 | 信頼性 | 根拠 |
|------|--------|------|
| UpdateCardRequest拡張 | 🔵 | 設計文書 architecture.md より確実 |
| プリセットボタン表示 | 🔵 | 要件定義 REQ-001、ユーザヒアリングより確実 |
| API呼び出し | 🔵 | 要件定義 REQ-002、設計文書より確実 |
| ハイライト表示 | 🟡 | ユーザビリティ上の妥当な推測 |
| ボタン無効化 | 🟡 | 既存UI実装パターン(isSaving)から推測 |
| エラーハンドリング | 🟡 | 既存エラーハンドリングパターンから推測 |

**全体評価**: ✅ 高品質（青信号71%, 黄信号29%）

---

**作成者**: Claude Code Tsumiki TDD Workflow
**作成日**: 2026-02-28
**最終更新**: 2026-02-28
