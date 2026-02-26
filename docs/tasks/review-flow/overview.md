# review-flow タスク概要

**作成日**: 2026-02-25
**推定工数**: 42時間
**総タスク数**: 7件

## 関連文書

- **要件定義書**: [📋 requirements.md](../../spec/review-flow/requirements.md)
- **設計文書**: [📐 architecture.md](../../design/review-flow/architecture.md)
- **インターフェース定義**: [📝 interfaces.ts](../../design/review-flow/interfaces.ts)
- **データフロー図**: [🔄 dataflow.md](../../design/review-flow/dataflow.md)
- **コンテキストノート**: [📝 note.md](../../spec/review-flow/note.md)

## フェーズ構成

| フェーズ | 成果物 | タスク数 | 工数 | ファイル |
|---------|--------|----------|------|----------|
| Phase 1 | 基盤コンポーネント（FlipCard, GradeButtons, ReviewProgress, ReviewComplete） | 4件 | 22h | [TASK-0066~0069](#phase-1-基盤コンポーネント実装) |
| Phase 2 | ReviewPage統合、ルーティング、統合テスト | 3件 | 20h | [TASK-0070~0072](#phase-2-ページ統合ナビゲーション) |

## タスク番号管理

**使用済みタスク番号**: TASK-0066 ~ TASK-0072
**次回開始番号**: TASK-0073

## 全体進捗

- [x] Phase 1: 基盤コンポーネント実装 (TASK-0066 ~ TASK-0069)
- [x] Phase 2: ページ統合・ナビゲーション (TASK-0070 ~ TASK-0072)

## マイルストーン

- **M1: コンポーネント完成**: FlipCard, GradeButtons, ReviewProgress, ReviewComplete の単体テスト完了
- **M2: 復習画面完成**: ReviewPage 統合・ナビゲーション・全テスト完了

---

## Phase 1: 基盤コンポーネント実装

**目標**: 復習画面を構成する4つの基盤コンポーネントを個別に TDD で実装する
**成果物**: FlipCard, GradeButtons, ReviewProgress, ReviewComplete コンポーネント + 単体テスト

### タスク一覧

- [x] [TASK-0066: FlipCard コンポーネント + フリップアニメーション CSS](TASK-0066.md) - 8h (TDD) 🔵
- [x] [TASK-0067: GradeButtons 採点ボタンコンポーネント](TASK-0067.md) - 6h (TDD) 🔵
- [x] [TASK-0068: ReviewProgress 進捗バーコンポーネント](TASK-0068.md) - 4h (TDD) 🔵
- [x] [TASK-0069: ReviewComplete 復習完了画面コンポーネント](TASK-0069.md) - 4h (TDD) 🔵

### 依存関係

```
TASK-0066 ─┐
TASK-0067 ─┤
TASK-0068 ─┼──► TASK-0070 (Phase 2)
TASK-0069 ─┘
```

**Note**: Phase 1 の4タスクはすべて独立しており、並行実装可能。

---

## Phase 2: ページ統合・ナビゲーション

**目標**: Phase 1 のコンポーネントを統合し、ルーティング・既存ページ変更・統合テストを行う
**成果物**: ReviewPage、ルーティング設定、既存ページ変更、統合テスト

### タスク一覧

- [x] [TASK-0070: ReviewPage メインコンポーネント](TASK-0070.md) - 8h (TDD) 🔵
- [x] [TASK-0071: ルーティング追加 + 既存ページ変更](TASK-0071.md) - 6h (TDD) 🔵
- [x] [TASK-0072: 統合テスト + アクセシビリティ確認](TASK-0072.md) - 6h (TDD) 🟡

### 依存関係

```
TASK-0070 → TASK-0071 → TASK-0072
```

---

## 信頼性レベルサマリー

### 全タスク統計

- **総タスク数**: 7件
- 🔵 **青信号**: 6件 (86%)
- 🟡 **黄信号**: 1件 (14%)
- 🔴 **赤信号**: 0件 (0%)

### フェーズ別信頼性

| フェーズ | 🔵 青 | 🟡 黄 | 🔴 赤 | 合計 |
|---------|-------|-------|-------|------|
| Phase 1 | 4 | 0 | 0 | 4 |
| Phase 2 | 2 | 1 | 0 | 3 |

**品質評価**: ✅ 高品質（青信号が86%。黄信号は統合テスト・アクセシビリティのエッジケース詳細のみ）

## クリティカルパス

```
TASK-0066 → TASK-0070 → TASK-0071 → TASK-0072
```

**クリティカルパス工数**: 28時間
**並行作業可能工数**: 14時間（Phase 1 の TASK-0067, 0068, 0069）

## 次のステップ

タスクを実装するには:
- 全タスク順番に実装: `/tsumiki:kairo-implement`
- 特定タスクを実装: `/tsumiki:kairo-implement TASK-0066`
