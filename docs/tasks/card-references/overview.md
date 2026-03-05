# Card References タスク概要

**作成日**: 2026-03-05
**推定工数**: 11時間
**総タスク数**: 4件

## 関連文書

- **要件定義書**: [requirements.md](../../spec/card-references/requirements.md)
- **設計文書**: [architecture.md](../../design/card-references/architecture.md)

## フェーズ構成

| フェーズ | 成果物 | タスク数 | 工数 |
| --- | --- | --- | --- |
| Phase 1 | バックエンド（モデル + サービス） | 2件 | 5h |
| Phase 2 | フロントエンド（型定義 + コンポーネント + 統合） | 2件 | 6h |

> Phase 1 と Phase 2 は並行実行可能（TASK-0157/0158 と TASK-0159/0160 は独立）

## タスク番号管理

**使用済みタスク番号**: TASK-0157 ~ TASK-0160
**次回開始番号**: TASK-0161

## 全体進捗

- [ ] Phase 1: バックエンド
- [ ] Phase 2: フロントエンド

---

## Phase 1: バックエンド

**目標**: Reference モデル追加と CardService の参考情報対応
**成果物**: Pydantic モデル拡張 + DynamoDB シリアライズ + サービス層対応

### タスク一覧

| 状態 | タスク | 工数 | タイプ | 概要 |
| --- | --- | --- | --- | --- |
| [ ] | [TASK-0157: Reference モデル + Card モデル拡張](TASK-0157.md) | 3h | TDD | Pydantic モデル + DynamoDB 変換 |
| [ ] | [TASK-0158: CardService 参考情報対応](TASK-0158.md) | 2h | TDD | create/update + 後方互換性 |

### 依存関係

```
TASK-0157 → TASK-0158
```

---

## Phase 2: フロントエンド

**目標**: 参考情報の入力・表示コンポーネントと各ページへの統合
**成果物**: Reference 型定義 + ReferenceEditor/Display + ページ統合

### タスク一覧

| 状態 | タスク | 工数 | タイプ | 概要 |
| --- | --- | --- | --- | --- |
| [ ] | [TASK-0159: 型定義 + ReferenceEditor/Display](TASK-0159.md) | 3h | TDD | 型 + 入力/表示コンポーネント |
| [ ] | [TASK-0160: CardForm + CardDetailPage + ReviewPage 統合](TASK-0160.md) | 3h | TDD | ページ統合 |

### 依存関係

```
TASK-0159 → TASK-0160
```

---

## 全体依存関係図

```
Phase 1 (Backend)           Phase 2 (Frontend)

TASK-0157 ──→ TASK-0158     TASK-0159 ──→ TASK-0160
(モデル)      (サービス)     (型+部品)     (ページ統合)

├─────── 並行実行可能 ────────┤
```

---

## 信頼性レベルサマリー

### 全タスク統計

- **総タスク数**: 4件
- 🔵 **青信号**: 4件 (100%)
- 🟡 **黄信号**: 0件 (0%)
- 🔴 **赤信号**: 0件 (0%)

**品質評価**: ✅ 高品質

## 次のステップ

タスクを実装するには:
- 全タスク順番に実装: `/tsumiki:kairo-implement`
- 特定タスクを実装: `/tsumiki:kairo-implement TASK-0157`
