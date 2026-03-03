# カード AI アシスト入力 タスク概要

**作成日**: 2026-03-03
**推定工数**: 18時間
**総タスク数**: 5件

## 関連文書

- **要件定義書**: [📋 requirements.md](../spec/card-back-ai-assist/requirements.md)
- **設計文書**: [📐 architecture.md](../design/card-back-ai-assist/architecture.md)
- **データフロー図**: [🔄 dataflow.md](../design/card-back-ai-assist/dataflow.md)
- **コンテキストノート**: [📝 note.md](../spec/card-back-ai-assist/note.md)

## フェーズ構成

| フェーズ | 成果物 | タスク数 | 工数 |
|---------|--------|----------|------|
| Phase 1 | バックエンド API 完成 | 3件 | 12h |
| Phase 2 | フロントエンド UI 完成 | 2件 | 6h |

## タスク番号管理

**使用済みタスク番号**: TASK-0137 ~ TASK-0141
**次回開始番号**: TASK-0142

## 全体進捗

- [x] Phase 1: バックエンド実装
- [ ] Phase 2: フロントエンド実装

## マイルストーン

- **M1: API 完成**: バックエンド POST /cards/refine 実装完了
- **M2: UI 完成**: CardForm「AI で補足」ボタン実装完了

---

## Phase 1: バックエンド実装

**目標**: POST /cards/refine API エンドポイント完成
**成果物**: Pydantic モデル、プロンプト定義、AI サービス実装、API ハンドラー

### タスク一覧

- [x] [TASK-0137: Pydantic モデル・プロンプト定義](TASK-0137.md) - 4h (TDD) 🔵
- [x] [TASK-0138: AI サービス refine_card 実装](TASK-0138.md) - 4h (TDD) 🔵
- [x] [TASK-0139: API ハンドラー POST /cards/refine](TASK-0139.md) - 4h (TDD) 🔵

### 依存関係

```
TASK-0137 → TASK-0138 → TASK-0139
```

---

## Phase 2: フロントエンド実装

**目標**: CardForm「AI で補足」ボタン動作完了
**成果物**: TypeScript 型定義、API クライアント、CardForm UI 更新

### タスク一覧

- [ ] [TASK-0140: フロントエンド型定義・API クライアント](TASK-0140.md) - 2h (TDD) 🔵
- [ ] [TASK-0141: CardForm 「AI で補足」ボタン実装](TASK-0141.md) - 4h (TDD) 🔵

### 依存関係

```
TASK-0140 → TASK-0141
```

---

## 信頼性レベルサマリー

### 全タスク統計

- **総タスク数**: 5件
- 🔵 **青信号**: 5件 (100%)
- 🟡 **黄信号**: 0件 (0%)
- 🔴 **赤信号**: 0件 (0%)

### フェーズ別信頼性

| フェーズ | 🔵 青 | 🟡 黄 | 🔴 赤 | 合計 |
|---------|-------|-------|-------|------|
| Phase 1 | 3 | 0 | 0 | 3 |
| Phase 2 | 2 | 0 | 0 | 2 |

**品質評価**: ✅ 高品質

## クリティカルパス

```
TASK-0137 → TASK-0138 → TASK-0139
```

**クリティカルパス工数**: 12時間
**並行作業可能**: Phase 2 (TASK-0140, TASK-0141) は Phase 1 と並行開発可能

## 次のステップ

タスクを実装するには:
- 全タスク順番に実装: `/tsumiki:kairo-implement card-back-ai-assist`
- 特定タスクを実装: `/tsumiki:kairo-implement card-back-ai-assist TASK-0137`
