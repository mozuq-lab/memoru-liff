# learning-stats-dashboard タスク概要

**作成日**: 2026-03-05
**推定工数**: 19時間
**総タスク数**: 6件

## 関連文書

- **要件定義書**: [requirements.md](../../spec/learning-stats-dashboard/requirements.md)
- **設計文書**: [architecture.md](../../design/learning-stats-dashboard/architecture.md)

## フェーズ構成

| フェーズ | 成果物 | タスク数 | 工数 | ファイル |
|---------|--------|----------|------|----------|
| Phase 1 | バックエンド API | 2件 | 7h | [TASK-0151~0152](#phase-1-バックエンド-api) |
| Phase 2 | フロントエンド UI | 3件 | 10h | [TASK-0153~0155](#phase-2-フロントエンド-ui) |
| Phase 3 | 統合 | 1件 | 2h | [TASK-0156](#phase-3-統合) |

## タスク番号管理

**使用済みタスク番号**: TASK-0151 ~ TASK-0156
**次回開始番号**: TASK-0157

## 全体進捗

- [ ] Phase 1: バックエンド API
- [ ] Phase 2: フロントエンド UI
- [ ] Phase 3: 統合

## マイルストーン

- **M1: バックエンド API 完成**: StatsService + stats_handler 完了
- **M2: フロントエンド基盤完成**: 型定義・API関数・useStats フック完了
- **M3: UI + ナビゲーション統合完成**: StatsPage + ナビゲーション統合完了

---

## Phase 1: バックエンド API

**目標**: 学習統計データを提供する API エンドポイントを実装
**成果物**: StatsService, stats_handler, Pydantic モデル

### タスク一覧

- [ ] [TASK-0151: バックエンド Pydantic モデル + StatsService](TASK-0151.md) - 4h (TDD) 🔵
- [x] [TASK-0152: バックエンド stats_handler + handler.py 登録](TASK-0152.md) - 3h (TDD) 🔵

### 依存関係

```
TASK-0151 → TASK-0152 → TASK-0156
```

---

## Phase 2: フロントエンド UI

**目標**: 学習統計ダッシュボード UI を実装
**成果物**: StatsPage, 統計コンポーネント群, useStats フック

### タスク一覧

- [x] [TASK-0153: フロントエンド型定義 + API サービス + useStats フック](TASK-0153.md) - 3h (TDD) 🔵
- [x] [TASK-0154: フロントエンド StatsPage + コンポーネント実装](TASK-0154.md) - 5h (TDD) 🔵
- [x] [TASK-0155: ナビゲーション統合 + ルーティング](TASK-0155.md) - 2h (TDD) 🔵

### 依存関係

```
TASK-0153 → TASK-0154 → TASK-0155 → TASK-0156
```

---

## Phase 3: 統合

**目標**: SAM template 更新と統合テストで全体動作を確認
**成果物**: SAM ルート定義, 統合テスト

### タスク一覧

- [ ] [TASK-0156: SAM template 更新 + 統合テスト](TASK-0156.md) - 2h (DIRECT) 🔵

### 依存関係

```
TASK-0152 ──┐
            ├→ TASK-0156
TASK-0155 ──┘
```

---

## 信頼性レベルサマリー

### 全タスク統計

- **総タスク数**: 6件
- 🔵 **青信号**: 6件 (100%)
- 🟡 **黄信号**: 0件 (0%)
- 🔴 **赤信号**: 0件 (0%)

### タスク内項目の信頼性

| タスク | 🔵 青 | 🟡 黄 | 🔴 赤 | 合計 |
|--------|-------|-------|-------|------|
| TASK-0151 | 4 | 0 | 0 | 4 |
| TASK-0152 | 3 | 0 | 0 | 3 |
| TASK-0153 | 4 | 0 | 0 | 4 |
| TASK-0154 | 5 | 0 | 0 | 5 |
| TASK-0155 | 3 | 0 | 0 | 3 |
| TASK-0156 | 2 | 0 | 0 | 2 |
| **合計** | **21** | **0** | **0** | **21** |

**品質評価**: ✅ 高品質

## クリティカルパス

```
TASK-0151 → TASK-0152 ──┐
                        ├→ TASK-0156
TASK-0153 → TASK-0154 → TASK-0155 ──┘
```

**クリティカルパス工数**: 12時間（TASK-0153 → 0154 → 0155 → 0156）
**並行作業可能工数**: 7時間（Phase 1 と Phase 2 は並行可能）

## 次のステップ

タスクを実装するには:
- 全タスク順番に実装: `/tsumiki:kairo-implement`
- 特定タスクを実装: `/tsumiki:kairo-implement TASK-0151`
