# AI Strands Migration タスク概要

**作成日**: 2026-02-23
**推定工数**: 104時間
**総タスク数**: 14件

## 関連文書

- **要件定義書**: [requirements.md](../../spec/ai-strands-migration/requirements.md)
- **ユーザストーリー**: [user-stories.md](../../spec/ai-strands-migration/user-stories.md)
- **受け入れ基準**: [acceptance-criteria.md](../../spec/ai-strands-migration/acceptance-criteria.md)
- **アーキテクチャ設計**: [architecture.md](../../design/ai-strands-migration/architecture.md)
- **API仕様**: [api-endpoints.md](../../design/ai-strands-migration/api-endpoints.md)
- **インターフェース定義**: [interfaces.py](../../design/ai-strands-migration/interfaces.py)
- **データフロー図**: [dataflow.md](../../design/ai-strands-migration/dataflow.md)
- **設計ヒアリング**: [design-interview.md](../../design/ai-strands-migration/design-interview.md)
- **コンテキストノート**: [note.md](../../spec/ai-strands-migration/note.md)

## フェーズ構成

| フェーズ | 成果物 | タスク数 | 工数 | ファイル |
|---------|--------|----------|------|----------|
| Phase 1: 基盤構築 | Protocol + Factory + プロンプト分割 + 例外統一 | 5件 | 36h | [TASK-0052~0056](#phase-1-基盤構築) |
| Phase 2: Strands カード生成移行 | StrandsAIService + 互換性検証 | 2件 | 16h | [TASK-0057~0058](#phase-2-strands-カード生成移行) |
| Phase 3: 新機能追加 | 回答採点 + 学習アドバイス + 統合テスト | 5件 | 40h | [TASK-0059~0063](#phase-3-新機能追加) |
| Phase 4: ローカル開発 + 最終検証 | Ollama 統合 + 品質確認 | 2件 | 12h | [TASK-0064~0065](#phase-4-ローカル開発--最終検証) |

## タスク番号管理

**使用済みタスク番号**: TASK-0052 ~ TASK-0065
**次回開始番号**: TASK-0066

## 全体進捗

- [x] Phase 1: 基盤構築
- [ ] Phase 2: Strands カード生成移行
- [ ] Phase 3: 新機能追加
- [ ] Phase 4: ローカル開発 + 最終検証

## マイルストーン

- **M1: 基盤完成**: Protocol + Factory + プロンプト分割 + 例外統一 + handler 統合完了
- **M2: カード生成移行完了**: USE_STRANDS=true で既存 API 完全互換動作
- **M3: 新機能完成**: 回答採点 + 学習アドバイス API 実装完了
- **M4: リリース準備完了**: Ollama 統合 + 全テスト通過 + カバレッジ 80%+

---

## Phase 1: 基盤構築

**目標**: Strands Agents SDK の導入、AIService Protocol による抽象化レイヤー構築、プロンプトモジュール分割、既存 BedrockService の Protocol 準拠改修、handler.py のファクトリ統合
**成果物**: ai_service.py, prompts/ ディレクトリ, bedrock.py 改修, handler.py 改修, template.yaml 更新

### タスク一覧

- [x] [TASK-0052: Strands Agents SDK 依存追加 + ビルド確認](TASK-0052.md) - 4h (DIRECT) 🔵
- [x] [TASK-0053: AIService Protocol + 共通型定義 + 例外階層](TASK-0053.md) - 8h (TDD) 🔵
- [x] [TASK-0054: プロンプトモジュールディレクトリ化](TASK-0054.md) - 8h (TDD) 🔵
- [x] [TASK-0055: BedrockAIService Protocol 準拠改修](TASK-0055.md) - 8h (TDD) 🔵
- [x] [TASK-0056: handler.py AIServiceFactory 統合 + template.yaml 更新](TASK-0056.md) - 8h (TDD) 🔵

### 依存関係

```
TASK-0052 → TASK-0053
TASK-0053 → TASK-0054
TASK-0053 → TASK-0055
TASK-0054 + TASK-0055 → TASK-0056
```

---

## Phase 2: Strands カード生成移行

**目標**: StrandsAIService のカード生成実装、USE_STRANDS フラグによる新旧実装の切替検証、API レスポンス形式の完全互換性保証
**成果物**: strands_service.py, test_migration_compat.py

### タスク一覧

- [ ] [TASK-0057: StrandsAIService 基本実装（カード生成）](TASK-0057.md) - 8h (TDD) 🟡
- [ ] [TASK-0058: カード生成 API 互換性検証 + 移行テスト](TASK-0058.md) - 8h (TDD) 🔵

### 依存関係

```
TASK-0052 + TASK-0054 + TASK-0056 → TASK-0057
TASK-0055 + TASK-0057 → TASK-0058
```

---

## Phase 3: 新機能追加

**目標**: 回答採点/AI 評価機能（POST /reviews/{card_id}/grade-ai）と学習アドバイス機能（GET /advice）の完全実装、統合テスト
**成果物**: models/grading.py, models/advice.py, 新エンドポイント, test_integration.py

### タスク一覧

- [ ] [TASK-0059: 回答採点モデル・プロンプト・AI 実装](TASK-0059.md) - 8h (TDD) 🔵
- [ ] [TASK-0060: POST /reviews/{card_id}/grade-ai エンドポイント](TASK-0060.md) - 8h (TDD) 🔵
- [ ] [TASK-0061: 学習データ集計 + アドバイスモデル・プロンプト](TASK-0061.md) - 8h (TDD) 🟡
- [ ] [TASK-0062: 学習アドバイス AI 実装 + GET /advice エンドポイント](TASK-0062.md) - 8h (TDD) 🔵
- [ ] [TASK-0063: Phase 3 統合テスト](TASK-0063.md) - 8h (TDD) 🔵

### 依存関係

```
TASK-0054 + TASK-0057 → TASK-0059
TASK-0056 + TASK-0059 → TASK-0060

TASK-0054 + TASK-0057 → TASK-0061
TASK-0056 + TASK-0061 → TASK-0062

TASK-0058 + TASK-0060 + TASK-0062 → TASK-0063
```

---

## Phase 4: ローカル開発 + 最終検証

**目標**: Ollama プロバイダーによるローカル AI 動作確認環境の構築、全実装の品質確認
**成果物**: docker-compose.yaml 更新, Makefile 更新, 全テスト通過確認

### タスク一覧

- [ ] [TASK-0064: Ollama プロバイダー + docker-compose 統合](TASK-0064.md) - 6h (DIRECT) 🔵
- [ ] [TASK-0065: 全体統合テスト + 品質確認](TASK-0065.md) - 6h (TDD) 🔵

### 依存関係

```
TASK-0057 → TASK-0064
TASK-0063 + TASK-0064 → TASK-0065
```

---

## 信頼性レベルサマリー

### 全タスク統計

- **総タスク数**: 14件
- 🔵 **青信号**: 12件 (86%)
- 🟡 **黄信号**: 2件 (14%)
- 🔴 **赤信号**: 0件 (0%)

### フェーズ別信頼性

| フェーズ | 🔵 青 | 🟡 黄 | 🔴 赤 | 合計 |
|---------|-------|-------|-------|------|
| Phase 1 | 5 | 0 | 0 | 5 |
| Phase 2 | 1 | 1 | 0 | 2 |
| Phase 3 | 4 | 1 | 0 | 5 |
| Phase 4 | 2 | 0 | 0 | 2 |

**品質評価**: ✅ 高品質（青信号 86%、赤信号なし）

### 黄信号の項目

- **TASK-0057** (StrandsAIService 基本実装): Strands Agents SDK の具体的な API は実装時に SDK ドキュメントで確認が必要
- **TASK-0061** (学習データ集計): ReviewSummary.streak_days の計算ロジック詳細は実装時に決定

## クリティカルパス

```
TASK-0052 → TASK-0053 → TASK-0054 → TASK-0057 → TASK-0059 → TASK-0060 → TASK-0063 → TASK-0065
```

**クリティカルパス工数**: 62時間
**並行作業可能工数**: 42時間

## 次のステップ

タスクを実装するには:
- 全タスク順番に実装: `/tsumiki:kairo-implement ai-strands-migration`
- 特定タスクを実装: `/tsumiki:kairo-implement ai-strands-migration TASK-0052`
