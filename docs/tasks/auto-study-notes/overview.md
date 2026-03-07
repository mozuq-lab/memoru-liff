# Auto Study Notes タスク概要

**作成日**: 2026-03-07
**推定工数**: 98時間
**総タスク数**: 16件

## 関連文書

- **要件定義書**: [requirements.md](../../spec/auto-study-notes/requirements.md)
- **設計文書**: [architecture.md](../../design/auto-study-notes/architecture.md)
- **API仕様**: [api-endpoints.md](../../design/auto-study-notes/api-endpoints.md)
- **データベース設計**: [database-schema.md](../../design/auto-study-notes/database-schema.md)
- **型定義（BE）**: [interfaces.py](../../design/auto-study-notes/interfaces.py)
- **型定義（FE）**: [interfaces.ts](../../design/auto-study-notes/interfaces.ts)
- **データフロー図**: [dataflow.md](../../design/auto-study-notes/dataflow.md)
- **コンテキストノート**: [note.md](../../spec/auto-study-notes/note.md)

## フェーズ構成

| フェーズ | 成果物 | タスク数 | 工数 |
|---------|--------|----------|------|
| Phase 1 | 基盤（DB・モデル・プロンプト） | 4件 | 20h |
| Phase 2 | バックエンド（サービス・API） | 6件 | 40h |
| Phase 3 | フロントエンド（UI） | 4件 | 24h |
| Phase 4 | 統合テスト・品質 | 2件 | 14h |

## タスク番号管理

**使用済みタスク番号**: TASK-0161 ~ TASK-0176
**次回開始番号**: TASK-0177

## 全体進捗

- [ ] Phase 1: 基盤構築
- [ ] Phase 2: バックエンド実装
- [ ] Phase 3: フロントエンド実装
- [ ] Phase 4: 統合テスト・品質

## マイルストーン

- **M1: 基盤完成**: DB テーブル・データクラス・プロンプト完了
- **M2: API完成**: バックエンドAPI実装完了、単体テスト通過
- **M3: UI完成**: フロントエンド実装完了
- **M4: リリース準備完了**: 全テスト完了、品質チェック通過

---

## Phase 1: 基盤構築

**目標**: DynamoDB テーブル定義、データクラス、Pydantic モデル、プロンプトテンプレートの完成
**成果物**: study-notes テーブル、AIService Protocol 拡張、リクエスト/レスポンスモデル

### タスク一覧

| 状態 | タスク | 工数 | タイプ | 信頼性 |
|------|--------|------|--------|--------|
| [ ] | [TASK-0161: DynamoDB study-notes テーブル定義](TASK-0161.md) | 4h | DIRECT | 🔵 |
| [ ] | [TASK-0162: StudyNotesResult データクラス & AIService Protocol 拡張](TASK-0162.md) | 6h | TDD | 🔵 |
| [ ] | [TASK-0163: Pydantic リクエスト/レスポンスモデル](TASK-0163.md) | 4h | TDD | 🔵 |
| [ ] | [TASK-0164: プロンプトテンプレート作成](TASK-0164.md) | 6h | TDD | 🟡 |

### 依存関係

```
TASK-0161 (独立)
TASK-0162 (独立) → TASK-0163, TASK-0164, TASK-0167
TASK-0163 → TASK-0169
TASK-0164 → TASK-0167
```

---

## Phase 2: バックエンド実装

**目標**: StudyNotesService、AIService実装、APIエンドポイント、キャッシュ無効化の完成
**成果物**: 完全に動作するバックエンドAPI

### タスク一覧

| 状態 | タスク | 工数 | タイプ | 信頼性 |
|------|--------|------|--------|--------|
| [ ] | [TASK-0165: StudyNotesService キャッシュ管理](TASK-0165.md) | 6h | TDD | 🔵 |
| [ ] | [TASK-0166: カード取得・バリデーション・代表選択ロジック](TASK-0166.md) | 8h | TDD | 🔵 |
| [ ] | [TASK-0167: AIService generate_study_notes() 実装](TASK-0167.md) | 8h | TDD | 🔵 |
| [ ] | [TASK-0168: StudyNotesService 生成オーケストレーション](TASK-0168.md) | 6h | TDD | 🔵 |
| [ ] | [TASK-0169: StudyNotesHandler API エンドポイント](TASK-0169.md) | 6h | TDD | 🔵 |
| [ ] | [TASK-0170: カードCRUD時のキャッシュ無効化](TASK-0170.md) | 6h | TDD | 🔵 |

### 依存関係

```
TASK-0161 + TASK-0162 → TASK-0165
TASK-0165 → TASK-0166
TASK-0162 + TASK-0164 → TASK-0167
TASK-0165 + TASK-0166 + TASK-0167 → TASK-0168
TASK-0163 + TASK-0168 → TASK-0169
TASK-0165 → TASK-0170
```

---

## Phase 3: フロントエンド実装

**目標**: TypeScript型定義、APIサービス、カスタムフック、UIコンポーネントの完成
**成果物**: デッキ詳細画面に統合された要約ノート表示

### タスク一覧

| 状態 | タスク | 工数 | タイプ | 信頼性 |
|------|--------|------|--------|--------|
| [ ] | [TASK-0171: TypeScript型定義 & APIサービス](TASK-0171.md) | 4h | TDD | 🔵 |
| [ ] | [TASK-0172: useStudyNotes カスタムフック](TASK-0172.md) | 6h | TDD | 🟡 |
| [ ] | [TASK-0173: StudyNotesSection コンポーネント](TASK-0173.md) | 8h | TDD | 🟡 |
| [ ] | [TASK-0174: デッキ詳細画面への統合](TASK-0174.md) | 6h | TDD | 🔵 |

### 依存関係

```
TASK-0169 → TASK-0171
TASK-0171 → TASK-0172
TASK-0172 → TASK-0173
TASK-0173 → TASK-0174
```

---

## Phase 4: 統合テスト・品質

**目標**: バックエンド統合テスト、E2Eテスト、セキュリティ確認、品質チェックの完了
**成果物**: テスト完了・品質基準達成

### タスク一覧

| 状態 | タスク | 工数 | タイプ | 信頼性 |
|------|--------|------|--------|--------|
| [ ] | [TASK-0175: バックエンド統合テスト](TASK-0175.md) | 8h | TDD | 🔵 |
| [ ] | [TASK-0176: E2Eテスト・品質チェック](TASK-0176.md) | 6h | DIRECT | 🟡 |

### 依存関係

```
TASK-0169 + TASK-0170 → TASK-0175
TASK-0174 + TASK-0175 → TASK-0176
```

---

## 信頼性レベルサマリー

### 全タスク統計

- **総タスク数**: 16件
- 🔵 **青信号**: 12件 (75%)
- 🟡 **黄信号**: 4件 (25%)
- 🔴 **赤信号**: 0件 (0%)

### フェーズ別信頼性

| フェーズ | 🔵 青 | 🟡 黄 | 🔴 赤 | 合計 |
|---------|-------|-------|-------|------|
| Phase 1 | 3 | 1 | 0 | 4 |
| Phase 2 | 6 | 0 | 0 | 6 |
| Phase 3 | 2 | 2 | 0 | 4 |
| Phase 4 | 1 | 1 | 0 | 2 |

**品質評価**: ✅ 高品質（青信号が75%、赤信号なし）

## クリティカルパス

```
TASK-0162 → TASK-0164 → TASK-0167 → TASK-0168 → TASK-0169 → TASK-0171 → TASK-0172 → TASK-0173 → TASK-0174 → TASK-0176
```

**クリティカルパス工数**: 64時間

## 次のステップ

タスクを実装するには:
- 全タスク順番に実装: `/tsumiki:kairo-implement`
- 特定タスクを実装: `/tsumiki:kairo-implement TASK-0161`
