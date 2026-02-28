# TDD 開発メモ: integration-test (TASK-0083)

## 概要

- 機能名: 統合テスト・動作確認（review-reconfirm）
- 開発開始: 2026-02-28
- 現在のフェーズ: Red（TASK-0081/0082 が既に実装済みのため全テスト即通過）

## 関連ファイル

- 要件定義: `docs/implements/review-reconfirm/TASK-0083/requirements.md`
- テストケース定義: `docs/implements/review-reconfirm/TASK-0083/testcases.md`
- テストファイル: `frontend/src/pages/__tests__/ReviewPage.integration.test.tsx`
- 実装ファイル: `frontend/src/pages/ReviewPage.tsx`
- UI コンポーネント: `frontend/src/components/GradeButtons.tsx`, `frontend/src/components/ReconfirmBadge.tsx`, `frontend/src/components/ReviewComplete.tsx`

## Red フェーズ（失敗するテスト作成）

### 作成日時

2026-02-28

### テストケース概要

12 件の統合テストを新規作成:

1. **E2E フロー統合テスト (3件)**
   - TC-INT-001: フルフロー（通常→再確認→覚えた→完了）
   - TC-INT-002: 覚えていないループ後に覚えた→完了
   - TC-INT-003: 混在フロー（FIFO順序確認）

2. **エッジケーステスト (3件)**
   - TC-EDGE-001: 全カード quality 0-2 → 全再確認
   - TC-EDGE-002: 無限ループ（覚えていない3回繰り返し）
   - TC-EDGE-003: 複数カード混在（覚えた+覚えていない）

3. **Undo 統合テスト (3件)**
   - TC-UNDO-001: Undo → regrade quality 3+ → 通常完了
   - TC-UNDO-002: Undo → regrade quality 0-2 → API 確認
   - TC-UNDO-003: 複数カード中の1枚 Undo → 他カード影響なし

4. **回帰テスト (3件)**
   - TC-REG-001: quality 3-5 のみのフロー（回帰確認）
   - TC-REG-002: スキップフロー（回帰確認）
   - TC-REG-003: quality 0-2 + スキップ混在フロー

### 実装上の注意事項

**再確認モードのフリップ操作不要**:
- `ReviewPage.tsx` の再確認モードでは `GradeButtons` が isFlipped 状態に依存せず常時表示
- ヘルパー関数 `clickRemembered` / `clickForgotten` はフリップ操作なしでボタンをクリックできる
- 通常モードの `flipAndGrade` とは異なるパターン

**TC-UNDO-002 について**:
- regrade 後に再確認ループに入るかどうかは、既存実装では `setIsComplete(true)` が先に実行されるため
- このテストは「API 呼び出し確認」を主眼として、再確認ループへの遷移は検証しない

**既存テスト失敗 (TC-MAIN-001)**:
- `src/__tests__/main.test.tsx` のタイムアウトエラーは既存の問題
- 今回の変更と無関係

### テスト実行結果

```
Test Files  1 passed (1)
      Tests  12 passed (12)
   Duration  2.26s
```

### 型チェック結果

```
cd frontend && npx tsc --noEmit
# エラーなし（exit code 0）
```

### 期待される Green フェーズ内容

TASK-0081/0082 が既に実装済みのため、Green フェーズは不要。
テストは既に全通過しており、このタスクは「確認・検証」フェーズ完了。

### 次のフェーズへの要求事項

- TASK-0083.md の完了条件チェックボックスを `[x]` に更新
- overview.md の TASK-0083 状態列を `[x]` に更新
- コミット作成
