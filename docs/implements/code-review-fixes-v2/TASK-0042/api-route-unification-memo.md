# TASK-0042: API ルート統一 - 開発履歴メモ

**作成日**: 2026-02-21
**要件名**: code-review-fixes-v2

---

## 概要

| 項目 | 内容 |
|------|------|
| タスク | APIルートの統一（SAMテンプレート、Lambdaハンドラー、フロントエンドAPIクライアントの3層） |
| 現在のフェーズ | **完了**（Refactorフェーズ終了） |
| 担当要件 | REQ-V2-001, REQ-V2-002, REQ-V2-003, REQ-V2-004 |

---

## フェーズ別記録

### Red フェーズ（テスト先行実装）

- `backend/tests/test_template_routes.py` 作成
- `frontend/src/services/__tests__/api.test.ts` に TASK-0042 テスト追加（TC-042-11 〜 TC-042-36）
- 当初のテストは意図的に FAIL することを確認

### Green フェーズ（最小実装で PASS）

**修正 1: SAM テンプレート (`backend/template.yaml`)**
- `UpdateUser`: パスを `/users/me` → `/users/me/settings` に変更
- `SubmitReview`: パスを `/reviews` → `/reviews/{cardId}` に変更
- `LinkLine`: 新規イベント `/users/link-line` (POST) を追加

**修正 2: フロントエンド API クライアント (`frontend/src/services/api.ts`)**
- `linkLine()`: パスを `/users/me/link-line` → `/users/link-line` に変更

**テスト結果**: バックエンド 25/25、フロントエンド 26/26 PASS

### Refactor フェーズ（2026-02-21）

**改善内容**:

1. `backend/tests/test_template_routes.py`
   - モジュール docstring から TDD Redフェーズの記述を削除し現状を正確に表現
   - 各テスト docstring から「修正前/修正後」の FAIL/PASS 記述を削除

2. `frontend/src/services/api.ts`
   - `submitReview()`: `this.request<void>(...)` の型引数を明示
   - コメントを英語から日本語に統一（`// Cards API` → `// カード API` 等）

**テスト結果（リファクタリング後）**: バックエンド 25/25、フロントエンド 26/26 PASS（リグレッションなし）

---

## 最終コード状態

### `backend/tests/test_template_routes.py`（主要部分）

```python
"""
TC-042: SAM テンプレート API ルート検証テスト

対応要件: REQ-V2-001, REQ-V2-002, REQ-V2-003, REQ-V2-004

テスト方針:
- backend/template.yaml を YAML としてパースし、ApiFunction の HttpApi イベント定義を静的に検証する
- backend/src/api/handler.py のソースコードから @app.<method>() デコレータのパスを正規表現で抽出し、
  SAM テンプレートとの整合性を検証する
- 3レイヤー（SAM / handler / frontend）の API パスが完全一致することを保証する
"""
```

### `frontend/src/services/api.ts`（修正エンドポイント）

```typescript
// レビュー API
async submitReview(cardId: string, grade: number): Promise<void> {
  await this.request<void>(`/reviews/${cardId}`, {
    method: 'POST',
    body: JSON.stringify({ grade }),
  });
}

// ユーザー API
async updateUser(data: UpdateUserRequest): Promise<User> {
  return this.request<User>('/users/me/settings', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

async linkLine(data: LinkLineRequest): Promise<User> {
  return this.request<User>('/users/link-line', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}
```

---

## 品質評価

| 評価項目 | 評価 | 詳細 |
|--------|------|------|
| テスト成功状況 | ✅ | バックエンド 25/25、フロントエンド 26/26 |
| セキュリティ | ✅ | 重大な脆弱性なし |
| パフォーマンス | ✅ | 重大な性能課題なし |
| リファクタ品質 | ✅ | TDD フェーズ記述削除・型注釈追加・コメント日本語化 |
| コード品質 | ✅ | 適切なレベル |
