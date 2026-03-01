# card-search-review-fixes タスク概要

**作成日**: 2026-03-01
**推定工数**: 10時間
**総タスク数**: 3件

## 関連文書

- **要件定義書**: [📋 requirements.md](../../spec/card-search-review-fixes/requirements.md)
- **設計文書**: [📐 architecture.md](../../design/card-search-review-fixes/architecture.md)
- **データフロー図**: [🔄 dataflow.md](../../design/card-search-review-fixes/dataflow.md)
- **設計ヒアリング記録**: [💬 design-interview.md](../../design/card-search-review-fixes/design-interview.md)
- **要件ヒアリング記録**: [💬 interview-record.md](../../spec/card-search-review-fixes/interview-record.md)

## フェーズ構成

| フェーズ | 成果物 | タスク数 | 工数 | ファイル |
|---------|--------|----------|------|----------|
| Phase 1 | フロントエンド修正 + 統合テスト | 3件 | 10h | [TASK-0099~0101](#phase-1-フロントエンド修正) |

## タスク番号管理

**使用済みタスク番号**: TASK-0099 ~ TASK-0101
**次回開始番号**: TASK-0102

## 全体進捗

- [x] Phase 1: フロントエンド修正

## マイルストーン

- **M1: 全修正完了**: 基盤修正 + コンポーネント修正 + 統合テスト完了

---

## Phase 1: フロントエンド修正

**目標**: PR #2 コードレビュー指摘の全項目を修正し、統合テストを追加する
**成果物**: normalize共通化、reset メモ化、FilterChips条件表示、型ガード、統合テスト

### タスク一覧

- [x] [TASK-0099: 基盤修正（normalize共通化 + reset useCallback + デッドコード削除）](TASK-0099.md) - 3h (TDD) 🔵
- [x] [TASK-0100: コンポーネント修正（FilterChips条件表示 + SortSelect型ガード + role属性）](TASK-0100.md) - 3h (TDD) 🔵
- [x] [TASK-0101: 統合テスト（CardsPage + CardList）](TASK-0101.md) - 4h (TDD) 🔵

### 依存関係

```
TASK-0099 ──┐
            ├──→ TASK-0101
TASK-0100 ──┘
```

TASK-0099 と TASK-0100 は並行実行可能。TASK-0101 は両方の完了後に実行。

---

## 信頼性レベルサマリー

### 全タスク統計

- **総タスク数**: 3件
- 🔵 **青信号**: 3件 (100%)
- 🟡 **黄信号**: 0件 (0%)
- 🔴 **赤信号**: 0件 (0%)

### タスク別信頼性（項目レベル）

| タスク | 🔵 青 | 🟡 黄 | 🔴 赤 | 合計 |
|-------|-------|-------|-------|------|
| TASK-0099 | 6 | 0 | 0 | 6 |
| TASK-0100 | 2 | 4 | 0 | 6 |
| TASK-0101 | 4 | 0 | 0 | 4 |
| **合計** | **12** | **4** | **0** | **16** |

**品質評価**: ✅ 高品質

## クリティカルパス

```
TASK-0099 → TASK-0101
```

**クリティカルパス工数**: 7時間
**並行作業可能工数**: 3時間（TASK-0100）

## 次のステップ

タスクを実装するには:
- 全タスク順番に実装: `/tsumiki:kairo-implement`
- 特定タスクを実装: `/tsumiki:kairo-implement TASK-0099`
