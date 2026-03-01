# deck-review-fixes タスク概要

**作成日**: 2026-03-01
**推定工数**: 47時間
**総タスク数**: 15件

## 関連文書

- **要件定義書**: [📋 requirements.md](../../spec/deck-review-fixes/requirements.md)
- **設計文書**: [📐 architecture.md](../../design/deck-review-fixes/architecture.md)
- **データフロー図**: [🔄 dataflow.md](../../design/deck-review-fixes/dataflow.md)
- **インターフェース定義**: [📝 interfaces.ts](../../design/deck-review-fixes/interfaces.ts)
- **設計ヒアリング記録**: [💬 design-interview.md](../../design/deck-review-fixes/design-interview.md)
- **コンテキストノート**: [📝 note.md](../../spec/deck-review-fixes/note.md)

## フェーズ構成

| フェーズ | 成果物 | タスク数 | 工数 | ファイル |
|---------|--------|----------|------|----------|
| Phase 1 | バックエンド基盤 + High修正 | 4件 | 16h | [TASK-0084~0087](#phase-1-バックエンド基盤--high修正) |
| Phase 2 | バックエンド Med/Low + フロントエンド High | 5件 | 16h | [TASK-0088~0092](#phase-2-バックエンド-mediumlow--フロントエンド-high) |
| Phase 3 | フロントエンド Med/Low + 統合テスト | 6件 | 15h | [TASK-0093~0098](#phase-3-フロントエンド-mediumlow--統合テスト) |

## タスク番号管理

**使用済みタスク番号**: TASK-0084 ~ TASK-0098
**次回開始番号**: TASK-0099

## 全体進捗

- [ ] Phase 1: バックエンド基盤 + High修正
- [ ] Phase 2: バックエンド Medium/Low + フロントエンド High
- [ ] Phase 3: フロントエンド Medium/Low + 統合テスト

## マイルストーン

- **M1: バックエンド基盤完成**: handler.py 分割 + Sentinel パターン + アトミック検証 + HTTP 409
- **M2: 全バックエンド修正完了**: total_due_count + REMOVE パターン + FE High 修正
- **M3: 全修正完了**: フロントエンド Medium/Low + 統合テスト完了

---

## Phase 1: バックエンド基盤 + High修正

**目標**: handler.py のルーター分割と High 優先度のバックエンド修正を完了
**成果物**: 分割された handler + Sentinel パターン + アトミックデッキ制限 + HTTP 409

### タスク一覧

- [ ] [TASK-0084: handler.py ルーター分割](TASK-0084.md) - 6h (TDD) 🔵
- [ ] [TASK-0085: Sentinel パターン導入 + deck_id REMOVE](TASK-0085.md) - 4h (TDD) 🔵
- [ ] [TASK-0086: デッキ数制限アトミック検証](TASK-0086.md) - 4h (TDD) 🔵
- [ ] [TASK-0087: DeckLimitExceededError HTTP 409](TASK-0087.md) - 2h (TDD) 🔵

### 依存関係

```
TASK-0084 → TASK-0085
TASK-0084 → TASK-0086
TASK-0084 + TASK-0086 → TASK-0087
```

---

## Phase 2: バックエンド Medium/Low + フロントエンド High

**目標**: 残りのバックエンド修正と High 優先度のフロントエンド修正を完了
**成果物**: total_due_count 修正 + description/color REMOVE + CardsPage フィルタ + null 送信

### タスク一覧

- [ ] [TASK-0088: total_due_count 修正](TASK-0088.md) - 3h (TDD) 🔵
- [ ] [TASK-0089: description/color REMOVE](TASK-0089.md) - 3h (TDD) 🔵
- [ ] [TASK-0090: TODO コメント追加](TASK-0090.md) - 1h (DIRECT) 🔵
- [ ] [TASK-0091: CardsPage deck_id フィルタ対応](TASK-0091.md) - 5h (TDD) 🔵
- [ ] [TASK-0092: フロントエンド型修正 + null 送信](TASK-0092.md) - 4h (TDD) 🔵

### 依存関係

```
TASK-0084 → TASK-0088
TASK-0085 → TASK-0089
TASK-0084 → TASK-0090
TASK-0084 → TASK-0091
TASK-0085 → TASK-0092
```

---

## Phase 3: フロントエンド Medium/Low + 統合テスト

**目標**: 残りのフロントエンド修正と全体の統合テストを完了
**成果物**: Provider 修正 + 差分送信 + コードクリーンアップ + 統合テスト

### タスク一覧

- [ ] [TASK-0093: App.tsx Provider 順序修正](TASK-0093.md) - 2h (TDD) 🟡
- [ ] [TASK-0094: DeckFormModal 差分送信](TASK-0094.md) - 4h (TDD) 🔵
- [ ] [TASK-0095: unassigned フィルタ削除](TASK-0095.md) - 1h (DIRECT) 🔵
- [ ] [TASK-0096: JSDoc コメントスタイル統一](TASK-0096.md) - 2h (DIRECT) 🟡
- [ ] [TASK-0097: CardDetailPage fetchDecks 呼び出し](TASK-0097.md) - 2h (TDD) 🔵
- [ ] [TASK-0098: 統合テスト](TASK-0098.md) - 4h (TDD) 🟡

### 依存関係

```
TASK-0089 → TASK-0094
TASK-0092 → TASK-0097
TASK-0087 + TASK-0088 + TASK-0091 + TASK-0092 + TASK-0093 + TASK-0094 + TASK-0097 → TASK-0098
```

---

## 信頼性レベルサマリー

### 全タスク統計

- **総タスク数**: 15件
- 🔵 **青信号**: 12件 (80%)
- 🟡 **黄信号**: 3件 (20%)
- 🔴 **赤信号**: 0件 (0%)

### フェーズ別信頼性

| フェーズ | 🔵 青 | 🟡 黄 | 🔴 赤 | 合計 |
|---------|-------|-------|-------|------|
| Phase 1 | 4 | 0 | 0 | 4 |
| Phase 2 | 5 | 0 | 0 | 5 |
| Phase 3 | 3 | 3 | 0 | 6 |

**品質評価**: ✅ 高品質

## クリティカルパス

```
TASK-0084 → TASK-0085 → TASK-0092 → TASK-0097 → TASK-0098
```

**クリティカルパス工数**: 20時間
**並行作業可能工数**: 27時間

## 次のステップ

タスクを実装するには:
- 全タスク順番に実装: `/tsumiki:kairo-implement`
- 特定タスクを実装: `/tsumiki:kairo-implement TASK-0084`
