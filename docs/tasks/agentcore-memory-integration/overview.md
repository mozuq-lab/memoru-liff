# AgentCore Memory 統合 タスク概要

**作成日**: 2026-03-07
**推定工数**: 54時間
**総タスク数**: 10件

## 関連文書

- **要件定義書**: [📋 requirements.md](../../spec/agentcore-memory-integration/requirements.md)
- **ユーザストーリー**: [📖 user-stories.md](../../spec/agentcore-memory-integration/user-stories.md)
- **受け入れ基準**: [✅ acceptance-criteria.md](../../spec/agentcore-memory-integration/acceptance-criteria.md)
- **設計文書**: [📐 architecture.md](../../design/agentcore-memory-integration/architecture.md)
- **データフロー図**: [🔄 dataflow.md](../../design/agentcore-memory-integration/dataflow.md)
- **インターフェース定義**: [📝 interfaces.py](../../design/agentcore-memory-integration/interfaces.py)
- **設計ヒアリング記録**: [🗣️ design-interview.md](../../design/agentcore-memory-integration/design-interview.md)
- **コンテキストノート**: [📝 note.md](../../spec/agentcore-memory-integration/note.md)

## フェーズ構成

| フェーズ | 成果物 | タスク数 | 工数 | ファイル |
|---------|--------|----------|------|----------|
| Phase 1 | 基盤構築（依存パッケージ・SAM・ファクトリ） | 3件 | 12h | [TASK-0161~0163](#phase-1-基盤構築) |
| Phase 2 | SessionManager 実装（DynamoDB・AI Service） | 2件 | 14h | [TASK-0164~0165](#phase-2-sessionmanager-実装) |
| Phase 3 | TutorService リファクタリング | 3件 | 20h | [TASK-0166~0168](#phase-3-tutorservice-リファクタリング) |
| Phase 4 | 統合テスト・ドキュメント | 2件 | 8h | [TASK-0169~0170](#phase-4-統合テストドキュメント) |

## タスク番号管理

**使用済みタスク番号**: TASK-0161 ~ TASK-0170
**次回開始番号**: TASK-0171

## 全体進捗

- [ ] Phase 1: 基盤構築
- [ ] Phase 2: SessionManager 実装
- [ ] Phase 3: TutorService リファクタリング
- [ ] Phase 4: 統合テスト・ドキュメント

## マイルストーン

- **M1: 基盤完成**: ファクトリパターン・SAM テンプレート・依存パッケージ完了
- **M2: SessionManager 完成**: DynamoDBSessionManager・StrandsTutorAIService 改修完了
- **M3: リファクタリング完成**: TutorService 全メソッド SessionManager 対応完了
- **M4: リリース準備完了**: 統合テスト・ドキュメント完了

---

## Phase 1: 基盤構築

**目標**: SessionManager ファクトリパターンの基盤を構築する
**成果物**: 依存パッケージ追加、SAM テンプレート更新、SessionManager ファクトリ実装

### タスク一覧

- [ ] [TASK-0161: 依存パッケージ追加](TASK-0161.md) - 2h (DIRECT) 🔵
- [ ] [TASK-0162: SAM テンプレート更新](TASK-0162.md) - 4h (DIRECT) 🔵
- [ ] [TASK-0163: SessionManager ファクトリ実装](TASK-0163.md) - 6h (TDD) 🔵

### 依存関係

```
TASK-0161 → TASK-0162 → TASK-0163
```

---

## Phase 2: SessionManager 実装

**目標**: DynamoDBSessionManager と StrandsTutorAIService の SessionManager 対応を実装する
**成果物**: DynamoDBSessionManager 実装、StrandsTutorAIService 改修

### タスク一覧

- [x] [TASK-0164: DynamoDBSessionManager 実装](TASK-0164.md) - 8h (TDD) 🔵
- [x] [TASK-0165: StrandsTutorAIService SessionManager 対応](TASK-0165.md) - 6h (TDD) 🔵

### 依存関係

```
TASK-0163 → TASK-0164
TASK-0163 → TASK-0165
```

**備考**: TASK-0164 と TASK-0165 は並行実装可能

---

## Phase 3: TutorService リファクタリング

**目標**: TutorService の全メソッドを SessionManager 経由に改修する
**成果物**: start_session / send_message / get_session の SessionManager 対応

### タスク一覧

- [x] [TASK-0166: TutorService.start_session リファクタリング](TASK-0166.md) - 8h (TDD) 🔵
- [x] [TASK-0167: TutorService.send_message リファクタリング](TASK-0167.md) - 8h (TDD) 🔵
- [ ] [TASK-0168: TutorService.get_session 対応](TASK-0168.md) - 4h (TDD) 🟡

### 依存関係

```
TASK-0164 + TASK-0165 → TASK-0166 → TASK-0167 → TASK-0168
```

---

## Phase 4: 統合テスト・ドキュメント

**目標**: E2E 統合テストの実施とドキュメント整備
**成果物**: 統合テスト、API 互換性確認、ドキュメント更新

### タスク一覧

- [ ] [TASK-0169: 統合テスト・API 互換性確認](TASK-0169.md) - 6h (TDD) 🔵
- [ ] [TASK-0170: ドキュメント整備・最終確認](TASK-0170.md) - 2h (DIRECT) 🔵

### 依存関係

```
TASK-0168 → TASK-0169 → TASK-0170
```

---

## 信頼性レベルサマリー

### 全タスク統計

- **総タスク数**: 10件
- 🔵 **青信号**: 9件 (90%)
- 🟡 **黄信号**: 1件 (10%)
- 🔴 **赤信号**: 0件 (0%)

### フェーズ別信頼性

| フェーズ | 🔵 青 | 🟡 黄 | 🔴 赤 | 合計 |
|---------|-------|-------|-------|------|
| Phase 1 | 3 | 0 | 0 | 3 |
| Phase 2 | 2 | 0 | 0 | 2 |
| Phase 3 | 2 | 1 | 0 | 3 |
| Phase 4 | 2 | 0 | 0 | 2 |

**品質評価**: ✅ 高品質（青信号 90%、赤信号なし。黄信号は TASK-0168 get_session の会話履歴取得方法が SessionManager 実装依存のため）

## クリティカルパス

```
TASK-0161 → TASK-0162 → TASK-0163 → TASK-0164 → TASK-0166 → TASK-0167 → TASK-0168 → TASK-0169 → TASK-0170
```

**クリティカルパス工数**: 48時間
**並行作業可能工数**: 6時間（TASK-0164 と TASK-0165 が並行実行可能）

## 次のステップ

タスクを実装するには:
- 全タスク順番に実装: `/tsumiki:kairo-implement`
- 特定タスクを実装: `/tsumiki:kairo-implement TASK-0161`
