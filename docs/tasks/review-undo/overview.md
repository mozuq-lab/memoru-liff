# review-undo タスク概要

**作成日**: 2026-02-28
**推定工数**: 26時間
**総タスク数**: 5件

## 関連文書

- **要件定義書**: [requirements.md](../../spec/review-undo/requirements.md)
- **設計文書**: [architecture.md](../../design/review-undo/architecture.md)
- **API仕様**: [api-endpoints.md](../../design/review-undo/api-endpoints.md)
- **インターフェース定義**: [interfaces.ts](../../design/review-undo/interfaces.ts)
- **データフロー図**: [dataflow.md](../../design/review-undo/dataflow.md)

## フェーズ構成

| フェーズ | 成果物 | タスク数 | 工数 | ファイル |
|---------|--------|----------|------|----------|
| Phase 1 | review-undo機能実装 | 5件 | 26h | [TASK-0073~0077](#phase-1-review-undo機能実装) |

## タスク番号管理

**使用済みタスク番号**: TASK-0073 ~ TASK-0077
**次回開始番号**: TASK-0078

## 全体進捗

- [x] Phase 1: review-undo機能実装

## マイルストーン

- **M1: バックエンドAPI完成**: Backend Undo API + ReviewHistoryEntry拡張完了
- **M2: フロントエンド基盤完成**: 型定義・API関数・結果蓄積ロジック完了
- **M3: UI + フロー統合完成**: ReviewComplete UI + Undo/再採点フロー完了

---

## Phase 1: review-undo機能実装

**目標**: 復習完了画面に結果一覧・取り消し・再採点機能を実装
**成果物**: Undo API, ReviewComplete UI, 再採点フロー

### タスク一覧

- [x] [TASK-0073: ReviewHistoryEntry拡張 + submit_review保存値追加](TASK-0073.md) - 4h (TDD) 🔵
- [x] [TASK-0074: Undo API実装](TASK-0074.md) - 6h (TDD) 🔵
- [x] [TASK-0075: 型定義・API関数・ReviewPage結果蓄積](TASK-0075.md) - 4h (TDD) 🔵
- [x] [TASK-0076: ReviewComplete・ReviewResultItem UI実装](TASK-0076.md) - 6h (TDD) 🔵
- [x] [TASK-0077: Undo/再採点フロー統合](TASK-0077.md) - 6h (TDD) 🔵

### 依存関係

```
TASK-0073 → TASK-0074 → TASK-0075 → TASK-0076 → TASK-0077
                ↑                                     ↑
                └─────────────────────────────────────┘
```

---

## 信頼性レベルサマリー

### 全タスク統計

- **総タスク数**: 5件
- 🔵 **青信号**: 5件 (100%)
- 🟡 **黄信号**: 0件 (0%)
- 🔴 **赤信号**: 0件 (0%)

### タスク内項目の信頼性

| タスク | 🔵 青 | 🟡 黄 | 🔴 赤 | 合計 |
|--------|-------|-------|-------|------|
| TASK-0073 | 4 | 0 | 0 | 4 |
| TASK-0074 | 5 | 1 | 0 | 6 |
| TASK-0075 | 5 | 1 | 0 | 6 |
| TASK-0076 | 3 | 2 | 0 | 5 |
| TASK-0077 | 4 | 2 | 0 | 6 |
| **合計** | **21** | **6** | **0** | **27** |

**品質評価**: ✅ 高品質

## クリティカルパス

```
TASK-0073 → TASK-0074 → TASK-0075 → TASK-0076 → TASK-0077
```

**クリティカルパス工数**: 26時間
**並行作業可能工数**: 0時間（全タスクが直列依存）

## 次のステップ

タスクを実装するには:
- 全タスク順番に実装: `/tsumiki:kairo-implement`
- 特定タスクを実装: `/tsumiki:kairo-implement TASK-0073`
