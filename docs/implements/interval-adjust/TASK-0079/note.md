# TASK-0079 開発コンテキストノート

**タスク**: フロントエンド プリセットボタンUI
**要件名**: interval-adjust
**作成日**: 2026-02-28

---

## 1. 技術スタック

### 使用技術・フレームワーク
- **React 18** + **TypeScript** - フロントエンドフレームワーク
- **Vite** - ビルドツール
- **Vitest** + **@testing-library/react** - テストフレームワーク
- **userEvent** - ユーザーインタラクションテスト
- **react-router-dom** - ルーティング（useParams, useNavigate）
- **Tailwind CSS** - スタイリング（ユーティリティクラス）

### アーキテクチャパターン
- **ページコンポーネントパターン**: `pages/CardDetailPage.tsx` がページ単位の状態管理を担当
- **APIサービスレイヤー**: `services/api.ts` の `cardsApi` オブジェクトでAPI呼び出しを一元管理
- **型定義分離**: `types/card.ts` にリクエスト/レスポンス型を定義
- **状態管理**: useState ベースのローカルステート（Context不使用）

### 参照元
- `CLAUDE.md`
- `docs/design/interval-adjust/architecture.md`

---

## 2. 開発ルール

### コーディング規約
- コミットメッセージ形式: `TASK-XXXX: タスク名` + 箇条書き + Co-Authored-By
- タスクごとにコミット（複数タスクをまとめない）
- テストカバレッジ 80% 以上を目標

### テスト要件
- TDD で開発（Red -> Green -> Refactor）
- Vitest + @testing-library/react + userEvent でコンポーネントテスト
- `vi.mock` で API モジュールをモック
- `MemoryRouter` でルーティングをラップ
- `data-testid` 属性でテスト対象要素を特定

### 型チェック
- TypeScript strict mode
- インターフェースで Optional フィールドは `?` を使用
- `type` インポートを使用（`import type { ... }`）

### 参照元
- `CLAUDE.md`

---

## 3. 関連実装

### 3.1 UpdateCardRequest（変更対象）

**ファイル**: `frontend/src/types/card.ts`

現在のインターフェース:
```typescript
export interface UpdateCardRequest {
  front?: string;
  back?: string;
  deck_id?: string;
  tags?: string[];
}
```

追加するフィールド:
```typescript
interval?: number;  // 追加
```

### 3.2 CardDetailPage（変更対象）

**ファイル**: `frontend/src/pages/CardDetailPage.tsx`

現在の状態管理:
```typescript
const [card, setCard] = useState<Card | null>(null);
const [isLoading, setIsLoading] = useState(true);
const [isEditing, setIsEditing] = useState(false);
const [isSaving, setIsSaving] = useState(false);
const [isDeleting, setIsDeleting] = useState(false);
const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
const [error, setError] = useState<string | null>(null);
const [successMessage, setSuccessMessage] = useState<string | null>(null);
```

追加する状態:
```typescript
const [isAdjusting, setIsAdjusting] = useState(false);
```

既存のパターン（handleSave）を参考にしたイベントフロー:
1. `setIsAdjusting(true)` + `setError(null)`
2. `cardsApi.updateCard(id, { interval })` 呼び出し
3. 成功時: `setCard(updatedCard)` + `setSuccessMessage('復習間隔を更新しました')`
4. 失敗時: `setError('復習間隔の更新に失敗しました')`
5. finally: `setIsAdjusting(false)`

UIの配置場所: `data-testid="card-meta"` のメタ情報セクションの下、削除ボタンの上

### 3.3 cardsApi.updateCard（変更不要）

**ファイル**: `frontend/src/services/api.ts`

```typescript
async updateCard(id: string, data: UpdateCardRequest): Promise<Card> {
  return this.request<Card>(`/cards/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}
```

UpdateCardRequest の型拡張のみで対応可能。メソッド自体の変更は不要。

### 3.4 既存テストパターン（参考）

**ファイル**: `frontend/src/pages/__tests__/CardDetailPage.test.tsx`

テスト構造:
- `vi.mock('@/services/api', ...)` で cardsApi をモック
- `vi.mock('react-router-dom', ...)` で useNavigate をモック
- `vi.mock('@/components/Navigation', ...)` で Navigation をモック
- `mockCard` オブジェクトでテストデータを定義（interval=7, repetitions=3）
- `renderCardDetailPage()` ヘルパー関数で MemoryRouter + Routes ラップ
- `waitFor` で非同期操作の完了を待機
- `userEvent.setup()` でユーザーインタラクションをシミュレート

成功メッセージテストパターン:
```typescript
await waitFor(() => {
  expect(screen.getByTestId('success-message')).toHaveTextContent('カードを保存しました');
});
```

エラーメッセージテストパターン:
```typescript
mockUpdateCard.mockRejectedValue(new Error('保存エラー'));
// ...
await waitFor(() => {
  expect(screen.getByTestId('error-message')).toHaveTextContent('カードの保存に失敗しました');
});
```

### 3.5 Card型（参照用）

**ファイル**: `frontend/src/types/card.ts`

```typescript
export interface Card {
  card_id: string;
  user_id: string;
  front: string;
  back: string;
  deck_id?: string | null;
  tags: string[];
  next_review_at?: string | null;
  interval: number;
  ease_factor: number;
  repetitions: number;
  created_at: string;
  updated_at?: string | null;
}
```

### 参照元
- `frontend/src/types/card.ts`
- `frontend/src/pages/CardDetailPage.tsx`
- `frontend/src/services/api.ts`
- `frontend/src/pages/__tests__/CardDetailPage.test.tsx`

---

## 4. 設計文書

### UI設計

プリセットボタンの配置:
```
+-----------------------------+
| メタ情報                      |
|   次回復習日: 2026-03-07       |
|   復習間隔: 7日                |
+-----------------------------+
| 復習間隔を調整                 |
| [1日] [3日] [7日] [14日] [30日] |
+-----------------------------+
| [カードを削除]                 |
+-----------------------------+
```

プリセット値: `[1, 3, 7, 14, 30]`
ボタンテキスト: `{N}日`
セクションタイトル: 「復習間隔を調整」
タップ領域: 44px以上

### データフロー（正常系）

1. ユーザーがプリセットボタンタップ
2. `setIsAdjusting(true)` + 全ボタン disabled
3. `cardsApi.updateCard(cardId, { interval: N })` 呼び出し
4. バックエンド: interval + next_review_at 更新（ease_factor, repetitions 不変）
5. レスポンス: 更新後の Card オブジェクト
6. `setCard(updatedCard)` + `setSuccessMessage('復習間隔を更新しました')`
7. `setIsAdjusting(false)`

### データフロー（エラー系）

1. ユーザーがプリセットボタンタップ
2. `setIsAdjusting(true)`
3. API呼び出し失敗
4. `setError('復習間隔の更新に失敗しました')`
5. `setIsAdjusting(false)` - カードデータは変更前のまま

### 状態遷移

- 表示モード -> 調整中: プリセットボタンタップ
- 調整中 -> 表示モード: API成功（successMessage 表示）
- 調整中 -> 表示モード: APIエラー（error 表示）
- 表示モード -> 編集モード: 編集ボタン
- 編集モード: プリセットボタン非表示

### API仕様

`PUT /cards/:card_id` - カード更新（既存エンドポイント拡張）
- リクエスト: `{ interval?: number }` を追加（1-365）
- レスポンス: 更新後の Card オブジェクト（interval, next_review_at が新しい値）

### 参照元
- `docs/design/interval-adjust/architecture.md`
- `docs/design/interval-adjust/dataflow.md`
- `docs/spec/interval-adjust/requirements.md`
- `docs/spec/interval-adjust/acceptance-criteria.md`

---

## 5. 注意事項

### 技術的制約

1. **api.ts の変更不要**: `cardsApi.updateCard` メソッドは `UpdateCardRequest` をそのまま `JSON.stringify` するため、型定義の拡張のみで対応可能
2. **既存 state の再利用**: `error` と `successMessage` は既存の state を再利用。新規追加は `isAdjusting` のみ
3. **プリセットボタンのタップ領域**: 44px 以上を確保（LINE LIFF のモバイル操作性。既存の `min-h-[44px] min-w-[44px]` パターンに従う）
4. **成功メッセージの自動非表示**: 既存の `useEffect` で 3000ms 後に `setSuccessMessage(null)` するロジックが再利用される

### 編集モードとの排他制御

- `isEditing === true` の場合、プリセットボタンセクションは非表示
- プリセットボタンは表示モード（`isEditing === false`）でのみレンダリング
- 既存の条件分岐 `{isEditing ? <CardForm .../> : <> ... </>}` の `<>` 内に配置

### テスト上の注意

- 既存の `CardDetailPage.test.tsx` に追記する形でテストを追加
- `mockUpdateCard` は既にモック済み。返却値を適切に設定するだけで interval 更新テストが可能
- API呼び出し中のボタン無効化テストは `mockUpdateCard` を `new Promise(() => {})` で保留させるパターンを使用

### アクセシビリティ

- プリセットボタンに `aria-label="復習間隔を{N}日に設定"` を設定
- `data-testid="preset-button-{N}"` でテスト用識別子を設定

### 参照元
- `docs/tasks/interval-adjust/TASK-0079.md`（注意事項セクション）
- `docs/design/interval-adjust/architecture.md`（フロントエンド変更セクション）
- `docs/spec/interval-adjust/requirements.md`（REQ-201, REQ-202, NFR-202, NFR-301）
