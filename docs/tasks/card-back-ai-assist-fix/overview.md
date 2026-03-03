# card-back-ai-assist-fix タスク概要

**作成日**: 2026-03-03
**推定工数**: 10時間
**総タスク数**: 4件

## 関連文書

- **要件定義書**: [📋 requirements.md](../../spec/card-back-ai-assist-fix/requirements.md)
- **設計文書**: [📐 architecture.md](../../design/card-back-ai-assist-fix/architecture.md)
- **データフロー図**: [🔄 dataflow.md](../../design/card-back-ai-assist-fix/dataflow.md)
- **コンテキストノート**: [📝 note.md](../../spec/card-back-ai-assist/note.md)
- **コードレビュー**: [📋 card-back-ai-assist-review.md](../../review/card-back-ai-assist-review.md)

## フェーズ構成

| フェーズ | 成果物 | タスク数 | 工数 | ファイル |
|---------|--------|----------|------|----------|
| Phase 1 | レビュー指摘修正 + テスト追加 | 4件 | 10h | [TASK-0142~0145](#phase-1-レビュー修正) |

## タスク番号管理

**使用済みタスク番号**: TASK-0142 ~ TASK-0145
**次回開始番号**: TASK-0146

## 全体進捗

- [ ] Phase 1: レビュー修正

---

## Phase 1: レビュー修正

**目標**: コードレビュー指摘事項の修正とテストカバレッジの向上
**成果物**: 修正コード + テスト追加

### タスク一覧

- [ ] [TASK-0142: refine プロンプト ja/en テンプレート分岐 + テスト](TASK-0142.md) - 4h (TDD) 🔵
- [ ] [TASK-0143: body=null TypeError 対策 + テスト](TASK-0143.md) - 2h (TDD) 🔵
- [ ] [TASK-0144: CardForm useEffect cleanup + テスト](TASK-0144.md) - 1h (TDD) 🔵
- [ ] [TASK-0145: BedrockService refine テスト追加](TASK-0145.md) - 3h (TDD) 🔵

### 依存関係

```
すべてのタスクは独立しており、並行実行可能
TASK-0142 (独立)
TASK-0143 (独立)
TASK-0144 (独立)
TASK-0145 (独立)
```

### 要件カバレッジ

| タスク | カバーする要件 |
|--------|--------------|
| TASK-0142 | REQ-FIX-001, REQ-FIX-002, REQ-TEST-001 |
| TASK-0143 | REQ-FIX-003, REQ-FIX-004, REQ-TEST-002, REQ-TEST-003 |
| TASK-0144 | REQ-FIX-005, REQ-TEST-005 |
| TASK-0145 | REQ-TEST-004 |

---

## 信頼性レベルサマリー

### 全タスク統計

- **総タスク数**: 4件
- 🔵 **青信号**: 4件 (100%)
- 🟡 **黄信号**: 0件 (0%)
- 🔴 **赤信号**: 0件 (0%)

### タスク内項目の信頼性

| タスク | 🔵 青 | 🟡 黄 | 🔴 赤 | 合計 |
|--------|-------|-------|-------|------|
| TASK-0142 | 4 | 1 | 0 | 5 |
| TASK-0143 | 3 | 0 | 0 | 3 |
| TASK-0144 | 1 | 1 | 0 | 2 |
| TASK-0145 | 3 | 0 | 0 | 3 |
| **合計** | **11** | **2** | **0** | **13** |

**品質評価**: ✅ 高品質

## クリティカルパス

すべてのタスクが独立のため、クリティカルパスは最も工数の大きいタスク:
```
TASK-0142 (4h) が最長パス
```

**クリティカルパス工数**: 4時間
**並行作業可能工数**: 6時間（TASK-0143 + TASK-0144 + TASK-0145）

## 次のステップ

タスクを実装するには:
- 全タスク順番に実装: `/tsumiki:kairo-implement`
- 特定タスクを実装: `/tsumiki:kairo-implement TASK-0142`
